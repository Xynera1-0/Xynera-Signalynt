import os
from pathlib import Path

# Load env vars BEFORE any other imports that might use them
from dotenv import load_dotenv
env_path = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(env_path, override=True)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes.agents import router as agents_router
from .routes.auth import router as auth_router
from .routes.chat import router as chat_router
from .routes.graph import router as graph_router
from .neo4j_db import close_neo4j_driver

app = FastAPI(title="Xynera Backend API")

def _normalize_origin(origin: str) -> str:
    return origin.strip().rstrip("/")


frontend_url = _normalize_origin(os.getenv("FRONTEND_URL", "http://localhost:3000"))
allowed_origins = sorted(
    {
        frontend_url,
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    }
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

app.include_router(auth_router)
app.include_router(agents_router)
app.include_router(chat_router)
app.include_router(graph_router)


@app.on_event("shutdown")
def shutdown_neo4j() -> None:
    close_neo4j_driver()


@app.get("/")
def read_root():
    return {"status": "ok", "service": "xynera-backend"}
