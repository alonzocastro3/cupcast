"""
Abstract football data provider interface.

Concrete adapters implement FootballDataProvider. Raw payload schemas
validate external API responses before any data reaches the database.
"""
from __future__ import annotations

import abc
from datetime import datetime

from pydantic import BaseModel, Field


# ── Exceptions ────────────────────────────────────────────────────────────────

class ProviderError(Exception):
    """Raised when a provider call fails."""


class ProviderTimeoutError(ProviderError):
    """Raised when a provider call exceeds its configured timeout."""


class ProviderRateLimitError(ProviderError):
    """Raised when a provider responds with HTTP 429."""


class ProviderAuthError(ProviderError):
    """Raised when a provider responds with HTTP 401 or 403."""


# ── Raw payload schemas ───────────────────────────────────────────────────────

class RawTeam(BaseModel):
    """Validated representation of a team from an external provider.

    Statistical fields default to zero so adapters only need to provide
    fields they actually receive; the ingestion service preserves existing
    DB values when incoming stats are at their defaults.
    """

    external_id: str
    name: str = Field(..., min_length=1, max_length=100)
    country_code: str = Field(..., min_length=2, max_length=3)
    group_name: str = Field(default="unknown", max_length=10)
    flag_url: str | None = None
    fifa_ranking: int = Field(default=200, ge=1)
    elo_rating: int = Field(default=1500, ge=0)
    recent_form_score: float = Field(default=0.0, ge=0.0)
    goals_for: int = Field(default=0, ge=0)
    goals_against: int = Field(default=0, ge=0)
    wins: int = Field(default=0, ge=0)
    draws: int = Field(default=0, ge=0)
    losses: int = Field(default=0, ge=0)


class RawFixture(BaseModel):
    """Validated representation of a fixture from an external provider."""

    external_id: str
    home_team_external_id: str
    away_team_external_id: str
    kickoff_at: datetime
    status: str  # provider-native string; mapped to MatchStatus by the ingestion service
    stage: str = Field(..., max_length=50)
    venue: str | None = Field(None, max_length=200)
    home_score: int | None = Field(None, ge=0)
    away_score: int | None = Field(None, ge=0)


# ── Abstract interface ────────────────────────────────────────────────────────

class FootballDataProvider(abc.ABC):
    """
    Contract all football data adapters must satisfy.

    tournament_id is a provider-specific string (e.g. "WC" for
    football-data.org, or a numeric competition ID for other providers).
    """

    @abc.abstractmethod
    async def fetch_teams(self, tournament_id: str) -> list[RawTeam]:
        """Return all teams participating in the given tournament."""

    @abc.abstractmethod
    async def fetch_fixtures(self, tournament_id: str) -> list[RawFixture]:
        """Return all fixtures (scheduled, live, and finished) for the tournament."""
