from __future__ import annotations

import importlib
import os
from base64 import b64encode
from functools import lru_cache
from types import SimpleNamespace
from urllib.parse import quote_plus

import requests

from .content_generation_agent import ContentAgentPool


class ContentAgentConfigError(RuntimeError):
    pass


def _is_rate_limit_or_quota_error(exc: Exception) -> bool:
    message = str(exc).lower()
    indicators = (
        "429",
        "quota",
        "rate limit",
        "too many requests",
        "resource exhausted",
    )
    return any(token in message for token in indicators)


class GrokGenerativeModel:
    def __init__(self, api_key: str, model: str, api_base: str):
        self.api_key = api_key
        self.model = model
        self.api_base = api_base.rstrip("/")

    def generate_content(self, prompt: str):
        response = requests.post(
            f"{self.api_base}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=45,
        )
        response.raise_for_status()
        payload = response.json()
        content = (((payload.get("choices") or [{}])[0].get("message") or {}).get("content"))
        if isinstance(content, list):
            content = "".join(
                part.get("text", "") for part in content if isinstance(part, dict)
            )
        return SimpleNamespace(text=content or "")


class GeminiGenerativeModel:
    def __init__(self, api_key: str, model: str):
        try:
            genai = importlib.import_module("google.genai")
        except ModuleNotFoundError as exc:
            raise ContentAgentConfigError(
                "Missing dependency google-genai. Install backend requirements first."
            ) from exc

        self.client = genai.Client(api_key=api_key)
        self.model = model

    def generate_content(self, prompt: str):
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
        )
        text = getattr(response, "text", None)
        return SimpleNamespace(text=text or "")


class FallbackGenerativeModel:
    def __init__(self, primary_model, fallback_model):
        self.primary_model = primary_model
        self.fallback_model = fallback_model

    def generate_content(self, prompt: str):
        try:
            return self.primary_model.generate_content(prompt)
        except Exception as exc:
            if self.fallback_model and _is_rate_limit_or_quota_error(exc):
                return self.fallback_model.generate_content(prompt)
            raise


@lru_cache(maxsize=1)
def get_content_agent_pool() -> ContentAgentPool:
    google_api_key = os.getenv("GOOGLE_API_KEY")
    grok_api_key = os.getenv("GROK_API_KEY")

    gemini_model = None
    if google_api_key:
        google_model_name = os.getenv("GOOGLE_MODEL", "gemini-3-flash-preview")
        gemini_model = GeminiGenerativeModel(
            api_key=google_api_key,
            model=google_model_name,
        )

    grok_model = None
    if grok_api_key:
        grok_model_name = os.getenv("GROK_MODEL", "grok-2-latest")
        grok_api_base = os.getenv("GROK_API_URL", "https://api.x.ai/v1")
        grok_model = GrokGenerativeModel(
            api_key=grok_api_key,
            model=grok_model_name,
            api_base=grok_api_base,
        )

    if gemini_model and grok_model:
        model = FallbackGenerativeModel(gemini_model, grok_model)
    elif gemini_model:
        model = gemini_model
    elif grok_model:
        model = grok_model
    else:
        raise ContentAgentConfigError(
            "No LLM provider configured. Set GOOGLE_API_KEY or GROK_API_KEY."
        )

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
