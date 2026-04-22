"""
Patent search via Google Patents (Firecrawl) and USPTO full-text search.
Used by Contextual Scout to detect IP signals 12-18 months ahead of product launches.
"""
from app.tools.base import ToolResult
import httpx


async def patent_search(query: str, limit: int = 5) -> list[ToolResult]:
    """Search USPTO Patent Full-Text Database."""
    params = {"q": query, "f": "json", "o": str(0), "s": "relevance"}
    async with httpx.AsyncClient(timeout=20) as client:
        try:
            resp = await client.get("https://efts.uspto.gov/LATEST/search-efts", params=params)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            return [ToolResult(tool_name="patents_api", content="", error=f"USPTO API error: {e}")]

    results = []
    for hit in data.get("hits", {}).get("hits", [])[:limit]:
        source = hit.get("_source", {})
        patent_number = source.get("patentNumber", "")
        title = source.get("inventionTitle", "Unknown Patent")
        abstract = source.get("abstractText", "")
        filing_date = source.get("filingDate", "")
        assignee = source.get("assigneeEntityName", "Unknown Assignee")

        from app.tools.implementations.tavily import _estimate_recency
        recency = _estimate_recency(filing_date)

        content = f"Patent {patent_number}: {title}\nAssignee: {assignee}\nFiled: {filing_date}\nAbstract: {abstract[:400]}"
        results.append(ToolResult(
            tool_name="patents_api",
            source_url=f"https://patents.google.com/patent/US{patent_number}" if patent_number else "https://www.google.com/patents",
            source_name=f"USPTO Patent — {title[:60]}",
            content=content,
            quote=abstract[:300] if abstract else title,
            recency=recency,
            metadata={"patent_number": patent_number, "assignee": assignee, "filing_date": filing_date},
        ))
    return results
