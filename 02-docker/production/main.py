"""
Agent production-ready — dùng trong Docker production stack.
"""
import os
import time
import logging
import json
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from utils.mock_llm import ask

logging.basicConfig(
    level=logging.INFO,
    format='{"time":"%(asctime)s","level":"%(levelname)s","msg":"%(message)s"}',
)
logger = logging.getLogger(__name__)

START_TIME = time.time()
is_ready = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    global is_ready
    logger.info("Starting agent...")
    time.sleep(0.1)  # simulate init
    is_ready = True
    logger.info("Agent ready")
    yield
    is_ready = False
    logger.info("Agent shutdown")


app = FastAPI(title="Agent (Docker Advanced)", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "*").split(","),
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {
        "app": "AI Agent",
        "version": "2.0.0",
        "environment": os.getenv("ENVIRONMENT", "development"),
    }


@app.post("/ask")
async def ask_agent(request: Request):
    body = await request.json()
    question = body.get("question", "")
    if not question:
        raise HTTPException(422, "question required")
    logger.info(json.dumps({"event": "request", "q_len": len(question)}))
    return {"answer": ask(question)}


@app.get("/health")
def health():
    return {
        "status": "ok",
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "version": "2.0.0",
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/ready")
def ready():
    if not is_ready:
        raise HTTPException(503, "not ready")
    return {"ready": True}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
