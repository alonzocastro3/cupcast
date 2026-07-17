from __future__ import annotations

from app.models.prediction import Prediction
from app.repositories.match import MatchRepository
from app.repositories.prediction import PredictionRepository
from app.schemas.prediction import (
    PredictionSubmitRequest,
    PredictionSubmitResponse,
    PredictionSummary,
)
from app.services.cache import (
    CacheService,
    TTL_PREDICTION_SUMMARY,
    key_prediction_summary,
)


class MatchNotFoundError(Exception):
    pass


class DuplicatePredictionError(Exception):
    pass


class PredictionService:
    def __init__(
        self,
        match_repo: MatchRepository,
        prediction_repo: PredictionRepository,
        cache: CacheService | None = None,
    ) -> None:
        self.match_repo = match_repo
        self.prediction_repo = prediction_repo
        self._cache = cache

    async def get_summary(self, match_id: int) -> PredictionSummary | None:
        """Return None when the match does not exist."""
        match = await self.match_repo.get(match_id)
        if match is None:
            return None

        key = key_prediction_summary(match_id)

        if self._cache:
            cached = await self._cache.get(key)
            if cached is not None:
                return PredictionSummary.model_validate(cached)

        summary = await self._build_summary(match_id)

        if self._cache:
            await self._cache.set(key, summary.model_dump(mode="json"), TTL_PREDICTION_SUMMARY)

        return summary

    async def submit_prediction(
        self, match_id: int, data: PredictionSubmitRequest
    ) -> PredictionSubmitResponse:
        """
        Create a prediction for a match.
        Raises MatchNotFoundError if match is absent.
        Raises DuplicatePredictionError if (match_id, session_id) already exists.
        """
        match = await self.match_repo.get(match_id)
        if match is None:
            raise MatchNotFoundError(match_id)

        if await self.prediction_repo.exists(match_id, data.session_id):
            raise DuplicatePredictionError(match_id, data.session_id)

        prediction = Prediction(
            match_id=match_id,
            session_id=data.session_id,
            predicted_outcome=data.predicted_outcome,
            predicted_home_score=data.predicted_home_score,
            predicted_away_score=data.predicted_away_score,
        )
        created = await self.prediction_repo.create(prediction)

        # Invalidate stale summary so the next GET reflects the new prediction.
        if self._cache:
            await self._cache.delete(key_prediction_summary(match_id))

        summary = await self._build_summary(match_id)

        return PredictionSubmitResponse(prediction=created, community_summary=summary)  # type: ignore[arg-type]

    # ── Internal ──────────────────────────────────────────────────────────────

    async def _build_summary(self, match_id: int) -> PredictionSummary:
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
