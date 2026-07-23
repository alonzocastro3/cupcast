"""Monte Carlo tournament simulation engine.

Algorithm
---------
Group stage:  round-robin within each group, 3/1/0 point system, top 2 advance.
              Synthetic goal counts are generated for tie-breaking (GD → GF → team_code).
Knockout:     adjacent groups are paired (A1 vs B2, B1 vs A2). Draws resolved by a
              50/50 coin flip (penalty-shootout proxy).
Monte Carlo:  N independent single-threaded simulations share an in-memory prediction
              cache (predict() is deterministic), so each pair is evaluated only once.

Documented limitations
----------------------
- Goals are synthetic — the model outputs win/draw/loss probabilities, not scores.
- Home advantage (+0.05) is always applied to the first team in each pair; no
  neutral-ground mode is available.
- Tie-breaking uses no head-to-head record.
- For a 2-group bracket there is no separate quarterfinal round; group_advance,
  quarterfinal, and semifinal probabilities are therefore equivalent.
"""
from __future__ import annotations

import asyncio
import random
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from itertools import combinations
from typing import TYPE_CHECKING

from app.prediction_engine.model import MODEL_VERSION, PredictionResult, predict  # noqa: F401

if TYPE_CHECKING:
    from app.models.team import Team

# ── Internal primitives ───────────────────────────────────────────────────────


@dataclass
class _Standing:
    team: "Team"
    points: int = 0
    gd: int = 0  # goal difference
    gf: int = 0  # goals for


def _sample_outcome(home_p: float, draw_p: float, rng: random.Random) -> str:
    """Return 'home', 'draw', or 'away' sampled from model probabilities."""
    r = rng.random()
    if r < home_p:
        return "home"
    if r < home_p + draw_p:
        return "draw"
    return "away"


def _sample_goals(outcome: str, rng: random.Random) -> tuple[int, int]:
    """Return (home_goals, away_goals) consistent with outcome.

    Goals are synthetic — used only for group-stage tie-breaking.
    """
    if outcome == "home":
        hg = rng.randint(1, 4)
        ag = rng.randint(0, hg - 1) if hg > 1 else 0
        return hg, ag
    if outcome == "away":
        ag = rng.randint(1, 4)
        hg = rng.randint(0, ag - 1) if ag > 1 else 0
        return hg, ag
    # draw
    g = rng.randint(0, 3)
    return g, g


# ── Group stage ───────────────────────────────────────────────────────────────


def _simulate_group(
    teams: list["Team"],
    pred_cache: dict[tuple[int, int], PredictionResult],
    rng: random.Random,
) -> list["Team"]:
    """Simulate a round-robin group. Returns teams ranked by standings (index 0 = winner).

    Tie-breaking: points → goal difference → goals scored → team_code ascending.
    """
    standings: dict[int, _Standing] = {t.id: _Standing(team=t) for t in teams}

    for home, away in combinations(teams, 2):
        key = (home.id, away.id)
        if key not in pred_cache:
            pred_cache[key] = predict(home, away)
        result = pred_cache[key]

        outcome = _sample_outcome(result.home_win_probability, result.draw_probability, rng)
        hg, ag = _sample_goals(outcome, rng)

        h = standings[home.id]
        a = standings[away.id]
        if outcome == "home":
            h.points += 3
        elif outcome == "away":
            a.points += 3
        else:
            h.points += 1
            a.points += 1

        h.gd += hg - ag
        h.gf += hg
        a.gd += ag - hg
        a.gf += ag

    return [
        s.team
        for s in sorted(
            standings.values(),
            key=lambda s: (-s.points, -s.gd, -s.gf, s.team.country_code),
        )
    ]


# ── Knockout stage ────────────────────────────────────────────────────────────


def _simulate_knockout(
    team_a: "Team",
    team_b: "Team",
    pred_cache: dict[tuple[int, int], PredictionResult],
    rng: random.Random,
) -> "Team":
    """Simulate a single knockout match. Draw → 50/50 coin flip (penalty model)."""
    key = (team_a.id, team_b.id)
    if key not in pred_cache:
        pred_cache[key] = predict(team_a, team_b)
    result = pred_cache[key]

    outcome = _sample_outcome(result.home_win_probability, result.draw_probability, rng)
    if outcome == "home":
        return team_a
    if outcome == "away":
        return team_b
    return rng.choice([team_a, team_b])


