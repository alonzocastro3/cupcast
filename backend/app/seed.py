"""Idempotent seed script — safe to run multiple times."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.enums import MatchStatus
from app.models.match import Match
from app.models.team import Team

_TZ = timezone.utc

_TEAMS: list[dict] = [
    {
        "name": "Brazil",
        "country_code": "BRA",
        "group_name": "A",
        "fifa_ranking": 1,
        "elo_rating": 2080,
        "recent_form_score": 4.2,
        "wins": 8,
        "draws": 1,
        "losses": 1,
        "goals_for": 24,
        "goals_against": 7,
    },
    {
        "name": "France",
        "country_code": "FRA",
        "group_name": "A",
        "fifa_ranking": 2,
        "elo_rating": 2055,
        "recent_form_score": 3.9,
        "wins": 7,
        "draws": 2,
        "losses": 1,
        "goals_for": 20,
        "goals_against": 9,
    },
    {
        "name": "Spain",
        "country_code": "ESP",
        "group_name": "A",
        "fifa_ranking": 8,
        "elo_rating": 1992,
        "recent_form_score": 3.6,
        "wins": 6,
        "draws": 2,
        "losses": 2,
        "goals_for": 18,
        "goals_against": 10,
    },
    {
        "name": "Germany",
        "country_code": "GER",
        "group_name": "A",
        "fifa_ranking": 16,
        "elo_rating": 1974,
        "recent_form_score": 3.1,
        "wins": 5,
        "draws": 3,
        "losses": 2,
        "goals_for": 17,
        "goals_against": 12,
    },
    {
        "name": "Argentina",
        "country_code": "ARG",
        "group_name": "B",
        "fifa_ranking": 3,
        "elo_rating": 2090,
        "recent_form_score": 4.4,
        "wins": 9,
        "draws": 1,
        "losses": 0,
        "goals_for": 27,
        "goals_against": 5,
    },
    {
        "name": "England",
        "country_code": "ENG",
        "group_name": "B",
        "fifa_ranking": 4,
        "elo_rating": 2014,
        "recent_form_score": 3.7,
        "wins": 6,
        "draws": 3,
        "losses": 1,
        "goals_for": 19,
        "goals_against": 8,
    },
    {
        "name": "Portugal",
        "country_code": "POR",
        "group_name": "B",
        "fifa_ranking": 6,
        "elo_rating": 1985,
        "recent_form_score": 3.5,
        "wins": 6,
        "draws": 2,
        "losses": 2,
        "goals_for": 21,
        "goals_against": 11,
    },
    {
        "name": "Netherlands",
        "country_code": "NED",
        "group_name": "B",
        "fifa_ranking": 7,
        "elo_rating": 1979,
        "recent_form_score": 3.3,
        "wins": 5,
        "draws": 3,
        "losses": 2,
        "goals_for": 16,
        "goals_against": 10,
    },
]

# Template rows — home/away as country codes, resolved to IDs at runtime
_MATCH_TEMPLATES: list[dict] = [
    # ── Group A ───────────────────────────────────────────────────────────────
    {"external_id": "SEED-GRP-A-1", "home": "BRA", "away": "GER", "stage": "group_a",
     "kickoff_at": datetime(2026, 6, 11, 15, 0, tzinfo=_TZ)},
    {"external_id": "SEED-GRP-A-2", "home": "FRA", "away": "ESP", "stage": "group_a",
     "kickoff_at": datetime(2026, 6, 12, 15, 0, tzinfo=_TZ)},
    {"external_id": "SEED-GRP-A-3", "home": "BRA", "away": "ESP", "stage": "group_a",
     "kickoff_at": datetime(2026, 6, 15, 15, 0, tzinfo=_TZ)},
    {"external_id": "SEED-GRP-A-4", "home": "GER", "away": "FRA", "stage": "group_a",
     "kickoff_at": datetime(2026, 6, 16, 15, 0, tzinfo=_TZ)},
    {"external_id": "SEED-GRP-A-5", "home": "BRA", "away": "FRA", "stage": "group_a",
     "kickoff_at": datetime(2026, 6, 19, 15, 0, tzinfo=_TZ)},
    {"external_id": "SEED-GRP-A-6", "home": "ESP", "away": "GER", "stage": "group_a",
     "kickoff_at": datetime(2026, 6, 19, 18, 0, tzinfo=_TZ)},
    # ── Group B ───────────────────────────────────────────────────────────────
    {"external_id": "SEED-GRP-B-1", "home": "ARG", "away": "ENG", "stage": "group_b",
     "kickoff_at": datetime(2026, 6, 11, 18, 0, tzinfo=_TZ)},
    {"external_id": "SEED-GRP-B-2", "home": "POR", "away": "NED", "stage": "group_b",
     "kickoff_at": datetime(2026, 6, 12, 18, 0, tzinfo=_TZ)},
    {"external_id": "SEED-GRP-B-3", "home": "ARG", "away": "POR", "stage": "group_b",
     "kickoff_at": datetime(2026, 6, 15, 18, 0, tzinfo=_TZ)},
    {"external_id": "SEED-GRP-B-4", "home": "ENG", "away": "NED", "stage": "group_b",
     "kickoff_at": datetime(2026, 6, 16, 18, 0, tzinfo=_TZ)},
    {"external_id": "SEED-GRP-B-5", "home": "ARG", "away": "NED", "stage": "group_b",
     "kickoff_at": datetime(2026, 6, 19, 21, 0, tzinfo=_TZ)},
    {"external_id": "SEED-GRP-B-6", "home": "POR", "away": "ENG", "stage": "group_b",
     "kickoff_at": datetime(2026, 6, 19, 21, 0, tzinfo=_TZ)},
]


async def seed(session: AsyncSession) -> None:
    """Insert seed data. Safe to call multiple times — uses ON CONFLICT DO NOTHING."""
    await session.execute(pg_insert(Team).values(_TEAMS).on_conflict_do_nothing())
    await session.flush()

    rows = await session.execute(select(Team.id, Team.country_code))
    id_map: dict[str, int] = {row.country_code: row.id for row in rows}

    matches = [
        {
            "external_id": t["external_id"],
            "home_team_id": id_map[t["home"]],
            "away_team_id": id_map[t["away"]],
            "kickoff_at": t["kickoff_at"],
            "status": MatchStatus.SCHEDULED,
            "stage": t["stage"],
        }
        for t in _MATCH_TEMPLATES
    ]

    await session.execute(pg_insert(Match).values(matches).on_conflict_do_nothing())
    await session.flush()


async def _main() -> None:
    async with AsyncSessionLocal() as session:
        async with session.begin():
            await seed(session)
    print(f"Seeded {len(_TEAMS)} teams and {len(_MATCH_TEMPLATES)} matches.")


if __name__ == "__main__":
    asyncio.run(_main())
