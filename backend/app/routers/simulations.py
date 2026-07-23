"""GET /api/v1/simulations/tournament — Monte Carlo World Cup simulation."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query

from app.dependencies import CacheDep, SessionDep
from app.prediction_engine.model import MODEL_VERSION
from app.repositories.team import TeamRepository
from app.services.cache import TTL_SIMULATION, key_simulation
from app.simulation.engine import run_simulations
from app.simulation.schemas import (
    SimulationMeta,
    TeamTournamentProbabilities,
    TournamentSimulationResponse,
)

router = APIRouter(tags=["simulations"])

_META = SimulationMeta(
    algorithm=(
        "Monte Carlo: N independent simulations of a round-robin group stage "
        "followed by a single-elimination knockout bracket"
    ),
    goal_model=(
        "Synthetic goals for tie-breaking only — "
        "winner draws from U[1,4], loser from U[0,winner-1]; "
        "draws both draw from U[0,3]"
    ),
    tie_breaking="Points → Goal Difference → Goals Scored → Alphabetical team code",
    knockout_draws="50/50 coin flip (penalty-shootout proxy; no extra-time model)",
    limitations=[
        "Goal counts are synthetic — the model predicts win/draw/loss probabilities only, not scores",
        "Home advantage (+0.05) is applied to the first team in each pairing; no neutral-ground mode",
        "Tie-breaking uses no head-to-head record within groups",
        "Knockout draws are resolved by a coin flip, not an extra-time model",
        (
            "For a 2-group bracket, group_advance_probability, quarterfinal_probability, "
            "and semifinal_probability are equivalent (no separate QF round)"
        ),
        "Probabilities reflect historical statistics; real-time form changes are not captured",
    ],
)


@router.get("/api/v1/simulations/tournament", response_model=TournamentSimulationResponse)
async def tournament_simulation(
    n: int = Query(default=1000, ge=100, le=10000, description="Number of Monte Carlo simulations"),
    seed: int | None = Query(None, description="Random seed for reproducibility"),
    session: SessionDep = ...,
    cache: CacheDep = ...,
) -> TournamentSimulationResponse:
    cache_key = key_simulation(n, seed)
    cached = await cache.get(cache_key)
    if cached:
        return TournamentSimulationResponse(**cached)

    teams = await TeamRepository(session).list(limit=200, offset=0)
    if not teams:
        raise HTTPException(status_code=503, detail="No teams in database — run the seed script first")

    probs, used_seed = await run_simulations(teams, n=n, seed=seed)

    team_results = sorted(
        [
            TeamTournamentProbabilities(
                team_code=t.country_code,
                team_name=t.name,
                group=t.group_name,
                **probs[t.id],
            )
            for t in teams
        ],
        key=lambda r: -r.championship_probability,
    )

    response = TournamentSimulationResponse(
        simulation_count=n,
        model_version=MODEL_VERSION,
        random_seed=used_seed,
        generated_at=datetime.now(timezone.utc).isoformat(),
        teams=team_results,
        metadata=_META,
    )

    await cache.set(cache_key, response.model_dump(), TTL_SIMULATION)
    return response
