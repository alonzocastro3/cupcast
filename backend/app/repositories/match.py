from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.enums import MatchStatus
from app.models.match import Match


class MatchRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ── Internal filter builder ───────────────────────────────────────────────

    @staticmethod
    def _filters(
        status: MatchStatus | None,
        stage: str | None,
        team_id: int | None,
    ) -> list:
        conditions: list = []
        if status is not None:
            conditions.append(Match.status == status)
        if stage is not None:
            conditions.append(Match.stage == stage)
        if team_id is not None:
            conditions.append(
                or_(Match.home_team_id == team_id, Match.away_team_id == team_id)
            )
        return conditions

    # ── Public methods ────────────────────────────────────────────────────────

    async def list(
        self,
        limit: int,
        offset: int,
        status: MatchStatus | None = None,
        stage: str | None = None,
        team_id: int | None = None,
    ) -> list[Match]:
        conditions = self._filters(status, stage, team_id)
        q = (
            select(Match)
            .where(*conditions)
            .order_by(Match.kickoff_at)
            .limit(limit)
            .offset(offset)
        )
        rows = await self.session.execute(q)
        return list(rows.scalars().all())

    async def count(
        self,
        status: MatchStatus | None = None,
        stage: str | None = None,
        team_id: int | None = None,
    ) -> int:
        conditions = self._filters(status, stage, team_id)
        q = select(func.count(Match.id)).where(*conditions)
        result = await self.session.execute(q)
        return result.scalar_one()

    async def get(self, match_id: int) -> Match | None:
        result = await self.session.execute(select(Match).where(Match.id == match_id))
        return result.scalar_one_or_none()

    async def get_with_teams(self, match_id: int) -> Match | None:
        result = await self.session.execute(
            select(Match)
            .where(Match.id == match_id)
            .options(selectinload(Match.home_team), selectinload(Match.away_team))
        )
        return result.scalar_one_or_none()
