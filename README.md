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

## API Endpoints

All endpoints are under `/api/v1`. Interactive docs at `http://localhost:8000/docs`.

### Teams

```bash
# List all teams (paginated)
curl "http://localhost:8000/api/v1/teams"
curl "http://localhost:8000/api/v1/teams?limit=5&offset=0"

# Get a single team
curl "http://localhost:8000/api/v1/teams/1"
```

### Matches

```bash
# List all matches
curl "http://localhost:8000/api/v1/matches"

# Filter by status (scheduled | live | finished | cancelled)
curl "http://localhost:8000/api/v1/matches?status=scheduled"

# Filter by stage
curl "http://localhost:8000/api/v1/matches?stage=group_a"

# Filter by team (home OR away)
curl "http://localhost:8000/api/v1/matches?team_id=1"

# Combine filters + pagination
curl "http://localhost:8000/api/v1/matches?status=live&stage=group_b&limit=10&offset=0"

# Get a single match
curl "http://localhost:8000/api/v1/matches/1"

# Prediction summary for a match
curl "http://localhost:8000/api/v1/matches/1/prediction-summary"

# Model prediction for a match
curl "http://localhost:8000/api/v1/matches/1/model-prediction"
```

### Predictions (anonymous submission)

```bash
# Submit a prediction (outcome only)
curl -X POST "http://localhost:8000/api/v1/matches/1/predictions" \
  -H "Content-Type: application/json" \
  -d '{"session_id": "my-browser-uuid", "predicted_outcome": "home_win"}'

# Submit a prediction with score guess
curl -X POST "http://localhost:8000/api/v1/matches/1/predictions" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "my-browser-uuid",
    "predicted_outcome": "home_win",
    "predicted_home_score": 2,
    "predicted_away_score": 1
  }'
```

**Request fields:**
| Field | Type | Required | Rules |
|-------|------|----------|-------|
| `session_id` | string | yes | 1–36 chars |
| `predicted_outcome` | `home_win` \| `draw` \| `away_win` | yes | |
| `predicted_home_score` | integer ≥ 0 | no | must be paired with away score; must agree with outcome |
| `predicted_away_score` | integer ≥ 0 | no | must be paired with home score |

**Response (201 Created):**
```json
{
  "prediction": {
    "id": 1,
    "match_id": 1,
    "session_id": "my-browser-uuid",
    "predicted_outcome": "home_win",
    "predicted_home_score": 2,
    "predicted_away_score": 1,
    "created_at": "2026-06-15T15:00:00Z"
  },
  "community_summary": {
    "match_id": 1,
    "total_predictions": 151,
    "home_win_count": 91,
    "draw_count": 30,
    "away_win_count": 30,
    "home_win_percentage": 60.26,
    "draw_percentage": 19.87,
    "away_win_percentage": 19.87
  }
}
```

**Error responses:**
| Status | Reason |
|--------|--------|
| 404 | Match not found |
| 409 | Session has already predicted this match |
| 422 | Invalid field values (bad outcome, negative score, score/outcome mismatch, partial scores) |

## Caching

All read endpoints are served from Redis when available. Redis failures are swallowed silently and the request falls through to PostgreSQL, so the API stays up even if Redis is down.

| Endpoint | Cache key pattern | TTL |
|----------|-------------------|-----|
| `GET /api/v1/teams` | `cupcast:teams:list:{limit}:{offset}` | 10 min |
| `GET /api/v1/teams/{id}` | `cupcast:teams:{id}` | 10 min |
| `GET /api/v1/matches` | `cupcast:matches:list:{limit}:{offset}:{status}:{stage}:{team_id}` | 2 min |
| `GET /api/v1/matches/{id}` | `cupcast:matches:{id}` | 2 min |
| `GET /api/v1/matches/{id}/model-prediction` | `cupcast:matches:{id}:model-prediction` | 5 min |
| `GET /api/v1/matches/{id}/prediction-summary` | `cupcast:matches:{id}:prediction-summary` | 30 sec |

`POST /api/v1/matches/{id}/predictions` deletes the prediction-summary cache key immediately after inserting the new prediction, so the next GET returns a fresh count from PostgreSQL.

Cache behaviour is logged at `DEBUG` level (`cache hit`, `cache miss`, `cache invalidated`). Errors are logged at `WARNING` level but never propagated to API consumers.

