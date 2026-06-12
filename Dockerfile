# ============================================================
# Multi-stage build — final image stays small (< 500 MB) and
# contains no build tooling.
# ============================================================

# ---- Stage 1: builder — install dependencies only ----
FROM python:3.12-slim AS builder
WORKDIR /app
COPY requirements.txt .
# --user installs to /root/.local so the runtime stage can copy it wholesale
RUN pip install --no-cache-dir --user -r requirements.txt

# ---- Stage 2: runtime — only what is needed to RUN ----
FROM python:3.12-slim AS runtime

# Non-root user: containers should never run as root
RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

COPY --from=builder /root/.local /home/appuser/.local
COPY app/ ./app/
COPY utils/ ./utils/
RUN chown -R appuser:appuser /app /home/appuser/.local

USER appuser
ENV PATH=/home/appuser/.local/bin:$PATH \
    PYTHONPATH=/app \
    PYTHONUNBUFFERED=1

EXPOSE 8000

# Docker restarts the container if this starts failing
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

# sh -c so the platform-injected PORT env var (Render/Railway) is honored;
# exec makes uvicorn PID 1 so it receives SIGTERM directly (graceful shutdown)
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
