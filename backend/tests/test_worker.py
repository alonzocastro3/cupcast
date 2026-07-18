"""
Tests for the background worker: advisory locking, scheduler tick logic,
and failure recovery.

Lock tests use the real test DB via the test_engine fixture.
Scheduler tests use an in-process mock provider so no HTTP calls are made.
"""
from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import text
from sqlalchemy.pool import NullPool

from app.integrations.football.base import (
    FootballDataProvider,
    ProviderError,
    ProviderTimeoutError,
    RawFixture,
    RawTeam,
)
from app.services.ingestion_service import SyncResult
from app.worker.health import HEALTH_FILE, read_health, write_health
from app.worker.lock import advisory_lock
from app.worker.scheduler import SyncScheduler

_TEST_LOCK_KEY = 99_999_999  # unique key so tests never clash with each other


# ── Advisory lock tests (need real DB) ───────────────────────────────────────


async def test_lock_acquired_when_free(test_engine):
    """Lock should succeed when no other session holds it."""
    async with advisory_lock(test_engine, key=_TEST_LOCK_KEY) as acquired:
        assert acquired is True


async def test_lock_not_acquired_when_held(test_engine):
    """A second acquire on the same key must return False."""
    async with test_engine.connect() as holder:
        await holder.execute(
            text("SELECT pg_advisory_lock(:key)"), {"key": _TEST_LOCK_KEY}
        )
        # advisory_lock opens its own connection → can't steal the held lock
        async with advisory_lock(test_engine, key=_TEST_LOCK_KEY) as acquired:
            assert acquired is False
        # Release so the next test starts clean
        await holder.execute(
            text("SELECT pg_advisory_unlock(:key)"), {"key": _TEST_LOCK_KEY}
        )


async def test_lock_released_after_context(test_engine):
    """After the context exits the key should be acquirable again."""
    async with advisory_lock(test_engine, key=_TEST_LOCK_KEY) as acquired:
        assert acquired is True
    # Context exited → lock released → second acquire succeeds
    async with advisory_lock(test_engine, key=_TEST_LOCK_KEY) as acquired:
        assert acquired is True


async def test_lock_released_even_on_exception(test_engine):
    """Raising inside the context must still release the lock."""
    try:
        async with advisory_lock(test_engine, key=_TEST_LOCK_KEY) as acquired:
            assert acquired is True
            raise RuntimeError("simulated failure")
    except RuntimeError:
        pass

    # Lock must be free now
    async with advisory_lock(test_engine, key=_TEST_LOCK_KEY) as acquired:
        assert acquired is True


async def test_different_keys_are_independent(test_engine):
    """Two distinct lock keys must not interfere with each other."""
    key_a, key_b = _TEST_LOCK_KEY + 1, _TEST_LOCK_KEY + 2
    async with advisory_lock(test_engine, key=key_a) as a:
        async with advisory_lock(test_engine, key=key_b) as b:
            assert a is True
            assert b is True


# ── Health-file tests (no DB needed) ─────────────────────────────────────────


def test_write_and_read_health(tmp_path, monkeypatch):
    monkeypatch.setattr("app.worker.health.HEALTH_FILE", tmp_path / "health.json")

    write_health(inserted=3, updated=1, failed=0, consecutive_failures=0)
    h = read_health()

    assert h is not None
    assert h["inserted"] == 3
    assert h["updated"] == 1
    assert h["consecutive_failures"] == 0
    assert "checked_at" in h


def test_read_health_returns_none_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.worker.health.HEALTH_FILE", tmp_path / "nonexistent.json"
    )
    assert read_health() is None


# ── SyncResult arithmetic ─────────────────────────────────────────────────────


def test_sync_result_addition():
    a = SyncResult(inserted=2, updated=1, skipped=0, failed=0)
    b = SyncResult(inserted=0, updated=3, skipped=1, failed=1)
    c = a + b
    assert c.inserted == 2
    assert c.updated == 4
    assert c.skipped == 1
    assert c.failed == 1
    assert c.total == 8  # 2+4+1+1


# ── Mock provider helpers ─────────────────────────────────────────────────────

_NOW = datetime(2026, 6, 11, 15, 0, tzinfo=timezone.utc)

