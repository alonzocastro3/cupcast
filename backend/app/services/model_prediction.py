from __future__ import annotations

from app.prediction_engine.explanations import build_explanation
from app.prediction_engine.model import MODEL_VERSION, ModelPredictor
from app.repositories.match import MatchRepository
from app.schemas.prediction import ModelPrediction
from app.services.cache import (
    CacheService,
    TTL_MODEL_PREDICTION,
    key_model_prediction,
)

_predictor = ModelPredictor()


class ModelPredictionService:
    def __init__(
        self, match_repo: MatchRepository, cache: CacheService | None = None
    ) -> None:
        self.match_repo = match_repo
        self._cache = cache

    async def get_model_prediction(self, match_id: int) -> ModelPrediction | None:
        key = key_model_prediction(match_id)

        if self._cache:
            cached = await self._cache.get(key)
            if cached is not None:
                return ModelPrediction.model_validate(cached)

        match = await self.match_repo.get_with_teams(match_id)
        if match is None:
            return None

        result = _predictor.predict(match.home_team, match.away_team)
        explanation = build_explanation(match.home_team.name, match.away_team.name, result)

        prediction = ModelPrediction(
            match_id=match_id,
            home_team=match.home_team,  # type: ignore[arg-type]
            away_team=match.away_team,  # type: ignore[arg-type]
            home_win_probability=result.home_win_probability,
            draw_probability=result.draw_probability,
            away_win_probability=result.away_win_probability,
            predicted_outcome=result.predicted_outcome,
            confidence=result.confidence,
            explanation=explanation,
            model_version=MODEL_VERSION,
        )

        if self._cache:
            await self._cache.set(
                key,
                prediction.model_dump(mode="json"),
                TTL_MODEL_PREDICTION,
            )

        return prediction
