FROM ghcr.io/astral-sh/uv:0.11.17 AS uv
FROM python:3.12-slim

WORKDIR /app
COPY --from=uv /uv /uvx /bin/
COPY pyproject.toml uv.lock ./
COPY lunch_mcp ./lunch_mcp
RUN uv sync --frozen --no-dev
RUN useradd --create-home appuser
USER appuser

ENV PATH="/app/.venv/bin:$PATH"
ENV MCP_HOST="0.0.0.0"
EXPOSE 8000
CMD ["school-lunch-mcp"]
