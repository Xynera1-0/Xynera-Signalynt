import os
from contextlib import asynccontextmanager
from pathlib import Path

# Load env vars BEFORE any other imports that might use them
from dotenv import load_dotenv
env_path = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(env_path, override=True)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes.agents import router as agents_router
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.tools.setup import setup_tool_registry
from app.tools.mcp_client import init_mcp_client, close_mcp_client
from app.api.research import router as research_router
from app.api.alerts import router as alerts_router
from app.api.campaign import router as campaign_router
from app.routes.auth import router as auth_router
from .routes.chat import router as chat_router
from .routes.graph import router as graph_router
from .neo4j_db import close_neo4j_driver

settings = get_settings()


def _normalize_origin(origin: str) -> str:
    return origin.strip().rstrip("/")


frontend_url = _normalize_origin(os.getenv("FRONTEND_URL", settings.frontend_url))
allowed_origins = sorted(
    {
        frontend_url,
        settings.frontend_url,
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    }
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ────────────────────────────────────────────────────────────
    setup_logging()                 # configure structured logging first
    setup_tool_registry()           # register all SDK tool wrappers
    await init_mcp_client()         # start MCP server processes (npx)
    yield
    # ── Shutdown ───────────────────────────────────────────────────────────
    await close_mcp_client()        # cleanly terminate MCP server processes


app = FastAPI(
    title="Signalynt Research API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    # Allow local frontend origins across ports during development.
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ────────────────────────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(research_router)
app.include_router(alerts_router)
app.include_router(campaign_router)
app.include_router(agents_router)
app.include_router(chat_router)
app.include_router(graph_router)


@app.on_event("shutdown")
def shutdown_neo4j() -> None:
    close_neo4j_driver()


@app.get("/")
def read_root():
    return {"status": "ok", "service": "Signalynt Research API"}


@app.get("/health")
def health():
    return {"status": "healthy"}
