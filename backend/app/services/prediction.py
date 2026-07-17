from __future__ import annotations

from app.repositories.match import MatchRepository
from app.repositories.prediction import PredictionRepository
from app.schemas.prediction import PredictionSummary


class PredictionService:
    def __init__(
        self,
        match_repo: MatchRepository,
        prediction_repo: PredictionRepository,
    ) -> None:
        self.match_repo = match_repo
        self.prediction_repo = prediction_repo

    async def get_summary(self, match_id: int) -> PredictionSummary | None:
        """Return None when the match does not exist."""
        match = await self.match_repo.get(match_id)
        if match is None:
            return None

        counts = await self.prediction_repo.get_summary_counts(match_id)
        total = counts["total"]
        home_win_count = counts["home_win_count"]
        draw_count = counts["draw_count"]
        away_win_count = counts["away_win_count"]

        if total == 0:
            return PredictionSummary(
                match_id=match_id,
                total_predictions=0,
                home_win_count=0,
                draw_count=0,
                away_win_count=0,
                home_win_percentage=0.0,
                draw_percentage=0.0,
                away_win_percentage=0.0,
            )

        return PredictionSummary(
            match_id=match_id,
            total_predictions=total,
            home_win_count=home_win_count,
            draw_count=draw_count,
            away_win_count=away_win_count,
            home_win_percentage=round(home_win_count / total * 100, 2),
            draw_percentage=round(draw_count / total * 100, 2),
            away_win_percentage=round(away_win_count / total * 100, 2),
        )
