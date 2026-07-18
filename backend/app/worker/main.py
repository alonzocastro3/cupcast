"""
CupCast background worker entry point.

Runs the tournament-data sync scheduler in an asyncio loop.
Handles SIGTERM and SIGINT for graceful shutdown.

Usage (Docker):
    python -m app.worker.main

Usage (local development):
    cd backend
    python -m app.worker.main

Environment variables:
    FOOTBALL_API_KEY          — required for live data (worker runs without it,
                                but logs a warning and skips each sync cycle)
    SYNC_INTERVAL_SECONDS     — seconds between sync cycles (default: 900)
    FOOTBALL_TOURNAMENT_ID    — competition code (default: "WC")
    FOOTBALL_API_BASE_URL     — provider base URL
    FOOTBALL_API_TIMEOUT      — per-request timeout in seconds
    FOOTBALL_API_MAX_RETRIES  — retry attempts on transient errors
    SYNC_LOCK_KEY             — PostgreSQL advisory lock integer key

The worker writes a health snapshot to /tmp/worker_health.json after every
cycle.  Docker's healthcheck reads this file to confirm liveness.
"""
from __future__ import annotations

import asyncio
import logging
import signal

from app.worker.scheduler import SyncScheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)


async def _run() -> None:
    scheduler = SyncScheduler()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, scheduler.stop)

    try:
        await scheduler.run_forever()
    finally:
        logger.info("Worker process exiting.")


if __name__ == "__main__":
    asyncio.run(_run())
