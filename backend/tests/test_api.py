"""API integration tests — all hit the test DB via the overridden get_db dep."""

from __future__ import annotations

from datetime import datetime, timezone

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import MatchStatus, PredictedOutcome
from app.models.match import Match
from app.models.prediction import Prediction
from app.models.team import Team

_TZ = timezone.utc


# ── Fixtures / helpers ────────────────────────────────────────────────────────

def _team(name: str, code: str, group: str = "A") -> Team:
    return Team(
        name=name,
        country_code=code,
        group_name=group,
        fifa_ranking=10,
        elo_rating=1900,
    )


def _match(home_id: int, away_id: int, stage: str = "group_a", *, days_offset: int = 0) -> Match:
    return Match(
        home_team_id=home_id,
        away_team_id=away_id,
        kickoff_at=datetime(2026, 6, 11 + days_offset, 15, 0, tzinfo=_TZ),
        stage=stage,
    )


# ── GET /api/v1/teams ─────────────────────────────────────────────────────────

async def test_list_teams_empty(api_client: AsyncClient) -> None:
    resp = await api_client.get("/api/v1/teams")
    assert resp.status_code == 200
    body = resp.json()
    assert body["items"] == []
    assert body["total"] == 0
    assert body["limit"] == 20
    assert body["offset"] == 0


async def test_list_teams_returns_all(api_client: AsyncClient, db_session: AsyncSession) -> None:
    db_session.add_all([_team("Brazil", "BRA"), _team("Germany", "GER")])
    await db_session.flush()

    resp = await api_client.get("/api/v1/teams")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert len(body["items"]) == 2


async def test_list_teams_pagination_limit(api_client: AsyncClient, db_session: AsyncSession) -> None:
    db_session.add_all([_team("Brazil", "BRA"), _team("Germany", "GER"), _team("France", "FRA")])
    await db_session.flush()

    resp = await api_client.get("/api/v1/teams?limit=2&offset=0")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    assert len(body["items"]) == 2
    assert body["limit"] == 2
    assert body["offset"] == 0


async def test_list_teams_pagination_offset(api_client: AsyncClient, db_session: AsyncSession) -> None:
    db_session.add_all([_team("Brazil", "BRA"), _team("Germany", "GER"), _team("France", "FRA")])
    await db_session.flush()

    resp = await api_client.get("/api/v1/teams?limit=2&offset=2")
    body = resp.json()
    assert body["total"] == 3
    assert len(body["items"]) == 1


async def test_list_teams_limit_cannot_exceed_100(api_client: AsyncClient) -> None:
    resp = await api_client.get("/api/v1/teams?limit=101")
    assert resp.status_code == 422


# ── GET /api/v1/teams/{id} ────────────────────────────────────────────────────

async def test_get_team_success(api_client: AsyncClient, db_session: AsyncSession) -> None:
    team = _team("Brazil", "BRA")
    db_session.add(team)
    await db_session.flush()

    resp = await api_client.get(f"/api/v1/teams/{team.id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == team.id
    assert body["name"] == "Brazil"
    assert body["country_code"] == "BRA"
    assert body["fifa_ranking"] == 10
    assert body["elo_rating"] == 1900


async def test_get_team_not_found(api_client: AsyncClient) -> None:
    resp = await api_client.get("/api/v1/teams/99999")
    assert resp.status_code == 404
    assert "99999" in resp.json()["detail"]


# ── GET /api/v1/matches ───────────────────────────────────────────────────────

async def test_list_matches_empty(api_client: AsyncClient) -> None:
    resp = await api_client.get("/api/v1/matches")
    assert resp.status_code == 200
    body = resp.json()
    assert body["items"] == []
    assert body["total"] == 0


async def test_list_matches_returns_all(api_client: AsyncClient, db_session: AsyncSession) -> None:
    home = _team("Brazil", "BRA")
    away = _team("Germany", "GER")
    db_session.add_all([home, away])
    await db_session.flush()

    db_session.add(_match(home.id, away.id))
    await db_session.flush()

    resp = await api_client.get("/api/v1/matches")
    body = resp.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0]["status"] == "scheduled"


async def test_list_matches_filter_by_status(api_client: AsyncClient, db_session: AsyncSession) -> None:
    home = _team("Brazil", "BRA")
    away = _team("Germany", "GER")
    db_session.add_all([home, away])
    await db_session.flush()

    scheduled = _match(home.id, away.id, days_offset=0)
    live = Match(
        home_team_id=home.id,
        away_team_id=away.id,
        kickoff_at=datetime(2026, 6, 12, 15, 0, tzinfo=_TZ),
        stage="group_a",
        status=MatchStatus.LIVE,
    )
    db_session.add_all([scheduled, live])
    await db_session.flush()

    resp = await api_client.get("/api/v1/matches?status=live")
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["status"] == "live"


async def test_list_matches_filter_by_stage(api_client: AsyncClient, db_session: AsyncSession) -> None:
    home = _team("Brazil", "BRA")
    away = _team("Germany", "GER")
    db_session.add_all([home, away])
    await db_session.flush()

    db_session.add_all([
        _match(home.id, away.id, stage="group_a", days_offset=0),
        _match(home.id, away.id, stage="final", days_offset=1),
    ])
    await db_session.flush()

    resp = await api_client.get("/api/v1/matches?stage=final")
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["stage"] == "final"


