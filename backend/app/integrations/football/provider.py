"""
football-data.org v4 adapter.

Configuration (all via environment variables, never in code):
  FOOTBALL_API_KEY         — X-Auth-Token header (required to call the API)
  FOOTBALL_API_BASE_URL    — defaults to https://api.football-data.org
  FOOTBALL_API_TIMEOUT     — request timeout in seconds (default 10)
  FOOTBALL_API_MAX_RETRIES — retry attempts on transient errors (default 3)

Retries with exponential backoff (1s, 2s, 4s) on timeouts, 5xx, and 429.
Auth errors (401/403) raise immediately without retrying.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime

import httpx
from pydantic import ValidationError

from .base import (
    FootballDataProvider,
    ProviderAuthError,
    ProviderError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    RawFixture,
    RawTeam,
)

logger = logging.getLogger(__name__)

_RETRYABLE_STATUSES = frozenset({429, 500, 502, 503, 504})

_STATUS_MAP: dict[str, str] = {
    "SCHEDULED": "scheduled",
    "TIMED": "scheduled",
    "IN_PLAY": "live",
    "PAUSED": "live",
    "HALFTIME": "live",
    "EXTRA_TIME": "live",
    "PENALTY_SHOOTOUT": "live",
    "FINISHED": "finished",
    "AWARDED": "finished",
    "POSTPONED": "cancelled",
    "SUSPENDED": "cancelled",
    "CANCELLED": "cancelled",
}

_STAGE_MAP: dict[str, str] = {
    "ROUND_OF_16": "round_of_16",
    "QUARTER_FINALS": "quarter_finals",
    "SEMI_FINALS": "semi_finals",
    "FINAL": "final",
    "THIRD_PLACE": "third_place",
    "THIRD_PLACE_PLAY_OFF": "third_place",
}


def _parse_group_letter(group: str | None) -> str:
    """'GROUP_A' or 'Group A' → 'A'; None → 'unknown'."""
    if not group:
        return "unknown"
    upper = group.upper().replace("GROUP_", "").replace("GROUP ", "").strip()
    return upper[:10] if upper else "unknown"


def _parse_stage(stage: str | None, group: str | None) -> str:
    """Build our internal stage slug from provider stage + group values."""
    if not stage:
        return "unknown"
    if stage.upper() == "GROUP_STAGE":
        letter = _parse_group_letter(group).lower()
        return f"group_{letter}" if letter != "unknown" else "group_stage"
    return _STAGE_MAP.get(stage.upper(), stage.lower().replace(" ", "_"))


class FootballDataOrgProvider(FootballDataProvider):
    """Adapter for the football-data.org v4 REST API."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.football-data.org",
        timeout: float = 10.0,
        max_retries: int = 3,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._max_retries = max_retries

    async def _request(self, path: str) -> dict:
        """GET request with retry + exponential backoff."""
        url = f"{self._base_url}{path}"
        headers = {"X-Auth-Token": self._api_key}
        last_exc: Exception = ProviderError(f"No attempts made: {url}")

        for attempt in range(self._max_retries + 1):
            if attempt > 0:
                delay = 2.0 ** (attempt - 1)  # 1s, 2s, 4s
                logger.debug(
                    "Retry %d/%d after %.1fs for %s", attempt, self._max_retries, delay, path
                )
                await asyncio.sleep(delay)

            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    resp = await client.get(url, headers=headers)
            except httpx.TimeoutException:
                last_exc = ProviderTimeoutError(f"Timeout ({self._timeout}s): {url}")
                logger.warning("Timeout on attempt %d for %s", attempt + 1, path)
                continue
            except httpx.RequestError as exc:
                last_exc = ProviderError(f"Request error: {exc}")
                logger.warning("Request error on attempt %d for %s: %s", attempt + 1, path, exc)
                continue

            if resp.status_code in (401, 403):
                raise ProviderAuthError(f"Auth failure (HTTP {resp.status_code}): {url}")

            if resp.status_code == 429:
                last_exc = ProviderRateLimitError(f"Rate limited: {url}")
                logger.warning("Rate limited on attempt %d for %s", attempt + 1, path)
                continue

            if resp.status_code in _RETRYABLE_STATUSES:
                last_exc = ProviderError(f"HTTP {resp.status_code}: {url}")
                logger.warning(
                    "HTTP %d on attempt %d for %s", resp.status_code, attempt + 1, path
                )
                continue

            if not resp.is_success:
                raise ProviderError(f"HTTP {resp.status_code}: {url}")

            return resp.json()

        raise last_exc

    async def fetch_teams(self, tournament_id: str) -> list[RawTeam]:
        data = await self._request(f"/v4/competitions/{tournament_id}/teams")
        raw_teams: list[RawTeam] = []

        for item in data.get("teams", []):
            try:
                raw = RawTeam(
                    external_id=str(item["id"]),
                    name=item.get("name") or item.get("shortName") or "Unknown",
                    country_code=(item.get("tla") or "UNK")[:3].upper(),
                    group_name=_parse_group_letter(item.get("group")),
                    flag_url=item.get("crest") or item.get("flag"),
                )
                raw_teams.append(raw)
            except (KeyError, ValidationError) as exc:
                logger.warning("Skipping malformed team (id=%s): %s", item.get("id"), exc)

        logger.info("Fetched %d teams for tournament=%s", len(raw_teams), tournament_id)
        return raw_teams

    async def fetch_fixtures(self, tournament_id: str) -> list[RawFixture]:
        data = await self._request(f"/v4/competitions/{tournament_id}/matches")
        raw_fixtures: list[RawFixture] = []

        for item in data.get("matches", []):
            try:
                score = item.get("score") or {}
                full_time = score.get("fullTime") or {}

                raw = RawFixture(
                    external_id=str(item["id"]),
                    home_team_external_id=str(item["homeTeam"]["id"]),
                    away_team_external_id=str(item["awayTeam"]["id"]),
                    kickoff_at=datetime.fromisoformat(
                        item["utcDate"].replace("Z", "+00:00")
                    ),
                    status=_STATUS_MAP.get(item.get("status", "SCHEDULED"), "scheduled"),
                    stage=_parse_stage(item.get("stage"), item.get("group")),
                    venue=item.get("venue"),
                    home_score=full_time.get("home"),
                    away_score=full_time.get("away"),
                )
                raw_fixtures.append(raw)
            except (KeyError, TypeError, ValueError, ValidationError) as exc:
                logger.warning("Skipping malformed fixture (id=%s): %s", item.get("id"), exc)

        logger.info("Fetched %d fixtures for tournament=%s", len(raw_fixtures), tournament_id)
        return raw_fixtures
