from __future__ import annotations

from collections.abc import AsyncGenerator
from urllib.parse import urlparse

import asyncpg
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

import app.models  # noqa: F401 — registers all models with Base.metadata
from app.config import settings
from app.database import Base
from app.main import app as fastapi_app

_TEST_DB_URL = settings.database_url.rsplit("/", 1)[0] + "/cupcast_test"


async def _ensure_test_db() -> None:
    """Create cupcast_test database if it does not already exist."""
    parsed = urlparse(settings.database_url.replace("postgresql+asyncpg://", "postgresql://"))
    conn = await asyncpg.connect(
        host=parsed.hostname,
        port=parsed.port or 5432,
        user=parsed.username,
        password=parsed.password,
        database="postgres",
    )
    try:
        await conn.execute("CREATE DATABASE cupcast_test")
    except asyncpg.exceptions.DuplicateDatabaseError:
        pass
    finally:
        await conn.close()


# ── HTTP client ──────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(transport=ASGITransport(app=fastapi_app), base_url="http://test") as ac:
        yield ac


# ── Database ─────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def test_engine():
    """Fresh schema in cupcast_test for each test function."""
    await _ensure_test_db()
    engine = create_async_engine(_TEST_DB_URL, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Session that always rolls back — leaves cupcast_test clean."""
    factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with factory() as session:
        yield session
        await session.rollback()
