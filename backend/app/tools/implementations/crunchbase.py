"""Crunchbase API — VC funding flows, startup activity in adjacent categories."""
from app.tools.base import ToolResult
from app.core.config import get_settings
import httpx

settings = get_settings()
CB_BASE = "https://api.crunchbase.com/api/v4"


async def crunchbase_search(query: str, entity_type: str = "organizations", limit: int = 10) -> list[ToolResult]:
    if not settings.crunchbase_api_key:
        return [ToolResult(tool_name="crunchbase", content="", error="CRUNCHBASE_API_KEY not configured")]

    headers = {"X-cb-user-key": settings.crunchbase_api_key, "Content-Type": "application/json"}
    payload = {
        "field_ids": ["short_description", "funding_total", "last_funding_type", "last_funding_at", "homepage_url", "name"],
        "query": [{"type": "predicate", "field_id": "facet_ids", "operator_id": "includes", "values": [entity_type]}],
        "limit": limit,
    }
    if query:
        payload["query"].append({"type": "predicate", "field_id": "name", "operator_id": "contains", "values": [query]})

    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(f"{CB_BASE}/searches/{entity_type}", headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()

    results = []
    for entity in data.get("entities", []):
        props = entity.get("properties", {})
        name = props.get("name", "Unknown")
        desc = props.get("short_description", "")
        funding = props.get("funding_total", {})
        last_type = props.get("last_funding_type", "")
        last_date = props.get("last_funding_at", "")
        homepage = props.get("homepage_url", "")

        from app.tools.implementations.tavily import _estimate_recency
        recency = _estimate_recency(last_date)

        funding_str = ""
        if funding:
            funding_str = f" | Total funding: {funding.get('value_usd', '?')} USD"

        content = f"{name}: {desc}\nLast round: {last_type}{funding_str} ({last_date})"
        results.append(ToolResult(
            tool_name="crunchbase",
            source_url=homepage or f"https://www.crunchbase.com/organization/{name.lower().replace(' ', '-')}",
            source_name=f"Crunchbase — {name}",
            content=content,
            quote=desc[:300] if desc else None,
            recency=recency,
            metadata={"name": name, "last_funding_type": last_type, "last_funding_at": last_date, "query": query},
        ))
    return results
