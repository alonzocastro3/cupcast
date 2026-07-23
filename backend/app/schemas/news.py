from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class NewsArticle(BaseModel):
    """
    A single World Cup news article returned by the API.

    Only metadata is included — no full article text.
    related_team_codes contains ISO 3-letter country codes (e.g. "BRA", "FRA")
    detected from the title and summary.
    """

    model_config = ConfigDict(from_attributes=False)

    id: str = Field(..., description="Deterministic ID derived from the article URL")
    title: str
    source: str
    url: str
    published_at: datetime
    image_url: str | None = None
    summary: str | None = None
    related_team_codes: list[str] = Field(default_factory=list)
