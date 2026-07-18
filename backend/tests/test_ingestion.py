"""
Tests for the football data ingestion layer.

Covers:
- Successful team and fixture sync
- Idempotency (second sync inserts nothing new)
- Update detection (changed data on second sync)
- Malformed data validation
- Fixture skipped when team missing or home==away
- ProviderError graceful degradation in sync_all
- Country-code fallback for seed-style teams (no external_id)
- SyncResult arithmetic
- _parse_status fallback
- Group enrichment from fixture stage slugs
- Provider timeout exception type
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.integrations.football.base import (
    FootballDataProvider,
    ProviderError,
    ProviderTimeoutError,
    RawFixture,
    RawTeam,
)
from app.models.team import Team
from app.models.match import Match
from app.services.ingestion_service import (
    IngestionService,
    SyncResult,
    _enrich_team_groups,
)

_TZ = timezone.utc


# ── Mock provider ─────────────────────────────────────────────────────────────

class MockProvider(FootballDataProvider):
    def __init__(
        self,
        teams: list[RawTeam] | None = None,
        fixtures: list[RawFixture] | None = None,
        teams_error: Exception | None = None,
        fixtures_error: Exception | None = None,
    ) -> None:
        self._teams = teams or []
        self._fixtures = fixtures or []
        self._teams_error = teams_error
        self._fixtures_error = fixtures_error

    async def fetch_teams(self, tournament_id: str) -> list[RawTeam]:
        if self._teams_error:
            raise self._teams_error
        return self._teams

    async def fetch_fixtures(self, tournament_id: str) -> list[RawFixture]:
        if self._fixtures_error:
            raise self._fixtures_error
        return self._fixtures


# ── Sample data factories ─────────────────────────────────────────────────────

def _team(
    ext_id: str = "1",
    name: str = "Brazil",
    code: str = "BRA",
    group: str = "A",
) -> RawTeam:
    return RawTeam(
        external_id=ext_id,
        name=name,
        country_code=code,
        group_name=group,
        fifa_ranking=5,
        elo_rating=2000,
    )


def _fixture(
    ext_id: str = "F1",
    home_ext: str = "1",
    away_ext: str = "2",
    status: str = "scheduled",
    stage: str = "group_a",
) -> RawFixture:
    return RawFixture(
        external_id=ext_id,
        home_team_external_id=home_ext,
        away_team_external_id=away_ext,
        kickoff_at=datetime(2026, 6, 11, 15, 0, tzinfo=_TZ),
        status=status,
        stage=stage,
    )


# ── Pure-unit tests (no DB) ───────────────────────────────────────────────────

def test_sync_result_addition():
    a = SyncResult(inserted=1, updated=2, skipped=3, failed=4)
    b = SyncResult(inserted=10, updated=20, skipped=30, failed=40)
    c = a + b
    assert c.inserted == 11
    assert c.updated == 22
    assert c.skipped == 33
    assert c.failed == 44
    assert c.total == 110


def test_sync_result_total():
    r = SyncResult(inserted=2, updated=3, skipped=1, failed=0)
    assert r.total == 6


def test_parse_status_valid():
    svc = IngestionService.__new__(IngestionService)
    from app.enums import MatchStatus
    assert svc._parse_status("scheduled") == MatchStatus.SCHEDULED
    assert svc._parse_status("live") == MatchStatus.LIVE
    assert svc._parse_status("finished") == MatchStatus.FINISHED
    assert svc._parse_status("cancelled") == MatchStatus.CANCELLED


def test_parse_status_unknown_falls_back_to_scheduled():
    svc = IngestionService.__new__(IngestionService)
    from app.enums import MatchStatus
    result = svc._parse_status("NONSENSE_STATUS")
    assert result == MatchStatus.SCHEDULED


def test_enrich_team_groups_fills_unknown():
    teams = [
        RawTeam(external_id="1", name="Brazil", country_code="BRA", group_name="unknown"),
        RawTeam(external_id="2", name="France", country_code="FRA", group_name="unknown"),
    ]
    fixtures = [
        RawFixture(
            external_id="F1",
            home_team_external_id="1",
            away_team_external_id="2",
            kickoff_at=datetime(2026, 6, 11, 15, 0, tzinfo=_TZ),
            status="scheduled",
            stage="group_a",
        )
    ]
    _enrich_team_groups(teams, fixtures)
    assert teams[0].group_name == "A"
    assert teams[1].group_name == "A"


def test_enrich_team_groups_skips_knockout_stages():
    teams = [
        RawTeam(external_id="1", name="Brazil", country_code="BRA", group_name="unknown"),
    ]
    fixtures = [
        RawFixture(
            external_id="F1",
            home_team_external_id="1",
            away_team_external_id="2",
            kickoff_at=datetime(2026, 7, 1, 15, 0, tzinfo=_TZ),
            status="scheduled",
            stage="quarter_finals",
        )
    ]
    _enrich_team_groups(teams, fixtures)
    assert teams[0].group_name == "unknown"


def test_enrich_team_groups_preserves_known_groups():
    teams = [
        RawTeam(external_id="1", name="Brazil", country_code="BRA", group_name="B"),
    ]
    fixtures = [
        RawFixture(
            external_id="F1",
            home_team_external_id="1",
            away_team_external_id="2",
            kickoff_at=datetime(2026, 6, 11, 15, 0, tzinfo=_TZ),
            status="scheduled",
            stage="group_a",
        )
    ]
    _enrich_team_groups(teams, fixtures)
    # Already had a real group; should not be overwritten
    assert teams[0].group_name == "B"


def test_raw_team_validation_rejects_empty_name():
    with pytest.raises(ValidationError):
        RawTeam(external_id="1", name="", country_code="BRA")


def test_raw_team_validation_rejects_invalid_ranking():
    with pytest.raises(ValidationError):
        RawTeam(external_id="1", name="Brazil", country_code="BRA", fifa_ranking=0)


def test_raw_team_validation_rejects_negative_goals():
    with pytest.raises(ValidationError):
        RawTeam(external_id="1", name="Brazil", country_code="BRA", goals_for=-1)


def test_raw_fixture_validation_rejects_negative_score():
    with pytest.raises(ValidationError):
        RawFixture(
            external_id="F1",
            home_team_external_id="1",
            away_team_external_id="2",
            kickoff_at=datetime(2026, 6, 11, 15, 0, tzinfo=_TZ),
            status="scheduled",
            stage="group_a",
            home_score=-1,
        )


def test_provider_timeout_is_provider_error():
    exc = ProviderTimeoutError("timed out")
    assert isinstance(exc, ProviderError)


# ── DB integration tests ──────────────────────────────────────────────────────

async def test_sync_teams_inserts_new(db_session):
    svc = IngestionService(db_session)
    result = await svc.sync_teams([_team("1", "Brazil", "BRA", "A")])
    assert result.inserted == 1
    assert result.updated == 0
    assert result.skipped == 0
    assert result.failed == 0


async def test_sync_teams_idempotent(db_session):
    svc = IngestionService(db_session)
    team_data = [_team("1", "Brazil", "BRA", "A")]
    r1 = await svc.sync_teams(team_data)
    r2 = await svc.sync_teams(team_data)
    assert r1.inserted == 1
    assert r2.inserted == 0
    assert r2.skipped == 1


async def test_sync_teams_detects_update(db_session):
    svc = IngestionService(db_session)
    await svc.sync_teams([_team("1", "Brazil", "BRA", "A")])

    updated_team = RawTeam(
        external_id="1",
        name="Brazil",
        country_code="BRA",
        group_name="A",
        fifa_ranking=3,  # changed from 5
        elo_rating=2000,
    )
    r2 = await svc.sync_teams([updated_team])
    assert r2.updated == 1
    assert r2.inserted == 0


async def test_sync_teams_country_code_fallback(db_session):
    """A team seeded without external_id is matched by country_code and updated."""
    # Insert seed-style team directly (no external_id)
    seed_team = Team(
        name="Argentina",
        country_code="ARG",
        group_name="B",
        fifa_ranking=3,
        elo_rating=2090,
    )
    db_session.add(seed_team)
    await db_session.flush()

    svc = IngestionService(db_session)
    raw = RawTeam(
        external_id="ext-arg",
        name="Argentina",
        country_code="ARG",
        group_name="B",
        fifa_ranking=3,
        elo_rating=2090,
    )
    result = await svc.sync_teams([raw])
    # Should update (sets external_id on existing row), not insert
    assert result.inserted == 0
    assert result.failed == 0


async def test_sync_fixtures_inserts_new(db_session):
    svc = IngestionService(db_session)
    await svc.sync_teams([_team("1", "Brazil", "BRA", "A"), _team("2", "France", "FRA", "A")])
    result = await svc.sync_fixtures([_fixture("F1", "1", "2")])
    assert result.inserted == 1
    assert result.failed == 0


async def test_sync_fixtures_idempotent(db_session):
    svc = IngestionService(db_session)
    await svc.sync_teams([_team("1", "Brazil", "BRA", "A"), _team("2", "France", "FRA", "A")])
    r1 = await svc.sync_fixtures([_fixture("F1", "1", "2")])
    r2 = await svc.sync_fixtures([_fixture("F1", "1", "2")])
    assert r1.inserted == 1
    assert r2.inserted == 0
    assert r2.skipped == 1


async def test_sync_fixtures_detects_status_update(db_session):
    svc = IngestionService(db_session)
    await svc.sync_teams([_team("1", "Brazil", "BRA", "A"), _team("2", "France", "FRA", "A")])
    await svc.sync_fixtures([_fixture("F1", "1", "2", status="scheduled")])

    updated = _fixture("F1", "1", "2", status="finished")
    updated.home_score = 2  # type: ignore[assignment]
    updated.away_score = 1  # type: ignore[assignment]

    # Build a fresh RawFixture with updated scores
    updated_fixture = RawFixture(
        external_id="F1",
        home_team_external_id="1",
        away_team_external_id="2",
        kickoff_at=datetime(2026, 6, 11, 15, 0, tzinfo=_TZ),
        status="finished",
        stage="group_a",
        home_score=2,
        away_score=1,
    )
    r2 = await svc.sync_fixtures([updated_fixture])
    assert r2.updated == 1


async def test_sync_fixtures_skipped_when_team_missing(db_session):
    svc = IngestionService(db_session)
    # Only insert home team, not away team
    await svc.sync_teams([_team("1", "Brazil", "BRA", "A")])
    result = await svc.sync_fixtures([_fixture("F1", "1", "99")])
    assert result.skipped == 1
    assert result.inserted == 0


async def test_sync_fixtures_skipped_when_same_team(db_session):
    """Fixture with identical home and away external_id is skipped."""
    svc = IngestionService(db_session)
    await svc.sync_teams([_team("1", "Brazil", "BRA", "A")])
    result = await svc.sync_fixtures([_fixture("F1", "1", "1")])
    assert result.skipped == 1


async def test_sync_all_graceful_on_provider_teams_error(db_session):
    """When fetch_teams raises ProviderError, sync_all continues with no teams."""
    provider = MockProvider(
        teams_error=ProviderError("API down"),
        fixtures=[],
    )
    svc = IngestionService(db_session)
    results = await svc.sync_all(provider, "WC")
    assert results["teams"].inserted == 0
    assert results["fixtures"].inserted == 0


async def test_sync_all_graceful_on_provider_fixtures_error(db_session):
    """When fetch_fixtures raises ProviderError, teams are still synced."""
    provider = MockProvider(
        teams=[_team("1", "Brazil", "BRA", "A")],
        fixtures_error=ProviderError("fixtures unavailable"),
    )
    svc = IngestionService(db_session)
    results = await svc.sync_all(provider, "WC")
    assert results["teams"].inserted == 1
    assert results["fixtures"].inserted == 0


async def test_sync_all_full_flow(db_session):
    """End-to-end: provider with two teams and one fixture syncs cleanly."""
    provider = MockProvider(
        teams=[
            _team("10", "Brazil", "BRA", "A"),
            _team("20", "Germany", "GER", "A"),
        ],
        fixtures=[_fixture("F1", "10", "20", stage="group_a")],
    )
    svc = IngestionService(db_session)
    results = await svc.sync_all(provider, "WC")
    assert results["teams"].inserted == 2
    assert results["fixtures"].inserted == 1
    assert results["teams"].failed == 0
    assert results["fixtures"].failed == 0


async def test_sync_all_idempotent_second_run(db_session):
    """Running sync_all twice produces zero new inserts on the second run."""
    provider = MockProvider(
        teams=[_team("10", "Brazil", "BRA", "A"), _team("20", "Germany", "GER", "A")],
        fixtures=[_fixture("F1", "10", "20")],
    )
    svc = IngestionService(db_session)
    await svc.sync_all(provider, "WC")
    r2 = await svc.sync_all(provider, "WC")
    assert r2["teams"].inserted == 0
    assert r2["fixtures"].inserted == 0
