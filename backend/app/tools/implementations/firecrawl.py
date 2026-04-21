from app.tools.base import ToolResult
from app.core.config import get_settings
import httpx

settings = get_settings()


async def firecrawl_scrape(url: str, extract_main_content: bool = True) -> ToolResult:
    if not settings.firecrawl_api_key:
        return ToolResult(tool_name="firecrawl_scrape", source_url=url, content="", error="FIRECRAWL_API_KEY not configured")

    headers = {"Authorization": f"Bearer {settings.firecrawl_api_key}", "Content-Type": "application/json"}
    payload = {"url": url, "formats": ["markdown"]}

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post("https://api.firecrawl.dev/v1/scrape", headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()

    content = data.get("data", {}).get("markdown", "") or ""
    title = data.get("data", {}).get("metadata", {}).get("title", "") or _domain(url)

    return ToolResult(
        tool_name="firecrawl_scrape",
        source_url=url,
        source_name=title,
        content=content[:4000],
        quote=content[:300] if content else None,
        recency="30d",
        metadata={"original_url": url, "char_count": len(content)},
    )


async def firecrawl_crawl(base_url: str, max_pages: int = 5) -> list[ToolResult]:
    """Crawl a site and return up to max_pages scraped pages."""
    if not settings.firecrawl_api_key:
        return [ToolResult(tool_name="firecrawl_scrape", content="", error="FIRECRAWL_API_KEY not configured")]

    headers = {"Authorization": f"Bearer {settings.firecrawl_api_key}", "Content-Type": "application/json"}
    payload = {"url": base_url, "limit": max_pages, "scrapeOptions": {"formats": ["markdown"]}}

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post("https://api.firecrawl.dev/v1/crawl", headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()

    results = []
    for page in data.get("data", []):
        content = page.get("markdown", "") or ""
        title = page.get("metadata", {}).get("title", "") or _domain(base_url)
        url = page.get("metadata", {}).get("sourceURL", base_url)
        results.append(ToolResult(
            tool_name="firecrawl_scrape",
            source_url=url,
            source_name=title,
            content=content[:4000],
            quote=content[:300] if content else None,
            recency="30d",
        ))
    return results


def _domain(url: str) -> str:
    try:
        from urllib.parse import urlparse
        return urlparse(url).netloc
    except Exception:
        return url
