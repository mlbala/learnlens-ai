# LearnLens API — multi-stage image (Python 3.12 + uv)
# No paid provider calls; defaults to fake AI providers.

FROM ghcr.io/astral-sh/uv:0.13.6 AS uv

FROM python:3.12-slim-bookworm AS builder
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv
COPY pyproject.toml uv.lock ./
COPY app ./app
RUN uv sync --frozen --no-dev --no-editable

FROM python:3.12-slim-bookworm AS runtime
WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    AI_CHAT_PROVIDER=fake \
    AI_EMBED_PROVIDER=fake
RUN useradd --create-home --uid 10001 appuser
COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv
COPY --chown=appuser:appuser app ./app
USER appuser
EXPOSE 8000
# Health vertical slice — no paid AI calls on startup.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
