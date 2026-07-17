from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel

from app.schemas.match import MatchCreate, MatchRead
from app.schemas.prediction import PredictionRead, PredictionSummary
from app.schemas.team import TeamCreate, TeamRead

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """Generic paginated response envelope."""

    items: list[T]
    total: int
    limit: int
    offset: int


__all__ = [
    "Page",
    "TeamCreate",
    "TeamRead",
    "MatchCreate",
    "MatchRead",
    "PredictionRead",
    "PredictionSummary",
]
