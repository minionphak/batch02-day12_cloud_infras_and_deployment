# Day 12 — Production-Ready AI Agent

Final project for **AICB-P1 Day 12: Cloud Infra & Production Deployment** (VinUniversity 2026).

A FastAPI AI agent built for production: containerized (multi-stage, 291 MB), API-key auth, Redis-backed rate limiting and monthly cost guard, health/readiness probes, graceful shutdown, stateless sessions, structured JSON logging, and load-balanced behind Nginx.

## Architecture

```text
                ┌──────────┐
   client ───▶  │  nginx   │  :80 — load balancer, IP rate limit, security headers
                └────┬─────┘
                     ▼  round-robin (Docker DNS)
          ┌──────────┴──────────┐
          │  agent × N (FastAPI)│  auth → rate limit → cost guard → mock LLM
          └──────────┬──────────┘
                     ▼
                ┌─────────┐
                │  redis  │  sessions · rate limits · budgets (stateless design)
                └─────────┘
```

## Project layout

```
app/
├── main.py           # FastAPI app: endpoints, lifespan, SIGTERM handling
├── config.py         # 12-factor config via pydantic-settings (.env / env vars)
├── auth.py           # X-API-Key authentication (401 missing / 403 invalid)
├── rate_limiter.py   # Redis sliding-window limit (10 req/min/user → 429)
├── cost_guard.py     # Redis monthly budget ($10/user → 402)
├── logging_utils.py  # structured JSON logging helpers
└── redis_client.py   # shared Redis client
utils/mock_llm.py     # mock LLM (provided by the course — no API key needed)
Dockerfile            # multi-stage build, non-root user, HEALTHCHECK
docker-compose.yml    # agent (scalable) + redis + nginx
nginx.conf            # reverse proxy / load balancer config
render.yaml           # Render Blueprint (web service + managed Redis)
railway.toml          # Railway alternative config
```

## Run locally

```bash
# 1. Configure (never commit .env)
cp .env.example .env
#    edit AGENT_API_KEY in .env

# 2. Start the full stack with 3 agent replicas
docker compose up -d --build --scale agent=3

# 3. Smoke test
curl http://localhost/health
curl http://localhost/ready

# 4. Ask the agent (replace YOUR_KEY with AGENT_API_KEY from .env)
curl -X POST http://localhost/ask \
  -H "X-API-Key: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test", "question": "What is deployment?"}'
```

> Port 80 already taken on your machine? Set `NGINX_PORT=8080` in `.env`.

## API

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/` | — | service info |
| GET | `/health` | — | liveness probe |
| GET | `/ready` | — | readiness probe (checks Redis, 503 if down) |
| GET | `/metrics` | — | basic metrics |
| POST | `/ask` | X-API-Key | ask a question; body `{user_id, question, session_id?}` |
| GET | `/usage/{user_id}` | X-API-Key | current-month spend vs budget |
| GET | `/chat/{session_id}/history` | X-API-Key | conversation history |

Error responses: `401` missing key · `403` invalid key · `429` rate limit (10 req/min/user) · `402` monthly budget exceeded ($10/user).

## Verify production readiness

```bash
python check_production_ready.py   
```

## Deploy

See [DEPLOYMENT.md](DEPLOYMENT.md). Render: connect this repo as a **Blueprint** — `render.yaml` provisions the Docker web service and a managed Redis instance; set `AGENT_API_KEY` in the dashboard.

## Lab answers

All exercise answers for Parts 1–5 are in [MISSION_ANSWERS.md](MISSION_ANSWERS.md).
