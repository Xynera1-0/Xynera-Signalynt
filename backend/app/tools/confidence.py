"""
Confidence scoring — all weights live in Postgres.
Change DB rows, scoring changes. No code deploy needed.
"""
from decimal import Decimal
from typing import Any
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession


async def calculate_confidence(
    tool_name: str,
    recency: str,
    source_count: int,
    quote_present: bool,
    db: AsyncSession,
) -> tuple[float, dict[str, Any]]:
    """
    Returns (final_score, breakdown_dict).
    All weights fetched from Postgres at call time.
    """
    # 1. Base score for the tool
    base_row = await db.execute(
        text(
            "SELECT base_score FROM tool_confidence_config WHERE tool_name = :tool_name"
        ),
        {"tool_name": tool_name},
    )
    base_score_raw = base_row.scalar_one_or_none()
    if base_score_raw is None:
        # Unknown tool — use conservative default, don't crash
        base_score_raw = Decimal("0.50")

    # 2. Recency modifier
    recency_row = await db.execute(
        text(
            "SELECT multiplier FROM confidence_modifiers "
            "WHERE modifier_key = 'recency' AND condition = :condition"
        ),
        {"condition": recency},
    )
    recency_mult = recency_row.scalar_one_or_none() or Decimal("1.0")

    # 3. Quote modifier
    quote_condition = "yes" if quote_present else "no"
    quote_row = await db.execute(
        text(
            "SELECT multiplier FROM confidence_modifiers "
            "WHERE modifier_key = 'quote_present' AND condition = :condition"
        ),
        {"condition": quote_condition},
    )
    quote_mult = quote_row.scalar_one_or_none() or Decimal("1.0")

    # 4. Corroboration multiplier — pick the highest matching band
    corroboration_row = await db.execute(
        text(
            "SELECT multiplier FROM corroboration_rules "
            "WHERE min_sources <= :count AND (max_sources >= :count OR max_sources IS NULL) "
            "ORDER BY min_sources DESC LIMIT 1"
        ),
        {"count": source_count},
    )
    corroboration_mult = corroboration_row.scalar_one_or_none() or Decimal("1.0")

    raw = float(base_score_raw) * float(recency_mult) * float(quote_mult) * float(corroboration_mult)
    final = round(min(raw, 1.0), 4)

    breakdown = {
        "base_score": float(base_score_raw),
        "recency_multiplier": float(recency_mult),
        "quote_multiplier": float(quote_mult),
        "corroboration_multiplier": float(corroboration_mult),
        "source_count": source_count,
        "final_score": final,
    }
    return final, breakdown
