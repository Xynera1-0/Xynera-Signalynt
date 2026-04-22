"""
Google Trends via pytrends (unofficial Google API wrapper).
Returns interest over time and related queries.
"""
from app.tools.base import ToolResult
from datetime import datetime, timezone


async def pytrends_interest(keywords: list[str], timeframe: str = "today 3-m", geo: str = "") -> list[ToolResult]:
    """
    timeframe options: 'now 1-d', 'now 7-d', 'today 1-m', 'today 3-m', 'today 12-m', 'today 5-y'
    """
    try:
        from pytrends.request import TrendReq
    except ImportError:
        return [ToolResult(tool_name="pytrends", content="", error="pytrends not installed")]

    import asyncio

    def _fetch() -> dict:
        pt = TrendReq(hl="en-US", tz=0)
        pt.build_payload(kw_list=keywords[:5], timeframe=timeframe, geo=geo)
        interest = pt.interest_over_time()
        related = pt.related_queries()
        return {"interest": interest, "related": related}

    try:
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, _fetch)
    except Exception as e:
        return [ToolResult(tool_name="pytrends", content="", error=str(e))]

    results = []

    interest_df = data["interest"]
    if not interest_df.empty:
        for kw in keywords:
            if kw in interest_df.columns:
                series = interest_df[kw]
                trend_summary = f"Keyword: '{kw}' | timeframe: {timeframe} | avg interest: {series.mean():.1f} | latest: {series.iloc[-1]} | peak: {series.max()}"
                results.append(ToolResult(
                    tool_name="pytrends",
                    source_url=f"https://trends.google.com/trends/explore?q={kw}",
                    source_name=f"Google Trends — {kw}",
                    content=trend_summary,
                    quote=trend_summary,
                    recency="7d",
                    metadata={"keyword": kw, "timeframe": timeframe, "geo": geo or "worldwide"},
                ))

    related = data["related"]
    for kw in keywords:
        kw_data = related.get(kw, {})
        top = kw_data.get("top")
        rising = kw_data.get("rising")
        content_parts = []
        if top is not None and not top.empty:
            content_parts.append(f"Top related: {top['query'].tolist()[:10]}")
        if rising is not None and not rising.empty:
            content_parts.append(f"Rising: {rising['query'].tolist()[:10]}")
        if content_parts:
            results.append(ToolResult(
                tool_name="pytrends",
                source_url=f"https://trends.google.com/trends/explore?q={kw}",
                source_name=f"Google Trends Related — {kw}",
                content="\n".join(content_parts),
                recency="7d",
                metadata={"keyword": kw, "type": "related_queries"},
            ))
    return results
