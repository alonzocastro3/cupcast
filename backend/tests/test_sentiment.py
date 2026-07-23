"""
Tests for sentiment analysis (Phase 12).

Tests cover:
- VaderSentimentAnalyzer: positive, neutral, negative, empty, malformed text
- SentimentService: aggregation, team filter, cache hit, empty articles
- API endpoints: GET /api/v1/sentiment and GET /api/v1/teams/{team_id}/sentiment
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app as fastapi_app
from app.routers.sentiment import _sentiment_service
from app.schemas.news import NewsArticle
from app.schemas.sentiment import DISCLAIMER, SentimentMetadata, TeamSentimentRead
from app.services.sentiment.base import SentimentAnalyzer, SentimentResult
from app.services.sentiment.vader import VaderSentimentAnalyzer
from app.services.sentiment_service import (
    SentimentService,
    _aggregate_confidence,
    _label,
)

_TZ = timezone.utc


# ── Helpers ───────────────────────────────────────────────────────────────────

def _article(
    title: str,
    team_codes: list[str],
    summary: str | None = None,
    article_id: str = "abc123",
    url: str = "https://example.com/news",
) -> NewsArticle:
    return NewsArticle(
        id=article_id,
        title=title,
        source="Test",
        url=url,
        published_at=datetime(2026, 6, 15, 12, 0, tzinfo=_TZ),
        related_team_codes=team_codes,
        summary=summary,
    )


class _InMemoryCache:
    def __init__(self) -> None:
        self._store: dict[str, Any] = {}

    async def get(self, key: str) -> Any | None:
        return self._store.get(key)

    async def set(self, key: str, value: Any, ttl: int) -> None:
        self._store[key] = value

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)


class _MockNewsService:
    def __init__(self, articles: list[NewsArticle]) -> None:
        self._articles = articles
        self.call_count = 0

    async def get_news(
        self,
        team_codes: list[str] | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[NewsArticle], int]:
        self.call_count += 1
        filtered = self._articles
        if team_codes:
            upper = [c.upper() for c in team_codes]
            filtered = [a for a in filtered if any(c in a.related_team_codes for c in upper)]
        return filtered[offset : offset + limit], len(filtered)


class _ConstantAnalyzer(SentimentAnalyzer):
    """Returns a fixed result for every input — isolates service logic from VADER."""

    def __init__(self, score: float, label: str, confidence: float) -> None:
        self._result = SentimentResult(score=score, label=label, confidence=confidence)  # type: ignore[arg-type]

    def analyze(self, text: str) -> SentimentResult:
        return self._result


# ── VaderSentimentAnalyzer unit tests ─────────────────────────────────────────

def test_vader_positive_headline():
    analyzer = VaderSentimentAnalyzer()
    result = analyzer.analyze("Brazil dominates World Cup with spectacular victory celebration!")
    assert result.label == "positive"
    assert result.score > 0.05
    assert result.confidence > 0.0


def test_vader_negative_headline():
    analyzer = VaderSentimentAnalyzer()
    result = analyzer.analyze("Team suffers catastrophic defeat, worst performance ever seen")
    assert result.label == "negative"
    assert result.score < -0.05
    assert result.confidence > 0.0


def test_vader_neutral_headline():
    analyzer = VaderSentimentAnalyzer()
    result = analyzer.analyze("Match scheduled for Tuesday at 3pm local time in stadium")
    assert result.label == "neutral"
    assert -0.05 <= result.score <= 0.05


def test_vader_empty_string():
    analyzer = VaderSentimentAnalyzer()
    result = analyzer.analyze("")
    assert result.score == 0.0
    assert result.label == "neutral"
    assert result.confidence == 0.0


def test_vader_whitespace_only():
    analyzer = VaderSentimentAnalyzer()
    result = analyzer.analyze("   \t\n  ")
    assert result.score == 0.0
    assert result.label == "neutral"
    assert result.confidence == 0.0


def test_vader_malformed_numbers_only():
    analyzer = VaderSentimentAnalyzer()
    result = analyzer.analyze("42 0 1 2 3 99")
    assert result.label in ("positive", "neutral", "negative")
    assert -1.0 <= result.score <= 1.0
    assert 0.0 <= result.confidence <= 1.0


def test_vader_special_chars():
    analyzer = VaderSentimentAnalyzer()
    result = analyzer.analyze("!@#$%^&*()")
    assert result.label in ("positive", "neutral", "negative")
    assert -1.0 <= result.score <= 1.0


def test_vader_score_range():
    analyzer = VaderSentimentAnalyzer()
    for text in [
        "This is absolutely terrible and horrible and the worst",
        "This is amazing and wonderful and the best ever!",
        "There is a game on Tuesday.",
    ]:
        result = analyzer.analyze(text)
        assert -1.0 <= result.score <= 1.0
        assert 0.0 <= result.confidence <= 1.0


def test_vader_deterministic():
    analyzer = VaderSentimentAnalyzer()
    text = "Brazil wins the World Cup in thrilling final match"
    r1 = analyzer.analyze(text)
    r2 = analyzer.analyze(text)
    assert r1.score == r2.score
    assert r1.label == r2.label
    assert r1.confidence == r2.confidence


def test_vader_confidence_equals_abs_score():
    analyzer = VaderSentimentAnalyzer()
    result = analyzer.analyze("Brilliant stunning magnificent victory performance!")
    assert abs(result.confidence - abs(result.score)) < 0.0001


# ── Sentiment helper unit tests ───────────────────────────────────────────────

def test_label_thresholds():
    assert _label(0.5) == "positive"
    assert _label(0.05) == "positive"
    assert _label(0.04) == "neutral"
    assert _label(0.0) == "neutral"
    assert _label(-0.04) == "neutral"
    assert _label(-0.05) == "negative"
    assert _label(-0.5) == "negative"


def test_aggregate_confidence_zero_articles():
    assert _aggregate_confidence(0, []) == 0.0


def test_aggregate_confidence_increases_with_count():
    c1 = _aggregate_confidence(1, [0.5])
    c5 = _aggregate_confidence(5, [0.5, 0.5, 0.5, 0.5, 0.5])
    c10 = _aggregate_confidence(10, [0.5] * 10)
    assert c1 < c5 < c10


def test_aggregate_confidence_bounded():
    c = _aggregate_confidence(1000, [1.0] * 1000)
    assert 0.0 <= c <= 1.0


# ── SentimentService unit tests ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_service_aggregates_by_team():
    articles = [
        _article("Brazil wins!", ["BRA"], article_id="a1", url="https://a.com/1"),
        _article("France plays well", ["FRA"], article_id="a2", url="https://b.com/2"),
        _article("Brazil and France tied", ["BRA", "FRA"], article_id="a3", url="https://c.com/3"),
    ]
    news = _MockNewsService(articles)
    service = SentimentService(news_service=news, analyzer=VaderSentimentAnalyzer(), cache=_InMemoryCache())
    teams, meta = await service.get_all_teams_sentiment()
    codes = {t.team_code for t in teams}
    assert "BRA" in codes
    assert "FRA" in codes


@pytest.mark.asyncio
async def test_service_team_sentiment_with_articles():
    articles = [
        _article("Brazil wins spectacular victory!", ["BRA"], article_id="a1", url="https://a.com/1"),
    ]
    news = _MockNewsService(articles)
    service = SentimentService(
        news_service=news, analyzer=VaderSentimentAnalyzer(), cache=_InMemoryCache()
    )
    team, meta = await service.get_team_sentiment("BRA")
    assert team is not None
    assert team.team_code == "BRA"
    assert team.article_count == 1
    assert len(team.articles) == 1
    assert -1.0 <= team.average_score <= 1.0


@pytest.mark.asyncio
async def test_service_team_sentiment_no_articles_returns_none():
    news = _MockNewsService([])
    service = SentimentService(
        news_service=news, analyzer=VaderSentimentAnalyzer(), cache=_InMemoryCache()
    )
    team, meta = await service.get_team_sentiment("BRA")
    assert team is None
    assert meta.sample_size == 0


@pytest.mark.asyncio
async def test_service_cache_hit_skips_news_service():
    articles = [
        _article("Brazil wins!", ["BRA"], article_id="a1", url="https://a.com/1"),
    ]
    news = _MockNewsService(articles)
    service = SentimentService(
        news_service=news, analyzer=VaderSentimentAnalyzer(), cache=_InMemoryCache()
    )
    await service.get_all_teams_sentiment()
    await service.get_all_teams_sentiment()
    assert news.call_count == 1  # second call hits cache


@pytest.mark.asyncio
async def test_service_team_cache_hit_skips_news_service():
    articles = [
        _article("Brazil wins!", ["BRA"], article_id="a1", url="https://a.com/1"),
    ]
    news = _MockNewsService(articles)
    service = SentimentService(
        news_service=news, analyzer=VaderSentimentAnalyzer(), cache=_InMemoryCache()
    )
    await service.get_team_sentiment("BRA")
    await service.get_team_sentiment("BRA")
    assert news.call_count == 1


@pytest.mark.asyncio
async def test_service_metadata_disclaimer():
    news = _MockNewsService([])
    service = SentimentService(
        news_service=news, analyzer=VaderSentimentAnalyzer(), cache=_InMemoryCache()
    )
    _, meta = await service.get_all_teams_sentiment()
    assert "sampled" in meta.disclaimer.lower()
    assert "vader" in meta.analyzer.lower()


@pytest.mark.asyncio
async def test_service_all_teams_strips_article_list():
    articles = [
        _article("Brazil wins!", ["BRA"], article_id="a1", url="https://a.com/1"),
    ]
    news = _MockNewsService(articles)
    service = SentimentService(
        news_service=news, analyzer=VaderSentimentAnalyzer(), cache=_InMemoryCache()
    )
    teams, _ = await service.get_all_teams_sentiment()
    bra = next(t for t in teams if t.team_code == "BRA")
    assert bra.articles == []


@pytest.mark.asyncio
async def test_service_team_includes_article_list():
    articles = [
        _article("Brazil wins!", ["BRA"], article_id="a1", url="https://a.com/1"),
    ]
    news = _MockNewsService(articles)
    service = SentimentService(
        news_service=news, analyzer=VaderSentimentAnalyzer(), cache=_InMemoryCache()
    )
    team, _ = await service.get_team_sentiment("BRA")
    assert team is not None
    assert len(team.articles) == 1
    assert team.articles[0].title == "Brazil wins!"


@pytest.mark.asyncio
async def test_service_uses_summary_in_analysis():
    negative_summary = "Terrible, crushing, catastrophic defeat and humiliation for the squad"
    article = _article(
        "Match report", ["BRA"], summary=negative_summary,
        article_id="a1", url="https://a.com/1",
    )
    news = _MockNewsService([article])
    service = SentimentService(
        news_service=news, analyzer=VaderSentimentAnalyzer(), cache=_InMemoryCache()
    )
    team, _ = await service.get_team_sentiment("BRA")
    assert team is not None
    assert team.average_score < 0


@pytest.mark.asyncio
async def test_service_constant_analyzer_positive():
    articles = [_article("anything", ["BRA"], article_id="a1", url="https://a.com/1")]
    news = _MockNewsService(articles)
    service = SentimentService(
        news_service=news,
        analyzer=_ConstantAnalyzer(score=0.8, label="positive", confidence=0.8),
        cache=_InMemoryCache(),
    )
    team, _ = await service.get_team_sentiment("BRA")
    assert team is not None
    assert team.label == "positive"
    assert team.average_score == 0.8


@pytest.mark.asyncio
async def test_service_constant_analyzer_negative():
    articles = [_article("anything", ["BRA"], article_id="a1", url="https://a.com/1")]
    news = _MockNewsService(articles)
    service = SentimentService(
        news_service=news,
        analyzer=_ConstantAnalyzer(score=-0.7, label="negative", confidence=0.7),
        cache=_InMemoryCache(),
    )
    team, _ = await service.get_team_sentiment("BRA")
    assert team is not None
    assert team.label == "negative"
    assert team.average_score == -0.7


# ── API endpoint tests ────────────────────────────────────────────────────────

class _MockSentimentService:
    def __init__(self) -> None:
        self._all_result: tuple[list[TeamSentimentRead], SentimentMetadata] = (
            [
                TeamSentimentRead(
                    team_code="BRA",
                    team_name="Brazil",
                    article_count=5,
                    average_score=0.35,
                    label="positive",
                    confidence=0.6,
                ),
                TeamSentimentRead(
                    team_code="FRA",
                    team_name="France",
                    article_count=3,
                    average_score=-0.12,
                    label="negative",
                    confidence=0.37,
                ),
            ],
            SentimentMetadata(
                analyzer="vader-lexicon-v3.3",
                disclaimer=DISCLAIMER,
                sample_size=20,
            ),
        )
        self._team_result: tuple[TeamSentimentRead, SentimentMetadata] = (
            TeamSentimentRead(
                team_code="BRA",
                team_name="Brazil",
                article_count=5,
                average_score=0.35,
                label="positive",
                confidence=0.6,
            ),
            SentimentMetadata(
                analyzer="vader-lexicon-v3.3",
                disclaimer=DISCLAIMER,
                sample_size=5,
            ),
        )

    async def get_all_teams_sentiment(self) -> tuple[list[TeamSentimentRead], SentimentMetadata]:
        return self._all_result

    async def get_team_sentiment(
        self, team_code: str, team_name: str | None = None
    ) -> tuple[TeamSentimentRead, SentimentMetadata]:
        return self._team_result


@pytest_asyncio.fixture
async def sentiment_api_client(db_session):
    from app.database import get_db
    from app.dependencies import get_cache_service

    mock_service = _MockSentimentService()
    fastapi_app.dependency_overrides[_sentiment_service] = lambda: mock_service

    async def _override_db():
        yield db_session

    fastapi_app.dependency_overrides[get_db] = _override_db
    fastapi_app.dependency_overrides[get_cache_service] = lambda: _InMemoryCache()

    async with AsyncClient(transport=ASGITransport(app=fastapi_app), base_url="http://test") as ac:
        yield ac

    fastapi_app.dependency_overrides.pop(_sentiment_service, None)
    fastapi_app.dependency_overrides.pop(get_db, None)
    fastapi_app.dependency_overrides.pop(get_cache_service, None)


@pytest.mark.asyncio
async def test_all_teams_sentiment_200(sentiment_api_client: AsyncClient):
    resp = await sentiment_api_client.get("/api/v1/sentiment")
    assert resp.status_code == 200
    data = resp.json()
    assert "teams" in data
    assert "metadata" in data
    assert len(data["teams"]) == 2


@pytest.mark.asyncio
async def test_all_teams_sentiment_schema(sentiment_api_client: AsyncClient):
    resp = await sentiment_api_client.get("/api/v1/sentiment")
    team = resp.json()["teams"][0]
    assert "team_code" in team
    assert "article_count" in team
    assert "average_score" in team
    assert "label" in team
    assert "confidence" in team


@pytest.mark.asyncio
async def test_all_teams_sentiment_metadata(sentiment_api_client: AsyncClient):
    resp = await sentiment_api_client.get("/api/v1/sentiment")
    meta = resp.json()["metadata"]
    assert "disclaimer" in meta
    assert "analyzer" in meta
    assert "sample_size" in meta


@pytest.mark.asyncio
async def test_team_sentiment_unknown_team_404(sentiment_api_client: AsyncClient):
    resp = await sentiment_api_client.get("/api/v1/teams/99999/sentiment")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_all_sentiment_response_score_range(sentiment_api_client: AsyncClient):
    resp = await sentiment_api_client.get("/api/v1/sentiment")
    for team in resp.json()["teams"]:
        assert -1.0 <= team["average_score"] <= 1.0
        assert 0.0 <= team["confidence"] <= 1.0
        assert team["label"] in ("positive", "neutral", "negative")
