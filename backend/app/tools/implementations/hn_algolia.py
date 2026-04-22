"""
HackerNews via Algolia API — direct HTTP, no API key required.

Endpoints:
  /search          — sorted by relevance, then points, then num_comments
  /search_by_date  — sorted by date, most recent first

Rate limit: 10,000 requests/hour per IP.
"""
from __future__ import annotations

import logging

import httpx

from app.tools.base import ToolResult

logger = logging.getLogger(__name__)

_BASE = "https://hn.algolia.com/api/v1"


def _hits_to_results(hits: list[dict], query: str) -> list[ToolResult]:
    from app.tools.implementations.tavily import _estimate_recency

    results = []
    for hit in hits:
        object_id = hit.get("objectID", "")
        url = hit.get("url") or f"https://news.ycombinator.com/item?id={object_id}"
        title = hit.get("title") or hit.get("story_title") or "HN Post"
        text = (hit.get("story_text") or hit.get("comment_text") or "").strip()
        created = hit.get("created_at", "")
        points = hit.get("points") or 0
        num_comments = hit.get("num_comments") or 0

        content_parts = [title]
        if text:
            content_parts.append(text[:600])
        content = "\n".join(content_parts)

        results.append(ToolResult(
            tool_name="hn_algolia",
            source_url=url,
            source_name=f"Hacker News — {title[:70]}",
            content=content,
            quote=text[:300] if text else title,
            recency=_estimate_recency(created),
            metadata={
                "author": hit.get("author"),
                "points": points,
                "num_comments": num_comments,
                "created_at": created,
                "object_id": object_id,
                "query": query,
            },
        ))
    return results


async def hn_search(
    query: str,
    tags: str = "story",
    hits_per_page: int = 10,
    page: int = 0,
    numeric_filters: str = "",
    sort_by_date: bool = False,
) -> list[ToolResult]:
    """
    Search Hacker News via Algolia.

    Args:
        query:          Full-text search query.
        tags:           Filter tag(s). Single: 'story', 'comment', 'ask_hn', 'show_hn',
                        'front_page'. Combined (AND): 'story,author_pg'.
                        OR group: '(story,poll)'.
        hits_per_page:  Results per page (default 10, max 50).
        page:           Page number for pagination (0-indexed).
        numeric_filters: e.g. 'points>100' or 'created_at_i>1700000000'.
        sort_by_date:   If True use /search_by_date (most recent first).
                        If False use /search (relevance → points → comments).
    """
    endpoint = f"{_BASE}/search_by_date" if sort_by_date else f"{_BASE}/search"
    params: dict[str, str | int] = {
        "query": query,
        "tags": tags,
        "hitsPerPage": min(hits_per_page, 50),
        "page": page,
    }
    if numeric_filters:
        params["numericFilters"] = numeric_filters

    logger.info(
        "hn_algolia | endpoint=%s query=%r tags=%s hits_per_page=%d page=%d numeric_filters=%r",
        endpoint.split("/")[-1], query, tags, hits_per_page, page, numeric_filters,
    )

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(endpoint, params=params)
        resp.raise_for_status()
        data = resp.json()

    hits = data.get("hits", [])
    logger.info("hn_algolia | returned hits=%d nbPages=%d", len(hits), data.get("nbPages", 1))
    return _hits_to_results(hits, query)


async def hn_search_recent(
    query: str,
    tags: str = "story",
    hits_per_page: int = 10,
    numeric_filters: str = "",
) -> list[ToolResult]:
    """Convenience wrapper: search sorted by date (most recent first)."""
    return await hn_search(
        query=query,
        tags=tags,
        hits_per_page=hits_per_page,
        sort_by_date=True,
        numeric_filters=numeric_filters,
    )
