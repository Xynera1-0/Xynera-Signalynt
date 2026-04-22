"""
Meta Ad Library API — official, free, identity-verified.
Returns active ad creatives for a brand/keyword search.
Requires: META_ACCESS_TOKEN + verified identity with Meta.

API constraints:
  - search_terms: max 100 characters (API hard limit)
  - ad_reached_countries: must be a JSON array string e.g. '["ALL"]' or '["LK","IN"]'
  - spend/impressions/demographic_distribution fields are ONLY available for
    POLITICAL_AND_ISSUE_ADS — using them with ad_type=ALL causes a 400 error.
  - Available fields for ALL ads: id, page_id, page_name, ad_snapshot_url,
    ad_creative_bodies, ad_creative_link_captions,
    ad_delivery_start_time, ad_delivery_stop_time
"""
from __future__ import annotations
import json

from app.tools.base import ToolResult
from app.core.config import get_settings
import httpx

settings = get_settings()
META_ADS_BASE = "https://graph.facebook.com/v19.0/ads_archive"

# Fields available for ALL ad types (spend/impressions require POLITICAL_AND_ISSUE_ADS)
_FIELDS_ALL = (
    "id,page_id,page_name,ad_snapshot_url,"
    "ad_creative_bodies,ad_creative_link_captions,"
    "ad_delivery_start_time,ad_delivery_stop_time"
)


def _truncate_search_terms(query: str) -> str:
    """Meta API requires search_terms ≤ 100 characters.
    Extract the first 5 meaningful words to keep it representative.
    """
    words = query.strip().split()
    truncated = " ".join(words[:6])
    return truncated[:100]


async def meta_ad_search(
    query: str,
    countries: list[str] | None = None,
    limit: int = 10,
) -> list[ToolResult]:
    if not settings.meta_access_token:
        return [ToolResult(tool_name="meta_ad_library", content="", error="META_ACCESS_TOKEN not configured")]

    # Enforce API constraints
    search_terms = _truncate_search_terms(query)
    # ad_reached_countries must be a JSON array
    country_list = countries or ["ALL"]
    params = {
        "search_terms": search_terms,
        "ad_type": "ALL",
        "ad_reached_countries": json.dumps(country_list),
        "limit": limit,
        "fields": _FIELDS_ALL,
        "access_token": settings.meta_access_token,
    }

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(META_ADS_BASE, params=params)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as exc:
        return [ToolResult(
            tool_name="meta_ad_library",
            content="",
            error=f"Meta Ads API error {exc.response.status_code}: {exc.response.text[:300]}",
        )]

    results = []
    for ad in data.get("data", []):
        bodies = ad.get("ad_creative_bodies") or []
        captions = ad.get("ad_creative_link_captions") or []
        page = ad.get("page_name", "Unknown Page")
        start = ad.get("ad_delivery_start_time", "")
        stop = ad.get("ad_delivery_stop_time", "")
        snapshot_url = ad.get("ad_snapshot_url", "")

        content_parts = []
        if bodies:
            content_parts.append(f"Ad copy: {' | '.join(bodies[:2])}")
        if captions:
            content_parts.append(f"CTA: {' | '.join(captions[:2])}")
        if start:
            period = f"{start[:10]}" + (f" → {stop[:10]}" if stop else " → active")
            content_parts.append(f"Delivery: {period}")

        from app.tools.implementations.tavily import _estimate_recency
        recency = _estimate_recency(start)
        content = "\n".join(content_parts) or "Ad found (no creative text available)"

        results.append(ToolResult(
            tool_name="meta_ad_library",
            source_url=snapshot_url or f"https://www.facebook.com/ads/library/?id={ad.get('id')}",
            source_name=f"Meta Ad Library — {page}",
            content=content,
            quote=bodies[0][:300] if bodies else None,
            recency=recency,
            metadata={
                "page_name": page,
                "page_id": ad.get("page_id"),
                "ad_id": ad.get("id"),
                "search_terms_used": search_terms,
                "original_query": query,
            },
        ))
    return results
