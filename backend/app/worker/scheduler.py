"""
SyncScheduler: runs one sync cycle per interval in a tight asyncio loop.

Design decisions:
- The advisory lock is acquired on a dedicated connection so it is held
  independently of the ingestion transaction.  If the DB is shared by
  multiple worker replicas (e.g. a blue/green deploy), only one acquires
  the lock per cycle; the rest log and sleep.
- The loop sleeps in 1-second ticks so SIGTERM / stop() responds within
  one second rather than waiting out the full interval.
- Provider failures are caught and logged; the scheduler keeps running.
  consecutive_failures is tracked so downstream alerting can threshold on it.
- When FOOTBALL_API_KEY is absent the scheduler still runs, writes the
  health file, and waits for the key to appear without exiting.
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.config import settings
from app.database import AsyncSessionLocal
from app.database import engine as _default_engine
from app.integrations.football.base import FootballDataProvider
from app.integrations.football.provider import FootballDataOrgProvider
from app.services.ingestion_service import IngestionService, SyncResult
from app.worker.health import write_health
from app.worker.lock import advisory_lock

logger = logging.getLogger(__name__)


@dataclass
class _TickResult:
    duration_s: float = 0.0
    inserted: int = 0
    updated: int = 0
    skipped: int = 0
    failed: int = 0
    skipped_no_key: bool = False
    skipped_locked: bool = False
    error: Exception | None = None


class SyncScheduler:
    """
    Runs the tournament-data sync on a configurable interval.

    Parameters
    ----------
    engine:
        SQLAlchemy async engine.  Defaults to the app engine; override in
        tests to use an isolated test engine.
    provider:
        FootballDataProvider implementation.  Defaults to None, in which
        case FootballDataOrgProvider is built from settings on each tick.
        Pass an explicit provider in tests to avoid real HTTP calls.
    interval_seconds:
        Seconds between sync cycles.  Defaults to settings.sync_interval_seconds.
    lock_key:
        PostgreSQL advisory lock key.  Defaults to settings.sync_lock_key.
    """

    def __init__(
        self,
        *,
        engine: AsyncEngine | None = None,
        provider: FootballDataProvider | None = None,
        interval_seconds: int | None = None,
        lock_key: int | None = None,
    ) -> None:
        self._engine = engine or _default_engine
        self._provider = provider
        self._interval = interval_seconds if interval_seconds is not None else settings.sync_interval_seconds
        self._lock_key = lock_key if lock_key is not None else settings.sync_lock_key
        self._running = False
        self._consecutive_failures = 0

    def stop(self) -> None:
        """Signal the loop to exit after the current sleep tick."""
        self._running = False
        logger.info("Shutdown requested.")

    async def run_forever(self) -> None:
        """Run sync cycles until stop() is called."""
        self._running = True
        logger.info(
            "Worker started — interval=%ds tournament=%s lock_key=%d",
            self._interval,
            settings.football_tournament_id,
            self._lock_key,
        )

        while self._running:
            result = await self._tick()
            self._flush_health(result)

            # Sleep in 1-second ticks so stop() is responsive
            for _ in range(self._interval):
                if not self._running:
                    break
                await asyncio.sleep(1)

    async def _tick(self) -> _TickResult:
        """Execute one sync attempt and return its outcome."""
        t0 = time.monotonic()

        if not settings.football_api_key:
            logger.warning(
                "FOOTBALL_API_KEY not configured — skipping sync. "
                "Set it in .env to enable live data ingestion."
            )
            return _TickResult(skipped_no_key=True)

        logger.info(
            "Sync starting — tournament=%s", settings.football_tournament_id
        )

        try:
            async with advisory_lock(self._engine, self._lock_key) as acquired:
                if not acquired:
                    logger.info(
                        "Advisory lock (key=%d) not acquired — "
                        "another worker is syncing. Skipping this cycle.",
                        self._lock_key,
                    )
                    return _TickResult(skipped_locked=True)

                results = await self._run_sync()

        except Exception as exc:
            self._consecutive_failures += 1
            duration = time.monotonic() - t0
            logger.error(
                "Sync failed after %.1fs (consecutive_failures=%d): %s",
                duration,
                self._consecutive_failures,
                exc,
                exc_info=True,
            )
            return _TickResult(
                duration_s=duration,
                error=exc,
                failed=1,
            )

        duration = time.monotonic() - t0
        self._consecutive_failures = 0

        total = SyncResult()
        for r in results.values():
            total = total + r

        logger.info(
            "Sync finished in %.1fs — inserted=%d updated=%d skipped=%d failed=%d",
            duration,
            total.inserted,
            total.updated,
            total.skipped,
            total.failed,
        )
        return _TickResult(
            duration_s=duration,
            inserted=total.inserted,
            updated=total.updated,
            skipped=total.skipped,
            failed=total.failed,
        )

    async def _run_sync(self) -> dict[str, SyncResult]:
        """Create a session and delegate to IngestionService.sync_all."""
        provider = self._provider or FootballDataOrgProvider(
            api_key=settings.football_api_key,  # type: ignore[arg-type]
            base_url=settings.football_api_base_url,
            timeout=settings.football_api_timeout,
            max_retries=settings.football_api_max_retries,
        )
        session_factory = async_sessionmaker(self._engine, expire_on_commit=False)
        async with session_factory() as session:
            async with session.begin():
                service = IngestionService(session)
                return await service.sync_all(provider, settings.football_tournament_id)

    def _flush_health(self, result: _TickResult) -> None:
        write_health(
            duration_s=result.duration_s,
            inserted=result.inserted,
            updated=result.updated,
            skipped=result.skipped,
            failed=result.failed,
            consecutive_failures=self._consecutive_failures,
            skipped_no_key=result.skipped_no_key,
            skipped_locked=result.skipped_locked,
        )
