# ─── AetherTest Multi-Stage Dockerfile ────────────────────────────────────────
# Stage 1: Build frontend (Node)
# Stage 2: Python 3.12 runtime with FastAPI backend

# ── Stage 1: Frontend Build ───────────────────────────────────────────────────
FROM node:20-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json ./
COPY frontend/package-lock.json* ./
RUN npm ci --prefer-offline || npm install
COPY frontend/index.html frontend/tsconfig.json frontend/vite.config.ts ./
COPY frontend/src/ ./src/
COPY frontend/public/ ./public/
# Build with empty API base (served from same origin)
ENV VITE_API_BASE=""
RUN npm run build

# ── Stage 2: Python Runtime ───────────────────────────────────────────────────
FROM python:3.12-slim AS runtime
WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python deps
COPY pyproject.toml ./
RUN pip install --no-cache-dir \
    fastapi[standard] \
    uvicorn[standard] \
    boto3 \
    botocore \
    pydantic>=2.0.0 \
    python-multipart

# App source
COPY aethertest/ ./aethertest/
COPY lambdas/ ./lambdas/
COPY layers/ ./layers/
COPY frontend/api-server.py ./api-server.py
COPY orchestrator.py ./

# Frontend static build
COPY --from=frontend-build /app/frontend/dist ./static/

# Add layers to Python path
ENV PYTHONPATH="/app:/app/layers"

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8001/api/health || exit 1

EXPOSE 8001

# Serve static + API from same process
CMD ["python", "api-server.py"]
