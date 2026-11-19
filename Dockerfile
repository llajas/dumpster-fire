FROM ghcr.io/astral-sh/uv:0.13.8 AS uv

FROM python:3.11-slim
COPY --from=uv /uv /usr/local/bin/uv

WORKDIR /app
COPY controller/pyproject.toml controller/uv.lock /app/controller/
RUN uv sync --project /app/controller --frozen --no-dev --no-install-project
COPY controller /app/controller

ENV PATH="/app/controller/.venv/bin:${PATH}" \
    PYTHONPATH=/app \
    PYTHONUNBUFFERED=1
USER 10001:10001
CMD ["python", "-m", "controller"]
