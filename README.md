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
# Generate a new migration (run from backend/ or via docker compose exec)
docker compose exec backend alembic revision --autogenerate -m "describe change"

# Apply all pending migrations
docker compose exec backend alembic upgrade head

# Roll back one migration
docker compose exec backend alembic downgrade -1
```

## Running Tests

```bash
docker compose exec backend pytest
# or locally:
cd backend && pytest
```

## Project Structure

```
cupcast/
├── docker-compose.yml
├── .env.example
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── alembic/           # Alembic migration env + versions
│   ├── app/
│   │   ├── main.py        # FastAPI app, CORS, routers
│   │   ├── config.py      # Typed settings via pydantic-settings
│   │   ├── database.py    # Async SQLAlchemy engine + Base + get_db
│   │   └── cache.py       # Redis async client
│   └── tests/
└── frontend/
    ├── Dockerfile
    ├── package.json
    └── src/app/           # Next.js App Router
```
