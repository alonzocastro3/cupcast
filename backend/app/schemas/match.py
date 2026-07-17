from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.enums import MatchStatus


class MatchBase(BaseModel):
    external_id: str | None = None
    home_team_id: int
    away_team_id: int
    kickoff_at: datetime
    status: MatchStatus = MatchStatus.SCHEDULED
    stage: str = Field(..., max_length=50)
    venue: str | None = Field(None, max_length=200)
    home_score: int | None = Field(None, ge=0)
    away_score: int | None = Field(None, ge=0)

    @model_validator(mode="after")
    def teams_must_differ(self) -> MatchBase:
        if self.home_team_id == self.away_team_id:
            raise ValueError("home_team_id and away_team_id must be different")
        return self


class MatchCreate(MatchBase):
    pass


class MatchRead(MatchBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
