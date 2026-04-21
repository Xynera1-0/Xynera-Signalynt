"""
Meta Ad Library API — official, free, identity-verified.
Returns active ad creatives, spend ranges, demographics for a page/keyword.
Requires: META_ACCESS_TOKEN + verified identity with Meta.
"""
from app.tools.base import ToolResult
from app.core.config import get_settings
import httpx

settings = get_settings()
META_ADS_BASE = "https://graph.facebook.com/v19.0/ads_archive"


async def meta_ad_search(query: str, country: str = "ALL", limit: int = 10) -> list[ToolResult]:
    if not settings.meta_access_token:
        return [ToolResult(tool_name="meta_ad_library", content="", error="META_ACCESS_TOKEN not configured")]

    params = {
        "search_terms": query,
        "ad_type": "ALL",
        "ad_reached_countries": country,
        "limit": limit,
        "fields": "id,ad_creative_bodies,ad_creative_link_captions,page_name,spend,impressions,demographic_distribution,ad_delivery_start_time",
        "access_token": settings.meta_access_token,
    }
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(META_ADS_BASE, params=params)
        resp.raise_for_status()
        data = resp.json()

    results = []
    for ad in data.get("data", []):
        bodies = ad.get("ad_creative_bodies", [])
        captions = ad.get("ad_creative_link_captions", [])
        spend = ad.get("spend", {})
        impressions = ad.get("impressions", {})
        page = ad.get("page_name", "Unknown Page")
        start = ad.get("ad_delivery_start_time", "")

        content_parts = []
        if bodies:
            content_parts.append(f"Ad copy: {' | '.join(bodies[:2])}")
        if captions:
            content_parts.append(f"CTA: {' | '.join(captions[:2])}")
        if spend:
            content_parts.append(f"Spend: {spend.get('lower_bound', '?')}–{spend.get('upper_bound', '?')} USD")
        if impressions:
            content_parts.append(f"Impressions: {impressions.get('lower_bound', '?')}–{impressions.get('upper_bound', '?')}")

        from app.tools.implementations.tavily import _estimate_recency
        recency = _estimate_recency(start)
        content = "\n".join(content_parts)

        results.append(ToolResult(
            tool_name="meta_ad_library",
            source_url=f"https://www.facebook.com/ads/library/?id={ad.get('id')}",
            source_name=f"Meta Ad Library — {page}",
            content=content,
            quote=bodies[0][:300] if bodies else None,
            recency=recency,
            metadata={"page_name": page, "ad_id": ad.get("id"), "spend": spend, "query": query},
        ))
    return results
