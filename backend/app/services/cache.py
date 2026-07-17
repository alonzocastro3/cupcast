"""Redis-backed cache service with graceful degradation on failure."""

from __future__ import annotations

import json
import logging
from typing import Any

from redis.asyncio import Redis

logger = logging.getLogger(__name__)

# ── TTLs (seconds) ────────────────────────────────────────────────────────────

TTL_TEAMS: int = 600           # 10 min
TTL_MATCHES: int = 120         # 2 min
TTL_MODEL_PREDICTION: int = 300  # 5 min
TTL_PREDICTION_SUMMARY: int = 30  # 30 sec


# ── Cache key builders ────────────────────────────────────────────────────────

def key_team_list(limit: int, offset: int) -> str:
    return f"cupcast:teams:list:{limit}:{offset}"


def key_team(team_id: int) -> str:
    return f"cupcast:teams:{team_id}"


def key_match_list(
    limit: int,
    offset: int,
    status: str | None,
    stage: str | None,
    team_id: int | None,
) -> str:
    return f"cupcast:matches:list:{limit}:{offset}:{status}:{stage}:{team_id}"


def key_match(match_id: int) -> str:
    return f"cupcast:matches:{match_id}"


def key_model_prediction(match_id: int) -> str:
    return f"cupcast:matches:{match_id}:model-prediction"


def key_prediction_summary(match_id: int) -> str:
    return f"cupcast:matches:{match_id}:prediction-summary"


# ── Service ───────────────────────────────────────────────────────────────────

class CacheService:
    """Thin async wrapper around Redis with JSON (de)serialisation.

    All methods catch every exception so a Redis outage never surfaces to the
    caller — they simply get None on get() and a no-op on set()/delete().
    """

    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def get(self, key: str) -> Any | None:
        try:
            raw = await self._redis.get(key)
            if raw is None:
                logger.debug("cache miss key=%s", key)
                return None
            logger.debug("cache hit key=%s", key)
            return json.loads(raw)
        except Exception as exc:  # noqa: BLE001
            logger.warning("cache get error key=%s exc=%s", key, exc)
            return None

    async def set(self, key: str, value: Any, ttl: int) -> None:
        try:
            await self._redis.set(key, json.dumps(value, default=str), ex=ttl)
        except Exception as exc:  # noqa: BLE001
            logger.warning("cache set error key=%s exc=%s", key, exc)

    async def delete(self, key: str) -> None:
        try:
            deleted = await self._redis.delete(key)
            if deleted:
                logger.debug("cache invalidated key=%s", key)
        except Exception as exc:  # noqa: BLE001
            logger.warning("cache delete error key=%s exc=%s", key, exc)
