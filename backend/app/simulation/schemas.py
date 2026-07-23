from __future__ import annotations

from pydantic import BaseModel


class TeamTournamentProbabilities(BaseModel):
    team_code: str
    team_name: str | None
    group: str
    group_advance_probability: float
    quarterfinal_probability: float
    semifinal_probability: float
    final_probability: float
    championship_probability: float


class SimulationMeta(BaseModel):
    algorithm: str
    goal_model: str
    tie_breaking: str
    knockout_draws: str
    limitations: list[str]


class TournamentSimulationResponse(BaseModel):
    simulation_count: int
    model_version: str
    random_seed: int
    generated_at: str
    teams: list[TeamTournamentProbabilities]
    metadata: SimulationMeta
