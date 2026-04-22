"""
Content Graph — Team 2.
  1. Content Strategist — reads research + KB → defines angles + test hypothesis
  2. Content Generator  — ContentAgentPool.content_agent, one call per platform
  3. Variant Builder    — structurally composes variants from base content + strategy spec
                          (no additional LLM calls — reuses tones/headlines already generated)

Design spec is NOT generated here. ContentAgentPool.design_agent is available
for on-demand asset generation when a visual is explicitly requested.
"""
from __future__ import annotations
import json
import logging
import uuid
from typing import TypedDict, List

from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.base import get_content_llm, coerce_llm_content, llm_ainvoke_with_retry

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# State
# ─────────────────────────────────────────────────────────────────────────────

class ContentState(TypedDict, total=False):
    # ── Input (required at invocation) ──────────────────────────────
    user_query: str                  # the raw user message — primary creative brief
    conversation_history: list       # prior turns (newest last) for context
    content_brief: dict              # synthesis data if research ran first
    kb_context: dict
    platforms: List[str]
    hypothesis: str
    # ── Intermediate ────────────────────────────────────────────
    strategy: dict
    content_type: str                # detected content type: flyer | post | email | ...
    variants_plan: List[dict]
    base_contents: dict
    # ── Output ───────────────────────────────────────────────
    variants: List[dict]



# ─────────────────────────────────────────────────────────────────────────────
# Node 1 — Content Strategist
# ─────────────────────────────────────────────────────────────────────────────

