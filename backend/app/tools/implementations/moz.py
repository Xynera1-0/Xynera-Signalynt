"""Moz Link Explorer API v2 — domain authority and link metrics for competitor domains."""
from __future__ import annotations

import httpx
from app.tools.base import ToolResult
from app.core.config import get_settings

MOZ_URL_METRICS = "https://lsapi.seomoz.com/v2/url_metrics"


def _get_auth() -> tuple[str, str] | None:
    settings = get_settings()
    if settings.moz_access_id and settings.moz_secret_key:
        return (settings.moz_access_id, settings.moz_secret_key)
    return None


async def moz_domain_metrics(domain: str) -> list[ToolResult]:
    """
    Fetch Domain Authority, Page Authority, backlink counts, and spam score
    for a competitor domain from the Moz Link Explorer API.

    Returns metrics useful for competitive SEO positioning analysis.
    """
    auth = _get_auth()
    if not auth:
        return [ToolResult(
            tool_name="moz_domain_metrics",
            content="",
            error="MOZ_ACCESS_ID or MOZ_SECRET_KEY not configured",
        )]

    # Strip protocol prefix for cleaner targets
    target = domain.replace("https://", "").replace("http://", "").rstrip("/")

    payload = {"targets": [target]}

    async with httpx.AsyncClient(timeout=20) as client:
        try:
            resp = await client.post(MOZ_URL_METRICS, json=payload, auth=auth)
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            return [ToolResult(
                tool_name="moz_domain_metrics",
                content="",
                error=f"Moz API error {e.response.status_code}: {e.response.text[:200]}",
            )]

    data = resp.json()
    results_list = data.get("results", [])
    if not results_list:
        return [ToolResult(
            tool_name="moz_domain_metrics",
            source_url=f"https://moz.com/domain-analysis?site={target}",
            source_name=f"Moz — {target}",
            content=f"No metrics returned for {target}",
            error="empty_results",
        )]

    r = results_list[0]
    da = r.get("domain_authority", "N/A")
    pa = r.get("page_authority", "N/A")
    spam = r.get("spam_score", "N/A")
    root_domains_in = r.get("root_domains_to_root_domain", "N/A")
    ext_pages_in = r.get("external_pages_to_root_domain", "N/A")
    last_crawled = r.get("last_crawled", "N/A")
    link_propensity = r.get("link_propensity", "N/A")

    content = (
        f"Domain: {target} | "
        f"Domain Authority: {da}/100 | "
        f"Page Authority: {pa}/100 | "
        f"Spam Score: {spam} | "
        f"Root Domains Linking In: {root_domains_in} | "
        f"External Pages Linking In: {ext_pages_in} | "
        f"Link Propensity: {link_propensity} | "
        f"Last Crawled: {last_crawled}"
    )

    return [ToolResult(
        tool_name="moz_domain_metrics",
        source_url=f"https://moz.com/domain-analysis?site={target}",
        source_name=f"Moz Link Explorer — {target}",
        content=content,
        quote=f"Domain Authority: {da}/100, Spam Score: {spam}, Root Domains Linking In: {root_domains_in}",
        recency="7d",
        metadata={
            "domain": target,
            "domain_authority": da,
            "page_authority": pa,
            "spam_score": spam,
            "root_domains_to_root_domain": root_domains_in,
            "external_pages_to_root_domain": ext_pages_in,
            "last_crawled": last_crawled,
        },
    )]


async def moz_bulk_domain_metrics(domains: list[str]) -> list[ToolResult]:
    """
    Fetch DA/PA/backlink metrics for up to 50 competitor domains in a single request.
    Useful when spy_scout needs to compare multiple competitors at once.
    """
    auth = _get_auth()
    if not auth:
        return [ToolResult(
            tool_name="moz_domain_metrics",
            content="",
            error="MOZ_ACCESS_ID or MOZ_SECRET_KEY not configured",
        )]

    targets = [d.replace("https://", "").replace("http://", "").rstrip("/") for d in domains[:50]]
    payload = {"targets": targets}

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.post(MOZ_URL_METRICS, json=payload, auth=auth)
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            return [ToolResult(
                tool_name="moz_domain_metrics",
                content="",
                error=f"Moz API error {e.response.status_code}: {e.response.text[:200]}",
            )]

    results = []
    for r in resp.json().get("results", []):
        domain = r.get("root_domain", targets[len(results)])
        da = r.get("domain_authority", "N/A")
        pa = r.get("page_authority", "N/A")
        spam = r.get("spam_score", "N/A")
        root_domains_in = r.get("root_domains_to_root_domain", "N/A")
        content = (
            f"Domain: {domain} | DA: {da}/100 | PA: {pa}/100 | "
            f"Spam: {spam} | Root Domains In: {root_domains_in}"
        )
        results.append(ToolResult(
            tool_name="moz_domain_metrics",
            source_url=f"https://moz.com/domain-analysis?site={domain}",
            source_name=f"Moz — {domain}",
            content=content,
            quote=f"DA: {da}/100, Spam: {spam}, Root Domains In: {root_domains_in}",
            recency="7d",
            metadata={"domain": domain, "domain_authority": da, "page_authority": pa, "spam_score": spam},
        ))
    return results
