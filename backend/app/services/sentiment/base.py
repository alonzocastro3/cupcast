"""Abstract sentiment analyzer interface."""
from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import Literal

SentimentLabel = Literal["positive", "neutral", "negative"]


@dataclass(frozen=True)
class SentimentResult:
    score: float        # -1.0 to 1.0 (VADER compound)
    label: SentimentLabel
    confidence: float   # 0.0 to 1.0 — abs(score), how strongly the text signals sentiment


class SentimentAnalyzer(abc.ABC):
    """
    Synchronous text sentiment classifier.

    Implementations must not block the event loop — analysis runs on short
    text only (headlines + brief summaries).
    """

    @abc.abstractmethod
    def analyze(self, text: str) -> SentimentResult:
        """Return sentiment for *text*."""
