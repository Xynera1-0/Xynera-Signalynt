from app.tools.base import ToolResult
from app.core.config import get_settings
from datetime import datetime, timezone
import httpx

settings = get_settings()


async def tavily_search(query: str, max_results: int = 5) -> list[ToolResult]:
    if not settings.tavily_api_key:
        return [ToolResult(tool_name="tavily_search", content="", error="TAVILY_API_KEY not configured")]

    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(
            "https://api.tavily.com/search",
            json={"api_key": settings.tavily_api_key, "query": query, "max_results": max_results, "include_raw_content": False},
        )
        resp.raise_for_status()
        data = resp.json()

    results = []
    for r in data.get("results", []):
        published = r.get("published_date", "")
        recency = _estimate_recency(published)
        results.append(ToolResult(
            tool_name="tavily_search",
            source_url=r.get("url"),
            source_name=r.get("title") or _domain(r.get("url", "")),
            content=r.get("content", ""),
            quote=r.get("content", "")[:300] if r.get("content") else None,
            recency=recency,
            metadata={"score": r.get("score"), "published_date": published, "query": query},
        ))
    return results


def _domain(url: str) -> str:
    try:
        from urllib.parse import urlparse
        return urlparse(url).netloc
    except Exception:
        return url


def _estimate_recency(date_str: str) -> str:
    if not date_str:
        return "30d"
    try:
        from dateutil import parser as dp
        dt = dp.parse(date_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        delta = (datetime.now(timezone.utc) - dt).days
        if delta <= 1:
            return "24h"
        if delta <= 7:
            return "7d"
        if delta <= 30:
            return "30d"
        if delta <= 90:
            return "90d"
        return "older"
    except Exception:
        return "30d"
