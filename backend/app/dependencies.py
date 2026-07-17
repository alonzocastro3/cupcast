from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache import redis_client
from app.database import get_db
from app.services.cache import CacheService

# ── Session ───────────────────────────────────────────────────────────────────

SessionDep = Annotated[AsyncSession, Depends(get_db)]


# ── Cache ─────────────────────────────────────────────────────────────────────

def get_cache_service() -> CacheService:
    return CacheService(redis_client)


CacheDep = Annotated[CacheService, Depends(get_cache_service)]


# ── Pagination ────────────────────────────────────────────────────────────────

class Pagination:
    def __init__(
        self,
        limit: int = Query(default=20, ge=1, le=100, description="Number of items to return (max 100)"),
        offset: int = Query(default=0, ge=0, description="Number of items to skip"),
    ) -> None:
        self.limit = limit
        self.offset = offset


PaginationDep = Annotated[Pagination, Depends(Pagination)]
