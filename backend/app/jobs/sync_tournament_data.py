"""
Sync tournament data from the configured football data provider.

Usage:
    python -m app.jobs.sync_tournament_data

Required environment variable:
    FOOTBALL_API_KEY  — API key for football-data.org

Optional environment variables (with defaults):
    FOOTBALL_TOURNAMENT_ID   — competition code (default: "WC")
    FOOTBALL_API_BASE_URL    — base URL (default: https://api.football-data.org)
    FOOTBALL_API_TIMEOUT     — request timeout in seconds (default: 10.0)
    FOOTBALL_API_MAX_RETRIES — retries on transient errors (default: 3)

Exit codes:
    0 — sync completed (individual record failures are logged, not fatal)
    1 — FOOTBALL_API_KEY not configured
"""
from __future__ import annotations

import asyncio
import logging
import sys

from app.config import settings
from app.database import AsyncSessionLocal
from app.integrations.football.provider import FootballDataOrgProvider
from app.services.ingestion_service import IngestionService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)


async def _run() -> None:
    if not settings.football_api_key:
        print(
            "FOOTBALL_API_KEY is not configured.\n"
            "Add it to your .env file or shell environment before running this command.\n"
            "See backend/.env.example for all available variables.",
            file=sys.stderr,
        )
        sys.exit(1)

    provider = FootballDataOrgProvider(
        api_key=settings.football_api_key,
        base_url=settings.football_api_base_url,
        timeout=settings.football_api_timeout,
        max_retries=settings.football_api_max_retries,
    )

    logger.info(
        "Starting sync — tournament=%s provider=%s",
        settings.football_tournament_id,
        settings.football_api_base_url,
    )

    async with AsyncSessionLocal() as session:
        async with session.begin():
            service = IngestionService(session)
            results = await service.sync_all(provider, settings.football_tournament_id)

    total_failed = 0
    for entity, result in results.items():
        result.log(entity.capitalize())
        total_failed += result.failed

    if total_failed:
        logger.warning("Sync complete with %d failed record(s).", total_failed)
    else:
        logger.info("Sync complete — no failures.")


if __name__ == "__main__":
    asyncio.run(_run())
