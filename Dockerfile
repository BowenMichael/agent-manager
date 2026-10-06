# Multi-stage Dockerfile for Agent Manager Backend & Static Frontend
# Stage 1: Build Frontend Assets
FROM node:20-slim AS frontend-builder

WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm ci --ignore-scripts || npm install

COPY frontend/ ./
RUN npm run build

# Stage 2: Production Python Runtime
FROM python:3.11-slim AS runner

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000 \
    APP_ENV=production

# Install essential system dependencies (git, curl for health checks)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python requirements
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend codebase and config
COPY agent_manager/ ./agent_manager/
COPY docs/ ./docs/
COPY alembic/ ./alembic/
COPY alembic.ini ./
COPY MANIFESTO.md ./
COPY CHANGELOG.md ./

# Copy compiled frontend distribution from builder stage
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Setup non-root execution user for security
RUN useradd -m -u 1000 appuser && \
    mkdir -p /app/data /app/.worktrees && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

# Container liveness & readiness healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/healthz || exit 1

# Launch ASGI server using runtime port with proxy header trust for Render / reverse proxies
CMD ["sh", "-c", "uvicorn agent_manager.server:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]

