from app.tools.base import ToolResult
from app.core.config import get_settings
import httpx

settings = get_settings()


async def serpapi_search(query: str, engine: str = "google", num: int = 10) -> list[ToolResult]:
    if not settings.serpapi_key:
        return [ToolResult(tool_name="serpapi", content="", error="SERPAPI_KEY not configured")]

    params = {"q": query, "engine": engine, "num": num, "api_key": settings.serpapi_key}

    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get("https://serpapi.com/search", params=params)
        resp.raise_for_status()
        data = resp.json()

    results = []
    for r in data.get("organic_results", []):
        results.append(ToolResult(
            tool_name="serpapi",
            source_url=r.get("link"),
            source_name=r.get("title") or r.get("displayed_link", ""),
            content=r.get("snippet", ""),
            quote=r.get("snippet", "")[:300] if r.get("snippet") else None,
            recency="30d",
            metadata={"position": r.get("position"), "query": query, "engine": engine},
        ))

    # Also surface People Also Ask if present
    for paa in data.get("related_questions", [])[:3]:
        results.append(ToolResult(
            tool_name="serpapi",
            source_url=paa.get("link"),
            source_name=f"People Also Ask: {paa.get('question', '')}",
            content=paa.get("snippet", ""),
            recency="30d",
            metadata={"type": "people_also_ask", "question": paa.get("question")},
        ))
    return results