**Paginated response shape:**
```json
{
  "items": [...],
  "total": 12,
  "limit": 20,
  "offset": 0
}
```

**Prediction summary shape:**
```json
{
  "match_id": 1,
  "total_predictions": 150,
  "home_win_count": 90,
  "draw_count": 30,
  "away_win_count": 30,
  "home_win_percentage": 60.0,
  "draw_percentage": 20.0,
  "away_win_percentage": 20.0
}
```

## Prediction Engine

`GET /api/v1/matches/{match_id}/model-prediction` returns a deterministic, explainable probability estimate with no ML dependencies.

### Formula

For each team a **strength score** is computed as a weighted sum of five normalized features:

| Feature | Weight | Source field(s) |
|---------|--------|-----------------|
| Attacking | 25 % | `goals_for / (goals_for + goals_against)` |
| Elo | 25 % | sigmoid((elo_rating − 1500) / 200) |
| Defensive | 20 % | `1 − goals_against / (goals_for + goals_against)` |
| FIFA ranking | 20 % | `1 − log(rank) / log(210)` (rank 1 → 1.0) |
| Recent form | 5 % | `recent_form_score` clamped to [0, 1] |
| Win rate | 5 % | `wins / (wins + draws + losses)` |

A **home advantage bonus** (+0.05) is added to the home score. A **draw score** is derived as a baseline fraction of the average team strength. The three raw scores are passed through **softmax** to produce probabilities that sum to 1.0. Values are clamped to [0.01, 0.98] before re-normalizing to prevent degenerate outputs on extreme inputs.

**Confidence** is scaled as `(max_probability − 0.333) / 0.667` and represents how far the leading outcome is above a uniform three-way split.

The engine lives in `backend/app/prediction_engine/` and is designed to be swapped out for a trained model without changing the API contract.

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

## Data Ingestion

