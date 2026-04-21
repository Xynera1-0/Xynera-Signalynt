from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..agents.content_generation_service import (
    ContentAgentConfigError,
    run_content_generation,
)

router = APIRouter(prefix="/agents", tags=["agents"])


class ContentGenerationRequest(BaseModel):
    prompt: str = Field(min_length=1)
    audience: str | None = None
    goal: str | None = None
    tone: str | None = None
    platform: str = Field(default="Flyer")
    insights: str | None = None
    extra_context: dict[str, Any] | None = None


@router.post("/content-generation/run")
def run_content_generation_agent(payload: ContentGenerationRequest):
    try:
        input_data = payload.model_dump(exclude_none=True)
        result = run_content_generation(input_data)
        flyer_image = result.pop("flyer_image", None)
        return {"input": input_data, "result": result, "flyer_image": flyer_image}
    except ContentAgentConfigError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
