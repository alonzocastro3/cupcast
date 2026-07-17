from __future__ import annotations

from app.repositories.team import TeamRepository
from app.schemas.team import TeamRead
from app.services.cache import (
    CacheService,
    TTL_TEAMS,
    key_team,
    key_team_list,
)


class TeamService:
    def __init__(self, repo: TeamRepository, cache: CacheService | None = None) -> None:
        self.repo = repo
        self._cache = cache

    async def list_teams(self, limit: int, offset: int) -> tuple[list, int]:
        key = key_team_list(limit, offset)

        if self._cache:
            cached = await self._cache.get(key)
            if cached is not None:
                return [TeamRead.model_validate(t) for t in cached["items"]], cached["total"]

        teams = await self.repo.list(limit, offset)
        total = await self.repo.count()

        if self._cache:
            await self._cache.set(
                key,
                {
                    "items": [
                        TeamRead.model_validate(t, from_attributes=True).model_dump(mode="json")
                        for t in teams
                    ],
                    "total": total,
                },
                TTL_TEAMS,
            )

        return teams, total

    async def get_team(self, team_id: int) -> TeamRead | None:
        key = key_team(team_id)

        if self._cache:
            cached = await self._cache.get(key)
            if cached is not None:
                return TeamRead.model_validate(cached)

        team = await self.repo.get(team_id)
        if team is None:
            return None

        if self._cache:
            await self._cache.set(
                key,
                TeamRead.model_validate(team, from_attributes=True).model_dump(mode="json"),
                TTL_TEAMS,
            )

        return team  # type: ignore[return-value]
