from __future__ import annotations

import importlib
import os
from base64 import b64encode
from functools import lru_cache
from urllib.parse import quote_plus

import requests

from .content_generation_agent import ContentAgentPool


class ContentAgentConfigError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def get_content_agent_pool() -> ContentAgentPool:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ContentAgentConfigError("GOOGLE_API_KEY is not configured")

    try:
        genai = importlib.import_module("google.generativeai")
    except ModuleNotFoundError as exc:
        raise ContentAgentConfigError(
            "Missing dependency google-generativeai. Install backend requirements first."
        ) from exc

    genai.configure(api_key=api_key)
    model_name = os.getenv("GOOGLE_MODEL", "gemini-3-flash-preview")
    model = genai.GenerativeModel(model_name)
    return ContentAgentPool(model)


def run_content_generation(input_data: dict) -> dict:
    pool = get_content_agent_pool()
    result = pool.run(input_data)
    image = generate_flyer_image(input_data, result)
    if image:
        result["flyer_image"] = image
    return result


def _build_flyer_image_prompt(input_data: dict, result: dict) -> str:
    content = result.get("content") or {}
    critique = result.get("critique") or {}
    headline = (content.get("headlines") or [""])[0]
    body = content.get("body") or ""
    cta = content.get("cta") or ""
    final_output = critique.get("final_output") or ""

    brand_hint = input_data.get("prompt") or input_data.get("goal") or "business flyer"
    platform = input_data.get("platform") or "flyer"

    return (
        "Create a high-quality marketing flyer, portrait orientation, print-ready style. "
        f"Primary brief: {brand_hint}. Platform: {platform}. "
        f"Use this headline: {headline}. "
        f"Use this body copy: {body}. "
        f"Use this call to action: {cta}. "
        f"Design refinement: {final_output}. "
        "Modern typography, strong visual hierarchy, balanced whitespace, no watermark, no logo corruption, professional composition."
    )


def generate_flyer_image(input_data: dict, result: dict) -> dict | None:
    prompt = _build_flyer_image_prompt(input_data, result)
    image_api_base = os.getenv("IMAGE_API_URL", "https://image.pollinations.ai/prompt")
    image_url = f"{image_api_base}/{quote_plus(prompt)}?width=1024&height=1536&nologo=true"

    try:
        response = requests.get(image_url, timeout=45)
        response.raise_for_status()
    except requests.RequestException:
        return None

    content_type = response.headers.get("Content-Type", "image/jpeg")
    image_base64 = b64encode(response.content).decode("ascii")

    return {
        "mime_type": content_type,
        "base64": image_base64,
        "source_url": image_url,
    }
