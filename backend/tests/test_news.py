"""
Tests for the news aggregation feature (Phase 11).

Unit tests cover: URL sanitisation, deduplication, team detection, caching,
team filtering, pagination, and graceful failure recovery.  All provider
interactions are mocked — no HTTP calls are made.

API tests cover: the GET /api/v1/news endpoint with a fully mocked service.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.integrations.news.base import NewsProvider, NewsProviderError, RawArticle
from app.integrations.news.provider import NewsApiOrgProvider
from app.main import app as fastapi_app
from app.routers.news import _news_service
from app.schemas.news import NewsArticle
from app.services.news_service import (
    NewsService,
    _deduplicate,
    _detect_team_codes,
    _jaccard,
    _title_tokens,
    _url_dedup_key,
    _validate_and_sanitize_url,
)

_TZ = timezone.utc


# ── Helpers ───────────────────────────────────────────────────────────────────

def _raw(
    title: str = "World Cup 2026 news",
    url: str = "https://example.com/article",
    source_name: str = "Example News",
    summary: str | None = None,
    image_url: str | None = None,
) -> RawArticle:
    return RawArticle(
        title=title,
        source_name=source_name,
        url=url,
        published_at=datetime(2026, 6, 15, 12, 0, tzinfo=_TZ),
        image_url=image_url,
        summary=summary,
    )


class _MockProvider(NewsProvider):
    def __init__(self, articles: list[RawArticle] | None = None) -> None:
        self._articles = articles or []
        self.call_count = 0

    async def fetch_articles(self, query: str, page_size: int = 100) -> list[RawArticle]:
        self.call_count += 1
        return list(self._articles)


class _FailingProvider(NewsProvider):
    async def fetch_articles(self, query: str, page_size: int = 100) -> list[RawArticle]:
        raise NewsProviderError("provider is down")


class _InMemoryCache:
    def __init__(self) -> None:
        self._store: dict[str, Any] = {}

    async def get(self, key: str) -> Any | None:
        return self._store.get(key)

    async def set(self, key: str, value: Any, ttl: int) -> None:
        self._store[key] = value

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)


# ── URL validation unit tests ─────────────────────────────────────────────────

def test_validate_url_https_passes():
    assert _validate_and_sanitize_url("https://reuters.com/sports/article") is not None


def test_validate_url_http_passes():
    assert _validate_and_sanitize_url("http://bbc.com/sport/football") is not None


def test_validate_url_rejects_javascript_scheme():
    assert _validate_and_sanitize_url("javascript:alert(1)") is None


def test_validate_url_rejects_data_scheme():
    assert _validate_and_sanitize_url("data:text/html,<h1>hi</h1>") is None


def test_validate_url_rejects_empty_netloc():
    assert _validate_and_sanitize_url("https:///path/only") is None


def test_validate_url_strips_utm_params():
    url = "https://example.com/article?utm_source=google&utm_medium=cpc&id=42"
    clean = _validate_and_sanitize_url(url)
    assert clean is not None
    assert "utm_source" not in clean
    assert "utm_medium" not in clean
    assert "id=42" in clean


def test_validate_url_strips_fbclid():
    url = "https://example.com/news?fbclid=abc123&page=1"
    clean = _validate_and_sanitize_url(url)
    assert clean is not None
    assert "fbclid" not in clean
    assert "page=1" in clean


def test_validate_url_drops_fragment():
    url = "https://example.com/article#section-2"
    clean = _validate_and_sanitize_url(url)
    assert clean is not None
    assert "#" not in clean


# ── Deduplication unit tests ──────────────────────────────────────────────────

def test_url_dedup_key_strips_www():
    assert _url_dedup_key("https://www.bbc.com/sport") == _url_dedup_key("https://bbc.com/sport")


def test_url_dedup_key_case_insensitive():
    assert _url_dedup_key("https://BBC.COM/Sport") == _url_dedup_key("https://bbc.com/sport")


def test_url_dedup_key_strips_trailing_slash():
    assert _url_dedup_key("https://bbc.com/sport/") == _url_dedup_key("https://bbc.com/sport")


def test_jaccard_identical():
    tokens = frozenset(["world", "cup", "2026", "final"])
    assert _jaccard(tokens, tokens) == 1.0


def test_jaccard_disjoint():
    a = frozenset(["world", "cup"])
    b = frozenset(["premier", "league"])
    assert _jaccard(a, b) == 0.0


def test_jaccard_partial():
    a = frozenset(["world", "cup", "final", "2026"])
    b = frozenset(["world", "cup", "semifinal", "2026"])
    score = _jaccard(a, b)
    assert 0.0 < score < 1.0


def test_deduplicate_exact_url():
    articles = [
        _raw(title="Article A", url="https://example.com/article"),
        _raw(title="Article B", url="https://example.com/article"),  # same URL
    ]
    result = _deduplicate(articles)
    assert len(result) == 1
    assert result[0].title == "Article A"


def test_deduplicate_www_variant_url():
    articles = [
        _raw(title="Story One", url="https://www.bbc.com/sport/football-123"),
        _raw(title="Story Two", url="https://bbc.com/sport/football-123"),
    ]
    result = _deduplicate(articles)
    assert len(result) == 1


def test_deduplicate_title_similarity():
    articles = [
        _raw(title="Brazil beats France in World Cup Final 2026", url="https://a.com/1"),
        _raw(title="Brazil beats France in World Cup Final 2026 match", url="https://b.com/2"),
    ]
    result = _deduplicate(articles)
    assert len(result) == 1


def test_deduplicate_different_articles_kept():
    articles = [
        _raw(title="Brazil beats France in World Cup Final", url="https://a.com/1"),
        _raw(title="Argentina defeats England in semifinal", url="https://b.com/2"),
    ]
    result = _deduplicate(articles)
    assert len(result) == 2


# ── Team detection unit tests ─────────────────────────────────────────────────

def test_detect_brazil_from_title():
    codes = _detect_team_codes("Brazil wins World Cup 2026", None)
    assert "BRA" in codes


def test_detect_team_from_summary():
    codes = _detect_team_codes("Match report", "La Albiceleste secured victory")
    assert "ARG" in codes


def test_detect_multiple_teams():
    codes = _detect_team_codes("France vs Spain World Cup semifinal", None)
    assert "FRA" in codes
    assert "ESP" in codes


def test_detect_team_alias():
    codes = _detect_team_codes("Die Mannschaft triumph in Group A", None)
    assert "GER" in codes


def test_detect_no_teams_returns_empty():
    codes = _detect_team_codes("Transfer window opens next week", None)
    assert codes == []


def test_detect_codes_sorted():
    codes = _detect_team_codes("Spain vs Brazil clash today", None)
    assert codes == sorted(codes)


# ── NewsService unit tests ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_service_returns_articles():
    provider = _MockProvider([_raw(title="World Cup news", summary="Brazil leads")])
    service = NewsService(provider=provider, cache=_InMemoryCache())
    articles, total = await service.get_news()
    assert total == 1
    assert articles[0].title == "World Cup news"
    assert "BRA" in articles[0].related_team_codes


@pytest.mark.asyncio
async def test_service_provider_failure_returns_empty():
    service = NewsService(provider=_FailingProvider(), cache=_InMemoryCache())
    articles, total = await service.get_news()
    assert articles == []
    assert total == 0


@pytest.mark.asyncio
async def test_service_cache_hit_skips_provider():
    provider = _MockProvider([_raw()])
    cache = _InMemoryCache()
    service = NewsService(provider=provider, cache=cache)

    # Prime the cache
    await service.get_news()
    assert provider.call_count == 1

    # Second call should use cache
    await service.get_news()
    assert provider.call_count == 1


@pytest.mark.asyncio
async def test_service_drops_invalid_url_articles():
    articles = [
        _raw(title="Good article", url="https://valid.com/story"),
        _raw(title="Bad article", url="javascript:alert(1)"),
    ]
    provider = _MockProvider(articles)
    service = NewsService(provider=provider, cache=_InMemoryCache())
    result, total = await service.get_news()
    assert total == 1
    assert result[0].title == "Good article"


@pytest.mark.asyncio
async def test_service_team_codes_filter():
    articles = [
        _raw(title="Brazil beats France", url="https://a.com/1"),
        _raw(title="Argentina defeats England", url="https://b.com/2"),
        _raw(title="General World Cup news", url="https://c.com/3"),
    ]
    provider = _MockProvider(articles)
    service = NewsService(provider=provider, cache=_InMemoryCache())

    result, total = await service.get_news(team_codes=["BRA"])
    titles = [a.title for a in result]
    assert any("Brazil" in t for t in titles)
    assert not any("Argentina" in t for t in titles)


@pytest.mark.asyncio
async def test_service_team_codes_filter_case_insensitive():
    articles = [_raw(title="Brazil in the World Cup", url="https://a.com/1")]
    provider = _MockProvider(articles)
    service = NewsService(provider=provider, cache=_InMemoryCache())

    result_upper, _ = await service.get_news(team_codes=["BRA"])
    result_lower, _ = await service.get_news(team_codes=["bra"])
    assert len(result_upper) == len(result_lower)


@pytest.mark.asyncio
async def test_service_pagination():
    # Use sufficiently distinct titles so Jaccard dedup doesn't collapse them
    titles_and_urls = [
        ("Brazil beats France World Cup Final 2026", "https://reuters.com/a"),
        ("Argentina defeats England semifinal match result", "https://bbc.com/b"),
        ("Germany draws Spain first group stage game", "https://espn.com/c"),
        ("Morocco stuns Portugal quarterfinal victory upset", "https://goal.com/d"),
        ("Japan eliminates Colombia penalty shootout drama", "https://sky.com/e"),
    ]
    articles = [_raw(title=t, url=u) for t, u in titles_and_urls]
    provider = _MockProvider(articles)
    service = NewsService(provider=provider, cache=_InMemoryCache())

    page, total = await service.get_news(limit=2, offset=0)
    assert total == 5
    assert len(page) == 2

    page2, total2 = await service.get_news(limit=2, offset=2)
    assert total2 == 5
    assert len(page2) == 2
    assert page[0].title != page2[0].title


@pytest.mark.asyncio
async def test_service_pagination_beyond_end():
    articles = [_raw(title="Single article", url="https://example.com/1")]
    provider = _MockProvider(articles)
    service = NewsService(provider=provider, cache=_InMemoryCache())

    page, total = await service.get_news(limit=10, offset=5)
    assert total == 1
    assert page == []


@pytest.mark.asyncio
async def test_service_image_url_sanitized():
    article = _raw(
        title="World Cup final preview",
        url="https://example.com/story",
        image_url="https://cdn.example.com/img.jpg?utm_source=feed",
    )
    provider = _MockProvider([article])
    service = NewsService(provider=provider, cache=_InMemoryCache())
    result, _ = await service.get_news()
    assert result[0].image_url is not None
    assert "utm_source" not in result[0].image_url


@pytest.mark.asyncio
async def test_service_invalid_image_url_becomes_none():
    article = _raw(
        title="World Cup final preview",
        url="https://example.com/story",
        image_url="not-a-valid-url",
    )
    provider = _MockProvider([article])
    service = NewsService(provider=provider, cache=_InMemoryCache())
    result, _ = await service.get_news()
    assert result[0].image_url is None


# ── Provider unit tests (NewsApiOrgProvider) ──────────────────────────────────

def _mock_httpx_response(payload: dict, status_code: int = 200):
    """Return an AsyncMock that simulates httpx.AsyncClient.get."""
    from unittest.mock import AsyncMock, MagicMock
    import httpx

    response = MagicMock(spec=httpx.Response)
    response.status_code = status_code
    response.is_success = (200 <= status_code < 300)
    response.json.return_value = payload

    client_mock = AsyncMock()
    client_mock.__aenter__ = AsyncMock(return_value=client_mock)
    client_mock.__aexit__ = AsyncMock(return_value=False)
    client_mock.get = AsyncMock(return_value=response)
    return client_mock


@pytest.mark.asyncio
async def test_provider_skips_removed_sentinel(monkeypatch):
    payload = {
        "articles": [
            {
                "title": "[Removed]",
                "source": {"name": "Removed Source"},
                "url": "https://removed.com/article",
                "publishedAt": "2026-06-15T12:00:00Z",
                "description": None,
                "urlToImage": None,
            },
            {
                "title": "Real article about World Cup",
                "source": {"name": "BBC Sport"},
                "url": "https://bbc.com/sport/wc-2026",
                "publishedAt": "2026-06-15T12:00:00Z",
                "description": "Match report",
                "urlToImage": None,
            },
        ]
    }
    client_mock = _mock_httpx_response(payload)
    monkeypatch.setattr("httpx.AsyncClient", lambda **kw: client_mock)

    provider = NewsApiOrgProvider(api_key="test-key")
    articles = await provider.fetch_articles("World Cup 2026")
    assert len(articles) == 1
    assert articles[0].title == "Real article about World Cup"


@pytest.mark.asyncio
async def test_provider_skips_article_with_bad_date(monkeypatch):
    payload = {
        "articles": [
            {
                "title": "Good article",
                "source": {"name": "ESPN"},
                "url": "https://espn.com/wc",
                "publishedAt": "not-a-date",
                "description": None,
                "urlToImage": None,
            }
        ]
    }
    client_mock = _mock_httpx_response(payload)
    monkeypatch.setattr("httpx.AsyncClient", lambda **kw: client_mock)

    provider = NewsApiOrgProvider(api_key="test-key")
    articles = await provider.fetch_articles("World Cup 2026")
    assert articles == []


@pytest.mark.asyncio
async def test_provider_auth_error_raises(monkeypatch):
    from app.integrations.news.base import NewsProviderAuthError

    client_mock = _mock_httpx_response({"message": "Unauthorized"}, status_code=401)
    monkeypatch.setattr("httpx.AsyncClient", lambda **kw: client_mock)

    provider = NewsApiOrgProvider(api_key="bad-key", max_retries=0)
    with pytest.raises(NewsProviderAuthError):
        await provider.fetch_articles("World Cup 2026")


# ── API endpoint tests ────────────────────────────────────────────────────────

def _make_article(title: str, team_codes: list[str]) -> NewsArticle:
    return NewsArticle(
        id="abc123",
        title=title,
        source="Test Source",
        url="https://example.com/news",
        published_at=datetime(2026, 6, 15, 12, 0, tzinfo=_TZ),
        related_team_codes=team_codes,
    )


class _MockNewsService:
    def __init__(self, articles: list[NewsArticle]) -> None:
        self._articles = articles

    async def get_news(
        self,
        team_codes: list[str] | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[NewsArticle], int]:
        filtered = self._articles
        if team_codes:
            upper = [c.upper() for c in team_codes]
            filtered = [a for a in filtered if any(c in a.related_team_codes for c in upper)]
        total = len(filtered)
        return filtered[offset : offset + limit], total


@pytest_asyncio.fixture
async def news_api_client():
    """HTTP client with the news service dependency mocked."""
    articles = [
        _make_article("Brazil beats France", ["BRA", "FRA"]),
        _make_article("Argentina defeats England", ["ARG", "ENG"]),
    ]
    mock_service = _MockNewsService(articles)

    fastapi_app.dependency_overrides[_news_service] = lambda: mock_service
    async with AsyncClient(transport=ASGITransport(app=fastapi_app), base_url="http://test") as ac:
        yield ac
    fastapi_app.dependency_overrides.pop(_news_service, None)


@pytest.mark.asyncio
async def test_list_news_returns_200(news_api_client: AsyncClient):
    resp = await news_api_client.get("/api/v1/news")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


@pytest.mark.asyncio
async def test_list_news_pagination_params(news_api_client: AsyncClient):
    resp = await news_api_client.get("/api/v1/news?limit=1&offset=0")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["items"]) == 1
    assert data["limit"] == 1
    assert data["offset"] == 0


@pytest.mark.asyncio
async def test_list_news_team_filter(news_api_client: AsyncClient):
    resp = await news_api_client.get("/api/v1/news?team_codes=BRA")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "Brazil beats France"


@pytest.mark.asyncio
async def test_list_news_team_filter_multiple(news_api_client: AsyncClient):
    resp = await news_api_client.get("/api/v1/news?team_codes=BRA&team_codes=ARG")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2


@pytest.mark.asyncio
async def test_list_news_response_schema(news_api_client: AsyncClient):
    resp = await news_api_client.get("/api/v1/news")
    assert resp.status_code == 200
    item = resp.json()["items"][0]
    assert "id" in item
    assert "title" in item
    assert "source" in item
    assert "url" in item
    assert "published_at" in item
    assert "related_team_codes" in item
