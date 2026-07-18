"""
Worker health file.

The worker writes a JSON snapshot to HEALTH_FILE after every tick so that
Docker's healthcheck (and human operators) can confirm the process is alive
and see the outcome of the last sync.

Docker healthcheck reads this file and exits non-zero if checked_at is
older than 2 × sync_interval_seconds (i.e. the worker missed two cycles).
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path

HEALTH_FILE = Path("/tmp/worker_health.json")

logger = logging.getLogger(__name__)


def write_health(
    *,
    duration_s: float = 0.0,
    inserted: int = 0,
    updated: int = 0,
    skipped: int = 0,
    failed: int = 0,
    consecutive_failures: int = 0,
    skipped_no_key: bool = False,
    skipped_locked: bool = False,
) -> None:
    """Write the current worker state to HEALTH_FILE.

    Always overwrites the previous snapshot.  Errors are logged at WARNING
    level and never propagated — a missing health file is not fatal.
    """
    payload: dict = {
        "checked_at": time.time(),
        "duration_s": round(duration_s, 2),
        "inserted": inserted,
        "updated": updated,
        "skipped": skipped,
        "failed": failed,
        "consecutive_failures": consecutive_failures,
        "skipped_no_key": skipped_no_key,
        "skipped_locked": skipped_locked,
    }
    try:
        HEALTH_FILE.write_text(json.dumps(payload))
    except OSError as exc:
        logger.warning("Cannot write health file %s: %s", HEALTH_FILE, exc)


def read_health() -> dict | None:
    """Return the last health snapshot, or None if the file does not exist."""
    try:
        return json.loads(HEALTH_FILE.read_text())
    except (OSError, json.JSONDecodeError):
        return None