CupCast can pull live team and fixture data from [football-data.org](https://www.football-data.org/) and upsert it into the database. The seed data is never deleted — ingestion only inserts or updates records.

### 1. Get a free API key

Register at https://www.football-data.org/client/register. The free tier covers World Cup fixtures.

### 2. Set the environment variable

Add to your `backend/.env` file:

```env
FOOTBALL_API_KEY=your_key_here
```

Optional settings (defaults shown):

```env
FOOTBALL_TOURNAMENT_ID=WC
FOOTBALL_API_BASE_URL=https://api.football-data.org
FOOTBALL_API_TIMEOUT=10.0
FOOTBALL_API_MAX_RETRIES=3
```

### 3. Run the sync

```bash
# Via Docker
docker compose exec backend python -m app.jobs.sync_tournament_data

# Locally (inside the backend venv)
python -m app.jobs.sync_tournament_data
```

### Output

```
2026-07-18T12:00:00 [INFO] __main__ — Starting sync — tournament=WC provider=https://api.football-data.org
2026-07-18T12:00:02 [INFO] app.services.ingestion_service — Teams — inserted=32 updated=0 skipped=0 failed=0
2026-07-18T12:00:03 [INFO] app.services.ingestion_service — Fixtures — inserted=64 updated=0 skipped=0 failed=0
2026-07-18T12:00:03 [INFO] __main__ — Sync complete — no failures.
```

If `FOOTBALL_API_KEY` is not set the command exits immediately with a clear message (exit code 1) and no database changes are made. The seed data remains intact.

## Background Worker

CupCast includes a dedicated worker service that syncs tournament data on a configurable interval. It runs in a **separate Docker container** — the FastAPI web process never schedules background work.

### Architecture

```
┌───────────┐   HTTP    ┌──────────────────────────────────┐
│  Frontend │ ────────► │  backend  (FastAPI / uvicorn)    │
└───────────┘           └──────────────────────────────────┘
                                        │
                              PostgreSQL + Redis (shared)
                                        │
                        ┌──────────────────────────────────┐
                        │  worker  (asyncio loop)          │
                        │                                  │
                        │  every SYNC_INTERVAL_SECONDS:    │
                        │  1. pg_try_advisory_lock         │
                        │  2. fetch from football-data.org │
                        │  3. upsert teams + fixtures      │
                        │  4. release lock                 │
                        │  5. write /tmp/worker_health.json│
                        └──────────────────────────────────┘
```

### Concurrency safety

The worker acquires a **PostgreSQL session-level advisory lock** (`pg_try_advisory_lock`) at the start of each sync. If a second worker replica tries to start while the first is running, it skips the cycle and logs:

```
Advisory lock (key=20261001) not acquired — another worker is syncing. Skipping this cycle.
```

The lock is released automatically when the connection closes, so crashes never deadlock.

### Configuration

| Variable | Default | Description |
|---|---|---|
| `SYNC_INTERVAL_SECONDS` | `900` | Seconds between sync cycles (15 min) |
| `SYNC_LOCK_KEY` | `20261001` | PostgreSQL advisory lock integer key |
| `FOOTBALL_API_KEY` | *(none)* | Required for live data; worker keeps running without it |

Add to `backend/.env` (or the root `.env` used by Docker Compose):

```env
FOOTBALL_API_KEY=your_key_here
SYNC_INTERVAL_SECONDS=900
```

### Starting the worker

Included in `docker-compose.yml` — starts automatically with:

```bash
docker compose up --build
```

To run standalone (local dev, inside the backend venv):

```bash
cd backend
python -m app.worker.main
```

### Worker logs

```
2026-07-18T15:00:00 [INFO] app.worker.scheduler — Worker started — interval=900s tournament=WC lock_key=20261001
2026-07-18T15:00:00 [INFO] app.worker.scheduler — Sync starting — tournament=WC
2026-07-18T15:00:12 [INFO] app.services.ingestion_service — Teams — inserted=0 updated=4 skipped=28 failed=0
2026-07-18T15:00:13 [INFO] app.services.ingestion_service — Fixtures — inserted=2 updated=10 skipped=52 failed=0
2026-07-18T15:00:13 [INFO] app.worker.scheduler — Sync finished in 13.1s — inserted=2 updated=14 skipped=80 failed=0
```

### Health check

Docker polls `/tmp/worker_health.json` every 60 s. The worker is healthy if `checked_at` is within `2 × SYNC_INTERVAL_SECONDS` of now. Inspect directly:

```bash
docker compose exec worker cat /tmp/worker_health.json
```

```json
{
  "checked_at": 1752847213.4,
  "duration_s": 13.1,
  "inserted": 2,
  "updated": 14,
  "skipped": 80,
  "failed": 0,
  "consecutive_failures": 0,
  "skipped_no_key": false,
  "skipped_locked": false
}
```

### Graceful shutdown

The worker installs `SIGTERM` and `SIGINT` handlers that call `scheduler.stop()`. The loop exits within 1 second (sleep ticks are 1 s). Docker Compose sends `SIGTERM` on `docker compose stop`, so no sync is ever left half-finished.

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
├── docker-compose.yml           # db, redis, backend, worker, frontend
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
│   │   │   ├── team.py          # Team ORM model (+ external_id)
│   │   │   ├── match.py         # Match ORM model
│   │   │   └── prediction.py    # Prediction ORM model
│   │   ├── schemas/
│   │   │   ├── team.py          # Team Pydantic schemas
│   │   │   ├── match.py         # Match Pydantic schemas
│   │   │   └── prediction.py    # Prediction Pydantic schemas
│   │   ├── integrations/
│   │   │   └── football/
│   │   │       ├── base.py      # FootballDataProvider ABC + RawTeam/RawFixture
│   │   │       └── provider.py  # football-data.org v4 adapter (retries + backoff)
│   │   ├── jobs/
│   │   │   └── sync_tournament_data.py  # One-shot CLI sync command
│   │   ├── services/
│   │   │   └── ingestion_service.py     # Upsert logic + SyncResult
│   │   └── worker/
│   │       ├── main.py          # Entry point: asyncio loop + SIGTERM handler
│   │       ├── scheduler.py     # SyncScheduler (interval + tick logic)
│   │       ├── lock.py          # PostgreSQL advisory lock context manager
│   │       └── health.py        # /tmp/worker_health.json writer/reader
│   └── tests/
│       ├── conftest.py          # HTTP client + test DB fixtures
│       ├── test_health.py
│       ├── test_models.py       # DB constraint integration tests
│       ├── test_seed.py         # Seed correctness + idempotency
│       ├── test_ingestion.py    # Ingestion service: upserts, idempotency, errors
│       └── test_worker.py       # Advisory lock, scheduler ticks, failure recovery
└── frontend/
    ├── Dockerfile
    ├── package.json
    └── src/app/                 # Next.js App Router
```
