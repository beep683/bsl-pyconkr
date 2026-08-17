from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from agent_framework_ag_ui import add_agent_framework_fastapi_endpoint
from agent_framework_github_copilot import GitHubCopilotAgent
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .agui import LunchAnalysisAGUIWorkflow
from .config import Settings, get_settings
from .data import LunchDataSource, McpLunchDataSource
from .schemas import AnalysisState


def create_app(
    settings: Settings | None = None,
    data_source: LunchDataSource | None = None,
    agent_factory=None,
) -> FastAPI:
    resolved = settings or get_settings()
    mcp_tool = None
    if data_source is None:
        mcp_tool, data_source = McpLunchDataSource.create(str(resolved.mcp_url))

    if agent_factory is None:
        def agent_factory(name: str, instructions: str) -> GitHubCopilotAgent:
            return GitHubCopilotAgent(
                name=name,
                instructions=instructions,
                default_options={
                    "model": resolved.github_copilot_model,
                    "timeout": resolved.github_copilot_timeout,
                },
            )

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        if mcp_tool is None:
            yield
        else:
            async with mcp_tool:
                yield

    app = FastAPI(title="School Lunch Analysis Agent", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolved.allowed_origins,
        allow_credentials=False,
        allow_methods=["POST", "GET"],
        allow_headers=["*"],
    )
    workflow = LunchAnalysisAGUIWorkflow(data_source, agent_factory)
    add_agent_framework_fastapi_endpoint(
        app,
        workflow,
        "/agent",
        state_schema=AnalysisState,
        default_state=AnalysisState().model_dump(mode="json", by_alias=True),
        keepalive_seconds=15,
    )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
