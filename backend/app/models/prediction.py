from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.enums import PredictedOutcome


class Prediction(Base):
    __tablename__ = "predictions"
    __table_args__ = (
        UniqueConstraint("match_id", "session_id", name="uq_prediction_match_session"),
        Index("ix_predictions_match_id", "match_id"),
        Index("ix_predictions_session_id", "session_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    match_id: Mapped[int] = mapped_column(Integer, ForeignKey("matches.id"), nullable=False)
    session_id: Mapped[str] = mapped_column(String(36), nullable=False)
    predicted_outcome: Mapped[PredictedOutcome] = mapped_column(
        Enum(PredictedOutcome, name="predictedoutcome", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    predicted_home_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    predicted_away_score: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    match: Mapped[Match] = relationship("Match", back_populates="predictions")
