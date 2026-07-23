from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.config import settings
from app.dependencies import CacheDep, PaginationDep
from app.integrations.news.provider import NewsApiOrgProvider
from app.schemas import Page
from app.schemas.news import NewsArticle
from app.services.news_service import NewsService

router = APIRouter(prefix="/api/v1/news", tags=["news"])


def _news_service(cache: CacheDep) -> NewsService:
    provider = NewsApiOrgProvider(
        api_key=settings.news_api_key or "",
        base_url=settings.news_api_base_url,
        timeout=settings.news_api_timeout,
        max_retries=settings.news_api_max_retries,
    )
    return NewsService(provider=provider, cache=cache, query=settings.news_query)


NewsServiceDep = Annotated[NewsService, Depends(_news_service)]


@router.get("", response_model=Page[NewsArticle])
async def list_news(
    pagination: PaginationDep,
    service: NewsServiceDep,
    team_codes: list[str] | None = Query(
        None,
        description="Filter by ISO 3-letter country codes (e.g. BRA, FRA). Multiple values OR-matched.",
    ),
) -> dict:
    articles, total = await service.get_news(
        team_codes=team_codes,
        limit=pagination.limit,
        offset=pagination.offset,
    )
    return {
        "items": articles,
        "total": total,
        "limit": pagination.limit,
        "offset": pagination.offset,
    }
