from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.team import Team


class TeamRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(self, limit: int, offset: int) -> list[Team]:
        rows = await self.session.execute(
            select(Team).order_by(Team.id).limit(limit).offset(offset)
        )
        return list(rows.scalars().all())

    async def count(self) -> int:
        result = await self.session.execute(select(func.count(Team.id)))
        return result.scalar_one()

    async def get(self, team_id: int) -> Team | None:
        result = await self.session.execute(select(Team).where(Team.id == team_id))
        return result.scalar_one_or_none()
