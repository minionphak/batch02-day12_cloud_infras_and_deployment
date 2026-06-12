# Deployment Information

## Public URL

**https://day12-agent-b8x9.onrender.com**

> Free plan: the instance spins down when idle, so the first request after a
> quiet period can take ~50 s (cold start).

## Platform

**Render** — Blueprint deploy (`render.yaml`): Docker web service + managed Key Value (Redis) instance, both on the free plan.

## Deploy steps (Render)

1. Push this repo to GitHub.
2. [dashboard.render.com](https://dashboard.render.com) → **New → Blueprint** → connect this repo.
3. Render reads `render.yaml` and provisions `day12-agent` (web) + `day12-redis` (Key Value). `REDIS_URL` is injected automatically from the Redis instance.
4. Set the one secret marked `sync: false`: **AGENT_API_KEY** (use a long random string).
5. Deploy. Render health-checks `GET /health` and restarts the service if it fails.

## Test Commands

### Health Check

```bash
curl https://day12-agent-b8x9.onrender.com/health
# Expected: {"status": "ok", "uptime_seconds": ..., "instance": "...", ...}
```

### Readiness Check

```bash
curl https://day12-agent-b8x9.onrender.com/ready
# Expected: {"ready": true, "instance": "..."}
```

### Authentication required

```bash
curl -X POST https://day12-agent-b8x9.onrender.com/ask \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test", "question": "Hello"}'
# Expected: HTTP 401 (missing X-API-Key)
```

### API Test (with authentication)

```bash
curl -X POST https://day12-agent-b8x9.onrender.com/ask \
  -H "X-API-Key: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test", "question": "Hello"}'
# Expected: HTTP 200 with answer, session_id, served_by, rate_limit info
```

### Rate limiting (10 req/min per user)

```bash
for i in {1..12}; do
  curl -s -o /dev/null -w "%{http_code}\n" \
    -X POST https://day12-agent-b8x9.onrender.com/ask \
    -H "X-API-Key: YOUR_KEY" \
    -H "Content-Type: application/json" \
    -d '{"user_id": "test", "question": "test"}'
done
# Expected: ten 200s followed by 429s
```

## Environment Variables Set

- `ENVIRONMENT` = production
- `PORT` (injected by Render)
- `REDIS_URL` (injected from the day12-redis Key Value instance)
- `AGENT_API_KEY` (secret, set in dashboard)
- `LOG_LEVEL` = INFO
- `RATE_LIMIT_PER_MINUTE` = 10
- `MONTHLY_BUDGET_USD` = 10

## Production verification results (2026-06-12, live service)

| Check | Result |
|-------|--------|
| `GET /health` | 200 — `{"status":"ok", "instance":"instance-45bfc7", ...}` |
| `GET /ready` | 200 — `{"ready":true, "instance":"instance-45bfc7"}` (Redis connected) |
| `POST /ask` without key | 401 — "Missing API key" |
| `POST /ask` with wrong key | 403 — "Invalid API key" |
| `POST /ask` with valid key | 200 — answer + `session_id` + `served_by` + `rate_limit` + `cost_usd` |
| 12 requests in one minute | ten 200s, then 429s (sliding-window limit enforced) |
| `GET /usage/{user_id}` | 200 — `{"used_usd":0.00012, "budget_usd":10.0, "remaining_usd":9.99988}` |
| `GET /chat/{session_id}/history` | 200 — both conversation turns persisted in Redis |

## Local verification results (pre-deploy)

| Check | Result |
|-------|--------|
| `check_production_ready.py` | 20/20 passed |
| Docker image size | 291 MB (multi-stage; develop single-stage was 1.66 GB) |
| `/health`, `/ready` | 200 |
| No API key | 401 |
| Valid key | 200 |
| 11th request in a minute | 429 |
| Budget exceeded | 402 |
| Kill serving instance mid-conversation | history survives in Redis, turn continues on another instance |
| `docker stop` (SIGTERM) | graceful drain in ~1.3 s |

## Screenshots

- [Deployment dashboard](screenshots/dashboard.png)
- [Service running](screenshots/running.png)
- [Test results](screenshots/test.png)
