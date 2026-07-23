"""VADER-based sentiment analyzer — deterministic, no network required."""
from __future__ import annotations

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from .base import SentimentAnalyzer, SentimentLabel, SentimentResult

_POS_THRESHOLD = 0.05
_NEG_THRESHOLD = -0.05


class VaderSentimentAnalyzer(SentimentAnalyzer):
    """
    Rule-based sentiment via VADER lexicon.

    Designed for short informal text (headlines, social snippets).
    No network calls, no model weights to download, fully deterministic.
    """

    def __init__(self) -> None:
        self._sia = SentimentIntensityAnalyzer()

    def analyze(self, text: str) -> SentimentResult:
        if not text or not text.strip():
            return SentimentResult(score=0.0, label="neutral", confidence=0.0)
        scores = self._sia.polarity_scores(text.strip())
        compound: float = scores["compound"]
        if compound >= _POS_THRESHOLD:
            label: SentimentLabel = "positive"
        elif compound <= _NEG_THRESHOLD:
            label = "negative"
        else:
            label = "neutral"
        return SentimentResult(
            score=round(compound, 4),
            label=label,
            confidence=round(abs(compound), 4),
        )
