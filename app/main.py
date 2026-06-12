"""FastAPI entrypoint: auth + rate limit + cost guard + stateless sessions.

Production properties demonstrated here:
- Config from environment variables (12-factor)
- Structured JSON logging (no secrets, no raw question text)
- /health liveness and /ready readiness probes
- Graceful shutdown: the platform sends SIGTERM; uvicorn stops accepting
  new connections and drains in-flight requests before exiting
- Stateless design: all session state lives in Redis, so any scaled
  instance can serve any request
"""

import json
import logging
import os
import signal
import time
import uuid
from contextlib import asynccontextmanager
from typing import Dict, List, Optional

import uvicorn
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.auth import verify_api_key
from app.config import settings
from app.cost_guard import (
    PRICE_PER_1K_INPUT_TOKENS,
    PRICE_PER_1K_OUTPUT_TOKENS,
    check_budget,
    estimate_tokens,
    get_usage,
    record_usage,
)
from app.logging_utils import log_event, setup_logging
from app.rate_limiter import check_rate_limit
from app.redis_client import get_redis, redis_ping
from utils.mock_llm import ask

setup_logging(settings.log_level)
logger = logging.getLogger(__name__)

START_TIME = time.time()
INSTANCE_ID = os.getenv("INSTANCE_ID") or f"instance-{uuid.uuid4().hex[:6]}"
IS_READY = False

SESSION_TTL_SECONDS = 3600
MAX_HISTORY_MESSAGES = 20
ASSUMED_OUTPUT_TOKENS = 500  # pre-call cost estimate before answer length is known


class AskRequest(BaseModel):
    """Request body for POST /ask."""

    user_id: str
    question: str
    session_id: Optional[str] = None


def _load_history(session_id: str) -> List[Dict]:
    """Load conversation history from Redis (empty list if absent/unavailable)."""
    try:
        data = get_redis().get(f"session:{session_id}")
        return json.loads(data) if data else []
    except Exception:
        log_event(logger, "warning", "session_store_unavailable",
                  session_id=session_id, action="load")
        return []


def _save_history(session_id: str, history: List[Dict]) -> None:
    """Persist conversation history to Redis with a TTL."""
    try:
        get_redis().setex(
            f"session:{session_id}", SESSION_TTL_SECONDS, json.dumps(history)
        )
    except Exception:
        log_event(logger, "warning", "session_store_unavailable",
                  session_id=session_id, action="save")


_previous_sigterm_handler = None


def handle_sigterm(signum, frame) -> None:
    """Log SIGTERM receipt, then chain to uvicorn's own handler.

    The platform (Docker/Render/K8s) sends SIGTERM before killing the
    container. Chaining preserves uvicorn's graceful shutdown: it stops
    accepting new connections and finishes in-flight requests.
    """
    log_event(logger, "info", "sigterm_received", instance=INSTANCE_ID)
    if callable(_previous_sigterm_handler):
        _previous_sigterm_handler(signum, frame)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle: log, check Redis, flip readiness flag."""
    global IS_READY
    log_event(logger, "info", "startup", app=settings.app_name,
              version=settings.app_version, environment=settings.environment,
              port=settings.port, instance=INSTANCE_ID)

    redis_ok = redis_ping()
    log_event(logger, "info", "redis_connection",
              status="ok" if redis_ok else "failed")

    global _previous_sigterm_handler
    try:
        _previous_sigterm_handler = signal.getsignal(signal.SIGTERM)
        signal.signal(signal.SIGTERM, handle_sigterm)
    except ValueError:
        pass  # signal handlers can only be set in the main thread

    IS_READY = True
    log_event(logger, "info", "ready", instance=INSTANCE_ID)

    yield

    IS_READY = False
    log_event(logger, "info", "shutdown_graceful", instance=INSTANCE_ID)


app = FastAPI(title=settings.app_name, version=settings.app_version,
              lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/")
async def root() -> Dict:
    """Public service info."""
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "status": "running",
        "instance": INSTANCE_ID,
    }


@app.get("/health")
async def health() -> Dict:
    """Liveness probe: process is alive (no dependency checks)."""
    return {
        "status": "ok",
        "uptime_seconds": int(time.time() - START_TIME),
        "version": settings.app_version,
        "instance": INSTANCE_ID,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


@app.get("/ready")
async def ready() -> Dict:
    """Readiness probe: 503 until startup completes and Redis is reachable."""
    if not IS_READY:
        raise HTTPException(status_code=503, detail="Not ready: starting up")
    if not redis_ping():
        raise HTTPException(status_code=503, detail="Not ready: Redis unavailable")
    return {"ready": True, "instance": INSTANCE_ID}


@app.get("/metrics")
async def metrics() -> Dict:
    """Basic metrics for scraping."""
    return {
        "uptime_seconds": int(time.time() - START_TIME),
        "instance": INSTANCE_ID,
        "environment": settings.environment,
        "version": settings.app_version,
    }


@app.post("/ask")
async def ask_endpoint(body: AskRequest,
                       _key: str = Depends(verify_api_key)) -> Dict:
    """Answer a question: auth -> rate_limit -> budget -> LLM -> session save.

    Returns 429 when the per-minute rate_limit is exceeded and 402 when the
    monthly budget is exhausted (handled by the dependencies below).
    """
    rate_info = check_rate_limit(body.user_id)

    input_tokens = estimate_tokens(body.question)
    est_cost = (input_tokens / 1000) * PRICE_PER_1K_INPUT_TOKENS \
        + (ASSUMED_OUTPUT_TOKENS / 1000) * PRICE_PER_1K_OUTPUT_TOKENS
    check_budget(body.user_id, est_cost)

    session_id = body.session_id or str(uuid.uuid4())
    history = _load_history(session_id)
    history.append({"role": "user", "content": body.question,
                    "ts": time.time()})

    answer = ask(body.question)

    history.append({"role": "assistant", "content": answer,
                    "ts": time.time()})
    history = history[-MAX_HISTORY_MESSAGES:]
    _save_history(session_id, history)

    cost = record_usage(body.user_id, input_tokens, estimate_tokens(answer))

    log_event(logger, "info", "agent_request", user_id=body.user_id,
              question_length=len(body.question),
              response_length=len(answer),
              cost_usd=round(cost, 6), instance=INSTANCE_ID)

    return {
        "session_id": session_id,
        "question": body.question,
        "answer": answer,
        "turn": sum(1 for m in history if m["role"] == "user"),
        "served_by": INSTANCE_ID,
        "rate_limit": rate_info,
        "cost_usd": round(cost, 6),
    }


@app.get("/usage/{user_id}")
async def usage(user_id: str, _key: str = Depends(verify_api_key)) -> Dict:
    """Current-month spending for a user."""
    return get_usage(user_id)


@app.get("/chat/{session_id}/history")
async def chat_history(session_id: str,
                       _key: str = Depends(verify_api_key)) -> Dict:
    """Conversation history for a session, 404 if absent or expired."""
    history = _load_history(session_id)
    if not history:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"session_id": session_id, "messages": history,
            "count": len(history)}


if __name__ == "__main__":
    uvicorn.run("app.main:app", host=settings.host, port=settings.port)
