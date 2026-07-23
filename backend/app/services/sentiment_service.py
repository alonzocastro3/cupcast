"""
Sentiment aggregation service.

Pipeline:
  1. Fetch cached news articles from NewsService (already Redis-cached)
  2. Run synchronous VADER analysis on title + summary (if present)
  3. Group by team code (from article.related_team_codes)
  4. Compute per-team aggregates (mean score, label, confidence)
  5. Cache aggregates

Confidence formula per team:
  coverage = article_count / (article_count + SMOOTHING)   # ramps 0→1 with data
  signal   = mean(abs(score_i))                            # how non-neutral articles are
  confidence = coverage * 0.6 + signal * 0.4

This blends "do we have enough data?" with "is the data decisive?"
"""
from __future__ import annotations

import logging

from app.schemas.news import NewsArticle
from app.schemas.sentiment import (
    DISCLAIMER,
    ArticleSentimentRead,
    SentimentMetadata,
    TeamSentimentRead,
)
from app.services.cache import (
    CacheService,
    TTL_SENTIMENT,
    key_sentiment_all,
    key_sentiment_team,
)
from app.services.news_service import NewsService
from app.services.sentiment.base import SentimentAnalyzer, SentimentLabel

logger = logging.getLogger(__name__)

_ANALYZER_ID = "vader-lexicon-v3.3"
_SMOOTHING = 5  # half-confidence at 5 articles


def _label(score: float) -> SentimentLabel:
    if score >= 0.05:
        return "positive"
    if score <= -0.05:
        return "negative"
    return "neutral"


def _aggregate_confidence(article_count: int, scores: list[float]) -> float:
    if article_count == 0:
        return 0.0
    coverage = article_count / (article_count + _SMOOTHING)
    signal = sum(abs(s) for s in scores) / article_count
    return round(coverage * 0.6 + signal * 0.4, 4)


def _build_team_sentiment(
    team_code: str,
    scored: list[ArticleSentimentRead],
    team_name: str | None = None,
) -> TeamSentimentRead:
    count = len(scored)
    if count == 0:
        return TeamSentimentRead(
            team_code=team_code,
            team_name=team_name,
            article_count=0,
            average_score=0.0,
            label="neutral",
            confidence=0.0,
        )
    scores = [a.score for a in scored]
    avg = round(sum(scores) / count, 4)
    return TeamSentimentRead(
        team_code=team_code,
        team_name=team_name,
        article_count=count,
        average_score=avg,
        label=_label(avg),
        confidence=_aggregate_confidence(count, scores),
        articles=scored,
    )


class SentimentService:
    """
    Wraps NewsService + SentimentAnalyzer to produce team-level sentiment aggregates.
    All results are Redis-cached to avoid re-analyzing on every request.
    """

    def __init__(
        self,
        news_service: NewsService,
        analyzer: SentimentAnalyzer,
        cache: CacheService,
    ) -> None:
        self._news = news_service
        self._analyzer = analyzer
        self._cache = cache

    def _score_article(self, article: NewsArticle) -> ArticleSentimentRead:
        text = article.title
        if article.summary:
            text = f"{article.title}. {article.summary}"
        result = self._analyzer.analyze(text)
        return ArticleSentimentRead(
            article_id=article.id,
            title=article.title,
            score=result.score,
            label=result.label,
            confidence=result.confidence,
        )

    async def get_all_teams_sentiment(self) -> tuple[list[TeamSentimentRead], SentimentMetadata]:
        cache_key = key_sentiment_all()
        cached = await self._cache.get(cache_key)
        if cached is not None:
            teams = [TeamSentimentRead.model_validate(t) for t in cached["teams"]]
            meta = SentimentMetadata.model_validate(cached["metadata"])
            return teams, meta

        articles, _ = await self._news.get_news(limit=100, offset=0)
        team_buckets: dict[str, list[ArticleSentimentRead]] = {}
        for article in articles:
            scored = self._score_article(article)
            for code in article.related_team_codes:
                team_buckets.setdefault(code, []).append(scored)

        teams = [
            _build_team_sentiment(code, scored)
            for code, scored in sorted(team_buckets.items())
        ]
        # Strip article lists for the all-teams response to keep payload small
        teams_slim = [t.model_copy(update={"articles": []}) for t in teams]
        meta = SentimentMetadata(
            analyzer=_ANALYZER_ID,
            disclaimer=DISCLAIMER,
            sample_size=len(articles),
        )
        await self._cache.set(
            cache_key,
            {
                "teams": [t.model_dump(mode="json") for t in teams_slim],
                "metadata": meta.model_dump(mode="json"),
            },
            TTL_SENTIMENT,
        )
        return teams_slim, meta

    async def get_team_sentiment(
        self,
        team_code: str,
        team_name: str | None = None,
    ) -> tuple[TeamSentimentRead | None, SentimentMetadata]:
        code = team_code.upper()
        cache_key = key_sentiment_team(code)
        cached = await self._cache.get(cache_key)
        if cached is not None:
            team = TeamSentimentRead.model_validate(cached["team"])
            meta = SentimentMetadata.model_validate(cached["metadata"])
            return team, meta

        articles, _ = await self._news.get_news(team_codes=[code], limit=100, offset=0)
        meta = SentimentMetadata(
            analyzer=_ANALYZER_ID,
            disclaimer=DISCLAIMER,
            sample_size=len(articles),
        )
        if not articles:
            return None, meta

        scored = [self._score_article(a) for a in articles]
        team_sentiment = _build_team_sentiment(code, scored, team_name=team_name)
        await self._cache.set(
            cache_key,
            {
                "team": team_sentiment.model_dump(mode="json"),
                "metadata": meta.model_dump(mode="json"),
            },
            TTL_SENTIMENT,
        )
        return team_sentiment, meta
