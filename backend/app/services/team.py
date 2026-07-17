from __future__ import annotations

from app.models.team import Team
from app.repositories.team import TeamRepository


class TeamService:
    def __init__(self, repo: TeamRepository) -> None:
        self.repo = repo

    async def list_teams(self, limit: int, offset: int) -> tuple[list[Team], int]:
        teams = await self.repo.list(limit, offset)
        total = await self.repo.count()
        return teams, total

    async def get_team(self, team_id: int) -> Team | None:
        return await self.repo.get(team_id)
