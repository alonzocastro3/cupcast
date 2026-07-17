"""Tests for Redis caching: unit (mocked Redis) + integration (FakeCache via API)."""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_cache_service
from app.main import app as fastapi_app
from app.models.match import Match
from app.models.team import Team
from app.services.cache import (
    CacheService,
    key_match,
    key_match_list,
    key_model_prediction,
    key_prediction_summary,
    key_team,
    key_team_list,
)

_TZ = timezone.utc


# ── FakeCache ─────────────────────────────────────────────────────────────────

class FakeCache:
    """In-memory cache with observability for test assertions."""

    def __init__(self, *, fail: bool = False) -> None:
        self._store: dict[str, Any] = {}
        self.fail = fail
        self.gets: list[tuple[str, str]] = []   # (key, "hit"|"miss")
        self.sets: list[str] = []
        self.deletes: list[str] = []

    async def get(self, key: str) -> Any | None:
        if self.fail:
            return None
        val = self._store.get(key)
        self.gets.append((key, "hit" if val is not None else "miss"))
        return val

    async def set(self, key: str, value: Any, ttl: int) -> None:
        if not self.fail:
            self._store[key] = value
            self.sets.append(key)

    async def delete(self, key: str) -> None:
        if not self.fail:
            self._store.pop(key, None)
            self.deletes.append(key)

    def hit_count(self) -> int:
        return sum(1 for _, status in self.gets if status == "hit")

    def miss_count(self) -> int:
        return sum(1 for _, status in self.gets if status == "miss")


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def cached_client(
    db_session: AsyncSession,
) -> AsyncGenerator[tuple[AsyncClient, FakeCache], None]:
    """API client wired to test DB + a controllable FakeCache."""
    fake = FakeCache()

    async def _override_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    fastapi_app.dependency_overrides[get_db] = _override_db
    fastapi_app.dependency_overrides[get_cache_service] = lambda: fake

    async with AsyncClient(transport=ASGITransport(app=fastapi_app), base_url="http://test") as ac:
        yield ac, fake

    fastapi_app.dependency_overrides.pop(get_db, None)
    fastapi_app.dependency_overrides.pop(get_cache_service, None)


@pytest_asyncio.fixture
async def failing_client(
    db_session: AsyncSession,
) -> AsyncGenerator[AsyncClient, None]:
    """API client wired to test DB + a FakeCache that always fails (Redis down)."""
    broken = FakeCache(fail=True)

    async def _override_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    fastapi_app.dependency_overrides[get_db] = _override_db
    fastapi_app.dependency_overrides[get_cache_service] = lambda: broken

    async with AsyncClient(transport=ASGITransport(app=fastapi_app), base_url="http://test") as ac:
        yield ac

    fastapi_app.dependency_overrides.pop(get_db, None)
    fastapi_app.dependency_overrides.pop(get_cache_service, None)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _team(name: str, code: str) -> Team:
    return Team(
        name=name,
        country_code=code,
        group_name="A",
        fifa_ranking=10,
        elo_rating=1900,
    )


def _match(home_id: int, away_id: int) -> Match:
    return Match(
        home_team_id=home_id,
        away_team_id=away_id,
        kickoff_at=datetime(2026, 6, 15, 15, 0, tzinfo=_TZ),
        stage="group_a",
    )


async def _seed(db: AsyncSession) -> tuple[int, int]:
    home = _team("Brazil", "BRA")
    away = _team("Germany", "GER")
    db.add_all([home, away])
    await db.flush()
    match = _match(home.id, away.id)
    db.add(match)
    await db.flush()
    return match.id, home.id


# ═════════════════════════════════════════════════════════════════════════════
# CacheService unit tests (mocked Redis)
# ═════════════════════════════════════════════════════════════════════════════

async def test_cache_service_get_hit() -> None:
    payload = {"id": 1, "name": "Brazil"}
    mock_redis = AsyncMock()
    mock_redis.get.return_value = json.dumps(payload)

    svc = CacheService(mock_redis)
    result = await svc.get("some-key")

    assert result == payload
    mock_redis.get.assert_called_once_with("some-key")


