"""
GET /api/v1/sentiment                  — all-teams news sentiment aggregate
GET /api/v1/teams/{team_id}/sentiment  — single-team sentiment with per-article breakdown
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.config import settings
from app.dependencies import CacheDep, SessionDep
from app.integrations.news.provider import NewsApiOrgProvider
from app.repositories.team import TeamRepository
from app.schemas.sentiment import (
    AllSentimentResponse,
    TeamSentimentRead,
    TeamSentimentResponse,
)
from app.services.news_service import NewsService
from app.services.sentiment.vader import VaderSentimentAnalyzer
from app.services.sentiment_service import SentimentService

router = APIRouter(tags=["sentiment"])

_ANALYZER = VaderSentimentAnalyzer()  # module-level singleton; stateless


def _sentiment_service(cache: CacheDep) -> SentimentService:
    provider = NewsApiOrgProvider(
        api_key=settings.news_api_key or "",
        base_url=settings.news_api_base_url,
        timeout=settings.news_api_timeout,
        max_retries=settings.news_api_max_retries,
    )
    news_service = NewsService(provider=provider, cache=cache, query=settings.news_query)
    return SentimentService(news_service=news_service, analyzer=_ANALYZER, cache=cache)


SentimentServiceDep = Annotated[SentimentService, Depends(_sentiment_service)]


@router.get("/api/v1/sentiment", response_model=AllSentimentResponse)
async def all_teams_sentiment(service: SentimentServiceDep) -> AllSentimentResponse:
    teams, meta = await service.get_all_teams_sentiment()
    return AllSentimentResponse(metadata=meta, teams=teams)


@router.get("/api/v1/teams/{team_id}/sentiment", response_model=TeamSentimentResponse)
async def team_sentiment(
    team_id: int,
    session: SessionDep,
    service: SentimentServiceDep,
) -> TeamSentimentResponse:
    team_row = await TeamRepository(session).get(team_id)
    if team_row is None:
        raise HTTPException(status_code=404, detail=f"Team {team_id} not found")

    result, meta = await service.get_team_sentiment(
        team_code=team_row.country_code,
        team_name=team_row.name,
    )
    if result is None:
        result = TeamSentimentRead(
            team_code=team_row.country_code,
            team_name=team_row.name,
            article_count=0,
            average_score=0.0,
            label="neutral",
            confidence=0.0,
        )
    return TeamSentimentResponse(metadata=meta, team=result)
