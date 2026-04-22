"""
LinkedIn Ad Library — official API (requires approved access + identity verification).
Falls back to Firecrawl scrape of the public transparency page if API not available.
"""
from app.tools.base import ToolResult
from app.core.config import get_settings
import httpx

settings = get_settings()


async def linkedin_ad_search(query: str, limit: int = 10) -> list[ToolResult]:
    if not settings.linkedin_access_token:
        # Fall back to Firecrawl scrape of LinkedIn Ad Library public page
        from app.tools.implementations.firecrawl import firecrawl_scrape
        url = f"https://www.linkedin.com/ad-library/search?q={query}"
        result = await firecrawl_scrape(url)
        result.tool_name = "linkedin_ads"
        result.source_name = f"LinkedIn Ad Library (scraped) — {query}"
        return [result]

    headers = {
        "Authorization": f"Bearer {settings.linkedin_access_token}",
        "Content-Type": "application/json",
    }
    params = {"q": "creative", "search": query, "count": limit}

    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(
            "https://api.linkedin.com/v2/adCreativesV2",
            headers=headers,
            params=params,
        )
        if resp.status_code == 403:
            return [ToolResult(tool_name="linkedin_ads", content="", error="LinkedIn API access not approved. Complete identity verification.")]
        resp.raise_for_status()
        data = resp.json()

    results = []
    for item in data.get("elements", []):
        variables = item.get("variables", {}).get("data", {})
        headline = variables.get("com.linkedin.ads.rendering.update.variable.click.ClickAdVariables", {}).get("description", "")
        content = str(variables)[:500]
        results.append(ToolResult(
            tool_name="linkedin_ads",
            source_url="https://www.linkedin.com/ad-library/",
            source_name=f"LinkedIn Ad Library — {headline[:60] or 'Ad'}",
            content=content,
            quote=headline[:300] if headline else None,
            recency="7d",
            metadata={"query": query},
        ))
    return results
