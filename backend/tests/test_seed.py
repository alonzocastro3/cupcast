"""Tests for seed data correctness and idempotency."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.match import Match
from app.models.team import Team
from app.seed import seed


async def test_seed_inserts_all_teams(db_session: AsyncSession) -> None:
    await seed(db_session)

    count = (await db_session.execute(select(func.count()).select_from(Team))).scalar()
    assert count == 8


async def test_seed_inserts_all_matches(db_session: AsyncSession) -> None:
    await seed(db_session)

    count = (await db_session.execute(select(func.count()).select_from(Match))).scalar()
    assert count == 12


async def test_seed_creates_two_groups(db_session: AsyncSession) -> None:
    await seed(db_session)

    groups = (
        await db_session.execute(
            select(Team.group_name).distinct().order_by(Team.group_name)
        )
    ).scalars().all()
    assert sorted(groups) == ["A", "B"]


async def test_seed_is_idempotent_teams(db_session: AsyncSession) -> None:
    await seed(db_session)
    await seed(db_session)

    count = (await db_session.execute(select(func.count()).select_from(Team))).scalar()
    assert count == 8


async def test_seed_is_idempotent_matches(db_session: AsyncSession) -> None:
    await seed(db_session)
    await seed(db_session)

    count = (await db_session.execute(select(func.count()).select_from(Match))).scalar()
    assert count == 12


async def test_seed_teams_have_valid_stats(db_session: AsyncSession) -> None:
    await seed(db_session)

    teams = (await db_session.execute(select(Team))).scalars().all()
    for team in teams:
        assert team.fifa_ranking >= 1
        assert team.elo_rating > 0
        assert team.goals_for >= 0
        assert team.goals_against >= 0
        assert team.wins + team.draws + team.losses == 10


async def test_seed_matches_reference_valid_teams(db_session: AsyncSession) -> None:
    await seed(db_session)

    team_ids = set(
        (await db_session.execute(select(Team.id))).scalars().all()
    )
    matches = (await db_session.execute(select(Match))).scalars().all()

    for match in matches:
        assert match.home_team_id in team_ids
        assert match.away_team_id in team_ids
        assert match.home_team_id != match.away_team_id
