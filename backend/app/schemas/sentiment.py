from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

DISCLAIMER = (
    "Scores reflect sentiment in sampled news headlines and summaries only. "
    "They do not represent fan opinion, general public sentiment, or the broader internet. "
    "Analysis uses a deterministic lexicon model (VADER) applied to recent articles fetched from NewsAPI."
)


class ArticleSentimentRead(BaseModel):
    model_config = ConfigDict(from_attributes=False)

    article_id: str
    title: str
    score: float = Field(
        ..., ge=-1.0, le=1.0,
        description="Compound sentiment score (-1 most negative, 1 most positive)",
    )
    label: str = Field(..., description="positive | neutral | negative")
    confidence: float = Field(
        ..., ge=0.0, le=1.0,
        description="How strongly the text signals a non-neutral sentiment",
    )


class TeamSentimentRead(BaseModel):
    model_config = ConfigDict(from_attributes=False)

    team_code: str
    team_name: str | None = None
    article_count: int
    average_score: float = Field(..., ge=-1.0, le=1.0)
    label: str
    confidence: float = Field(
        ..., ge=0.0, le=1.0,
        description="Blend of article-count coverage and signal clarity",
    )
    articles: list[ArticleSentimentRead] = Field(default_factory=list)


class SentimentMetadata(BaseModel):
    model_config = ConfigDict(from_attributes=False)

    analyzer: str = Field(..., description="Analyzer identifier")
    disclaimer: str = Field(..., description="Scope limitation warning")
    sample_size: int = Field(..., description="Number of articles analyzed")


class AllSentimentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=False)

    metadata: SentimentMetadata
    teams: list[TeamSentimentRead]


class TeamSentimentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=False)

    metadata: SentimentMetadata
    team: TeamSentimentRead