async def test_cache_service_get_miss() -> None:
    mock_redis = AsyncMock()
    mock_redis.get.return_value = None

    svc = CacheService(mock_redis)
    result = await svc.get("some-key")

    assert result is None


async def test_cache_service_get_redis_error_returns_none() -> None:
    mock_redis = AsyncMock()
    mock_redis.get.side_effect = ConnectionError("Redis down")

    svc = CacheService(mock_redis)
    result = await svc.get("some-key")  # must not raise

    assert result is None


async def test_cache_service_set_serialises_to_json() -> None:
    mock_redis = AsyncMock()
    payload = {"items": [1, 2], "total": 2}

    svc = CacheService(mock_redis)
    await svc.set("my-key", payload, ttl=60)

    mock_redis.set.assert_called_once_with("my-key", json.dumps(payload, default=str), ex=60)


async def test_cache_service_set_redis_error_does_not_raise() -> None:
    mock_redis = AsyncMock()
    mock_redis.set.side_effect = ConnectionError("Redis down")

    svc = CacheService(mock_redis)
    await svc.set("key", {"x": 1}, ttl=30)  # must not raise


async def test_cache_service_delete_calls_redis() -> None:
    mock_redis = AsyncMock()
    mock_redis.delete.return_value = 1

    svc = CacheService(mock_redis)
    await svc.delete("stale-key")

    mock_redis.delete.assert_called_once_with("stale-key")


async def test_cache_service_delete_redis_error_does_not_raise() -> None:
    mock_redis = AsyncMock()
    mock_redis.delete.side_effect = ConnectionError("Redis down")

    svc = CacheService(mock_redis)
    await svc.delete("key")  # must not raise


# ═════════════════════════════════════════════════════════════════════════════
# Key builder tests
# ═════════════════════════════════════════════════════════════════════════════

def test_key_team_list_includes_pagination() -> None:
    assert key_team_list(10, 20) == "cupcast:teams:list:10:20"


def test_key_match_list_includes_all_filters() -> None:
    k = key_match_list(5, 0, "live", "group_a", 3)
    assert "live" in k and "group_a" in k and "3" in k


def test_key_match_list_none_filters_stable() -> None:
    k1 = key_match_list(20, 0, None, None, None)
    k2 = key_match_list(20, 0, None, None, None)
    assert k1 == k2


def test_key_prediction_summary_namespaced() -> None:
    assert key_prediction_summary(7) == "cupcast:matches:7:prediction-summary"


def test_key_model_prediction_namespaced() -> None:
    assert key_model_prediction(3) == "cupcast:matches:3:model-prediction"


# ═════════════════════════════════════════════════════════════════════════════
# Cache miss → hit via API (FakeCache)
# ═════════════════════════════════════════════════════════════════════════════

async def test_team_get_cache_miss_then_hit(
    cached_client: tuple[AsyncClient, FakeCache], db_session: AsyncSession
) -> None:
    client, fake = cached_client
    team = _team("Brazil", "BRA")
    db_session.add(team)
    await db_session.flush()

    r1 = await client.get(f"/api/v1/teams/{team.id}")
    assert r1.status_code == 200
    assert fake.miss_count() == 1
    assert key_team(team.id) in fake.sets

    r2 = await client.get(f"/api/v1/teams/{team.id}")
    assert r2.status_code == 200
    assert r2.json() == r1.json()
    assert fake.hit_count() == 1


async def test_team_list_cache_miss_then_hit(
    cached_client: tuple[AsyncClient, FakeCache], db_session: AsyncSession
) -> None:
    client, fake = cached_client
    db_session.add_all([_team("Brazil", "BRA"), _team("Germany", "GER")])
    await db_session.flush()

    r1 = await client.get("/api/v1/teams?limit=20&offset=0")
    assert r1.status_code == 200
    assert fake.miss_count() == 1

    r2 = await client.get("/api/v1/teams?limit=20&offset=0")
    assert r2.json()["total"] == r1.json()["total"]
    assert fake.hit_count() == 1


