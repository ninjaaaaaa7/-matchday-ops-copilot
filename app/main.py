"""FastAPI application entry point for MatchDay Ops Copilot.

Exposes a small, well-defined REST API and serves the accessible single-page
operations dashboard from the ``static`` directory.
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .ai_assistant import close_client, run_copilot
from .config import settings
from .context_engine import assess_stadium
from .models import (
    CopilotRequest,
    CopilotResponse,
    DashboardResponse,
    StadiumAssessment,
    StadiumState,
)
from .sample_data import sample_state

# Resolve directories relative to this file so the app runs from anywhere.
BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage startup/shutdown; release the shared HTTP client on exit."""
    yield
    await close_client()


app = FastAPI(
    title="MatchDay Ops Copilot",
    description="GenAI decision-support assistant for FIFA World Cup 2026 stadium operations.",
    version="1.0.0",
    lifespan=lifespan,
)

# Serve the front-end assets (CSS/JS) under /static.
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    """Serve the single-page operations dashboard."""
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health() -> dict:
    """Health check that also reports whether live AI is enabled."""
    return {
        "status": "ok",
        "ai_enabled": settings.ai_enabled,
        "model": settings.gemini_model,
    }


@app.get("/api/sample", response_model=StadiumState)
def get_sample() -> StadiumState:
    """Return a realistic sample stadium snapshot to populate the UI."""
    return sample_state()


@app.get("/api/dashboard", response_model=DashboardResponse)
def get_dashboard() -> DashboardResponse:
    """Return the sample snapshot and its assessment together.

    The UI loads its initial view from this single endpoint instead of calling
    /api/sample and /api/assess separately - one round trip instead of two.
    """
    state = sample_state()
    return DashboardResponse(state=state, assessment=assess_stadium(state))


@app.post("/api/assess", response_model=StadiumAssessment)
def post_assess(state: StadiumState) -> StadiumAssessment:
    """Run the deterministic context engine on a stadium snapshot."""
    return assess_stadium(state)


@app.post("/api/copilot", response_model=CopilotResponse)
async def post_copilot(req: CopilotRequest) -> CopilotResponse:
    """Answer a staff question, grounded in the computed assessment."""
    return await run_copilot(req.state, req.question, req.language)
