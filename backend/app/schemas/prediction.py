from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.enums import PredictedOutcome


class PredictionBase(BaseModel):
    match_id: int
    session_id: str = Field(..., min_length=1, max_length=36)
    predicted_outcome: PredictedOutcome
    predicted_home_score: int | None = Field(None, ge=0)
    predicted_away_score: int | None = Field(None, ge=0)


class PredictionCreate(PredictionBase):
    pass


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
