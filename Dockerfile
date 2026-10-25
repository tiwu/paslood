# syntax=docker/dockerfile:1
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

# Install dependencies first for maximum layer caching
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy application source & build documentation
COPY . .
RUN uv sync --frozen --no-dev
RUN uv run mkdocs build

# Runtime Stage
FROM python:3.12-slim-bookworm AS runtime

WORKDIR /app

# Create non-root system user
RUN groupadd -g 1000 wealthpilot && \
    useradd -u 1000 -g wealthpilot -s /bin/bash -m wealthpilot && \
    mkdir -p /data && chown -R wealthpilot:wealthpilot /data /app

# Copy built virtual environment, app source and docs
COPY --from=builder --chown=wealthpilot:wealthpilot /app/.venv /app/.venv
COPY --from=builder --chown=wealthpilot:wealthpilot /app/src /app/src
COPY --from=builder --chown=wealthpilot:wealthpilot /app/site /app/site

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    WEALTH_PILOT_DATA_DIR=/data \
    WEALTH_PILOT_MODE=self_host \
    PORT=8000

USER wealthpilot
VOLUME ["/data"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python3 -c 'import urllib.request; urllib.request.urlopen("http://127.0.0.1:8000/api/health")' || exit 1

ENTRYPOINT ["wealth-pilot"]
CMD ["web", "--host", "0.0.0.0", "--port", "8000"]
