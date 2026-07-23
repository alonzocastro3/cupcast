"""
Tests for the Monte Carlo tournament simulation engine (Phase 14).

Tests cover:
- _sample_outcome: correct bucket selection from probabilities
- _sample_goals: outcome-consistent goal generation
- _simulate_group: round-robin ranking, cache population, determinism
- _simulate_knockout: winner selection, coin-flip on draw
- _simulate_once: correct advance/finalist/champion accounting
- _run_simulations_sync: probability sanity invariants, determinism
- GET /api/v1/simulations/tournament: HTTP contract, schema, sanity checks
"""
from __future__ import annotations

import random
from unittest.mock import MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app as fastapi_app
from app.models.team import Team as TeamModel
from app.simulation.engine import (
    _run_simulations_sync,
    _sample_goals,
    _sample_outcome,
    _simulate_group,
    _simulate_knockout,
    _simulate_once,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────

def make_team(
    id: int,
    code: str,
    group: str,
    *,
    elo: int = 1800,
    ranking: int = 10,
    wins: int = 5,
    draws: int = 2,
    losses: int = 3,
    gf: int = 15,
    ga: int = 12,
    form: float = 0.7,
) -> MagicMock:
    t = MagicMock(spec=TeamModel)
    t.id = id
    t.country_code = code
    t.group_name = group
    t.name = f"Team {code}"
    t.elo_rating = elo
    t.fifa_ranking = ranking
    t.wins = wins
    t.draws = draws
    t.losses = losses
    t.goals_for = gf
    t.goals_against = ga
    t.recent_form_score = form
    return t


def _group_a() -> list:
    return [
        make_team(1, "BRA", "A", elo=2080, ranking=1, wins=8, draws=1, losses=1, gf=24, ga=7),
        make_team(2, "FRA", "A", elo=2055, ranking=2, wins=7, draws=2, losses=1, gf=20, ga=9),
        make_team(3, "ESP", "A", elo=1992, ranking=8, wins=6, draws=2, losses=2, gf=18, ga=10),
        make_team(4, "GER", "A", elo=1974, ranking=16, wins=5, draws=3, losses=2, gf=17, ga=12),
    ]


def _group_b() -> list:
    return [
        make_team(5, "ARG", "B", elo=2090, ranking=3, wins=9, draws=1, losses=0, gf=26, ga=6),
        make_team(6, "ENG", "B", elo=2040, ranking=5, wins=7, draws=2, losses=1, gf=22, ga=8),
        make_team(7, "POR", "B", elo=1985, ranking=6, wins=6, draws=2, losses=2, gf=19, ga=11),
        make_team(8, "NED", "B", elo=1960, ranking=12, wins=5, draws=3, losses=2, gf=16, ga=13),
    ]


def _all_teams() -> list:
    return _group_a() + _group_b()


def _all_groups() -> dict:
    return {"A": _group_a(), "B": _group_b()}


# ── _sample_outcome ───────────────────────────────────────────────────────────

class TestSampleOutcome:
    def test_home_when_random_lt_home_p(self):
        rng = MagicMock()
        rng.random.return_value = 0.30
        assert _sample_outcome(0.50, 0.25, rng) == "home"

    def test_draw_when_random_in_second_bucket(self):
        rng = MagicMock()
        rng.random.return_value = 0.60
        assert _sample_outcome(0.50, 0.25, rng) == "draw"

    def test_away_when_random_in_third_bucket(self):
        rng = MagicMock()
        rng.random.return_value = 0.90
        assert _sample_outcome(0.50, 0.25, rng) == "away"

    def test_boundary_at_home_p_falls_into_draw_bucket(self):
        rng = MagicMock()
        rng.random.return_value = 0.50  # equal to home_p → not < home_p → draw
        assert _sample_outcome(0.50, 0.25, rng) == "draw"

    def test_all_three_outcomes_reachable(self):
        outcomes = set()
        for seed in range(100):
            rng = random.Random(seed)
            outcomes.add(_sample_outcome(0.40, 0.30, rng))
        assert outcomes == {"home", "draw", "away"}


# ── _sample_goals ─────────────────────────────────────────────────────────────

class TestSampleGoals:
    def test_home_win_home_always_greater_than_away(self):
        rng = random.Random(42)
        for _ in range(300):
            hg, ag = _sample_goals("home", rng)
            assert hg > ag, f"home win but {hg}–{ag}"

    def test_away_win_away_always_greater_than_home(self):
        rng = random.Random(42)
        for _ in range(300):
            hg, ag = _sample_goals("away", rng)
            assert ag > hg, f"away win but {hg}–{ag}"

    def test_draw_goals_always_equal(self):
        rng = random.Random(42)
        for _ in range(300):
            hg, ag = _sample_goals("draw", rng)
            assert hg == ag

    def test_home_win_goals_in_valid_range(self):
        rng = random.Random(0)
        for _ in range(300):
            hg, ag = _sample_goals("home", rng)
            assert 1 <= hg <= 4
            assert 0 <= ag <= 3

    def test_away_win_goals_in_valid_range(self):
        rng = random.Random(0)
        for _ in range(300):
            hg, ag = _sample_goals("away", rng)
            assert 1 <= ag <= 4
            assert 0 <= hg <= 3

    def test_draw_goals_non_negative(self):
        rng = random.Random(0)
        for _ in range(300):
            hg, ag = _sample_goals("draw", rng)
            assert hg >= 0
            assert hg <= 3


# ── _simulate_group ───────────────────────────────────────────────────────────

class TestSimulateGroup:
    def test_returns_all_four_teams(self):
        teams = _group_a()
        result = _simulate_group(teams, {}, random.Random(0))
        assert len(result) == 4
        assert {t.id for t in result} == {1, 2, 3, 4}

    def test_deterministic_with_fixed_seed(self):
        teams = _group_a()
        r1 = _simulate_group(teams, {}, random.Random(42))
        r2 = _simulate_group(teams, {}, random.Random(42))
        assert [t.id for t in r1] == [t.id for t in r2]

    def test_populates_prediction_cache_with_six_pairs(self):
        teams = _group_a()
        cache: dict = {}
        _simulate_group(teams, cache, random.Random(0))
        # 4 choose 2 = 6 unique ordered pairs
        assert len(cache) == 6

    def test_cache_not_extended_on_second_call(self):
        teams = _group_a()
        cache: dict = {}
        _simulate_group(teams, cache, random.Random(0))
        size = len(cache)
        _simulate_group(teams, cache, random.Random(1))
        assert len(cache) == size

    def test_different_seeds_produce_different_rankings(self):
        teams = _group_a()
        rankings = set()
        for seed in range(40):
            r = _simulate_group(teams, {}, random.Random(seed))
            rankings.add(tuple(t.id for t in r))
        assert len(rankings) > 1

    def test_stronger_team_wins_group_more_often(self):
        # BRA (elo=2080, rank=1) vs GER (elo=1974, rank=16) — BRA should top the group more
        teams = _group_a()
        bra_wins = 0
        for seed in range(200):
            r = _simulate_group(teams, {}, random.Random(seed))
            if r[0].country_code == "BRA":
                bra_wins += 1
        assert bra_wins > 50  # above random-chance floor of 25% (50/200)


# ── _simulate_knockout ────────────────────────────────────────────────────────

class TestSimulateKnockout:
    def test_returns_one_of_two_teams(self):
        a, b = _group_a()[0], _group_a()[1]
        winner = _simulate_knockout(a, b, {}, random.Random(0))
        assert winner.id in (a.id, b.id)

    def test_deterministic_with_same_seed(self):
        a, b = _group_a()[0], _group_a()[1]
        w1 = _simulate_knockout(a, b, {}, random.Random(99))
        w2 = _simulate_knockout(a, b, {}, random.Random(99))
        assert w1.id == w2.id

    def test_strong_team_wins_more_often(self):
        strong = make_team(1, "STR", "A", elo=2200, ranking=1, wins=10, draws=0, losses=0, gf=30, ga=2)
        weak = make_team(2, "WEK", "A", elo=1400, ranking=100, wins=0, draws=1, losses=9, gf=3, ga=25)
        wins = sum(
            1
            for seed in range(300)
            if _simulate_knockout(strong, weak, {}, random.Random(seed)).id == strong.id
        )
        assert wins > 200  # strong wins >66% of time

    def test_prediction_added_to_cache(self):
        a, b = _group_a()[0], _group_a()[1]
        cache: dict = {}
        _simulate_knockout(a, b, cache, random.Random(0))
        assert (a.id, b.id) in cache


# ── _simulate_once ────────────────────────────────────────────────────────────

class TestSimulateOnce:
    def test_exactly_four_teams_advance(self):
        result = _simulate_once(_all_groups(), {}, random.Random(0))
        assert len(result.advanced) == 4

    def test_advanced_teams_are_subset_of_all(self):
        all_ids = {t.id for t in _all_teams()}
        result = _simulate_once(_all_groups(), {}, random.Random(0))
        assert result.advanced.issubset(all_ids)

    def test_exactly_two_finalists(self):
        result = _simulate_once(_all_groups(), {}, random.Random(0))
        assert len(result.finalists) == 2

    def test_finalists_are_subset_of_advanced(self):
        result = _simulate_once(_all_groups(), {}, random.Random(5))
        assert result.finalists.issubset(result.advanced)

    def test_champion_is_one_of_finalists(self):
        result = _simulate_once(_all_groups(), {}, random.Random(7))
        assert result.champion in result.finalists

    def test_exactly_one_champion(self):
        result = _simulate_once(_all_groups(), {}, random.Random(3))
        assert result.champion is not None

    def test_deterministic_with_same_seed(self):
        cache: dict = {}
        r1 = _simulate_once(_all_groups(), cache, random.Random(42))
        r2 = _simulate_once(_all_groups(), cache, random.Random(42))
        assert r1.advanced == r2.advanced
        assert r1.finalists == r2.finalists
        assert r1.champion == r2.champion

    def test_both_groups_contribute_to_advanced(self):
        group_a_ids = {t.id for t in _group_a()}
        group_b_ids = {t.id for t in _group_b()}
        result = _simulate_once(_all_groups(), {}, random.Random(0))
        assert result.advanced & group_a_ids
        assert result.advanced & group_b_ids


# ── _run_simulations_sync ─────────────────────────────────────────────────────

class TestRunSimulationsSync:
    def test_returns_entry_for_every_team(self):
        teams = _all_teams()
        probs = _run_simulations_sync(teams, n=100, seed=42)
        assert set(probs.keys()) == {t.id for t in teams}

    def test_all_probabilities_in_unit_interval(self):
        probs = _run_simulations_sync(_all_teams(), n=100, seed=0)
        for tp in probs.values():
            for p in tp.values():
                assert 0.0 <= p <= 1.0, f"probability {p} out of range"

    def test_group_advance_sums_to_four(self):
        """2 teams advance from each of 2 groups → expected total ≈ 4.0."""
        probs = _run_simulations_sync(_all_teams(), n=500, seed=1)
        total = sum(v["group_advance_probability"] for v in probs.values())
        assert 3.5 <= total <= 4.5

    def test_championship_probs_sum_to_one(self):
        """Exactly one champion per simulation."""
        probs = _run_simulations_sync(_all_teams(), n=500, seed=2)
        total = sum(v["championship_probability"] for v in probs.values())
        assert abs(total - 1.0) < 0.05

    def test_final_probs_sum_to_two(self):
        """Exactly two finalists per simulation."""
        probs = _run_simulations_sync(_all_teams(), n=500, seed=3)
        total = sum(v["final_probability"] for v in probs.values())
        assert abs(total - 2.0) < 0.2

    def test_monotonic_probability_through_rounds(self):
        """P(advance) ≥ P(final) ≥ P(championship) for every team."""
        probs = _run_simulations_sync(_all_teams(), n=300, seed=4)
        for tp in probs.values():
            assert tp["group_advance_probability"] >= tp["final_probability"]
            assert tp["final_probability"] >= tp["championship_probability"]

    def test_deterministic_with_same_seed(self):
        p1 = _run_simulations_sync(_all_teams(), n=200, seed=99)
        p2 = _run_simulations_sync(_all_teams(), n=200, seed=99)
        assert p1 == p2

    def test_different_seeds_differ(self):
        p1 = _run_simulations_sync(_all_teams(), n=100, seed=10)
        p2 = _run_simulations_sync(_all_teams(), n=100, seed=20)
        any_diff = any(
            p1[t.id]["championship_probability"] != p2[t.id]["championship_probability"]
            for t in _all_teams()
        )
        assert any_diff

    def test_stronger_team_higher_championship_prob(self):
        """ARG (elo=2090, rank=3) should beat NED (elo=1960, rank=12) on championship_prob."""
        teams = _all_teams()
        probs = _run_simulations_sync(teams, n=1000, seed=42)
        arg_id = next(t.id for t in teams if t.country_code == "ARG")
        ned_id = next(t.id for t in teams if t.country_code == "NED")
        assert probs[arg_id]["championship_probability"] > probs[ned_id]["championship_probability"]

    def test_qf_and_sf_equal_group_advance_for_two_group_bracket(self):
        probs = _run_simulations_sync(_all_teams(), n=200, seed=0)
        for tp in probs.values():
            assert tp["quarterfinal_probability"] == tp["group_advance_probability"]
            assert tp["semifinal_probability"] == tp["group_advance_probability"]


# ── API endpoint ──────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def sim_client(api_client: AsyncClient, db_session: AsyncSession):
    """api_client fixture with all 8 seed teams pre-inserted."""
    from app.seed import _TEAMS

    for td in _TEAMS:
        db_session.add(
            TeamModel(
                name=td["name"],
                country_code=td["country_code"],
                group_name=td["group_name"],
                fifa_ranking=td["fifa_ranking"],
                elo_rating=td["elo_rating"],
                recent_form_score=td["recent_form_score"],
                wins=td["wins"],
                draws=td.get("draws", 0),
                losses=td.get("losses", 0),
                goals_for=td.get("goals_for", 0),
                goals_against=td.get("goals_against", 0),
            )
        )
    await db_session.flush()
    yield api_client


class TestTournamentSimulationEndpoint:
    @pytest.mark.asyncio
    async def test_returns_200(self, sim_client):
        resp = await sim_client.get(
            "/api/v1/simulations/tournament", params={"seed": 42, "n": 100}
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_response_has_eight_teams(self, sim_client):
        resp = await sim_client.get(
            "/api/v1/simulations/tournament", params={"seed": 42, "n": 100}
        )
        assert len(resp.json()["teams"]) == 8

    @pytest.mark.asyncio
    async def test_simulation_count_matches_query_param(self, sim_client):
        resp = await sim_client.get(
            "/api/v1/simulations/tournament", params={"seed": 1, "n": 200}
        )
        assert resp.json()["simulation_count"] == 200

    @pytest.mark.asyncio
    async def test_seed_echoed_in_response(self, sim_client):
        resp = await sim_client.get(
            "/api/v1/simulations/tournament", params={"seed": 77, "n": 100}
        )
        assert resp.json()["random_seed"] == 77

    @pytest.mark.asyncio
    async def test_model_version_present(self, sim_client):
        resp = await sim_client.get(
            "/api/v1/simulations/tournament", params={"seed": 0, "n": 100}
        )
        assert resp.json()["model_version"] == "1.0.0"

    @pytest.mark.asyncio
    async def test_all_probabilities_in_unit_interval(self, sim_client):
        resp = await sim_client.get(
            "/api/v1/simulations/tournament", params={"seed": 0, "n": 100}
        )
        for team in resp.json()["teams"]:
            for field in (
                "group_advance_probability",
                "quarterfinal_probability",
                "semifinal_probability",
                "final_probability",
                "championship_probability",
            ):
                assert 0.0 <= team[field] <= 1.0

    @pytest.mark.asyncio
    async def test_championship_probs_sum_to_one(self, sim_client):
        resp = await sim_client.get(
            "/api/v1/simulations/tournament", params={"seed": 5, "n": 500}
        )
        total = sum(t["championship_probability"] for t in resp.json()["teams"])
        assert abs(total - 1.0) < 0.05

    @pytest.mark.asyncio
    async def test_deterministic_with_same_seed(self, sim_client):
        params = {"seed": 42, "n": 100}
        r1 = (await sim_client.get("/api/v1/simulations/tournament", params=params)).json()
        r2 = (await sim_client.get("/api/v1/simulations/tournament", params=params)).json()
        assert r1["teams"] == r2["teams"]

    @pytest.mark.asyncio
    async def test_metadata_present(self, sim_client):
        resp = await sim_client.get(
            "/api/v1/simulations/tournament", params={"seed": 0, "n": 100}
        )
        meta = resp.json()["metadata"]
        assert "algorithm" in meta
        assert "limitations" in meta
        assert len(meta["limitations"]) > 0

    @pytest.mark.asyncio
    async def test_no_teams_returns_503(self, api_client):
        resp = await api_client.get("/api/v1/simulations/tournament", params={"n": 100})
        assert resp.status_code == 503

    @pytest.mark.asyncio
    async def test_n_below_minimum_returns_422(self, api_client):
        resp = await api_client.get("/api/v1/simulations/tournament", params={"n": 50})
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_teams_sorted_by_championship_prob_desc(self, sim_client):
        resp = await sim_client.get(
            "/api/v1/simulations/tournament", params={"seed": 42, "n": 200}
        )
        probs = [t["championship_probability"] for t in resp.json()["teams"]]
        assert probs == sorted(probs, reverse=True)
