"""Integration tests for model-level database constraints."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import MatchStatus, PredictedOutcome
from app.models.match import Match
from app.models.prediction import Prediction
from app.models.team import Team

_TZ = timezone.utc
_KICKOFF = datetime(2026, 7, 1, 15, 0, tzinfo=_TZ)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _team(name: str, code: str, group: str = "X") -> Team:
    return Team(name=name, country_code=code, group_name=group, fifa_ranking=50, elo_rating=1800)


# ── Team tests ───────────────────────────────────────────────────────────────

async def test_team_is_created_with_defaults(db_session: AsyncSession) -> None:
    team = _team("Brazil", "BRA", "A")
    db_session.add(team)
    await db_session.flush()

    assert team.id is not None
    assert team.wins == 0
    assert team.draws == 0
    assert team.losses == 0
    assert team.goals_for == 0
    assert team.goals_against == 0
    assert team.recent_form_score == 0.0
    assert team.extra_stats is None
    assert team.created_at is not None


async def test_team_country_code_is_unique(db_session: AsyncSession) -> None:
    db_session.add(_team("Brazil A", "BRA"))
    await db_session.flush()

    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            db_session.add(_team("Brazil B", "BRA"))
            await db_session.flush()


async def test_team_name_is_unique(db_session: AsyncSession) -> None:
    db_session.add(_team("Brazil", "BRA"))
    await db_session.flush()

    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            db_session.add(_team("Brazil", "BR2"))
            await db_session.flush()


# ── Match tests ──────────────────────────────────────────────────────────────

async def test_match_created_with_two_different_teams(db_session: AsyncSession) -> None:
    home = _team("Brazil", "BRA", "A")
    away = _team("Germany", "GER", "A")
    db_session.add_all([home, away])
    await db_session.flush()

    match = Match(
        home_team_id=home.id,
        away_team_id=away.id,
        kickoff_at=_KICKOFF,
        stage="group_a",
    )
    db_session.add(match)
    await db_session.flush()

    assert match.id is not None
    assert match.status == MatchStatus.SCHEDULED
    assert match.home_score is None
    assert match.away_score is None


async def test_match_team_cannot_play_itself(db_session: AsyncSession) -> None:
    team = _team("Brazil", "BRA")
    db_session.add(team)
    await db_session.flush()

    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            db_session.add(
                Match(
                    home_team_id=team.id,
                    away_team_id=team.id,
                    kickoff_at=_KICKOFF,
                    stage="final",
                )
            )
            await db_session.flush()


async def test_match_external_id_is_unique(db_session: AsyncSession) -> None:
    home = _team("Brazil", "BRA")
    away = _team("Germany", "GER")
    db_session.add_all([home, away])
    await db_session.flush()

    db_session.add(
        Match(
            external_id="EXT-001",
            home_team_id=home.id,
            away_team_id=away.id,
            kickoff_at=_KICKOFF,
            stage="group_a",
        )
    )
    await db_session.flush()

    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            db_session.add(
                Match(
                    external_id="EXT-001",
                    home_team_id=away.id,
                    away_team_id=home.id,
                    kickoff_at=_KICKOFF,
                    stage="group_a",
                )
            )
            await db_session.flush()


# ── Prediction tests ─────────────────────────────────────────────────────────

async def test_prediction_is_created(db_session: AsyncSession) -> None:
    home = _team("Brazil", "BRA")
    away = _team("Germany", "GER")
    db_session.add_all([home, away])
    await db_session.flush()

    match = Match(home_team_id=home.id, away_team_id=away.id, kickoff_at=_KICKOFF, stage="group_a")
    db_session.add(match)
    await db_session.flush()

    pred = Prediction(
        match_id=match.id,
        session_id="sess-abc-123",
        predicted_outcome=PredictedOutcome.HOME_WIN,
        predicted_home_score=2,
        predicted_away_score=1,
    )
    db_session.add(pred)
    await db_session.flush()

    assert pred.id is not None
    assert pred.predicted_outcome == PredictedOutcome.HOME_WIN


async def test_one_prediction_per_session_per_match(db_session: AsyncSession) -> None:
    home = _team("Brazil", "BRA")
    away = _team("Germany", "GER")
    db_session.add_all([home, away])
    await db_session.flush()

    match = Match(home_team_id=home.id, away_team_id=away.id, kickoff_at=_KICKOFF, stage="group_a")
    db_session.add(match)
    await db_session.flush()

    db_session.add(
        Prediction(match_id=match.id, session_id="sess-dupe", predicted_outcome=PredictedOutcome.HOME_WIN)
    )
    await db_session.flush()

    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            db_session.add(
                Prediction(match_id=match.id, session_id="sess-dupe", predicted_outcome=PredictedOutcome.DRAW)
            )
            await db_session.flush()


async def test_different_sessions_can_predict_same_match(db_session: AsyncSession) -> None:
    home = _team("Brazil", "BRA")
    away = _team("Germany", "GER")
    db_session.add_all([home, away])
    await db_session.flush()

    match = Match(home_team_id=home.id, away_team_id=away.id, kickoff_at=_KICKOFF, stage="group_a")
    db_session.add(match)
    await db_session.flush()

    db_session.add_all([
        Prediction(match_id=match.id, session_id="sess-1", predicted_outcome=PredictedOutcome.HOME_WIN),
        Prediction(match_id=match.id, session_id="sess-2", predicted_outcome=PredictedOutcome.AWAY_WIN),
        Prediction(match_id=match.id, session_id="sess-3", predicted_outcome=PredictedOutcome.DRAW),
    ])
    await db_session.flush()  # all three should succeed
