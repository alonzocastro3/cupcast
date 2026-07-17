"""Unit and integration tests for the match prediction engine."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import PredictedOutcome
from app.models.match import Match
from app.models.team import Team
from app.prediction_engine.features import extract
from app.prediction_engine.model import ModelPredictor, predict

_TZ = timezone.utc


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_team(**kwargs) -> Team:
    defaults = dict(
        name="TestTeam",
        country_code="TST",
        group_name="A",
        fifa_ranking=50,
        elo_rating=1500,
        recent_form_score=0.5,
        goals_for=10,
        goals_against=10,
        wins=5,
        draws=3,
        losses=2,
    )
    defaults.update(kwargs)
    t = MagicMock(spec=Team)
    for k, v in defaults.items():
        setattr(t, k, v)
    return t


def _db_team(name: str, code: str, group: str = "A", **kwargs) -> Team:
    return Team(
        name=name,
        country_code=code,
        group_name=group,
        fifa_ranking=kwargs.get("fifa_ranking", 50),
        elo_rating=kwargs.get("elo_rating", 1500),
        recent_form_score=kwargs.get("recent_form_score", 0.5),
        goals_for=kwargs.get("goals_for", 10),
        goals_against=kwargs.get("goals_against", 10),
        wins=kwargs.get("wins", 5),
        draws=kwargs.get("draws", 3),
        losses=kwargs.get("losses", 2),
    )


def _db_match(home_id: int, away_id: int) -> Match:
    return Match(
        home_team_id=home_id,
        away_team_id=away_id,
        kickoff_at=datetime(2026, 6, 15, 15, 0, tzinfo=_TZ),
        stage="group_a",
    )


# ── Feature extraction ────────────────────────────────────────────────────────

def test_features_attacking_defensive_balanced() -> None:
    team = _make_team(goals_for=10, goals_against=10)
    f = extract(team)
    assert abs(f.attacking - 0.5) < 0.001
    assert abs(f.defensive - 0.5) < 0.001


def test_features_no_games_defaults_to_half() -> None:
    team = _make_team(goals_for=0, goals_against=0)
    f = extract(team)
    assert f.attacking == 0.5
    assert f.defensive == 0.5


def test_features_form_clamped() -> None:
    team_high = _make_team(recent_form_score=5.0)
    team_low = _make_team(recent_form_score=-2.0)
    assert extract(team_high).form == 1.0
    assert extract(team_low).form == 0.0


def test_features_win_rate_no_games() -> None:
    team = _make_team(wins=0, draws=0, losses=0)
    assert extract(team).win_rate == 0.0


def test_features_win_rate_all_wins() -> None:
    team = _make_team(wins=10, draws=0, losses=0)
    assert extract(team).win_rate == 1.0


def test_features_elo_midpoint_near_half() -> None:
    team = _make_team(elo_rating=1500)
    f = extract(team)
    assert abs(f.elo - 0.5) < 0.001


# ── Probabilities ─────────────────────────────────────────────────────────────

def test_probabilities_sum_to_one() -> None:
    home = _make_team(name="Home")
    away = _make_team(name="Away")
    result = predict(home, away)
    total = result.home_win_probability + result.draw_probability + result.away_win_probability
    assert abs(total - 1.0) < 1e-9


def test_no_negative_probabilities() -> None:
    home = _make_team(name="Home")
    away = _make_team(name="Away")
    result = predict(home, away)
    assert result.home_win_probability >= 0
    assert result.draw_probability >= 0
    assert result.away_win_probability >= 0


def test_stronger_team_favored() -> None:
    strong = _make_team(name="Strong", fifa_ranking=1, elo_rating=2100, wins=20, losses=0)
    weak = _make_team(name="Weak", fifa_ranking=150, elo_rating=1100, wins=0, losses=20)
    result = predict(strong, weak)
    assert result.home_win_probability > result.away_win_probability
    assert result.predicted_outcome == PredictedOutcome.HOME_WIN


def test_stronger_away_team_still_reflected() -> None:
    weak = _make_team(name="Weak", fifa_ranking=150, elo_rating=1100)
    strong = _make_team(name="Strong", fifa_ranking=1, elo_rating=2100, wins=20, losses=0)
    result = predict(weak, strong)
    # Away team is much stronger; despite home advantage, away should win.
    assert result.away_win_probability > result.home_win_probability


def test_equal_teams_roughly_balanced() -> None:
    home = _make_team(name="TeamA")
    away = _make_team(name="TeamB")
    result = predict(home, away)
    # With identical stats, home/away should be very close (home advantage is small).
    assert abs(result.home_win_probability - result.away_win_probability) < 0.10


def test_extreme_values_no_crash() -> None:
    home = _make_team(fifa_ranking=1, elo_rating=9999, wins=1000, recent_form_score=1.0)
    away = _make_team(fifa_ranking=200, elo_rating=0, losses=1000, recent_form_score=0.0)
    result = predict(home, away)
    total = result.home_win_probability + result.draw_probability + result.away_win_probability
    assert abs(total - 1.0) < 1e-9
    assert result.home_win_probability >= 0.01
    assert result.away_win_probability >= 0.01


def test_deterministic() -> None:
    home = _make_team(name="Home")
    away = _make_team(name="Away")
    r1 = predict(home, away)
    r2 = predict(home, away)
    assert r1.home_win_probability == r2.home_win_probability
    assert r1.draw_probability == r2.draw_probability
    assert r1.away_win_probability == r2.away_win_probability


def test_confidence_within_range() -> None:
    home = _make_team(name="Home")
    away = _make_team(name="Away")
    result = predict(home, away)
    assert 0.0 <= result.confidence <= 1.0


def test_model_predictor_class_consistent() -> None:
    predictor = ModelPredictor()
    home = _make_team(name="Home")
    away = _make_team(name="Away")
    r = predictor.predict(home, away)
    total = r.home_win_probability + r.draw_probability + r.away_win_probability
    assert abs(total - 1.0) < 1e-9


# ── API integration ───────────────────────────────────────────────────────────

async def test_model_prediction_not_found(api_client: AsyncClient) -> None:
    resp = await api_client.get("/api/v1/matches/99999/model-prediction")
    assert resp.status_code == 404
    assert "99999" in resp.json()["detail"]


async def test_model_prediction_returns_valid_response(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    home = _db_team("Brazil", "BRA", fifa_ranking=5, elo_rating=1900, wins=10)
    away = _db_team("Germany", "GER", fifa_ranking=15, elo_rating=1800, wins=7)
    db_session.add_all([home, away])
    await db_session.flush()

    match = _db_match(home.id, away.id)
    db_session.add(match)
    await db_session.flush()

    resp = await api_client.get(f"/api/v1/matches/{match.id}/model-prediction")
    assert resp.status_code == 200
    body = resp.json()

    assert body["match_id"] == match.id
    assert body["home_team"]["country_code"] == "BRA"
    assert body["away_team"]["country_code"] == "GER"
    assert "home_win_probability" in body
    assert "draw_probability" in body
    assert "away_win_probability" in body
    assert "predicted_outcome" in body
    assert "confidence" in body
    assert "explanation" in body
    assert "model_version" in body

    total = (
        body["home_win_probability"]
        + body["draw_probability"]
        + body["away_win_probability"]
    )
    assert abs(total - 1.0) < 1e-4
    assert 0.0 <= body["confidence"] <= 1.0


async def test_model_prediction_stronger_home_team_favored(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    strong = _db_team("Brazil", "BRA", fifa_ranking=1, elo_rating=2100, wins=20)
    weak = _db_team("Minnow", "MIN", fifa_ranking=150, elo_rating=1100, losses=20)
    db_session.add_all([strong, weak])
    await db_session.flush()

    match = _db_match(strong.id, weak.id)
    db_session.add(match)
    await db_session.flush()

    resp = await api_client.get(f"/api/v1/matches/{match.id}/model-prediction")
    body = resp.json()
    assert body["predicted_outcome"] == "home_win"
    assert body["home_win_probability"] > body["away_win_probability"]


async def test_model_prediction_is_deterministic(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    home = _db_team("Brazil", "BRA")
    away = _db_team("Germany", "GER")
    db_session.add_all([home, away])
    await db_session.flush()

    match = _db_match(home.id, away.id)
    db_session.add(match)
    await db_session.flush()

    r1 = (await api_client.get(f"/api/v1/matches/{match.id}/model-prediction")).json()
    r2 = (await api_client.get(f"/api/v1/matches/{match.id}/model-prediction")).json()

    assert r1["home_win_probability"] == r2["home_win_probability"]
    assert r1["draw_probability"] == r2["draw_probability"]
    assert r1["away_win_probability"] == r2["away_win_probability"]
