# Day 12 Lab - Mission Answers

> **Course:** AICB-P1 · VinUniversity 2026 — Day 12: Cloud Infra & Production Deployment

## Part 1: Localhost vs Production

### Exercise 1.1: Anti-patterns found

1. **Hardcoded secret (`OPENAI_API_KEY`)** — storing credentials directly in source code exposes them to anyone with repository access and makes rotation impossible without a code commit.
2. **Hardcoded database credentials (`DATABASE_URL`)** — embedding the DB password in code violates environment-specific configuration and risks leaking production access the moment the repo is shared.
3. **Secret logged to stdout (`print(f"... Using key: {OPENAI_API_KEY}")`)** — printing secrets puts them in plain text in any log aggregator, visible to anyone with log access.
4. **No health/readiness endpoints** — without `/health` and `/ready`, the platform cannot detect a crashed agent to restart it, or know when it is safe to route traffic.
5. **Localhost-only binding (`host="localhost"`)** — restricts the app to the loopback interface; inside a container nothing external (including the platform's proxy) can reach it. Production needs `0.0.0.0`.
6. **Fixed port (`port=8000` in code)** — Railway/Render inject the port via the `PORT` env var; a hardcoded port breaks deployment.
7. **`reload=True` in production** — debug auto-reload wastes resources, watches the filesystem, and is a security liability.
8. **`print()` instead of structured logging** — unstructured debug prints cannot be filtered, parsed, or alerted on by log tooling.
9. **No graceful shutdown** — no lifespan/SIGTERM handling means in-flight requests are killed abruptly on every deploy or restart.

### Exercise 1.3: Comparison table

| Feature | Develop | Production | Why Important? |
| :--- | :--- | :--- | :--- |
| Config | Hardcoded | Env vars (Settings) | Decouples code from environment; same image runs everywhere |
| Secrets | Hardcoded | Env vars, validated at startup | Prevents credential leakage; fail-fast if missing |
| Health check | None | `GET /health` | Platform restarts dead containers |
| Readiness check | None | `GET /ready` | LB only routes traffic when dependencies are up |
| Logging | `print()` | Structured JSON | Machine-parseable in Datadog/Loki; never logs secrets |
| Shutdown | Abrupt | Graceful (SIGTERM + lifespan) | In-flight requests finish on deploy/restart |
| Host binding | `localhost` | `0.0.0.0` | Reachable from outside the container |
| Port | Fixed 8000 | `PORT` env var | Platforms inject the port dynamically |
| CORS | None/open | Restricted origins | Blocks unauthorized cross-origin access |
| Debug/reload | Always on | Only when `DEBUG=true` | Performance and security in production |

These improvements follow the 12-Factor App methodology — most directly **Config** (store config in the environment), **Disposability** (fast startup, graceful shutdown), and **Logs** (treat logs as event streams). Separating code from configuration and making the app observable is what makes it cloud-deployable.

## Part 2: Docker

### Exercise 2.1: Dockerfile questions

1. **Base image:** `python:3.11` — the full Python distribution, roughly 1 GB, because it bundles build tools, headers, and extras.
2. **Working directory:** `/app` — the root for all subsequent COPY/RUN/CMD operations.
3. **Why COPY requirements.txt first:** Docker caches each layer. If only source code changes, the expensive `pip install` layer is reused from cache; dependencies are reinstalled only when `requirements.txt` itself changes. This cuts rebuild time dramatically.
4. **CMD vs ENTRYPOINT:** `CMD` provides a default command/arguments that are easily overridden at `docker run` time. `ENTRYPOINT` fixes the executable so the container behaves like a binary; runtime arguments are appended to it. Use `CMD` for a default that users may replace, `ENTRYPOINT` when the container must always run one specific program (optionally with `CMD` as its default flags).

### Exercise 2.3: Multi-stage build

- **Stage 1 (builder):** based on `python:3.11-slim`, installs build dependencies (`gcc`, `libpq-dev`) and runs `pip install --user` so all packages land in `/root/.local`, easy to copy out.
- **Stage 2 (runtime):** starts from a clean `python:3.11-slim`, copies only `/root/.local` (the installed packages) and the source code, creates a non-root `appuser`, and runs the app.

Why the final image is smaller and more secure:
1. **Slim base** — no docs, no extra utilities.
2. **No build tools in the final image** — `gcc` and dev headers stay in the discarded builder stage, shrinking size and attack surface.
3. **Non-root user** — least privilege; a compromised app process is not root in the container.

### Image size comparison (measured with `docker images`)

- Develop (single-stage, `python:3.11` full): **1660 MB (1.66 GB)**
- Production (multi-stage, `python:3.12-slim`, our final project image): **291 MB**
- Difference: **~82% smaller**

### Exercise 2.4: Docker Compose architecture

The stack runs on a private bridge network (`internal`); services reach each other via Docker's service-name DNS. Nginx is the only public entry point (ports 80/443): it terminates HTTP, applies an IP rate limit (10 r/s, burst 20 → 429 JSON), adds security headers, and proxies to the `agent` upstream. The FastAPI `agent` publishes **no** host port — it is reachable only through nginx — and declares a healthcheck plus `depends_on: condition: service_healthy` so it starts only after Redis/Qdrant are ready. Redis (256 MB, `allkeys-lru`) holds sessions and rate-limit state; Qdrant is the vector DB for RAG. Secrets come from a git-ignored `env_file`, and named volumes persist Redis/Qdrant data across restarts.

```text
                ┌──────────┐
   client ───▶  │  nginx   │  :80 (rate limit, security headers)
                └────┬─────┘
                     ▼  round-robin (Docker DNS)
                ┌──────────┐
                │  agent   │  FastAPI (no published port)
                └──┬───┬───┘
                   ▼   ▼
             ┌───────┐ ┌────────┐
             │ redis │ │ qdrant │
             └───────┘ └────────┘
              (internal bridge network, named volumes)
```

## Part 3: Cloud Deployment

### Exercise 3.1: Deployment

- Platform: **Render** (Blueprint deploy via `render.yaml` — web service from Dockerfile + managed Key Value/Redis instance)
- URL: _see [DEPLOYMENT.md](DEPLOYMENT.md)_
- Screenshot: [screenshots/](screenshots/)

**`render.yaml` vs `railway.toml`:** Render's Blueprint is declarative infrastructure — it defines *all* services (web + Redis), plans, env vars, and cross-service references (`fromService` injects the Redis connection string); deploy is triggered by connecting the GitHub repo. Railway's `railway.toml` only configures build/deploy behavior (builder, healthcheck, restart policy) for one service; services and variables are created via the CLI (`railway init`, `railway variables set`, `railway up`).

## Part 4: API Security

### Exercise 4.1: API Key authentication

The key is validated in the `verify_api_key` FastAPI dependency, which reads the `X-API-Key` header via `APIKeyHeader`. A missing header returns **401 Unauthorized**; a wrong key returns **403 Forbidden** (the comparison uses `secrets.compare_digest` to avoid timing attacks). Rotation in production: update the `AGENT_API_KEY` env var and do a rolling restart; to avoid client downtime, accept both old and new keys during a rotation window. Keys are never committed — only `.env.example` with a placeholder.

### Exercise 4.2: JWT flow

1. Client sends credentials to `POST /token`.
2. Server verifies username/password.
3. Server signs a JWT (HS256) with payload `sub` (user), `role`, `iat`, and `exp` (60-minute expiry).
4. Client sends `Authorization: Bearer <token>` on every request.
5. Server verifies the signature and expiry **statelessly** — no DB lookup per request.

Stateless auth scales because any instance holding the shared `JWT_SECRET` can verify any token. `ExpiredSignatureError` → 401 "Token expired"; `InvalidTokenError` → 403 "Invalid token".

### Exercise 4.3: Rate limiting

The course implementation is a **Sliding Window Counter**: a `deque` of timestamps per user; timestamps older than the 60 s window are evicted on each check; if the count reaches the limit, it raises **429** with `Retry-After` and `X-RateLimit-Limit/Remaining/Reset` headers. The limit is **10 requests/minute** for users; admins bypass it via a separate `RateLimiter` instance allowing 100 req/min, selected by JWT role. Production caveat: an in-memory limiter breaks with multiple instances (each has its own counters), so our final project moves the sliding window to a **Redis ZSET** shared by all replicas.

### Exercise 4.1–4.3: Test results (final project, via nginx)

```text
# no key
POST /ask                          → HTTP 401 {"detail":"Missing API key. Include header: X-API-Key: <your-key>"}

# valid key
POST /ask {"user_id":"u1", ...}    → HTTP 200 {"answer": "...", "served_by": "instance-40e63b",
                                                "rate_limit": {"limit": 10, "remaining": 9}, ...}

# 12 consecutive requests, same user (limit = 10/min)
200,200,200,200,200,200,200,200,200,200,429,429
```

### Exercise 4.4: Cost guard implementation

Every request estimates LLM cost from token counts (≈4 chars/token) at GPT-4o-mini reference prices ($0.15/1M input, $0.60/1M output). Spending is tracked **per user per calendar month** in Redis under `budget:{user_id}:{YYYY-MM}` using `INCRBYFLOAT`, with a 32-day TTL so the key naturally expires after the month ends. Before calling the LLM, the guard checks `current + estimated > $10` and raises **402 Payment Required**; at 80% of budget it logs a structured warning. After the call, actual usage is recorded.

Test result:

```text
# Redis: SET budget:budget-test:2026-06 10.5
POST /ask → HTTP 402 {"detail":{"error":"Monthly budget exceeded","used_usd":10.5,
                                 "budget_usd":10.0,"resets_at":"first day of next month (UTC)"}}
```

Compared with the course's in-memory `CostGuard` (daily $1/user + $10 global → 503): Redis is required for multi-instance correctness (all replicas see the same spend) and persistence across restarts/deploys — an in-memory counter resets to $0 every time a container is replaced.

## Part 5: Scaling & Reliability

### Exercise 5.1: Health & readiness checks

```python
@app.get("/health")
async def health():                       # liveness
    return {"status": "ok", "instance": INSTANCE_ID}

@app.get("/ready")
async def ready():                        # readiness
    if not redis_ping():
        raise HTTPException(status_code=503, detail="Not ready: Redis unavailable")
    return {"ready": True, "instance": INSTANCE_ID}
```

Liveness answers "is the process alive?" — on failure the platform **restarts** the container. Readiness answers "can it serve traffic right now?" — on failure the load balancer **stops routing** to the instance (no restart), e.g. during startup or a Redis outage.

### Exercise 5.2: Graceful shutdown

Cloud platforms send `SIGTERM` and wait a grace period (~10–30 s) before `SIGKILL`. uvicorn handles `SIGTERM` by refusing new connections while draining in-flight requests; our handler (registered with `signal.signal(SIGTERM, ...)`) logs the event and chains to uvicorn's handler, and the FastAPI lifespan shutdown block runs cleanup.

Two practical pitfalls we hit and fixed:
1. **Shell-form CMD**: with `CMD ["sh", "-c", "uvicorn ..."]`, `sh` is PID 1 and does **not** forward SIGTERM — uvicorn gets killed, not drained. Fix: `exec uvicorn ...` so uvicorn becomes PID 1.
2. **Handler override**: naively calling `signal.signal(SIGTERM, mine)` *replaces* uvicorn's handler; we save the previous handler and chain to it.

**Test result:** `docker stop` (sends SIGTERM) completes in ~1.3 s with uvicorn logging `Shutting down → Waiting for application shutdown → Application shutdown complete → Finished server process [1]` — a clean drain instead of the 10 s timeout + SIGKILL.

### Exercise 5.3: Stateless design

```python
# ❌ anti-pattern: state lives in one process's memory
conversation_history = {}

# ✅ fix: state lives in Redis, shared by all instances
redis.setex(f"session:{session_id}", 3600, json.dumps(history))  # capped at 20 messages
```

With N scaled instances behind a load balancer, request 2 of a conversation may land on a different instance than request 1. In-memory state is invisible to the other instances and is lost on every restart/redeploy. Redis centralizes the state so any replica can serve any request.

### Exercise 5.4: Load balancing

`docker compose up --scale agent=3` starts 3 replicas of the `agent` service. Nginx's upstream `server agent:8000` resolves through Docker's embedded DNS, which round-robins across the replicas. Each response carries `served_by: <instance_id>` proving distribution; if one instance dies, its healthcheck fails and traffic continues to the survivors while the restart policy brings it back.

Measured distribution over 6 requests:

```text
instance-7851b4, instance-25ee50, instance-40e63b, instance-7851b4, instance-25ee50, instance-40e63b
```

### Exercise 5.5: Stateless test

The test creates a conversation (turn 1), kills the exact instance that served it, then continues the same session (turn 2). It passes if the history survives and the turn counter increments — proving state lives in Redis, not in the killed process.

**Result (final project):**

```text
turn 1: served_by=instance-25ee50  session=fda867fb-...
docker kill day12-submission-agent-2        # the instance that served turn 1
turn 2: served_by=instance-40e63b  turn=2   # different instance, same conversation
GET /chat/{session}/history → count=4       # full history intact in Redis
```