# ── Single simulation run ─────────────────────────────────────────────────────


@dataclass
class _SimResult:
    advanced: set[int] = field(default_factory=set)   # team ids surviving group stage
    finalists: set[int] = field(default_factory=set)  # team ids reaching the final
    champion: int | None = None


def _simulate_once(
    groups: dict[str, list["Team"]],
    pred_cache: dict[tuple[int, int], PredictionResult],
    rng: random.Random,
) -> _SimResult:
    result = _SimResult()

    # Group stage — top 2 from each group advance
    ranked: dict[str, list["Team"]] = {}
    for g_name, teams in groups.items():
        order = _simulate_group(teams, pred_cache, rng)
        ranked[g_name] = order
        for t in order[:2]:
            result.advanced.add(t.id)

    sorted_groups = sorted(ranked.keys())
    n_groups = len(sorted_groups)
    if n_groups < 2:
        return result

    # First knockout round: pair adjacent groups (A1 vs B2, B1 vs A2)
    first_ko: list["Team"] = []
    for i in range(0, n_groups, 2):
        if i + 1 >= n_groups:
            first_ko.append(ranked[sorted_groups[i]][0])  # bye
        else:
            ga, gb = sorted_groups[i], sorted_groups[i + 1]
            w1 = _simulate_knockout(ranked[ga][0], ranked[gb][1], pred_cache, rng)
            w2 = _simulate_knockout(ranked[gb][0], ranked[ga][1], pred_cache, rng)
            first_ko.extend([w1, w2])

    # Continue knockout rounds until exactly 2 finalists remain
    current = first_ko
    while len(current) > 2:
        next_round: list["Team"] = []
        for i in range(0, len(current), 2):
            if i + 1 >= len(current):
                next_round.append(current[i])
            else:
                w = _simulate_knockout(current[i], current[i + 1], pred_cache, rng)
                next_round.append(w)
        current = next_round

    # Final
    if len(current) == 2:
        result.finalists.update(t.id for t in current)
        champion = _simulate_knockout(current[0], current[1], pred_cache, rng)
        result.champion = champion.id
    elif len(current) == 1:
        result.finalists.add(current[0].id)
        result.champion = current[0].id

    return result


# ── Monte Carlo runner ────────────────────────────────────────────────────────

_EXECUTOR = ThreadPoolExecutor(max_workers=2)


def _run_simulations_sync(
    teams: list["Team"],
    n: int,
    seed: int,
) -> dict[int, dict[str, float]]:
    """Run N simulations synchronously. CPU-bound — must be called from a thread pool."""
    rng = random.Random(seed)
    pred_cache: dict[tuple[int, int], PredictionResult] = {}

    groups: dict[str, list["Team"]] = {}
    for t in teams:
        groups.setdefault(t.group_name, []).append(t)

    advanced: dict[int, int] = {t.id: 0 for t in teams}
    finalists: dict[int, int] = {t.id: 0 for t in teams}
    champions: dict[int, int] = {t.id: 0 for t in teams}

    for _ in range(n):
        sim = _simulate_once(groups, pred_cache, rng)
        for tid in sim.advanced:
            advanced[tid] += 1
        for tid in sim.finalists:
            finalists[tid] += 1
        if sim.champion is not None:
            champions[sim.champion] += 1

    return {
        t.id: {
            # For a 2-group bracket, group_advance == quarterfinal == semifinal
            # (the 4 advancers ARE the semifinalists; there is no separate QF round)
            "group_advance_probability": round(advanced[t.id] / n, 4),
            "quarterfinal_probability": round(advanced[t.id] / n, 4),
            "semifinal_probability": round(advanced[t.id] / n, 4),
            "final_probability": round(finalists[t.id] / n, 4),
            "championship_probability": round(champions[t.id] / n, 4),
        }
        for t in teams
    }


async def run_simulations(
    teams: list["Team"],
    n: int = 1000,
    seed: int | None = None,
) -> tuple[dict[int, dict[str, float]], int]:
    """Run Monte Carlo tournament simulation off the async event loop.

    Returns (probabilities_by_team_id, seed_used).
    """
    if seed is None:
        seed = random.randint(0, 2**31 - 1)
    loop = asyncio.get_event_loop()
    probs: dict[int, dict[str, float]] = await loop.run_in_executor(
        _EXECUTOR, _run_simulations_sync, teams, n, seed
    )
    return probs, seed
