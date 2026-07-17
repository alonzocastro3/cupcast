# CupCast

World Cup prediction and live intelligence dashboard.

## Stack

| Layer    | Technology                        |
|----------|-----------------------------------|
| Frontend | Next.js 15, TypeScript, Tailwind  |
| Backend  | FastAPI, Python 3.12              |
| Database | PostgreSQL 16                     |
| Cache    | Redis 7                           |
| Dev      | Docker Compose                    |

## Quick Start

### Prerequisites

- Docker and Docker Compose v2

### 1. Configure environment

```bash
cp .env.example .env
```

Edit `.env` if you need non-default credentials.

### 2. Start all services

```bash
docker compose up --build
```

| Service      | URL                          |
|--------------|------------------------------|
| Frontend     | http://localhost:3000        |
| Backend API  | http://localhost:8000        |
| API docs     | http://localhost:8000/docs   |
| Redoc        | http://localhost:8000/redoc  |

### 3. Verify each service

```bash
# Backend health
curl http://localhost:8000/health

# PostgreSQL
docker compose exec db psql -U cupcast -c "\l"

# Redis
docker compose exec redis redis-cli ping
```

## Local Development (without Docker)

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
cp .env.example .env             # edit DATABASE_URL and REDIS_URL
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
cp .env.local.example .env.local
npm install
npm run dev
```

## Database Migrations

```bash
# Apply all pending migrations (required after first docker compose up)
docker compose exec backend alembic upgrade head

# Generate a migration after changing models
docker compose exec backend alembic revision --autogenerate -m "describe change"

# Roll back one step
docker compose exec backend alembic downgrade -1

# Check current state
docker compose exec backend alembic current
```

## Seed Data

Populates 8 teams (Groups A & B) and 12 group-stage matches. Safe to run multiple times.

```bash
docker compose exec backend python -m app.seed
```

To reseed after running tests (tests use an isolated `cupcast_test` database and do not touch `cupcast`):

```bash
docker compose exec backend python -m app.seed
```

## Running Tests

Tests run against a separate `cupcast_test` database (created automatically by the test suite).

```bash
# All tests with verbose output
docker compose exec backend pytest -v

# A single file
docker compose exec backend pytest tests/test_models.py -v
docker compose exec backend pytest tests/test_seed.py -v

# Locally (requires Postgres + Redis running)
cd backend && pytest -v
```

## Project Structure

```
cupcast/
├── docker-compose.yml
├── .env.example
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── alembic/
│   │   ├── env.py               # Async migration runner
│   │   └── versions/            # Generated migration files
│   ├── app/
│   │   ├── main.py              # FastAPI app, CORS
│   │   ├── config.py            # Typed settings (pydantic-settings)
│   │   ├── database.py          # Async SQLAlchemy engine + Base + get_db
│   │   ├── cache.py             # Redis async client
│   │   ├── enums.py             # MatchStatus, PredictedOutcome
│   │   ├── seed.py              # Idempotent seed script
│   │   ├── models/
│   │   │   ├── team.py          # Team ORM model
│   │   │   ├── match.py         # Match ORM model
│   │   │   └── prediction.py    # Prediction ORM model
│   │   └── schemas/
│   │       ├── team.py          # Team Pydantic schemas
│   │       ├── match.py         # Match Pydantic schemas
│   │       └── prediction.py    # Prediction Pydantic schemas
│   └── tests/
│       ├── conftest.py          # HTTP client + test DB fixtures
│       ├── test_health.py
│       ├── test_models.py       # DB constraint integration tests
│       └── test_seed.py         # Seed correctness + idempotency
└── frontend/
    ├── Dockerfile
    ├── package.json
    └── src/app/                 # Next.js App Router
```
