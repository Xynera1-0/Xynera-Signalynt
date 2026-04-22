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
from langchain_core.messages import HumanMessage

from app.agents.base import get_llm, coerce_llm_content

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# State
# ─────────────────────────────────────────────────────────────────────────────

class ContentState(TypedDict, total=False):
    # ── Input (required at invocation) ──────────────────────────────
    content_brief: dict
    kb_context: dict
    platforms: List[str]
    hypothesis: str
    # ── Intermediate ────────────────────────────────────────────
    strategy: dict
    variants_plan: List[dict]
    base_contents: dict
    # ── Output ───────────────────────────────────────────────
    variants: List[dict]



# ─────────────────────────────────────────────────────────────────────────────
# Node 1 — Content Strategist
# ─────────────────────────────────────────────────────────────────────────────

async def content_strategist_node(state: ContentState) -> dict:
    logger.info("content_strategist | starting platforms=%s", state.get("platforms"))
    llm = get_llm(temperature=0.3)

    content_brief = state.get("content_brief", {})
    kb_context = state.get("kb_context", {})
    platforms = state.get("platforms", ["linkedin"])

    growth_signals = kb_context.get("growth_signals", [])
    winning_patterns = kb_context.get("winning_patterns", [])
    audience_insights = kb_context.get("audience_insights", [])

    prompt = f"""
You are a content strategist for a data-driven marketing platform.
Your job is to define the content strategy and A/B test design for this campaign.

Research brief:
{json.dumps(content_brief, indent=2)[:2500]}

Prior KB growth signals (from past campaigns on similar topics):
{json.dumps(growth_signals[:5], indent=2)}

Winning content patterns from KB:
{json.dumps(winning_patterns[:5], indent=2)}

Audience response patterns from KB:
{json.dumps(audience_insights[:5], indent=2)}

Target platforms: {platforms}

Define:
1. Primary angle (the core message — not a tagline, a strategic lens)
2. Test hypothesis (what do you want to learn? e.g. "emotional hook outperforms rational for this audience")
3. Variables to test (hook type, CTA style, format, length, etc.)
4. 2–4 variant ideas with clear differentiation
5. Content attributes per variant (hook_type, cta_type, format, tone)

Return JSON:
{{
  "primary_angle": "...",
  "hypothesis": "...",
  "test_variables": ["hook_type", "cta_style"],
  "variants": [
    {{
      "name": "Variant A — Emotional Hook",
      "hook_type": "emotional",
      "cta_type": "urgency",
      "format": "carousel",
      "tone": "conversational",
      "angle": "pain point first, solution second",
      "is_control": true
    }},
    {{
      "name": "Variant B — Rational Hook",
      "hook_type": "rational",
      "cta_type": "value",
      "format": "single_image",
      "tone": "professional",
      "angle": "lead with data and results",
      "is_control": false
    }}
  ]
}}
"""
    response = await llm.ainvoke([HumanMessage(content=prompt)])
    content = coerce_llm_content(response.content) if hasattr(response, "content") else str(response)
    strategy = _parse_json(content)

    logger.info("content_strategist | completed angle=%r variants_planned=%d",
                 strategy.get("primary_angle", "")[:60], len(strategy.get("variants", [])))
    # Return only changed fields
    return {
        "strategy": strategy,
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

    llm = get_llm(temperature=0.7)
    pool = ContentAgentPool(llm=llm)

    content_brief = state.get("content_brief", {})
    strategy = state.get("strategy", {})
    platforms = state.get("platforms", ["linkedin"])

    base_contents = {}
    for platform in platforms:
        input_data = {
            **content_brief,
            "platform": platform,
            "primary_angle": strategy.get("primary_angle", ""),
            "tone": "professional",
            "prompt": content_brief.get("synthesis", {}).get("key_themes", [""])[0] if isinstance(content_brief.get("synthesis"), dict) else str(content_brief.get("synthesis", "")),
        }
        try:
            result = pool.content_agent(input_data)
            base_contents[platform] = result
        except Exception as e:
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
