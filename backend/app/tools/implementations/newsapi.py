from app.tools.base import ToolResult
from app.core.config import get_settings
import httpx

settings = get_settings()


async def newsapi_headlines(query: str, days_back: int = 7, language: str = "en", page_size: int = 10) -> list[ToolResult]:
    if not settings.newsapi_key:
        return [ToolResult(tool_name="newsapi", content="", error="NEWSAPI_KEY not configured")]

    from datetime import datetime, timedelta, timezone
    from_date = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y-%m-%d")

    params = {
        "q": query,
        "from": from_date,
        "language": language,
        "pageSize": page_size,
        "sortBy": "publishedAt",
        "apiKey": settings.newsapi_key,
    }

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get("https://newsapi.org/v2/everything", params=params)
        resp.raise_for_status()
        data = resp.json()

    results = []
    for a in data.get("articles", []):
        published = a.get("publishedAt", "")
        from app.tools.implementations.tavily import _estimate_recency
        recency = _estimate_recency(published)
        title = a.get("title", "")
        description = a.get("description", "") or ""
        content = f"{title}\n{description}".strip()
        results.append(ToolResult(
            tool_name="newsapi",
            source_url=a.get("url"),
            source_name=f"{a.get('source', {}).get('name', 'NewsAPI')} — {title[:60]}",
            content=content,
            quote=description[:300] if description else None,
            recency=recency,
            metadata={"published_at": published, "source": a.get("source", {}).get("name"), "query": query},
        ))
    return results
