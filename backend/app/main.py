from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.tools.setup import setup_tool_registry
from app.tools.mcp_client import init_mcp_client, close_mcp_client
from app.api.research import router as research_router
from app.api.alerts import router as alerts_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ────────────────────────────────────────────────────────────
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
    allow_origins=[settings.frontend_url, "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ────────────────────────────────────────────────────────────────
app.include_router(research_router)
app.include_router(alerts_router)


@app.get("/")
def read_root():
    return {"status": "ok", "service": "Signalynt Research API"}


@app.get("/health")
def health():
    return {"status": "healthy"}