async def test_match_get_cache_miss_then_hit(
    cached_client: tuple[AsyncClient, FakeCache], db_session: AsyncSession
) -> None:
    client, fake = cached_client
    match_id, _ = await _seed(db_session)

    r1 = await client.get(f"/api/v1/matches/{match_id}")
    assert r1.status_code == 200
    assert fake.miss_count() == 1
    assert key_match(match_id) in fake.sets

    r2 = await client.get(f"/api/v1/matches/{match_id}")
    assert r2.json()["id"] == match_id
    assert fake.hit_count() == 1


async def test_match_list_cache_miss_then_hit(
    cached_client: tuple[AsyncClient, FakeCache], db_session: AsyncSession
) -> None:
    client, fake = cached_client
    await _seed(db_session)

    r1 = await client.get("/api/v1/matches")
    assert r1.status_code == 200
    assert fake.miss_count() == 1

    r2 = await client.get("/api/v1/matches")
    assert r2.json()["total"] == r1.json()["total"]
    assert fake.hit_count() == 1


async def test_prediction_summary_cache_miss_then_hit(
    cached_client: tuple[AsyncClient, FakeCache], db_session: AsyncSession
) -> None:
    client, fake = cached_client
    match_id, _ = await _seed(db_session)

    r1 = await client.get(f"/api/v1/matches/{match_id}/prediction-summary")
    assert r1.status_code == 200
    assert fake.miss_count() >= 1  # match existence check + summary check

    r2 = await client.get(f"/api/v1/matches/{match_id}/prediction-summary")
    assert r2.json() == r1.json()
    assert fake.hit_count() >= 1


async def test_model_prediction_cache_miss_then_hit(
    cached_client: tuple[AsyncClient, FakeCache], db_session: AsyncSession
) -> None:
    client, fake = cached_client
    match_id, _ = await _seed(db_session)

    r1 = await client.get(f"/api/v1/matches/{match_id}/model-prediction")
    assert r1.status_code == 200
    assert key_model_prediction(match_id) in fake.sets

    r2 = await client.get(f"/api/v1/matches/{match_id}/model-prediction")
    assert r2.json()["home_win_probability"] == r1.json()["home_win_probability"]
    assert fake.hit_count() >= 1


async def test_different_pagination_keys_cached_separately(
    cached_client: tuple[AsyncClient, FakeCache], db_session: AsyncSession
) -> None:
    client, fake = cached_client
    db_session.add_all([_team("Brazil", "BRA"), _team("Germany", "GER"), _team("France", "FRA")])
    await db_session.flush()

    await client.get("/api/v1/teams?limit=2&offset=0")
    await client.get("/api/v1/teams?limit=2&offset=2")

    assert key_team_list(2, 0) in fake.sets
    assert key_team_list(2, 2) in fake.sets
    assert key_team_list(2, 0) != key_team_list(2, 2)


# ═════════════════════════════════════════════════════════════════════════════
# Prediction summary invalidation
# ═════════════════════════════════════════════════════════════════════════════

async def test_prediction_summary_invalidated_after_submit(
    cached_client: tuple[AsyncClient, FakeCache], db_session: AsyncSession
) -> None:
    client, fake = cached_client
    match_id, _ = await _seed(db_session)

    # Warm the cache
    await client.get(f"/api/v1/matches/{match_id}/prediction-summary")
    assert key_prediction_summary(match_id) in fake.sets

    # Submit a prediction → service should delete the summary key
    await client.post(
        f"/api/v1/matches/{match_id}/predictions",
        json={"session_id": "sess-001", "predicted_outcome": "home_win"},
    )
    assert key_prediction_summary(match_id) in fake.deletes


