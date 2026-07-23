"""
Abstract news provider interface.

Concrete adapters implement NewsProvider.  RawArticle validates external
API responses before they enter the service layer.  Only metadata fields
are captured — full article text is never stored.
"""
from __future__ import annotations

import abc
from datetime import datetime

from pydantic import BaseModel, Field


# ── Exceptions ────────────────────────────────────────────────────────────────

class NewsProviderError(Exception):
    """Raised when a news provider call fails for any reason."""


class NewsProviderTimeoutError(NewsProviderError):
    """Raised when a provider call exceeds its configured timeout."""


class NewsProviderRateLimitError(NewsProviderError):
    """Raised when a provider responds with HTTP 429."""


class NewsProviderAuthError(NewsProviderError):
    """Raised when a provider responds with HTTP 401 or 403."""


# ── Raw payload schema ────────────────────────────────────────────────────────

class RawArticle(BaseModel):
    """
    Validated external article payload.

    Adapters populate only the fields their API provides; the service
    fills in derived fields (id, related_team_codes) after validation.

    Full article text must never be stored — only the provider-supplied
    summary/description (typically ≤ 300 characters).
    """

    title: str = Field(..., min_length=1, max_length=500)
    source_name: str = Field(..., min_length=1, max_length=200)
    url: str = Field(..., min_length=10)
    published_at: datetime
    image_url: str | None = None
    summary: str | None = Field(None, max_length=2000)


# ── Abstract interface ────────────────────────────────────────────────────────

class NewsProvider(abc.ABC):
    """
    Contract all news adapters must satisfy.

    query is a free-text search string.  Implementations are responsible
    for translating it to their provider's query format and returning
    at most page_size results per call.
    """

    @abc.abstractmethod
    async def fetch_articles(
        self,
        query: str,
        page_size: int = 100,
    ) -> list[RawArticle]:
        """Return articles matching *query*, newest first."""
