"""Deterministic scoring model: team features → win/draw/away probabilities."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.enums import PredictedOutcome
from app.prediction_engine.features import TeamFeatures, extract

if TYPE_CHECKING:
    from app.models.team import Team

MODEL_VERSION = "1.0.0"

# Feature weights — intentionally readable and easy to tune.
_W_ATTACKING = 0.25
_W_DEFENSIVE = 0.20
_W_RANKING   = 0.20
_W_ELO       = 0.25
_W_FORM      = 0.05
_W_WIN_RATE  = 0.05

# Draw baseline: added symmetrically before normalization.
_DRAW_BASE = 0.30

# Home advantage bonus applied to the raw home score.
_HOME_ADVANTAGE = 0.05


@dataclass(frozen=True)
class PredictionResult:
    home_win_probability: float
    draw_probability: float
    away_win_probability: float
    predicted_outcome: PredictedOutcome
    confidence: float
    home_features: TeamFeatures
    away_features: TeamFeatures


def _team_score(f: TeamFeatures) -> float:
    return (
        _W_ATTACKING * f.attacking
        + _W_DEFENSIVE * f.defensive
        + _W_RANKING * f.ranking
        + _W_ELO * f.elo
        + _W_FORM * f.form
        + _W_WIN_RATE * f.win_rate
    )


def _softmax(values: list[float]) -> list[float]:
    exps = [math.exp(v) for v in values]
    total = sum(exps)
    return [e / total for e in exps]


def predict(home: Team, away: Team) -> PredictionResult:
    hf = extract(home)
    af = extract(away)

    home_score = _team_score(hf) + _HOME_ADVANTAGE
    away_score = _team_score(af)
    draw_score = _DRAW_BASE * (home_score + away_score) / 2

    home_p, draw_p, away_p = _softmax([home_score, draw_score, away_score])

    # Clamp to [0.01, 0.98] so extreme inputs never produce 0 or 1.
    def _clamp(x: float) -> float:
        return max(0.01, min(0.98, x))

    home_p = _clamp(home_p)
    draw_p = _clamp(draw_p)
    away_p = _clamp(away_p)

    # Re-normalize after clamping.
    total = home_p + draw_p + away_p
    home_p /= total
    draw_p /= total
    away_p /= total

    # Round to 4dp for clean output while preserving sum ≈ 1.
    home_p = round(home_p, 4)
    draw_p = round(draw_p, 4)
    away_p = round(1.0 - home_p - draw_p, 4)  # ensures exact sum

    max_p = max(home_p, draw_p, away_p)
    if max_p == home_p:
        outcome = PredictedOutcome.HOME_WIN
    elif max_p == away_p:
        outcome = PredictedOutcome.AWAY_WIN
    else:
        outcome = PredictedOutcome.DRAW

    # Confidence: how far the leading probability is above uniform (0.333).
    confidence = round(min(1.0, (max_p - 1 / 3) / (2 / 3)), 4)

    return PredictionResult(
        home_win_probability=home_p,
        draw_probability=draw_p,
        away_win_probability=away_p,
        predicted_outcome=outcome,
        confidence=confidence,
        home_features=hf,
        away_features=af,
    )


class ModelPredictor:
    """Thin callable wrapper — makes it easy to swap the underlying logic."""

    version: str = MODEL_VERSION

    def predict(self, home: Team, away: Team) -> PredictionResult:
        return predict(home, away)
