"""YouTube Data API v3 — video search + comment sentiment."""
from app.tools.base import ToolResult
from app.core.config import get_settings
import httpx

settings = get_settings()
YT_BASE = "https://www.googleapis.com/youtube/v3"


async def youtube_search(query: str, max_results: int = 10) -> list[ToolResult]:
    if not settings.youtube_api_key:
        return [ToolResult(tool_name="youtube_data_api", content="", error="YOUTUBE_API_KEY not configured")]

    params = {"part": "snippet", "q": query, "maxResults": max_results, "type": "video", "key": settings.youtube_api_key}
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(f"{YT_BASE}/search", params=params)
        resp.raise_for_status()
        data = resp.json()

    results = []
    for item in data.get("items", []):
        snippet = item.get("snippet", {})
        video_id = item.get("id", {}).get("videoId", "")
        url = f"https://www.youtube.com/watch?v={video_id}"
        published = snippet.get("publishedAt", "")
        from app.tools.implementations.tavily import _estimate_recency
        recency = _estimate_recency(published)
        description = snippet.get("description", "")
        results.append(ToolResult(
            tool_name="youtube_data_api",
            source_url=url,
            source_name=f"YouTube — {snippet.get('title', '')[:70]}",
            content=f"{snippet.get('title', '')}\n{description[:500]}".strip(),
            quote=description[:300] if description else None,
            recency=recency,
            metadata={"channel": snippet.get("channelTitle"), "published_at": published, "query": query},
        ))
    return results


async def youtube_comments(video_id: str, max_results: int = 50) -> list[ToolResult]:
    if not settings.youtube_api_key:
        return [ToolResult(tool_name="youtube_data_api", content="", error="YOUTUBE_API_KEY not configured")]

    params = {
        "part": "snippet",
        "videoId": video_id,
        "maxResults": max_results,
        "order": "relevance",
        "key": settings.youtube_api_key,
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(f"{YT_BASE}/commentThreads", params=params)
        resp.raise_for_status()
        data = resp.json()

    results = []
    for item in data.get("items", []):
        top = item.get("snippet", {}).get("topLevelComment", {}).get("snippet", {})
        text = top.get("textDisplay", "")
        published = top.get("publishedAt", "")
        from app.tools.implementations.tavily import _estimate_recency
        recency = _estimate_recency(published)
        results.append(ToolResult(
            tool_name="youtube_data_api",
            source_url=f"https://www.youtube.com/watch?v={video_id}",
            source_name=f"YouTube Comment — {top.get('authorDisplayName', 'User')}",
            content=text,
            quote=text[:300] if text else None,
            recency=recency,
            metadata={"likes": top.get("likeCount"), "video_id": video_id},
        ))
    return results
