from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import PredictedOutcome
from app.models.prediction import Prediction


class PredictionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_summary_counts(self, match_id: int) -> dict[str, int]:
        """Return aggregate counts for a match using PostgreSQL FILTER clause."""
        result = await self.session.execute(
            select(
                func.count(Prediction.id).label("total"),
                func.count(Prediction.id)
                .filter(Prediction.predicted_outcome == PredictedOutcome.HOME_WIN)
                .label("home_win_count"),
                func.count(Prediction.id)
                .filter(Prediction.predicted_outcome == PredictedOutcome.DRAW)
                .label("draw_count"),
                func.count(Prediction.id)
                .filter(Prediction.predicted_outcome == PredictedOutcome.AWAY_WIN)
                .label("away_win_count"),
            ).where(Prediction.match_id == match_id)
        )
        row = result.one()
        return {
            "total": row.total,
            "home_win_count": row.home_win_count,
            "draw_count": row.draw_count,
            "away_win_count": row.away_win_count,
        }
