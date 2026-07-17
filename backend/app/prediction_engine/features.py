"""Feature extraction and normalization from Team ORM objects."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.team import Team


@dataclass(frozen=True)
class TeamFeatures:
    attacking: float   # goals_for / (goals_for + goals_against), default 0.5
    defensive: float   # 1 - goals_against / (goals_for + goals_against), default 0.5
    ranking: float     # normalized FIFA ranking (lower rank → higher score)
    elo: float         # normalized Elo (sigmoid-scaled around 1500)
    form: float        # recent_form_score clamped to [0, 1]
    win_rate: float    # wins / (wins + draws + losses), default 0


def extract(team: Team) -> TeamFeatures:
    total_goals = team.goals_for + team.goals_against
    if total_goals > 0:
        attacking = team.goals_for / total_goals
        defensive = 1.0 - team.goals_against / total_goals
    else:
        attacking = 0.5
        defensive = 0.5

    # FIFA ranking: rank 1 → 1.0, rank 200 → ~0. Use inverse log scaling.
    ranking = max(0.0, 1.0 - math.log(max(team.fifa_ranking, 1)) / math.log(210))

    # Elo: sigmoid centered at 1500, range roughly [800, 2200].
    elo = 1.0 / (1.0 + math.exp(-(team.elo_rating - 1500) / 200))

    form = max(0.0, min(1.0, team.recent_form_score))

    total_games = team.wins + team.draws + team.losses
    win_rate = team.wins / total_games if total_games > 0 else 0.0

    return TeamFeatures(
        attacking=attacking,
        defensive=defensive,
        ranking=ranking,
        elo=elo,
        form=form,
        win_rate=win_rate,
    )
