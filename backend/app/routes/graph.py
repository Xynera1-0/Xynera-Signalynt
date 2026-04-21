from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..graph_service import (
    GraphNotFoundError,
    create_signal,
    fetch_persona_context,
    fetch_signal,
    seed_reference_graph,
)
from ..neo4j_db import Neo4jConfigError, ping_neo4j

router = APIRouter(prefix="/graph", tags=["graph"])


class SignalCreateRequest(BaseModel):
    id: str = Field(min_length=1)
    title: str | None = None
    description: str | None = None
    value: str | None = None
    source_name: str | None = None
    source_type: str | None = None


class SeedResponse(BaseModel):
    nodes_created: int
    relationships_created: int


@router.get("/health")
def graph_health():
    try:
        status = ping_neo4j()
    except Neo4jConfigError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    return {"service": "neo4j", **status}


@router.post("/seed", response_model=SeedResponse)
def seed_graph():
    try:
        return seed_reference_graph()
    except Neo4jConfigError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.post("/signals")
def upsert_signal(payload: SignalCreateRequest):
    try:
        props: dict[str, Any] = payload.model_dump(exclude={"id"}, exclude_none=True)
        if payload.value is not None:
            props["value"] = payload.value
        signal = create_signal(payload.id, props)
        return {"signal": signal}
    except Neo4jConfigError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.get("/signals/{signal_id}")
def get_signal(signal_id: str):
    try:
        return {"signal": fetch_signal(signal_id)}
    except GraphNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Neo4jConfigError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.get("/personas/{persona_id}")
def get_persona_context(persona_id: str):
    try:
        return fetch_persona_context(persona_id)
    except GraphNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Neo4jConfigError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
