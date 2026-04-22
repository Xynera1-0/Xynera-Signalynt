from app.tools.base import ToolResult
from app.core.config import get_settings
import httpx

settings = get_settings()

EXA_BASE = "https://api.exa.ai"


async def exa_search(query: str, num_results: int = 5, use_autoprompt: bool = True) -> list[ToolResult]:
    if not settings.exa_api_key:
        return [ToolResult(tool_name="exa_search", content="", error="EXA_API_KEY not configured")]

    headers = {"x-api-key": settings.exa_api_key, "Content-Type": "application/json"}
    payload = {
        "query": query,
        "numResults": num_results,
        "useAutoprompt": use_autoprompt,
        "contents": {"text": {"maxCharacters": 800}},
    }

    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(f"{EXA_BASE}/search", headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()

    results = []
    for r in data.get("results", []):
        text = (r.get("text") or "").strip()
        results.append(ToolResult(
            tool_name="exa_search",
            source_url=r.get("url"),
            source_name=r.get("title") or _domain(r.get("url", "")),
            content=text,
            quote=text[:300] if text else None,
            recency=_published_to_recency(r.get("publishedDate", "")),
            metadata={"score": r.get("score"), "published_date": r.get("publishedDate"), "query": query},
        ))
    return results


def _domain(url: str) -> str:
    try:
        from urllib.parse import urlparse
        return urlparse(url).netloc
    except Exception:
        return url


def _published_to_recency(date_str: str) -> str:
    from app.tools.implementations.tavily import _estimate_recency
    return _estimate_recency(date_str)