async def test_list_matches_filter_by_team_id(api_client: AsyncClient, db_session: AsyncSession) -> None:
    brazil = _team("Brazil", "BRA")
    germany = _team("Germany", "GER")
    france = _team("France", "FRA")
    db_session.add_all([brazil, germany, france])
    await db_session.flush()

    # Brazil vs Germany
    db_session.add(_match(brazil.id, germany.id, days_offset=0))
    # Germany vs France (no Brazil)
    db_session.add(_match(germany.id, france.id, days_offset=1))
    await db_session.flush()

    resp = await api_client.get(f"/api/v1/matches?team_id={brazil.id}")
    body = resp.json()
    assert body["total"] == 1
    item = body["items"][0]
    assert item["home_team_id"] == brazil.id or item["away_team_id"] == brazil.id


async def test_list_matches_filter_team_as_away(api_client: AsyncClient, db_session: AsyncSession) -> None:
    home = _team("Brazil", "BRA")
    away = _team("Germany", "GER")
    db_session.add_all([home, away])
    await db_session.flush()

    db_session.add(_match(home.id, away.id))
    await db_session.flush()

    # Filter by the AWAY team — should still appear
    resp = await api_client.get(f"/api/v1/matches?team_id={away.id}")
    body = resp.json()
    assert body["total"] == 1


async def test_list_matches_pagination(api_client: AsyncClient, db_session: AsyncSession) -> None:
    home = _team("Brazil", "BRA")
    away = _team("Germany", "GER")
    db_session.add_all([home, away])
    await db_session.flush()

    for i in range(5):
        db_session.add(_match(home.id, away.id, days_offset=i))
    await db_session.flush()

    resp = await api_client.get("/api/v1/matches?limit=3&offset=0")
    body = resp.json()
    assert body["total"] == 5
    assert len(body["items"]) == 3

    resp2 = await api_client.get("/api/v1/matches?limit=3&offset=3")
    body2 = resp2.json()
    assert len(body2["items"]) == 2


# ── GET /api/v1/matches/{id} ──────────────────────────────────────────────────

async def test_get_match_success(api_client: AsyncClient, db_session: AsyncSession) -> None:
    home = _team("Brazil", "BRA")
    away = _team("Germany", "GER")
    db_session.add_all([home, away])
    await db_session.flush()

    match = _match(home.id, away.id)
    db_session.add(match)
    await db_session.flush()

    resp = await api_client.get(f"/api/v1/matches/{match.id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == match.id
    assert body["home_team_id"] == home.id
    assert body["away_team_id"] == away.id
    assert body["stage"] == "group_a"


async def test_get_match_not_found(api_client: AsyncClient) -> None:
    resp = await api_client.get("/api/v1/matches/99999")
    assert resp.status_code == 404
    assert "99999" in resp.json()["detail"]


# ── GET /api/v1/matches/{id}/prediction-summary ───────────────────────────────

async def test_prediction_summary_no_predictions(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    home = _team("Brazil", "BRA")
    away = _team("Germany", "GER")
    db_session.add_all([home, away])
    await db_session.flush()

    match = _match(home.id, away.id)
    db_session.add(match)
    await db_session.flush()

    resp = await api_client.get(f"/api/v1/matches/{match.id}/prediction-summary")
    assert resp.status_code == 200
    body = resp.json()
    assert body["match_id"] == match.id
    assert body["total_predictions"] == 0
    assert body["home_win_percentage"] == 0.0
    assert body["draw_percentage"] == 0.0
    assert body["away_win_percentage"] == 0.0


async def test_prediction_summary_with_predictions(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    home = _team("Brazil", "BRA")
    away = _team("Germany", "GER")
    db_session.add_all([home, away])
    await db_session.flush()

    match = _match(home.id, away.id)
    db_session.add(match)
    await db_session.flush()

    db_session.add_all([
        Prediction(match_id=match.id, session_id="s1", predicted_outcome=PredictedOutcome.HOME_WIN),
        Prediction(match_id=match.id, session_id="s2", predicted_outcome=PredictedOutcome.HOME_WIN),
        Prediction(match_id=match.id, session_id="s3", predicted_outcome=PredictedOutcome.DRAW),
    ])
    await db_session.flush()

    resp = await api_client.get(f"/api/v1/matches/{match.id}/prediction-summary")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_predictions"] == 3
    assert body["home_win_count"] == 2
    assert body["draw_count"] == 1
    assert body["away_win_count"] == 0
    assert abs(body["home_win_percentage"] - 66.67) < 0.01
    assert abs(body["draw_percentage"] - 33.33) < 0.01
    assert body["away_win_percentage"] == 0.0


async def test_prediction_summary_percentages_sum_to_100(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    home = _team("Brazil", "BRA")
    away = _team("Germany", "GER")
    db_session.add_all([home, away])
    await db_session.flush()

    match = _match(home.id, away.id)
    db_session.add(match)
    await db_session.flush()

    db_session.add_all([
        Prediction(match_id=match.id, session_id="s1", predicted_outcome=PredictedOutcome.HOME_WIN),
        Prediction(match_id=match.id, session_id="s2", predicted_outcome=PredictedOutcome.DRAW),
        Prediction(match_id=match.id, session_id="s3", predicted_outcome=PredictedOutcome.AWAY_WIN),
    ])
    await db_session.flush()

    resp = await api_client.get(f"/api/v1/matches/{match.id}/prediction-summary")
    body = resp.json()
    total_pct = body["home_win_percentage"] + body["draw_percentage"] + body["away_win_percentage"]
    # Allow ≤ 0.02 deviation — rounding 33.33... to 2dp gives 99.99 for equal thirds
    assert abs(total_pct - 100.0) <= 0.02


async def test_prediction_summary_match_not_found(api_client: AsyncClient) -> None:
    resp = await api_client.get("/api/v1/matches/99999/prediction-summary")
    assert resp.status_code == 404
    assert "99999" in resp.json()["detail"]
