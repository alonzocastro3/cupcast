from __future__ import annotations

from app.enums import MatchStatus
from app.repositories.match import MatchRepository
from app.schemas.match import MatchRead
from app.services.cache import (
    CacheService,
    TTL_MATCHES,
    key_match,
    key_match_list,
)


class MatchService:
    def __init__(self, repo: MatchRepository, cache: CacheService | None = None) -> None:
        self.repo = repo
        self._cache = cache

    async def list_matches(
        self,
        limit: int,
        offset: int,
        status: MatchStatus | None = None,
        stage: str | None = None,
        team_id: int | None = None,
    ) -> tuple[list, int]:
        key = key_match_list(limit, offset, status, stage, team_id)

        if self._cache:
            cached = await self._cache.get(key)
            if cached is not None:
                return [MatchRead.model_validate(m) for m in cached["items"]], cached["total"]

        matches = await self.repo.list(limit, offset, status, stage, team_id)
        total = await self.repo.count(status, stage, team_id)

        if self._cache:
            await self._cache.set(
                key,
                {
                    "items": [
                        MatchRead.model_validate(m, from_attributes=True).model_dump(mode="json")
                        for m in matches
                    ],
                    "total": total,
                },
                TTL_MATCHES,
            )

        return matches, total

    async def get_match(self, match_id: int) -> MatchRead | None:
        key = key_match(match_id)

        if self._cache:
            cached = await self._cache.get(key)
            if cached is not None:
                return MatchRead.model_validate(cached)

        match = await self.repo.get(match_id)
        if match is None:
            return None

        if self._cache:
            await self._cache.set(
                key,
                MatchRead.model_validate(match, from_attributes=True).model_dump(mode="json"),
                TTL_MATCHES,
            )

        return match  # type: ignore[return-value]
