from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TeamBase(BaseModel):
    name: str = Field(..., max_length=100)
    country_code: str = Field(..., min_length=2, max_length=3)
    group_name: str = Field(..., max_length=10)
    flag_url: str | None = None
    fifa_ranking: int = Field(..., ge=1)
    elo_rating: int = Field(..., ge=0)
    recent_form_score: float = 0.0
    goals_for: int = 0
    goals_against: int = 0
    wins: int = 0
    draws: int = 0
    losses: int = 0
    extra_stats: dict[str, Any] | None = None


class TeamCreate(TeamBase):
    pass


class TeamRead(TeamBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
