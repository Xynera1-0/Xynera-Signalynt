"""SEMRush API — keyword data, traffic analytics, competitor SEO positioning."""
from app.tools.base import ToolResult
from app.core.config import get_settings
import httpx

settings = get_settings()
SEMRUSH_BASE = "https://api.semrush.com"


async def semrush_domain_overview(domain: str, database: str = "us") -> list[ToolResult]:
    if not settings.semrush_api_key:
        return [ToolResult(tool_name="semrush", content="", error="SEMRUSH_API_KEY not configured")]

    params = {
        "type": "domain_ranks",
        "key": settings.semrush_api_key,
        "export_columns": "Dn,Rk,Or,Ot,Oc,Ad,At,Ac",
        "domain": domain,
        "database": database,
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(SEMRUSH_BASE, params=params)
        resp.raise_for_status()
        raw = resp.text

    lines = raw.strip().split("\n")
    if len(lines) < 2:
        return [ToolResult(tool_name="semrush", content=raw, source_name=f"SEMRush — {domain}", recency="7d")]

    headers_row = lines[0].split(";")
    values_row = lines[1].split(";") if len(lines) > 1 else []
    data = dict(zip(headers_row, values_row))
    content = (
        f"Domain: {domain} | Organic keywords: {data.get('Organic Keywords')} | "
        f"Organic traffic: {data.get('Organic Traffic')} | "
        f"Paid keywords: {data.get('Adwords Keywords')} | "
        f"Paid traffic: {data.get('Adwords Traffic')}"
    )
    return [ToolResult(
        tool_name="semrush",
        source_url=f"https://www.semrush.com/analytics/overview/?q={domain}",
        source_name=f"SEMRush — {domain}",
        content=content,
        quote=content[:300],
        recency="7d",
        metadata={"domain": domain, "database": database, "raw_data": data},
    )]


async def semrush_keyword_overview(keyword: str, database: str = "us") -> list[ToolResult]:
    if not settings.semrush_api_key:
        return [ToolResult(tool_name="semrush", content="", error="SEMRUSH_API_KEY not configured")]

    params = {
        "type": "phrase_this",
        "key": settings.semrush_api_key,
        "export_columns": "Ph,Nq,Cp,Co,Nr,Td",
        "phrase": keyword,
        "database": database,
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(SEMRUSH_BASE, params=params)
        resp.raise_for_status()
        raw = resp.text

    lines = raw.strip().split("\n")
    headers_row = lines[0].split(";") if lines else []
    values_row = lines[1].split(";") if len(lines) > 1 else []
    data = dict(zip(headers_row, values_row))
    content = (
        f"Keyword: '{keyword}' | Volume: {data.get('Search Volume')} | "
        f"CPC: {data.get('CPC')} | Competition: {data.get('Competition')} | "
        f"Results: {data.get('Number of Results')} | Trend: {data.get('Trends')}"
    )
    return [ToolResult(
        tool_name="semrush",
        source_url=f"https://www.semrush.com/analytics/keywordoverview/?q={keyword}",
        source_name=f"SEMRush Keyword — {keyword}",
        content=content,
        quote=content[:300],
        recency="7d",
        metadata={"keyword": keyword, "database": database, "raw_data": data},
    )]