async def test_prediction_summary_updated_after_cache_invalidation(
    cached_client: tuple[AsyncClient, FakeCache], db_session: AsyncSession
) -> None:
    client, fake = cached_client
    match_id, _ = await _seed(db_session)

    r1 = await client.get(f"/api/v1/matches/{match_id}/prediction-summary")
    assert r1.json()["total_predictions"] == 0

    await client.post(
        f"/api/v1/matches/{match_id}/predictions",
        json={"session_id": "sess-001", "predicted_outcome": "home_win"},
    )

    r2 = await client.get(f"/api/v1/matches/{match_id}/prediction-summary")
    assert r2.json()["total_predictions"] == 1
    assert r2.json()["home_win_count"] == 1


# ═════════════════════════════════════════════════════════════════════════════
# Redis failure fallback — API must still work
# ═════════════════════════════════════════════════════════════════════════════

async def test_teams_work_when_redis_is_down(
    failing_client: AsyncClient, db_session: AsyncSession
) -> None:
    team = _team("Brazil", "BRA")
    db_session.add(team)
    await db_session.flush()

    resp = await failing_client.get(f"/api/v1/teams/{team.id}")
    assert resp.status_code == 200
    assert resp.json()["country_code"] == "BRA"


async def test_team_list_works_when_redis_is_down(
    failing_client: AsyncClient, db_session: AsyncSession
) -> None:
    db_session.add_all([_team("Brazil", "BRA"), _team("Germany", "GER")])
    await db_session.flush()

    resp = await failing_client.get("/api/v1/teams")
    assert resp.status_code == 200
    assert resp.json()["total"] == 2


async def test_match_works_when_redis_is_down(
    failing_client: AsyncClient, db_session: AsyncSession
) -> None:
    match_id, _ = await _seed(db_session)

    resp = await failing_client.get(f"/api/v1/matches/{match_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == match_id


async def test_model_prediction_works_when_redis_is_down(
    failing_client: AsyncClient, db_session: AsyncSession
) -> None:
    match_id, _ = await _seed(db_session)

    resp = await failing_client.get(f"/api/v1/matches/{match_id}/model-prediction")
    assert resp.status_code == 200
    total = (
        resp.json()["home_win_probability"]
        + resp.json()["draw_probability"]
        + resp.json()["away_win_probability"]
    )
    assert abs(total - 1.0) < 1e-4


async def test_prediction_summary_works_when_redis_is_down(
    failing_client: AsyncClient, db_session: AsyncSession
) -> None:
    match_id, _ = await _seed(db_session)

    resp = await failing_client.get(f"/api/v1/matches/{match_id}/prediction-summary")
    assert resp.status_code == 200
    assert resp.json()["total_predictions"] == 0


async def test_prediction_submit_works_when_redis_is_down(
    failing_client: AsyncClient, db_session: AsyncSession
) -> None:
    match_id, _ = await _seed(db_session)

    resp = await failing_client.post(
        f"/api/v1/matches/{match_id}/predictions",
        json={"session_id": "sess-x", "predicted_outcome": "draw"},
    )
    assert resp.status_code == 201
    assert resp.json()["community_summary"]["total_predictions"] == 1


# ═════════════════════════════════════════════════════════════════════════════
# Cache correctness — cached data matches live data
# ═════════════════════════════════════════════════════════════════════════════

async def test_cached_team_data_matches_db(
    cached_client: tuple[AsyncClient, FakeCache], db_session: AsyncSession
) -> None:
    client, _ = cached_client
    team = _team("Brazil", "BRA")
    db_session.add(team)
    await db_session.flush()

    live = (await client.get(f"/api/v1/teams/{team.id}")).json()
    cached = (await client.get(f"/api/v1/teams/{team.id}")).json()

    assert live == cached
    assert cached["name"] == "Brazil"
    assert cached["country_code"] == "BRA"


async def test_cached_match_data_matches_db(
    cached_client: tuple[AsyncClient, FakeCache], db_session: AsyncSession
) -> None:
    client, _ = cached_client
    match_id, _ = await _seed(db_session)

    live = (await client.get(f"/api/v1/matches/{match_id}")).json()
    cached = (await client.get(f"/api/v1/matches/{match_id}")).json()

    assert live == cached
    assert cached["id"] == match_id
