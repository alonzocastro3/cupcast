# CupCast Backend

FastAPI backend for the CupCast World Cup 2026 prediction dashboard.

## Quick start

```bash
cp .env.example .env   # fill in optional API keys
docker compose up
```

The API is available at `http://localhost:8000`. Interactive docs at `/docs`.

---

## Environment variables

All variables are optional unless marked required.

### Core

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://cupcast:cupcast@localhost:5432/cupcast` | PostgreSQL connection string |
| `REDIS_URL` | `redis://localhost:6379` | Redis connection string |
| `CORS_ORIGINS` | `http://localhost:3000` | Comma-separated list of allowed origins |

### Football data provider

Live match and team data from [football-data.org](https://www.football-data.org/client/register) (free tier).

| Variable | Default | Description |
|---|---|---|
| `FOOTBALL_API_KEY` | _(none)_ | API key — sync is skipped when absent |
| `FOOTBALL_API_BASE_URL` | `https://api.football-data.org` | |
| `FOOTBALL_TOURNAMENT_ID` | `WC` | Tournament code |
| `FOOTBALL_API_TIMEOUT` | `10.0` | Per-request timeout (seconds) |
| `FOOTBALL_API_MAX_RETRIES` | `3` | Retry attempts on transient errors |

### News provider

World Cup articles from [NewsAPI.org](https://newsapi.org/register) (free developer tier).

| Variable | Default | Description |
|---|---|---|
| `NEWS_API_KEY` | _(none)_ | API key — news endpoint returns empty list when absent |
| `NEWS_API_BASE_URL` | `https://newsapi.org` | |
| `NEWS_QUERY` | `FIFA World Cup 2026` | Search query sent to NewsAPI |
| `NEWS_API_TIMEOUT` | `10.0` | Per-request timeout (seconds) |
| `NEWS_API_MAX_RETRIES` | `2` | Retry attempts on transient errors |

### Background worker

| Variable | Default | Description |
|---|---|---|
| `SYNC_INTERVAL_SECONDS` | `900` | Seconds between football data syncs |
| `SYNC_LOCK_KEY` | `20261001` | PostgreSQL advisory lock key (change only if you run multiple apps sharing the same DB) |

---

## API endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/teams` | Paginated team list |
| `GET` | `/api/v1/teams/{id}` | Single team |
| `GET` | `/api/v1/matches` | Paginated match list (filter by status, stage, team) |
| `GET` | `/api/v1/matches/{id}` | Single match |
| `GET` | `/api/v1/matches/{id}/prediction-summary` | Community prediction breakdown |
| `GET` | `/api/v1/matches/{id}/model-prediction` | Model win-probability estimate |
| `POST` | `/api/v1/matches/{id}/predictions` | Submit a prediction |
| `GET` | `/api/v1/news` | World Cup news (paginated, team filter) |
| `GET` | `/api/v1/sentiment` | News sentiment for all teams |
| `GET` | `/api/v1/teams/{id}/sentiment` | News sentiment for one team |

---

## News sentiment — how it works and its limitations

### How it works

`GET /api/v1/sentiment` and `GET /api/v1/teams/{id}/sentiment` analyze the
most recent articles fetched from NewsAPI and return a sentiment score per team.

**Analysis pipeline:**

1. Fetch up to 100 articles from the cached news feed.
2. For each article, concatenate `title` and `summary` (when present).
3. Run [VADER](https://github.com/cjhutto/vaderSentiment) (Valence Aware Dictionary
   and sEntiment Reasoner), a rule-based lexicon model, on the concatenated text.
4. VADER returns a compound score in **[-1, 1]**:
   - ≥ 0.05 → `positive`
   - ≤ −0.05 → `negative`
   - otherwise → `neutral`
5. Group by team code (from `related_team_codes` on each article).
6. Average scores per team and cache for 5 minutes.

**Confidence** blends two signals:

```
coverage = article_count / (article_count + 5)   # half-confident at 5 articles
signal   = mean(|score_i|)                        # how non-neutral each article is
confidence = coverage × 0.6 + signal × 0.4
```

### Limitations — read before using

> **Every response includes a `metadata.disclaimer` field that must be surfaced
> to the user when displaying sentiment scores.**

| Limitation | Detail |
|---|---|
| **Sample, not population** | Scores reflect a sample of English-language news articles fetched in the last 10 minutes from NewsAPI, not all coverage on the internet. |
| **Not fan opinion** | These are news article scores, not social media, forums, or fan sentiment. Headlines are written by journalists, not supporters. |
| **VADER is lexicon-based** | VADER was tuned on social media and product reviews. It understands explicit sentiment words ("brilliant", "catastrophic") but misses sarcasm, irony, and domain-specific framing common in sports journalism. |
| **Short text only** | Analysis uses only the article title and a short description (≤ 2000 chars). Full article text is never fetched or stored. |
| **English only** | NewsAPI is queried with `language=en`. Non-English coverage is excluded. |
| **No social media data** | This system does not ingest Twitter/X, Reddit, or any private platform. |
| **Temporal noise** | A single breaking story can dominate the sample and swing the aggregate score significantly. Treat 24-hour trends as more reliable than single-snapshot scores. |
| **Low article count → low confidence** | The `confidence` field drops below 0.5 when fewer than 5 articles mention a team. Scores for minor teams with sparse coverage should be treated as indicative only. |

### Example response

```json
{
  "metadata": {
    "analyzer": "vader-lexicon-v3.3",
    "disclaimer": "Scores reflect sentiment in sampled news headlines and summaries only. ...",
    "sample_size": 47
  },
  "teams": [
    {
      "team_code": "BRA",
      "team_name": "Brazil",
      "article_count": 12,
      "average_score": 0.34,
      "label": "positive",
      "confidence": 0.72,
      "articles": []
    }
  ]
}
```

`articles` is populated (with per-article scores) only in the single-team endpoint
(`GET /api/v1/teams/{id}/sentiment`). The all-teams endpoint omits it to keep
the payload small.
