"""
NewsAPI.org adapter (v2 /everything endpoint).

Configuration — all via environment variables, never hardcoded:
  NEWS_API_KEY          Required.  Passed as X-Api-Key request header.
  NEWS_API_BASE_URL     Default: https://newsapi.org
  NEWS_API_TIMEOUT      Per-request timeout in seconds.  Default: 10.0
  NEWS_API_MAX_RETRIES  Retry attempts on transient errors.  Default: 2

Articles with title '[Removed]' (deleted/unavailable on NewsAPI) are
silently dropped.  Only the 'description' field is stored as summary;
the 'content' field is deliberately ignored because NewsAPI truncates it
with '[+N chars]' which is not useful and may contain partial copyrighted
text.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

import httpx
from pydantic import ValidationError

from .base import (
    NewsProvider,
    NewsProviderAuthError,
    NewsProviderError,
    NewsProviderRateLimitError,
    NewsProviderTimeoutError,
    RawArticle,
)

logger = logging.getLogger(__name__)

_RETRYABLE_STATUSES = frozenset({429, 500, 502, 503, 504})
_REMOVED_SENTINEL = "[Removed]"


class NewsApiOrgProvider(NewsProvider):
    """Adapter for the NewsAPI.org v2 REST API."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://newsapi.org",
        timeout: float = 10.0,
        max_retries: int = 2,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._max_retries = max_retries

    async def _request(self, path: str, params: dict) -> dict:
        """GET with retry and exponential backoff.  Auth via header, not URL."""
        url = f"{self._base_url}{path}"
        headers = {"X-Api-Key": self._api_key}
        last_exc: Exception = NewsProviderError(f"No attempts made: {url}")

        for attempt in range(self._max_retries + 1):
            if attempt > 0:
                delay = 2.0 ** (attempt - 1)
                logger.debug(
                    "Retry %d/%d after %.1fs for %s", attempt, self._max_retries, delay, path
                )
                await asyncio.sleep(delay)

            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    resp = await client.get(url, headers=headers, params=params)
            except httpx.TimeoutException:
                last_exc = NewsProviderTimeoutError(f"Timeout ({self._timeout}s): {url}")
                logger.warning("Timeout on attempt %d for %s", attempt + 1, path)
                continue
            except httpx.RequestError as exc:
                last_exc = NewsProviderError(f"Request error: {exc}")
                logger.warning("Request error on attempt %d for %s: %s", attempt + 1, path, exc)
                continue

            if resp.status_code in (401, 403):
                raise NewsProviderAuthError(
                    f"Auth failure (HTTP {resp.status_code}): {url}"
                )
            if resp.status_code == 429:
                last_exc = NewsProviderRateLimitError(f"Rate limited: {url}")
                logger.warning("Rate limited on attempt %d for %s", attempt + 1, path)
                continue
            if resp.status_code in _RETRYABLE_STATUSES:
                last_exc = NewsProviderError(f"HTTP {resp.status_code}: {url}")
                logger.warning(
                    "HTTP %d on attempt %d for %s", resp.status_code, attempt + 1, path
                )
                continue
            if not resp.is_success:
                raise NewsProviderError(f"HTTP {resp.status_code}: {url}")

            return resp.json()

        raise last_exc

    async def fetch_articles(
        self,
        query: str,
        page_size: int = 100,
    ) -> list[RawArticle]:
        data = await self._request(
            "/v2/everything",
            {
                "q": query,
                "language": "en",
                "sortBy": "publishedAt",
                "pageSize": min(page_size, 100),  # NewsAPI hard cap is 100
            },
        )

        raw_articles: list[RawArticle] = []
        for item in data.get("articles", []):
            title = (item.get("title") or "").strip()
            if not title or title == _REMOVED_SENTINEL:
                continue

            source_name = (item.get("source") or {}).get("name") or ""
            if not source_name or source_name == _REMOVED_SENTINEL:
                source_name = "Unknown"

            url = (item.get("url") or "").strip()
            if not url:
                continue

            # Use description as summary; never store content (truncated by NewsAPI)
            description = item.get("description") or None
            if description:
                description = description.strip()[:2000] or None

            image_url = item.get("urlToImage") or None
            published_raw = item.get("publishedAt") or ""

            try:
                published_at = datetime.fromisoformat(
                    published_raw.replace("Z", "+00:00")
                )
            except (ValueError, AttributeError):
                logger.debug("Skipping article with bad publishedAt: %r", published_raw)
                continue

            try:
                raw = RawArticle(
                    title=title,
                    source_name=source_name,
                    url=url,
                    published_at=published_at,
                    image_url=image_url,
                    summary=description,
                )
                raw_articles.append(raw)
            except ValidationError as exc:
                logger.debug("Skipping invalid article %r: %s", title[:40], exc)

        logger.info(
            "Fetched %d articles for query=%r from NewsAPI",
            len(raw_articles),
            query,
        )
        return raw_articles
