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
