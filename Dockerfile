# AetherTest Multi-Stage Dockerfile
# Stage 1: Build frontend (Node)
# Stage 2: Python 3.12 runtime with FastAPI backend

# Stage 1: Frontend Build
FROM public.ecr.aws/docker/library/node:20-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json ./
COPY frontend/package-lock.json* ./
RUN npm ci --prefer-offline || npm install
COPY frontend/index.html frontend/tsconfig.json frontend/vite.config.ts ./
COPY frontend/src/ ./src/
COPY frontend/public/ ./public/
ENV VITE_API_BASE=""
RUN npm run build

# Stage 2: Python Runtime
FROM public.ecr.aws/docker/library/python:3.12-slim AS runtime
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN pip install --no-cache-dir \
    fastapi[standard] \
    uvicorn[standard] \
    boto3 \
    botocore \
    pydantic>=2.0.0 \
    python-multipart

COPY aethertest/ ./aethertest/
COPY lambdas/ ./lambdas/
COPY layers/ ./layers/
COPY frontend/api-server.py ./api-server.py
COPY orchestrator.py ./

COPY --from=frontend-build /app/frontend/dist ./static/

# Force empty AWS_PROFILE so boto3 never tries SSO profile lookup
# Instance role credentials come via AWS_CONTAINER_CREDENTIALS_RELATIVE_URI
ENV AWS_PROFILE=""
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH="/app:/app/layers"

HEALTHCHECK --interval=15s --timeout=10s --start-period=60s --retries=5 \
    CMD curl -f http://localhost:8001/api/health || exit 1

EXPOSE 8001

CMD ["python", "api-server.py"]
