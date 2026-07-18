"""
Ingestion service: validates external payloads and upserts to the database.

Design:
- Teams match on external_id first, then fall back to country_code so that
  seed records (which have no external_id) are recognised and updated.
- Matches match on external_id only; records without one are skipped.
- No records are deleted automatically.
- Stat fields are only overwritten when the incoming value is non-default,
  preserving hand-curated seed data when the API returns zeros.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import MatchStatus
from app.integrations.football.base import (
    FootballDataProvider,
    ProviderError,
    RawFixture,
    RawTeam,
)
from app.models.match import Match
from app.models.team import Team

logger = logging.getLogger(__name__)

_DEFAULT_FIFA_RANKING = 200
_DEFAULT_ELO = 1500


@dataclass
class SyncResult:
    inserted: int = 0
    updated: int = 0
    skipped: int = 0
    failed: int = 0

    @property
    def total(self) -> int:
        return self.inserted + self.updated + self.skipped + self.failed

    def __add__(self, other: "SyncResult") -> "SyncResult":
        return SyncResult(
            inserted=self.inserted + other.inserted,
            updated=self.updated + other.updated,
            skipped=self.skipped + other.skipped,
            failed=self.failed + other.failed,
        )

    def log(self, label: str) -> None:
        logger.info(
            "%s — inserted=%d updated=%d skipped=%d failed=%d",
            label,
            self.inserted,
            self.updated,
            self.skipped,
            self.failed,
        )


class IngestionService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ── Public API ────────────────────────────────────────────────────────────

    async def sync_teams(self, raw_teams: list[RawTeam]) -> SyncResult:
        """Upsert teams from validated external payloads."""
        result = SyncResult()

        for raw in raw_teams:
            try:
                team = await self._find_team(raw.external_id, raw.country_code)
                if team is None:
                    team = Team(
                        external_id=raw.external_id,
                        name=raw.name,
                        country_code=raw.country_code,
                        group_name=raw.group_name,
                        flag_url=raw.flag_url,
                        fifa_ranking=raw.fifa_ranking,
                        elo_rating=raw.elo_rating,
                        recent_form_score=raw.recent_form_score,
                        goals_for=raw.goals_for,
                        goals_against=raw.goals_against,
                        wins=raw.wins,
                        draws=raw.draws,
                        losses=raw.losses,
                    )
                    self._session.add(team)
                    result.inserted += 1
                    logger.debug("Inserted team %s (%s)", raw.name, raw.country_code)
                else:
                    if self._update_team(team, raw):
                        result.updated += 1
                        logger.debug("Updated team %s (%s)", raw.name, raw.country_code)
                    else:
                        result.skipped += 1
            except Exception as exc:
                result.failed += 1
                logger.error("Failed to upsert team ext_id=%s: %s", raw.external_id, exc)

        await self._session.flush()
        result.log("Teams")
        return result

    async def sync_fixtures(self, raw_fixtures: list[RawFixture]) -> SyncResult:
        """Upsert fixtures. Teams must exist in the DB first."""
        result = SyncResult()
        team_map = await self._build_team_ext_id_map()

        for raw in raw_fixtures:
            if not raw.external_id:
                result.skipped += 1
                continue
            try:
                home_id = team_map.get(raw.home_team_external_id)
                away_id = team_map.get(raw.away_team_external_id)

                if home_id is None or away_id is None:
                    logger.warning(
                        "Skipping fixture ext_id=%s: team not found "
                        "(home_ext=%s away_ext=%s)",
                        raw.external_id,
                        raw.home_team_external_id,
                        raw.away_team_external_id,
                    )
                    result.skipped += 1
                    continue

                if home_id == away_id:
                    logger.warning(
                        "Skipping fixture ext_id=%s: home and away team are the same",
                        raw.external_id,
                    )
                    result.skipped += 1
                    continue

                status = self._parse_status(raw.status)
                match = await self._find_match(raw.external_id)

                if match is None:
                    match = Match(
                        external_id=raw.external_id,
                        home_team_id=home_id,
                        away_team_id=away_id,
                        kickoff_at=raw.kickoff_at,
                        status=status,
                        stage=raw.stage,
                        venue=raw.venue,
                        home_score=raw.home_score,
                        away_score=raw.away_score,
                    )
                    self._session.add(match)
                    result.inserted += 1
                    logger.debug("Inserted fixture ext_id=%s", raw.external_id)
                else:
                    if self._update_match(match, raw, status):
                        result.updated += 1
                        logger.debug("Updated fixture ext_id=%s", raw.external_id)
                    else:
                        result.skipped += 1

            except Exception as exc:
                result.failed += 1
                logger.error("Failed to upsert fixture ext_id=%s: %s", raw.external_id, exc)

        await self._session.flush()
        result.log("Fixtures")
        return result

    async def sync_all(
        self,
        provider: FootballDataProvider,
        tournament_id: str,
    ) -> dict[str, SyncResult]:
        """
        Fetch from provider then upsert teams and fixtures in one transaction.
        Teams are synced first so fixture FK lookups succeed.
        """
        results: dict[str, SyncResult] = {}

        try:
            raw_teams = await provider.fetch_teams(tournament_id)
        except ProviderError as exc:
            logger.error("fetch_teams failed: %s", exc)
            raw_teams = []

        try:
            raw_fixtures = await provider.fetch_fixtures(tournament_id)
        except ProviderError as exc:
            logger.error("fetch_fixtures failed: %s", exc)
            raw_fixtures = []

        # Back-fill group_name from fixture data when teams endpoint omitted it
        _enrich_team_groups(raw_teams, raw_fixtures)

        results["teams"] = await self.sync_teams(raw_teams)
        results["fixtures"] = await self.sync_fixtures(raw_fixtures)
        return results

    # ── Private helpers ───────────────────────────────────────────────────────

    async def _find_team(self, external_id: str, country_code: str) -> Team | None:
        if external_id:
            r = await self._session.execute(
                select(Team).where(Team.external_id == external_id)
            )
            team = r.scalar_one_or_none()
            if team is not None:
                return team
        r = await self._session.execute(
            select(Team).where(Team.country_code == country_code)
        )
        return r.scalar_one_or_none()

    async def _find_match(self, external_id: str) -> Match | None:
        r = await self._session.execute(
            select(Match).where(Match.external_id == external_id)
        )
        return r.scalar_one_or_none()

    async def _build_team_ext_id_map(self) -> dict[str, int]:
        rows = await self._session.execute(
            select(Team.external_id, Team.id).where(Team.external_id.is_not(None))
        )
        return {ext_id: team_id for ext_id, team_id in rows.all()}

    @staticmethod
    def _update_team(team: Team, raw: RawTeam) -> bool:
        """Apply non-default fields from raw to team. Returns True if anything changed."""
        changed = False

        always_update: dict[str, object] = {
            "external_id": raw.external_id,
            "name": raw.name,
            "flag_url": raw.flag_url,
        }
        if raw.group_name not in ("unknown", ""):
            always_update["group_name"] = raw.group_name

        stat_updates: dict[str, object] = {}
        if raw.fifa_ranking != _DEFAULT_FIFA_RANKING:
            stat_updates["fifa_ranking"] = raw.fifa_ranking
        if raw.elo_rating != _DEFAULT_ELO:
            stat_updates["elo_rating"] = raw.elo_rating
        if raw.recent_form_score > 0:
            stat_updates["recent_form_score"] = raw.recent_form_score
        if raw.goals_for > 0:
            stat_updates["goals_for"] = raw.goals_for
        if raw.goals_against > 0:
            stat_updates["goals_against"] = raw.goals_against
        if raw.wins > 0:
            stat_updates["wins"] = raw.wins
        if raw.draws > 0:
            stat_updates["draws"] = raw.draws
        if raw.losses > 0:
            stat_updates["losses"] = raw.losses

        for attr, value in {**always_update, **stat_updates}.items():
            if getattr(team, attr) != value:
                setattr(team, attr, value)
                changed = True
        return changed

    @staticmethod
    def _update_match(match: Match, raw: RawFixture, status: MatchStatus) -> bool:
        """Apply mutable fields from raw to match. Returns True if anything changed."""
        changed = False
        updates: dict[str, object] = {
            "status": status,
            "venue": raw.venue,
            "home_score": raw.home_score,
            "away_score": raw.away_score,
            "stage": raw.stage,
            "kickoff_at": raw.kickoff_at,
        }
        for attr, value in updates.items():
            if getattr(match, attr) != value:
                setattr(match, attr, value)
                changed = True
        return changed

    @staticmethod
    def _parse_status(raw_status: str) -> MatchStatus:
        try:
            return MatchStatus(raw_status)
        except ValueError:
            logger.warning("Unknown match status %r, defaulting to scheduled", raw_status)
            return MatchStatus.SCHEDULED


def _enrich_team_groups(raw_teams: list[RawTeam], raw_fixtures: list[RawFixture]) -> None:
    """
    Back-fill group_name on RawTeam objects that have group_name='unknown'
    by deriving the group letter from associated fixture stage slugs.
    """
    team_ids = {t.external_id for t in raw_teams}
    derived: dict[str, str] = {}

    for f in raw_fixtures:
        if not f.stage.startswith("group_"):
            continue
        letter = f.stage.split("_", 1)[1].upper()  # "group_a" → "A"
        for ext_id in (f.home_team_external_id, f.away_team_external_id):
            if ext_id in team_ids and ext_id not in derived:
                derived[ext_id] = letter

    for t in raw_teams:
        if t.group_name in ("unknown", "") and t.external_id in derived:
            t.group_name = derived[t.external_id]
