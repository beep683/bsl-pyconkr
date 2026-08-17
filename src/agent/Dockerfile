FROM ghcr.io/astral-sh/uv:0.11.17 AS uv
FROM python:3.12-slim

WORKDIR /app
COPY --from=uv /uv /uvx /bin/
COPY src/agent/pyproject.toml src/agent/uv.lock ./
COPY src/agent/app ./app
COPY src/agent/instructions ./instructions
COPY EVALUATION_RUBRIC.md ./EVALUATION_RUBRIC.md
RUN uv sync --frozen --no-dev
RUN useradd --create-home appuser
USER appuser

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