async def content_strategist_node(state: ContentState) -> dict:
    logger.info("content_strategist | starting platforms=%s", state.get("platforms"))
    from app.agents.content_generation_agent import _TYPE_KEYWORDS

    llm = get_content_llm(temperature=0.3)

    user_query = state.get("user_query") or ""
    content_brief = state.get("content_brief") or {}
    kb_context = state.get("kb_context") or {}
    platforms = state.get("platforms") or ["linkedin"]
    history = state.get("conversation_history") or []

    # ── Detect content type from user query first ────────────────────────────
    query_lower = user_query.lower()
    detected_type = "flyer"  # default
    for ctype, keywords in _TYPE_KEYWORDS.items():
        if any(kw in query_lower for kw in keywords):
            detected_type = ctype
            break
    logger.info("content_strategist | detected_type=%s", detected_type)

    # ── Extract prior conversation context (selected variant, research, etc.) ─
    history_text = ""
    if history:
        lines = [f"  [{m['role'].upper()}]: {m['content'][:400]}" for m in history[-8:]]
        history_text = "\n─── Prior conversation (newest last) ───\n" + "\n".join(lines)

    # ── Research data (may be empty for content_only route) ──────────────────
    brief_text = ""
    if content_brief:
        brief_text = f"\nResearch findings brief:\n{json.dumps(content_brief, indent=2)[:2000]}"

    # ── KB signals — cap each list tightly to avoid 413 ──────────────────────
    growth_signals  = kb_context.get("growth_signals",  [])[:3]
    winning_patterns = kb_context.get("winning_patterns", [])[:3]
    audience_insights = kb_context.get("audience_insights", [])[:3]
    kb_text = (
        f"\nKB growth signals: {json.dumps(growth_signals, indent=2)[:600]}"
        f"\nKB winning patterns: {json.dumps(winning_patterns, indent=2)[:600]}"
        f"\nKB audience insights: {json.dumps(audience_insights, indent=2)[:600]}"
    ) if (growth_signals or winning_patterns or audience_insights) else ""

    prompt = f"""You are a content strategist for a data-driven marketing platform.

User request: {user_query}
{history_text}
{brief_text}
{kb_text}

Target platforms: {platforms}
Content type to produce: {detected_type}

Instructions:
- If the user has already selected a variant (e.g. "Variant A — Emotional Hook"), use that as the single variant plan. Do NOT invent new variants.
- If the user references prior research findings or conversation context, use those details as the creative brief.
- If no research or brief is available, use the user's request directly as the creative brief — infer the minimum context needed, do not hallucinate details.
- Set primary_angle to reflect exactly what the user asked for.

Return JSON only:
{{
  "primary_angle": "...",
  "hypothesis": "...",
  "test_variables": ["hook_type"],
  "variants": [
    {{
      "name": "Variant A — Emotional Hook",
      "hook_type": "emotional",
      "cta_type": "urgency",
      "format": "{detected_type}",
      "tone": "conversational",
      "angle": "...",
      "is_control": true
    }}
  ]
}}"""

    response = await llm_ainvoke_with_retry(llm, [
        SystemMessage(content="You are a content strategist. Return valid JSON only."),
        HumanMessage(content=prompt),
    ])
    content = coerce_llm_content(response.content) if hasattr(response, "content") else str(response)
    strategy = _parse_json(content)

    logger.info("content_strategist | completed angle=%r variants_planned=%d",
                strategy.get("primary_angle", "")[:60], len(strategy.get("variants", [])))
    return {
        "strategy": strategy,
        "content_type": detected_type,
        "variants_plan": strategy.get("variants", []),
        "hypothesis": strategy.get("hypothesis", ""),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Node 2 — Content Generator
# Calls existing ContentAgentPool per platform, uses primary angle
# ─────────────────────────────────────────────────────────────────────────────

async def content_generator_node(state: ContentState) -> dict:
    logger.info("content_generator | starting platforms=%s", state.get("platforms"))
    from app.agents.content_generation_agent import ContentAgentPool

    llm = get_content_llm(temperature=0.7)
    pool = ContentAgentPool(llm=llm)

    user_query = state.get("user_query") or ""
    content_brief = state.get("content_brief") or {}
    strategy = state.get("strategy") or {}
    platforms = state.get("platforms") or ["linkedin"]
    # content_type detected by strategist; fall back to query detection
    content_type = state.get("content_type") or "flyer"

    base_contents = {}
    for platform in platforms:
        # Build a compact brief — user_query is the primary creative directive
        synthesis_data = content_brief.get("synthesis") or {}
        key_themes = synthesis_data.get("key_themes", []) if isinstance(synthesis_data, dict) else []
        research_summary = synthesis_data.get("summary", "") if isinstance(synthesis_data, dict) else str(synthesis_data)

        input_data = {
            "prompt": user_query or research_summary or strategy.get("primary_angle", ""),
            "platform": platform,
            "primary_angle": strategy.get("primary_angle", ""),
            "tone": strategy.get("variants", [{}])[0].get("tone", "professional") if strategy.get("variants") else "professional",
            "goal": content_brief.get("objective", ""),
            "key_themes": key_themes[:3],
        }
        try:
            result = pool.content_agent(input_data, content_type)
            base_contents[platform] = result
        except Exception as e:
            logger.warning("content_generator | platform=%s error=%s", platform, e)
            base_contents[platform] = {"error": str(e)}

    ok = [p for p, v in base_contents.items() if "error" not in v]
    fail = [p for p, v in base_contents.items() if "error" in v]
    logger.info("content_generator | completed ok=%s fail=%s", ok, fail)
    return {"base_contents": base_contents}


# ─────────────────────────────────────────────────────────────────────────────
# Node 3 — Variant Builder
# Structurally composes variants from base_contents + strategy variants_plan.
# content_generator already produced emotional/professional/minimal tones and
# 3 headlines per platform — we select and tag; no extra LLM calls.
# ─────────────────────────────────────────────────────────────────────────────

_TONE_MAP = {
    "emotional": "emotional",
    "conversational": "emotional",
    "urgent": "emotional",
    "professional": "professional",
    "rational": "professional",
    "data_driven": "professional",
    "minimal": "minimal",
    "concise": "minimal",
}


def _pick_body(base: dict, tone: str) -> str:
    """Select the pre-generated tone variation that best matches the spec."""
    variations: dict = base.get("variations") or {}
    bucket = _TONE_MAP.get(tone, "professional")
    return variations.get(bucket) or base.get("body", "")


def _pick_headline(base: dict, index: int) -> str:
    """Round-robin across the 3 pre-generated headlines."""
    headlines = base.get("headlines") or [base.get("headline", "")]
    return headlines[index % len(headlines)] if headlines else ""


async def variant_builder_node(state: ContentState) -> dict:
    logger.info("variant_builder | starting plans=%d platforms=%s",
                len(state.get("variants_plan", [])), state.get("platforms"))
    base_contents = state.get("base_contents", {})
    variants_plan = state.get("variants_plan", [])
    platforms = state.get("platforms", ["linkedin"])

    if not variants_plan:
        # No test plan — wrap base content as a single control variant
        platform = platforms[0]
        base = base_contents.get(platform, {})
        variants = [{
            "id": str(uuid.uuid4()),
            "name": "Default",
            "is_control": True,
            "platform": platform,
            "hook_type": "standard",
            "cta_type": "standard",
            "format": "post",
            "tone": "professional",
            "content": {
                "headline": _pick_headline(base, 0),
                "body": base.get("body", ""),
                "cta": base.get("cta", ""),
                "platform_output": base.get("platform_output", ""),
            },
            "variable_values": {},
        }]
        return {"variants": variants}

    all_variants = []
    for platform in platforms:
        base = base_contents.get(platform, {})
        for idx, variant_spec in enumerate(variants_plan):
            tone = variant_spec.get("tone", "") or variant_spec.get("hook_type", "")
            all_variants.append({
                "id": str(uuid.uuid4()),
                "name": variant_spec.get("name", f"Variant {idx + 1}"),
                "is_control": variant_spec.get("is_control", False),
                "platform": platform,
                "hook_type": variant_spec.get("hook_type", ""),
                "cta_type": variant_spec.get("cta_type", ""),
                "format": variant_spec.get("format", "post"),
                "tone": tone,
                "content": {
                    "headline": _pick_headline(base, idx),
                    "body": _pick_body(base, tone),
                    "cta": base.get("cta", ""),
                    "platform_output": base.get("platform_output", ""),
                },
                "variable_values": {
                    "hook": variant_spec.get("hook_type", ""),
                    "cta": variant_spec.get("cta_type", ""),
                    "format": variant_spec.get("format", ""),
                },
            })

    logger.info("variant_builder | completed variants=%d", len(all_variants))
    return {"variants": all_variants}


# ─────────────────────────────────────────────────────────────────────────────
# Graph wiring
# ─────────────────────────────────────────────────────────────────────────────

def build_content_graph():
    builder = StateGraph(ContentState)

    builder.add_node("content_strategist", content_strategist_node)
    builder.add_node("content_generator", content_generator_node)
    builder.add_node("variant_builder", variant_builder_node)

    builder.set_entry_point("content_strategist")
    builder.add_edge("content_strategist", "content_generator")
    builder.add_edge("content_generator", "variant_builder")
    builder.add_edge("variant_builder", END)

    return builder.compile()


content_graph = build_content_graph()


def _parse_json(text: str) -> dict:
    import re
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            return json.loads(match.group(0))
        except Exception:
            pass
    return {}
