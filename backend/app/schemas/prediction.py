from __future__ import annotations

from datetime import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.enums import PredictedOutcome
from app.schemas.team import TeamRead


class PredictionBase(BaseModel):
    match_id: int
    session_id: str = Field(..., min_length=1, max_length=36)
    predicted_outcome: PredictedOutcome
    predicted_home_score: int | None = Field(None, ge=0)
    predicted_away_score: int | None = Field(None, ge=0)


class PredictionRead(PredictionBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


class PredictionSummary(BaseModel):
    match_id: int
    total_predictions: int
    home_win_count: int
    draw_count: int
    away_win_count: int
    home_win_percentage: float
    draw_percentage: float
    away_win_percentage: float


class PredictionSubmitRequest(BaseModel):
    """Request body for POST /matches/{match_id}/predictions."""

    session_id: str = Field(..., min_length=1, max_length=36)
    predicted_outcome: PredictedOutcome
    predicted_home_score: int | None = Field(None, ge=0)
    predicted_away_score: int | None = Field(None, ge=0)

    @model_validator(mode="after")
    def scores_match_outcome(self) -> Self:
        home = self.predicted_home_score
        away = self.predicted_away_score

        if (home is None) != (away is None):
            raise ValueError(
                "Provide both predicted_home_score and predicted_away_score, or neither"
            )

        if home is not None and away is not None:
            outcome = self.predicted_outcome
            if home > away and outcome != PredictedOutcome.HOME_WIN:
                raise ValueError("Scores indicate home_win but predicted_outcome differs")
            if home < away and outcome != PredictedOutcome.AWAY_WIN:
                raise ValueError("Scores indicate away_win but predicted_outcome differs")
            if home == away and outcome != PredictedOutcome.DRAW:
                raise ValueError("Scores indicate draw but predicted_outcome differs")

        return self


class PredictionSubmitResponse(BaseModel):
    """Response envelope for a successful prediction submission."""

    prediction: PredictionRead
    community_summary: PredictionSummary


class ModelPrediction(BaseModel):
    match_id: int
    home_team: TeamRead
    away_team: TeamRead
    home_win_probability: float
    draw_probability: float
    away_win_probability: float
    predicted_outcome: PredictedOutcome
    confidence: float = Field(..., ge=0.0, le=1.0)
    explanation: str
    model_version: str
