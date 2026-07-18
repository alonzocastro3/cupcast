"""
PostgreSQL session-level advisory lock.

pg_try_advisory_lock acquires a lock immediately or returns false if it is
already held by another session. The lock is automatically released when
the database connection is closed, so callers never deadlock even on crash.

Usage::

    async with advisory_lock(engine, key=MY_KEY) as acquired:
        if not acquired:
            return  # another worker is running — skip this cycle
        ...         # do work while holding the lock
"""
from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


@asynccontextmanager
async def advisory_lock(
    engine: AsyncEngine,
    key: int,
) -> AsyncGenerator[bool, None]:
    """
    Try to acquire a PostgreSQL session-level advisory lock on *key*.

    Yields True if the lock was acquired, False if another session already
    holds it. The lock is always released (or abandoned via connection close)
    before the context exits — callers do not need to release it manually.
    """
    async with engine.connect() as conn:
        row = await conn.execute(
            text("SELECT pg_try_advisory_lock(:key)"),
            {"key": key},
        )
        acquired: bool = row.scalar_one()
        try:
            yield acquired
        finally:
            if acquired:
                await conn.execute(
                    text("SELECT pg_advisory_unlock(:key)"),
                    {"key": key},
                )
