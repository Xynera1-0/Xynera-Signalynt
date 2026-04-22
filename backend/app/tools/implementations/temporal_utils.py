"""
Temporal utilities — Calendarific (cultural calendar) + platform timing heuristics.
Used exclusively by the Temporal Intelligence Agent.
"""
from app.tools.base import ToolResult
from app.core.config import get_settings
from datetime import datetime, timezone
import httpx

settings = get_settings()


async def calendarific_events(country: str = "US", year: int | None = None, month: int | None = None) -> list[ToolResult]:
    if not settings.calendarific_api_key:
        return [ToolResult(tool_name="calendarific", content="", error="CALENDARIFIC_API_KEY not configured")]

    now = datetime.now(timezone.utc)
    params = {
        "api_key": settings.calendarific_api_key,
        "country": country,
        "year": year or now.year,
    }
    if month:
        params["month"] = month

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get("https://calendarific.com/api/v2/holidays", params=params)
        resp.raise_for_status()
        data = resp.json()

    holidays = data.get("response", {}).get("holidays", [])
    results = []
    for h in holidays[:20]:  # cap at 20
        date_str = h.get("date", {}).get("iso", "")
        content = f"{h.get('name')} ({date_str}): {h.get('description', '')}"
        results.append(ToolResult(
            tool_name="calendarific",
            source_url="https://calendarific.com",
            source_name=f"Cultural Calendar — {h.get('name')}",
            content=content,
            recency="30d",
            metadata={"country": country, "date": date_str, "type": h.get("type", [])},
        ))
    return results


def get_platform_timing_heuristics(platform: str) -> ToolResult:
    """
    Static heuristics — best times to post per platform.
    Based on well-established industry data. No API call needed.
    """
    heuristics = {
        "linkedin": {
            "best_days": ["Tuesday", "Wednesday", "Thursday"],
            "best_hours_utc": "08:00-10:00",
            "worst_days": ["Saturday", "Sunday"],
            "notes": "B2B content performs best during business hours. Avoid Friday afternoons.",
        },
        "instagram": {
            "best_days": ["Monday", "Wednesday", "Friday"],
            "best_hours_utc": "11:00-13:00",
            "worst_days": ["Sunday"],
            "notes": "Lunch hour engagement peaks. Reels can be posted evenings (18:00-20:00) for discovery.",
        },
        "twitter": {
            "best_days": ["Tuesday", "Wednesday", "Thursday"],
            "best_hours_utc": "09:00-11:00",
            "worst_days": ["Saturday"],
            "notes": "Morning news cycle amplifies reach. Trending topics window is 1-3 hours.",
        },
        "facebook": {
            "best_days": ["Wednesday"],
            "best_hours_utc": "13:00-16:00",
            "worst_days": ["Saturday"],
            "notes": "Midweek afternoon peak. Video content gets boosted distribution.",
        },
        "tiktok": {
            "best_days": ["Tuesday", "Thursday", "Friday"],
            "best_hours_utc": "18:00-22:00",
            "worst_days": ["Sunday"],
            "notes": "Evening posts capture prime scrolling time. Algorithm cares less about posting time than watch rate.",
        },
    }
    platform_lower = platform.lower()
    data = heuristics.get(platform_lower, {
        "best_days": ["Tuesday", "Wednesday"],
        "best_hours_utc": "09:00-11:00",
        "notes": "General best-practice timing. Check platform-specific analytics.",
    })
    content = (
        f"Platform: {platform}\n"
        f"Best days: {', '.join(data.get('best_days', []))}\n"
        f"Best hours (UTC): {data.get('best_hours_utc', 'N/A')}\n"
        f"Avoid: {', '.join(data.get('worst_days', []))}\n"
        f"Notes: {data.get('notes', '')}"
    )
    return ToolResult(
        tool_name="platform_timing",
        source_url=None,
        source_name=f"Platform Timing Heuristics — {platform}",
        content=content,
        recency="30d",
        metadata={"platform": platform, "source": "internal_heuristics"},
    )
