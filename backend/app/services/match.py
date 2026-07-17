from __future__ import annotations

from app.enums import MatchStatus
from app.models.match import Match
from app.repositories.match import MatchRepository


class MatchService:
    def __init__(self, repo: MatchRepository) -> None:
        self.repo = repo

    async def list_matches(
        self,
        limit: int,
        offset: int,
        status: MatchStatus | None = None,
        stage: str | None = None,
        team_id: int | None = None,
    ) -> tuple[list[Match], int]:
        matches = await self.repo.list(limit, offset, status, stage, team_id)
        total = await self.repo.count(status, stage, team_id)
        return matches, total

    async def get_match(self, match_id: int) -> Match | None:
        return await self.repo.get(match_id)
