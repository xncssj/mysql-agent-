# Dockerfile - Multi-stage build
# ========== Stage 1: Builder ==========
FROM python:3.12-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml requirements.txt ./
COPY src/ ./src/
RUN pip install --no-cache-dir --prefix=/install .

# ========== Stage 2: Runtime ==========
FROM python:3.12-slim AS runtime

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /usr/local
COPY src/ ./src/
COPY scripts/ ./scripts/
COPY configs/ ./configs/

RUN groupadd -r mysql-agent && useradd -r -g mysql-agent mysql-agent
RUN mkdir -p /app/data /app/logs && chown -R mysql-agent:mysql-agent /app
USER mysql-agent

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

ENTRYPOINT ["python", "-m", "mysql_agent.api"]
