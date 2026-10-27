# syntax=docker/dockerfile:1
FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim AS builder

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
FROM python:3.14-slim-bookworm AS runtime

WORKDIR /app

# Create non-root system user
RUN groupadd -g 1000 paslood && \
    useradd -u 1000 -g paslood -s /bin/bash -m paslood && \
    mkdir -p /data && chown -R paslood:paslood /data /app

# Copy built virtual environment, app source and docs
COPY --from=builder --chown=paslood:paslood /app/.venv /app/.venv
COPY --from=builder --chown=paslood:paslood /app/src /app/src
COPY --from=builder --chown=paslood:paslood /app/site /app/site

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PASLOOD_DATA_DIR=/data \
    PASLOOD_MODE=self_host \
    PORT=8000

USER paslood
VOLUME ["/data"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python3 -c 'import urllib.request; urllib.request.urlopen("http://127.0.0.1:8000/api/health")' || exit 1

ENTRYPOINT ["paslood"]
CMD ["web", "--host", "0.0.0.0", "--port", "8000"]
