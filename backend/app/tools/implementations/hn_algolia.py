"""HackerNews via Algolia API — full-text search across HN stories and comments."""
from app.tools.base import ToolResult
import httpx


async def hn_search(query: str, tags: str = "story", hits_per_page: int = 10) -> list[ToolResult]:
    """
    tags: 'story' | 'comment' | 'ask_hn' | 'show_hn' | 'front_page'
    """
    params = {"query": query, "tags": tags, "hitsPerPage": hits_per_page}

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get("https://hn.algolia.com/api/v1/search", params=params)
        resp.raise_for_status()
        data = resp.json()

    results = []
    for hit in data.get("hits", []):
        url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
        title = hit.get("title") or hit.get("story_title") or "HN Post"
        text = hit.get("story_text") or hit.get("comment_text") or ""
        created = hit.get("created_at", "")

        from app.tools.implementations.tavily import _estimate_recency
        recency = _estimate_recency(created)

        results.append(ToolResult(
            tool_name="hn_algolia",
            source_url=url,
            source_name=f"Hacker News — {title[:70]}",
            content=f"{title}\n{text[:600]}".strip(),
            quote=text[:300] if text else title,
            recency=recency,
            metadata={
                "author": hit.get("author"),
                "points": hit.get("points"),
                "num_comments": hit.get("num_comments"),
                "created_at": created,
                "query": query,
            },
        ))
    return results
