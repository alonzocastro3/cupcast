"""Integration tests for POST /api/v1/matches/{match_id}/predictions."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.match import Match
from app.models.team import Team

_TZ = timezone.utc


# ── Helpers ───────────────────────────────────────────────────────────────────

def _team(name: str, code: str) -> Team:
    return Team(
        name=name,
        country_code=code,
        group_name="A",
        fifa_ranking=10,
        elo_rating=1900,
    )


def _match(home_id: int, away_id: int) -> Match:
    return Match(
        home_team_id=home_id,
        away_team_id=away_id,
        kickoff_at=datetime(2026, 6, 15, 15, 0, tzinfo=_TZ),
        stage="group_a",
    )


async def _seed(db: AsyncSession) -> tuple[int, int]:
    """Insert one match and return (match_id, home_team_id)."""
    home = _team("Brazil", "BRA")
    away = _team("Germany", "GER")
    db.add_all([home, away])
    await db.flush()
    match = _match(home.id, away.id)
    db.add(match)
    await db.flush()
    return match.id, home.id


# ── Successful creation ───────────────────────────────────────────────────────

async def test_submit_prediction_returns_201(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    match_id, _ = await _seed(db_session)
    resp = await api_client.post(
        f"/api/v1/matches/{match_id}/predictions",
        json={"session_id": "sess-001", "predicted_outcome": "home_win"},
    )
    assert resp.status_code == 201


async def test_submit_prediction_response_shape(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    match_id, _ = await _seed(db_session)
    resp = await api_client.post(
        f"/api/v1/matches/{match_id}/predictions",
        json={"session_id": "sess-001", "predicted_outcome": "draw"},
    )
    body = resp.json()
    pred = body["prediction"]
    summary = body["community_summary"]

    assert pred["match_id"] == match_id
    assert pred["session_id"] == "sess-001"
    assert pred["predicted_outcome"] == "draw"
    assert pred["id"] is not None
    assert "created_at" in pred

    assert summary["match_id"] == match_id
    assert summary["total_predictions"] == 1
    assert summary["draw_count"] == 1
    assert summary["home_win_count"] == 0
    assert summary["away_win_count"] == 0


async def test_submit_prediction_with_scores(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    match_id, _ = await _seed(db_session)
    resp = await api_client.post(
        f"/api/v1/matches/{match_id}/predictions",
        json={
            "session_id": "sess-002",
            "predicted_outcome": "home_win",
            "predicted_home_score": 2,
            "predicted_away_score": 1,
        },
    )
    assert resp.status_code == 201
    pred = resp.json()["prediction"]
    assert pred["predicted_home_score"] == 2
    assert pred["predicted_away_score"] == 1


async def test_submit_prediction_without_scores_accepted(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    match_id, _ = await _seed(db_session)
    resp = await api_client.post(
        f"/api/v1/matches/{match_id}/predictions",
        json={"session_id": "sess-003", "predicted_outcome": "away_win"},
    )
    assert resp.status_code == 201
    pred = resp.json()["prediction"]
    assert pred["predicted_home_score"] is None
    assert pred["predicted_away_score"] is None


# ── Community summary updates ─────────────────────────────────────────────────

async def test_community_summary_accumulates(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    match_id, _ = await _seed(db_session)

    await api_client.post(
        f"/api/v1/matches/{match_id}/predictions",
        json={"session_id": "s1", "predicted_outcome": "home_win"},
    )
    await api_client.post(
        f"/api/v1/matches/{match_id}/predictions",
        json={"session_id": "s2", "predicted_outcome": "home_win"},
    )
    resp = await api_client.post(
        f"/api/v1/matches/{match_id}/predictions",
        json={"session_id": "s3", "predicted_outcome": "draw"},
    )

    summary = resp.json()["community_summary"]
    assert summary["total_predictions"] == 3
    assert summary["home_win_count"] == 2
    assert summary["draw_count"] == 1
    assert summary["away_win_count"] == 0
    assert abs(summary["home_win_percentage"] - 66.67) < 0.01
    assert abs(summary["draw_percentage"] - 33.33) < 0.01
    assert summary["away_win_percentage"] == 0.0


# ── Separate sessions ─────────────────────────────────────────────────────────

async def test_separate_sessions_can_each_predict(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    match_id, _ = await _seed(db_session)

    for i, outcome in enumerate(["home_win", "away_win", "draw"]):
        resp = await api_client.post(
            f"/api/v1/matches/{match_id}/predictions",
            json={"session_id": f"session-{i}", "predicted_outcome": outcome},
        )
        assert resp.status_code == 201

    summary_resp = await api_client.get(f"/api/v1/matches/{match_id}/prediction-summary")
    assert summary_resp.json()["total_predictions"] == 3


# ── Duplicate submission → 409 ────────────────────────────────────────────────

async def test_duplicate_prediction_returns_409(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    match_id, _ = await _seed(db_session)
    payload = {"session_id": "dup-session", "predicted_outcome": "home_win"}

    first = await api_client.post(f"/api/v1/matches/{match_id}/predictions", json=payload)
    assert first.status_code == 201

    second = await api_client.post(f"/api/v1/matches/{match_id}/predictions", json=payload)
    assert second.status_code == 409
    assert "dup-session" in second.json()["detail"]


async def test_same_session_different_matches_allowed(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    home = _team("Brazil", "BRA")
    away = _team("Germany", "GER")
    third = _team("France", "FRA")
    db_session.add_all([home, away, third])
    await db_session.flush()

    m1 = _match(home.id, away.id)
    m2 = _match(away.id, third.id)
    db_session.add_all([m1, m2])
    await db_session.flush()

    r1 = await api_client.post(
        f"/api/v1/matches/{m1.id}/predictions",
        json={"session_id": "shared-sess", "predicted_outcome": "home_win"},
    )
    r2 = await api_client.post(
        f"/api/v1/matches/{m2.id}/predictions",
        json={"session_id": "shared-sess", "predicted_outcome": "away_win"},
    )
    assert r1.status_code == 201
    assert r2.status_code == 201


# ── Invalid match → 404 ──────────────────────────────────────────────────────

async def test_invalid_match_returns_404(api_client: AsyncClient) -> None:
    resp = await api_client.post(
        "/api/v1/matches/99999/predictions",
        json={"session_id": "sess-x", "predicted_outcome": "draw"},
    )
    assert resp.status_code == 404
    assert "99999" in resp.json()["detail"]


# ── Invalid outcome → 422 ────────────────────────────────────────────────────

async def test_invalid_outcome_returns_422(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    match_id, _ = await _seed(db_session)
    resp = await api_client.post(
        f"/api/v1/matches/{match_id}/predictions",
        json={"session_id": "sess-y", "predicted_outcome": "not_a_real_outcome"},
    )
    assert resp.status_code == 422


# ── Negative score → 422 ─────────────────────────────────────────────────────

async def test_negative_home_score_returns_422(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    match_id, _ = await _seed(db_session)
    resp = await api_client.post(
        f"/api/v1/matches/{match_id}/predictions",
        json={
            "session_id": "sess-z",
            "predicted_outcome": "home_win",
            "predicted_home_score": -1,
            "predicted_away_score": 0,
        },
    )
    assert resp.status_code == 422


async def test_negative_away_score_returns_422(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    match_id, _ = await _seed(db_session)
    resp = await api_client.post(
        f"/api/v1/matches/{match_id}/predictions",
        json={
            "session_id": "sess-a",
            "predicted_outcome": "away_win",
            "predicted_home_score": 0,
            "predicted_away_score": -3,
        },
    )
    assert resp.status_code == 422


# ── Score / outcome mismatch → 422 ──────────────────────────────────────────

async def test_score_outcome_mismatch_home_win_returns_422(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    match_id, _ = await _seed(db_session)
    resp = await api_client.post(
        f"/api/v1/matches/{match_id}/predictions",
        json={
            "session_id": "sess-b",
            "predicted_outcome": "draw",       # mismatch: scores say home wins
            "predicted_home_score": 3,
            "predicted_away_score": 1,
        },
    )
    assert resp.status_code == 422


async def test_score_outcome_mismatch_away_win_returns_422(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    match_id, _ = await _seed(db_session)
    resp = await api_client.post(
        f"/api/v1/matches/{match_id}/predictions",
        json={
            "session_id": "sess-c",
            "predicted_outcome": "home_win",   # mismatch: scores say away wins
            "predicted_home_score": 0,
            "predicted_away_score": 2,
        },
    )
    assert resp.status_code == 422


async def test_score_outcome_mismatch_draw_returns_422(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    match_id, _ = await _seed(db_session)
    resp = await api_client.post(
        f"/api/v1/matches/{match_id}/predictions",
        json={
            "session_id": "sess-d",
            "predicted_outcome": "away_win",   # mismatch: equal scores → draw
            "predicted_home_score": 1,
            "predicted_away_score": 1,
        },
    )
    assert resp.status_code == 422


async def test_only_one_score_provided_returns_422(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    match_id, _ = await _seed(db_session)
    resp = await api_client.post(
        f"/api/v1/matches/{match_id}/predictions",
        json={
            "session_id": "sess-e",
            "predicted_outcome": "home_win",
            "predicted_home_score": 2,
            # predicted_away_score omitted intentionally
        },
    )
    assert resp.status_code == 422


# ── session_id validation ─────────────────────────────────────────────────────

async def test_empty_session_id_returns_422(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    match_id, _ = await _seed(db_session)
    resp = await api_client.post(
        f"/api/v1/matches/{match_id}/predictions",
        json={"session_id": "", "predicted_outcome": "draw"},
    )
    assert resp.status_code == 422


async def test_session_id_too_long_returns_422(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    match_id, _ = await _seed(db_session)
    resp = await api_client.post(
        f"/api/v1/matches/{match_id}/predictions",
        json={"session_id": "x" * 37, "predicted_outcome": "draw"},
    )
    assert resp.status_code == 422
