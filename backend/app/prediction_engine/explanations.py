"""Human-readable explanations for model predictions."""

from __future__ import annotations

from app.prediction_engine.model import PredictionResult


def build_explanation(home_name: str, away_name: str, result: PredictionResult) -> str:
    hf = result.home_features
    af = result.away_features
    factors: list[str] = []

    elo_diff = hf.elo - af.elo
    if abs(elo_diff) >= 0.10:
        stronger = home_name if elo_diff > 0 else away_name
        factors.append(f"{stronger} holds a significant Elo rating advantage")

    ranking_diff = hf.ranking - af.ranking
    if abs(ranking_diff) >= 0.10:
        higher = home_name if ranking_diff > 0 else away_name
        factors.append(f"{higher} is ranked considerably higher by FIFA")

    form_diff = hf.form - af.form
    if abs(form_diff) >= 0.20:
        in_form = home_name if form_diff > 0 else away_name
        factors.append(f"{in_form} is in stronger recent form")

    attacking_diff = hf.attacking - af.attacking
    if abs(attacking_diff) >= 0.15:
        sharper = home_name if attacking_diff > 0 else away_name
        factors.append(f"{sharper} has the better attacking output")

    defensive_diff = hf.defensive - af.defensive
    if abs(defensive_diff) >= 0.15:
        sturdier = home_name if defensive_diff > 0 else away_name
        factors.append(f"{sturdier} has the more solid defensive record")

    win_rate_diff = hf.win_rate - af.win_rate
    if abs(win_rate_diff) >= 0.15:
        more_consistent = home_name if win_rate_diff > 0 else away_name
        factors.append(f"{more_consistent} has a notably higher win rate")

    if not factors:
        return (
            f"{home_name} and {away_name} are evenly matched across all metrics; "
            "home advantage gives a slight edge to the hosts."
        )

    factor_text = "; ".join(factors)
    return f"Key factors: {factor_text}."