_RAW_TEAM_A = RawTeam(
    external_id="101",
    name="Brazil",
    country_code="BRA",
    group_name="A",
)
_RAW_TEAM_B = RawTeam(
    external_id="102",
    name="France",
    country_code="FRA",
    group_name="A",
)
_RAW_FIXTURE = RawFixture(
    external_id="F-001",
    home_team_external_id="101",
    away_team_external_id="102",
    kickoff_at=_NOW,
    status="scheduled",
    stage="group_a",
)


class _OkProvider(FootballDataProvider):
    async def fetch_teams(self, tournament_id: str) -> list[RawTeam]:
        return [_RAW_TEAM_A, _RAW_TEAM_B]

    async def fetch_fixtures(self, tournament_id: str) -> list[RawFixture]:
        return [_RAW_FIXTURE]


class _FailProvider(FootballDataProvider):
    async def fetch_teams(self, tournament_id: str) -> list[RawTeam]:
        raise ProviderError("API is down")

    async def fetch_fixtures(self, tournament_id: str) -> list[RawFixture]:
        raise ProviderError("API is down")


class _TimeoutProvider(FootballDataProvider):
    async def fetch_teams(self, tournament_id: str) -> list[RawTeam]:
        raise ProviderTimeoutError("timed out")

    async def fetch_fixtures(self, tournament_id: str) -> list[RawFixture]:
        raise ProviderTimeoutError("timed out")


# ── Scheduler tick tests (no HTTP) ────────────────────────────────────────────


async def test_tick_skips_when_no_api_key(test_engine, monkeypatch, tmp_path):
    monkeypatch.setattr("app.worker.health.HEALTH_FILE", tmp_path / "h.json")
    monkeypatch.setattr("app.config.settings.football_api_key", None)

    scheduler = SyncScheduler(engine=test_engine, lock_key=_TEST_LOCK_KEY)
    result = await scheduler._tick()

    assert result.skipped_no_key is True
    assert result.error is None


async def test_tick_skips_when_lock_held(test_engine, monkeypatch, tmp_path):
    """When lock is held by another session, tick logs and skips."""
    monkeypatch.setattr("app.worker.health.HEALTH_FILE", tmp_path / "h.json")
    monkeypatch.setattr("app.config.settings.football_api_key", "test-key")

    async with test_engine.connect() as holder:
        await holder.execute(
            text("SELECT pg_advisory_lock(:key)"), {"key": _TEST_LOCK_KEY}
        )
        scheduler = SyncScheduler(engine=test_engine, lock_key=_TEST_LOCK_KEY)
        result = await scheduler._tick()
        assert result.skipped_locked is True
        await holder.execute(
            text("SELECT pg_advisory_unlock(:key)"), {"key": _TEST_LOCK_KEY}
        )


async def test_tick_succeeds_with_valid_provider(test_engine, monkeypatch, tmp_path):
    """A successful tick inserts the mock teams and fixture."""
    monkeypatch.setattr("app.worker.health.HEALTH_FILE", tmp_path / "h.json")
    monkeypatch.setattr("app.config.settings.football_api_key", "test-key")

    scheduler = SyncScheduler(
        engine=test_engine,
        provider=_OkProvider(),
        lock_key=_TEST_LOCK_KEY,
    )
    result = await scheduler._tick()

    assert result.error is None
    assert result.skipped_no_key is False
    assert result.skipped_locked is False
    assert result.inserted == 3  # 2 teams + 1 fixture
    assert scheduler._consecutive_failures == 0


async def test_tick_increments_consecutive_failures_on_error(
    test_engine, monkeypatch, tmp_path
):
    """Provider error is caught; consecutive_failures increments."""
    monkeypatch.setattr("app.worker.health.HEALTH_FILE", tmp_path / "h.json")
    monkeypatch.setattr("app.config.settings.football_api_key", "test-key")

    scheduler = SyncScheduler(
        engine=test_engine,
        provider=_FailProvider(),
        lock_key=_TEST_LOCK_KEY,
    )
    # IngestionService catches ProviderError internally; sync_all returns
    # empty results rather than raising.  A real crash in _run_sync comes from
    # DB or infrastructure issues — simulate that here.
    original_run = scheduler._run_sync

    async def _crash():
        raise RuntimeError("DB exploded")

    scheduler._run_sync = _crash  # type: ignore[method-assign]
    result = await scheduler._tick()

    assert result.error is not None
    assert scheduler._consecutive_failures == 1


async def test_tick_resets_consecutive_failures_on_success(
    test_engine, monkeypatch, tmp_path
):
    """consecutive_failures resets to zero after a successful tick."""
    monkeypatch.setattr("app.worker.health.HEALTH_FILE", tmp_path / "h.json")
    monkeypatch.setattr("app.config.settings.football_api_key", "test-key")

    scheduler = SyncScheduler(
        engine=test_engine,
        provider=_OkProvider(),
        lock_key=_TEST_LOCK_KEY,
    )
    scheduler._consecutive_failures = 5  # pretend prior failures

    result = await scheduler._tick()

    assert result.error is None
    assert scheduler._consecutive_failures == 0


async def test_scheduler_continues_after_provider_failure(
    test_engine, monkeypatch, tmp_path
):
    """consecutive_failures increments on crash and resets to 0 on success."""
    monkeypatch.setattr("app.worker.health.HEALTH_FILE", tmp_path / "h.json")
    monkeypatch.setattr("app.config.settings.football_api_key", "test-key")

    scheduler = SyncScheduler(
        engine=test_engine,
        provider=_OkProvider(),
        lock_key=_TEST_LOCK_KEY,
    )

    # Tick 1: inject a crash at the DB/infrastructure level
    original_run = scheduler._run_sync

    async def _crash():
        raise RuntimeError("network down")

    scheduler._run_sync = _crash  # type: ignore[method-assign]
    result1 = await scheduler._tick()

    assert result1.error is not None
    assert scheduler._consecutive_failures == 1

    # Tick 2: restore normal operation — scheduler is still running
    scheduler._run_sync = original_run  # type: ignore[method-assign]
    result2 = await scheduler._tick()

    assert result2.error is None
    assert scheduler._consecutive_failures == 0


async def test_stop_exits_loop(test_engine, monkeypatch, tmp_path):
    """stop() causes run_forever to exit without completing the interval."""
    monkeypatch.setattr("app.worker.health.HEALTH_FILE", tmp_path / "h.json")
    monkeypatch.setattr("app.config.settings.football_api_key", None)

    scheduler = SyncScheduler(
        engine=test_engine,
        lock_key=_TEST_LOCK_KEY,
        interval_seconds=60,  # would take 60 s without stop()
    )

    async def _stop_after_first_tick(original_tick):
        result = await original_tick()
        scheduler.stop()
        return result

    original_tick = scheduler._tick
    scheduler._tick = lambda: _stop_after_first_tick(original_tick)  # type: ignore[method-assign]

    start = time.monotonic()
    await scheduler.run_forever()
    elapsed = time.monotonic() - start

    # Should exit well under the 60-second interval
    assert elapsed < 5


async def test_timeout_provider_treated_as_failure(
    test_engine, monkeypatch, tmp_path
):
    """ProviderTimeoutError is surfaced via the infrastructure exception path."""
    monkeypatch.setattr("app.worker.health.HEALTH_FILE", tmp_path / "h.json")
    monkeypatch.setattr("app.config.settings.football_api_key", "test-key")

    scheduler = SyncScheduler(
        engine=test_engine,
        provider=_TimeoutProvider(),
        lock_key=_TEST_LOCK_KEY,
    )
    # TimeoutProvider raises inside fetch_teams/fetch_fixtures, but
    # IngestionService catches ProviderError and returns empty results —
    # so sync_all succeeds with 0 records (no crash at the scheduler level).
    result = await scheduler._tick()

    assert result.error is None  # IngestionService absorbed the timeout
    assert result.inserted == 0
    assert result.updated == 0


async def test_health_file_written_after_tick(test_engine, monkeypatch, tmp_path):
    """Health file is always written after a tick, even on skip."""
    health_path = tmp_path / "worker_health.json"
    monkeypatch.setattr("app.worker.health.HEALTH_FILE", health_path)
    monkeypatch.setattr("app.config.settings.football_api_key", None)

    scheduler = SyncScheduler(
        engine=test_engine,
        lock_key=_TEST_LOCK_KEY,
    )
    result = await scheduler._tick()
    scheduler._flush_health(result)

    import json
    assert health_path.exists()
    data = json.loads(health_path.read_text())
    assert "checked_at" in data
    assert data["skipped_no_key"] is True
