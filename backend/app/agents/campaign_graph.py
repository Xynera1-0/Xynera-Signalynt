"""
Campaign Execution Graph — Team 3.
Runs after Content Team produces variants.

LangGraph best practices:
  - TypedDict state (NOT Pydantic BaseModel / raw dict as graph schema)
  - StateGraph(CampaignState) — typed, not StateGraph(dict)
  - Nodes return ONLY changed fields — never {**state, ...}
    Rationale: spreading state is redundant; with Annotated reducers it
    causes double-accumulation. LangGraph merges returned dicts automatically.
"""
from __future__ import annotations
import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import TypedDict, Optional, List

from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage

from app.agents.base import get_llm
from app.db.kb_writer import (
    write_campaign_to_kb,
    write_growth_signal_to_kb,
    write_variant_result_to_kb,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# State — TypedDict is the canonical LangGraph state type.
# total=False means all keys are optional at access time;
# required fields (campaign_id, workspace_id) must be supplied at invocation.
# ─────────────────────────────────────────────────────────────────────────────

class CampaignState(TypedDict, total=False):
    # ── Input (required at graph invocation) ──────────────────────────
    campaign_id: str
    workspace_id: str
    content_brief: dict
    variants: List[dict]
    # ── Experiment setup ─────────────────────────────────────────
    experiment_id: str
    experiment_config: dict
    test_type: str
    primary_metric: str
    hypothesis: str
    # ── DB id mapping (content_id → test_variant_id) ─────────────
    variant_db_ids: dict
    # ── Execution ───────────────────────────────────────────────
    scheduled_posts: List[dict]
    published_posts: List[dict]
    # ── Analytics ───────────────────────────────────────────────
    metrics_snapshot: List[dict]    # aggregated from Postgres by test_monitor
    marginal_analysis: dict         # from BigQuery analysis
    growth_signals: List[dict]
    # ── KB write ────────────────────────────────────────────────
    kb_write_result: dict
    # ── Status ──────────────────────────────────────────────────
    status: str
    error: Optional[str]


# ─────────────────────────────────────────────────────────────────────────────
# DB helpers (sync — called via asyncio.to_thread)
# ─────────────────────────────────────────────────────────────────────────────

def _write_campaign_setup(
    campaign_id: str,
    workspace_id: str,
    name: str,
    hypothesis: str,
    platforms: list,
    kb_context: dict,
    experiment_id: str,
    experiment_config: dict,
    test_type: str,
    primary_metric: str,
    variants: list,
) -> dict:
    """
    Writes campaigns, campaign_content, test_experiments, test_variants.
    Returns {content_id: test_variant_id} mapping.
    """
    from app.db import get_db_cursor

    variant_db_ids: dict = {}
    with get_db_cursor() as cursor:
        # 1. campaigns
        cursor.execute(
            """
            INSERT INTO campaigns
                (id, workspace_id, name, hypothesis, platforms, status, kb_context)
            VALUES (%s::uuid, %s::uuid, %s, %s, %s, 'active', %s::jsonb)
            ON CONFLICT (id) DO NOTHING
            """,
            (
                campaign_id,
                workspace_id or None,
                name,
                hypothesis,
                platforms,
                json.dumps(kb_context),
            ),
        )

        # 2. campaign_content — one row per variant
        for variant in variants:
            c = variant.get("content", {})
            cursor.execute(
                """
                INSERT INTO campaign_content
                    (id, campaign_id, platform, content_type, headline, body, cta,
                     is_base, content_brief)
                VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s, %s::jsonb)
                ON CONFLICT (id) DO NOTHING
                """,
                (
                    variant["id"],
                    campaign_id,
                    variant.get("platform", "linkedin"),
                    variant.get("format", "post"),
                    c.get("headline", ""),
                    c.get("body", ""),
                    c.get("cta", ""),
                    variant.get("is_control", False),
                    json.dumps({
                        "hook_type": variant.get("hook_type"),
                        "cta_type": variant.get("cta_type"),
                        "tone": variant.get("tone"),
                    }),
                ),
            )

        # 3. test_experiments
        cursor.execute(
            """
            INSERT INTO test_experiments
                (id, campaign_id, name, experiment_type, hypothesis,
                 primary_metric, secondary_metrics, min_sample_size,
                 status, started_at)
            VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s, 'running', now())
            ON CONFLICT (id) DO NOTHING
            """,
            (
                experiment_id,
                campaign_id,
                f"{test_type.upper()} test — {name}",
                test_type,
                hypothesis,
                primary_metric,
                experiment_config.get("secondary_metrics", []),
                experiment_config.get("min_sample_size"),
            ),
        )

        # 4. test_variants — one per variant, linking to campaign_content row
        traffic_splits = experiment_config.get("traffic_splits", {})
        default_split = 1.0 / max(len(variants), 1)
        for i, variant in enumerate(variants):
            tv_id = str(uuid.uuid4())
            split = traffic_splits.get(f"variant_{i}", default_split)
            cursor.execute(
                """
                INSERT INTO test_variants
                    (id, experiment_id, content_id, name, is_control,
                     variable_values, traffic_split)
                VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s, %s::jsonb, %s)
                """,
                (
                    tv_id,
                    experiment_id,
                    variant["id"],
                    variant.get("name", f"Variant {i + 1}"),
                    variant.get("is_control", False),
                    json.dumps(variant.get("variable_values", {})),
                    split,
                ),
            )
            variant_db_ids[variant["id"]] = tv_id

    return variant_db_ids


def _write_platform_posts(
    campaign_id: str,
    published_posts: list,
    variant_db_ids: dict,
) -> None:
    """Writes one platform_posts row per published post."""
    from app.db import get_db_cursor

    with get_db_cursor() as cursor:
        for post in published_posts:
            variant = post.get("variant", {})
            content_id = variant.get("id")
            variant_id = variant_db_ids.get(content_id)
            raw_ts = post.get("published_at")
            try:
                published_at = datetime.fromisoformat(raw_ts) if raw_ts else None
            except (ValueError, TypeError):
                published_at = None

            cursor.execute(
                """
                INSERT INTO platform_posts
                    (id, campaign_id, variant_id, content_id, platform,
                     platform_post_id, platform_url, status, published_at)
                VALUES (gen_random_uuid(), %s::uuid, %s::uuid, %s::uuid,
                        %s, %s, %s, 'published', %s)
                """,
                (
                    campaign_id,
                    variant_id,
                    content_id,
                    post.get("platform", variant.get("platform", "linkedin")),
                    post.get("platform_post_id"),
                    post.get("platform_url"),
                    published_at,
                ),
            )


def _write_signals_and_summary(
    campaign_id: str,
    experiment_id: str,
    signals: list,
    analysis: dict,
    kb_errors: list,
) -> None:
    """
    Writes growth_signals and campaign_performance_summary,
    concludes test_experiments, and marks campaign as completed.
    """
    from app.db import get_db_cursor

    with get_db_cursor() as cursor:
        # growth_signals
        for signal in signals:
            cursor.execute(
                """
                INSERT INTO growth_signals
                    (id, campaign_id, experiment_id, signal_type, description,
                     magnitude, confidence, metric, affected_variable,
                     audience_segment, content_attributes, written_to_kb, kb_node_id)
                VALUES
                    (%s::uuid, %s::uuid, %s::uuid, %s, %s,
                     %s, %s, %s, %s,
                     %s::jsonb, %s::jsonb, %s, %s)
                ON CONFLICT (id) DO NOTHING
                """,
                (
                    signal.get("id") or str(uuid.uuid4()),
                    campaign_id,
                    experiment_id or None,
                    signal.get("signal_type", "unknown"),
                    signal.get("description", ""),
                    signal.get("magnitude"),
                    signal.get("confidence"),
                    signal.get("metric", ""),
                    signal.get("affected_variable", ""),
                    json.dumps(signal.get("audience_segment") or {}),
                    json.dumps(signal.get("content_attributes") or {}),
                    bool(signal.get("kb_node_id")),
                    signal.get("kb_node_id"),
                ),
            )

        # campaign_performance_summary
        winning_variants = (
            {experiment_id: analysis.get("winner_variant")}
            if analysis.get("winner_variant") and experiment_id
            else {}
        )
        kb_status = "partial" if kb_errors else "completed"
        cursor.execute(
            """
            INSERT INTO campaign_performance_summary
                (campaign_id, winning_variants, growth_signals_count,
                 marginal_analysis_result, hypothesis_validated, kb_write_status)
            VALUES (%s::uuid, %s::jsonb, %s, %s::jsonb, %s, %s)
            ON CONFLICT (campaign_id) DO UPDATE SET
                winning_variants         = EXCLUDED.winning_variants,
                growth_signals_count     = EXCLUDED.growth_signals_count,
                marginal_analysis_result = EXCLUDED.marginal_analysis_result,
                hypothesis_validated     = EXCLUDED.hypothesis_validated,
                kb_write_status          = EXCLUDED.kb_write_status
            """,
            (
                campaign_id,
                json.dumps(winning_variants),
                len(signals),
                json.dumps(analysis),
                analysis.get("is_significant"),
                kb_status,
            ),
        )

        # Conclude the experiment
        if experiment_id:
            cursor.execute(
                """
                UPDATE test_experiments
                SET status = 'concluded', concluded_at = now()
                WHERE id = %s::uuid
                """,
                (experiment_id,),
            )

        # Mark campaign completed
        cursor.execute(
            """
            UPDATE campaigns
            SET status = 'completed', updated_at = now()
            WHERE id = %s::uuid
            """,
            (campaign_id,),
        )


# ─────────────────────────────────────────────────────────────────────────────
# Node 1 — Campaign Setup
# Returns ONLY changed fields (best practice)
# ─────────────────────────────────────────────────────────────────────────────

async def campaign_setup_node(state: CampaignState) -> dict:
    campaign_id = state.get("campaign_id", str(uuid.uuid4()))
    logger.info("campaign_setup | campaign=%s starting", campaign_id)

    llm = get_llm(temperature=0.1)

    prompt = f"""
You are a campaign setup specialist. Given these content variants and campaign brief,
design the experiment structure.

Campaign Brief:
{json.dumps(state.get("content_brief", {}), indent=2)[:2000]}

Variants ({len(state.get("variants", []))}):
{json.dumps(state.get("variants", []), indent=2)[:2000]}

Determine:
1. Experiment type: "ab" (2 variants) or "multivariate" (3+ variants testing multiple variables)
2. Primary metric to optimise for (ctr | engagement_rate | conversion_rate | reach)
3. Traffic split per variant (must sum to 1.0)
4. Minimum sample size estimate (use: n = 16 * sigma^2 / delta^2, assume sigma=0.5, delta=0.05)
5. Clear hypothesis statement

Return JSON:
{{
  "test_type": "ab",
  "primary_metric": "ctr",
  "hypothesis": "...",
  "traffic_splits": {{"variant_0": 0.5, "variant_1": 0.5}},
  "min_sample_size": 6400,
  "duration_days": 7,
  "secondary_metrics": ["engagement_rate", "reach"]
}}
"""
    response = await llm.ainvoke([HumanMessage(content=prompt)])
    content = response.content if hasattr(response, "content") else str(response)
    logger.debug("campaign_setup | llm_raw campaign=%s len=%d", campaign_id, len(content))

    config = _parse_json(content)
    experiment_id = str(uuid.uuid4())

    # Write to Postgres (non-fatal)
    variants = state.get("variants", [])
    brief = state.get("content_brief") or {}
    name = brief.get("topic", "Campaign")
    platforms = list({v.get("platform", "linkedin") for v in variants}) or ["linkedin"]
    kb_context = brief.get("kb_context", {})
    hypothesis = config.get("hypothesis", state.get("hypothesis", ""))

    variant_db_ids: dict = {}
    try:
        variant_db_ids = await asyncio.to_thread(
            _write_campaign_setup,
            campaign_id,
            state.get("workspace_id", ""),
            name,
            hypothesis,
            platforms,
            kb_context,
            experiment_id,
            config,
            config.get("test_type", "ab"),
            config.get("primary_metric", "ctr"),
            variants,
        )
        logger.info(
            "campaign_setup | db_written campaign=%s exp=%s content_rows=%d variant_rows=%d",
            campaign_id, experiment_id, len(variants), len(variant_db_ids),
        )
    except Exception as exc:
        logger.error(
            "campaign_setup | db_write_failed campaign=%s: %s",
            campaign_id, exc, exc_info=True,
        )

    logger.info(
        "campaign_setup | completed campaign=%s test_type=%s metric=%s exp=%s",
        campaign_id, config.get("test_type"), config.get("primary_metric"), experiment_id,
    )
    return {
        "experiment_id": experiment_id,
        "experiment_config": config,
        "test_type": config.get("test_type", "ab"),
        "primary_metric": config.get("primary_metric", "ctr"),
        "hypothesis": hypothesis,
        "variant_db_ids": variant_db_ids,
        "status": "scheduled",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Node 2 — Post Scheduler
# ─────────────────────────────────────────────────────────────────────────────

async def post_scheduler_node(state: CampaignState) -> dict:
    campaign_id = state.get("campaign_id", "")
    logger.info("post_scheduler | campaign=%s scheduling %d variants",
                campaign_id, len(state.get("variants", [])))

    from app.agents.temporal_agent import run_temporal_agent

    variants = state.get("variants", [])
    topic = (state.get("content_brief") or {}).get("topic", "")

    timing_result = await run_temporal_agent(
        topic=topic,
        mode="publish_timing",
        content=variants[0] if variants else {},
    )
    logger.debug("post_scheduler | timing campaign=%s window=%s",
                 campaign_id, timing_result.get("recommended_window"))

    scheduled = [
        {
            "variant_index": i,
            "variant": variant,
            "platform": variant.get("platform", "linkedin"),
            "scheduled_at": timing_result.get("recommended_window", "next_business_morning"),
            "stagger_hours": i * 2,
        }
        for i, variant in enumerate(variants)
    ]

    logger.info("post_scheduler | completed campaign=%s posts_scheduled=%d",
                campaign_id, len(scheduled))
    return {"scheduled_posts": scheduled, "status": "publishing"}


# ─────────────────────────────────────────────────────────────────────────────
# Node 3 — Platform Publisher
# Wire real SDKs here per platform string
# ─────────────────────────────────────────────────────────────────────────────

async def platform_publisher_node(state: CampaignState) -> dict:
    campaign_id = state.get("campaign_id", "")
    scheduled = state.get("scheduled_posts", [])
    logger.info("platform_publisher | campaign=%s publishing %d posts",
                campaign_id, len(scheduled))

    published = [
        {
            **post,
            "platform_post_id": f"mock_{uuid.uuid4().hex[:8]}",
            "platform_url": f"https://platform.example/{uuid.uuid4().hex[:8]}",
            "published_at": datetime.now(timezone.utc).isoformat(),
            "status": "published",
        }
        for post in scheduled
    ]

    # Write to Postgres (non-fatal)
    try:
        await asyncio.to_thread(
            _write_platform_posts,
            campaign_id,
            published,
            state.get("variant_db_ids", {}),
        )
        logger.info("platform_publisher | db_written campaign=%s posts=%d",
                    campaign_id, len(published))
    except Exception as exc:
        logger.error("platform_publisher | db_write_failed campaign=%s: %s",
                     campaign_id, exc, exc_info=True)

    logger.info("platform_publisher | completed campaign=%s", campaign_id)
    return {"published_posts": published, "status": "monitoring"}


# ─────────────────────────────────────────────────────────────────────────────
# Node 4 — Analytics Agent
# Writes to BigQuery content_engagement_nested, then runs SQL marginal analysis.
# Postgres post_metrics = operational (real-time significance checking).
# BigQuery = analytics layer (lift, interaction effects, marginal returns).
# ─────────────────────────────────────────────────────────────────────────────

async def analytics_node(state: CampaignState) -> dict:
    campaign_id = state.get("campaign_id", "")
    logger.info("analytics | campaign=%s starting", campaign_id)

    from app.db.bigquery_client import write_experiment_to_bq, run_marginal_analysis_query

    metrics = state.get("metrics_snapshot", [])
    if not metrics:
        logger.warning("analytics | campaign=%s no metrics collected yet, skipping BQ write",
                       campaign_id)
        return {"marginal_analysis": {"error": "no metrics collected yet"}, "status": "analyzing"}

    # 1. Write denormalised record to BigQuery
    try:
        await write_experiment_to_bq(
            experiment_id=state.get("experiment_id", ""),
            campaign_id=campaign_id,
            variants=state.get("variants", []),
            published_posts=state.get("published_posts", []),
            metrics_snapshot=metrics,
        )
        logger.info("analytics | bq_written campaign=%s exp=%s",
                    campaign_id, state.get("experiment_id"))
    except Exception as exc:
        logger.warning("analytics | bq_write_failed campaign=%s: %s — using LLM fallback",
                       campaign_id, exc)

    # 2. Marginal analysis — BigQuery first, LLM fallback
    try:
        analysis = await run_marginal_analysis_query(
            experiment_id=state.get("experiment_id", ""),
            primary_metric=state.get("primary_metric", "ctr"),
        )
        logger.info("analytics | bq_analysis_done campaign=%s winner=%s significant=%s",
                    campaign_id, analysis.get("winner_variant"), analysis.get("is_significant"))
    except Exception as exc:
        logger.warning("analytics | bq_query_failed campaign=%s: %s — using LLM fallback",
                       campaign_id, exc)
        analysis = await _llm_marginal_analysis(state, metrics)
        logger.info("analytics | llm_analysis_done campaign=%s winner=%s",
                    campaign_id, analysis.get("winner_variant"))

    logger.info("analytics | completed campaign=%s marginal_returns=%s",
                campaign_id, analysis.get("marginal_returns"))
    return {"marginal_analysis": analysis, "status": "analyzing"}


async def _llm_marginal_analysis(state: CampaignState, metrics: list) -> dict:
    """Fallback when BigQuery is unavailable — LLM interprets Postgres snapshot."""
    llm = get_llm(temperature=0.1)
    prompt = f"""
You are a quantitative marketing analyst performing marginal analysis.

Experiment: {state.get('test_type')} test
Primary metric: {state.get('primary_metric')}
Hypothesis: {state.get('hypothesis')}

Metrics by variant:
{json.dumps(metrics, indent=2)[:3000]}

Return JSON:
{{
  "winner_variant": "variant_name or null if inconclusive",
  "lift_vs_control": {{"variant_1": 0.34, "variant_2": -0.05}},
  "statistical_significance": {{"variant_1": 0.97, "variant_2": 0.41}},
  "is_significant": true,
  "marginal_returns": "improving|plateauing|diminishing",
  "interaction_effects": [],
  "conclusion": "narrative summary"
}}
"""
    response = await llm.ainvoke([HumanMessage(content=prompt)])
    return _parse_json(response.content if hasattr(response, "content") else str(response))


# ─────────────────────────────────────────────────────────────────────────────
# Node 5 — Growth Signal Detector
# LLM over BigQuery analysis output → typed GrowthSignals
# ─────────────────────────────────────────────────────────────────────────────

async def growth_signal_detector_node(state: CampaignState) -> dict:
    campaign_id = state.get("campaign_id", "")
    logger.info("growth_signal_detector | campaign=%s starting", campaign_id)

    llm = get_llm(temperature=0.2)
    kb_context = (state.get("content_brief") or {}).get("kb_context", {})

    prompt = f"""
You are a growth signal specialist. Extract structured, reusable growth signals.

Campaign hypothesis: {state.get('hypothesis')}
Analysis: {json.dumps(state.get('marginal_analysis', {}), indent=2)[:2000]}
Prior KB signals: {json.dumps(kb_context, indent=2)[:800]}

Rules:
- Specific: "emotional hooks outperformed rational by 34% CTR for SaaS audience"
- Actionable: next campaign can use this directly
- Falsifiable: has a metric, magnitude, confidence level

Return JSON array:
[
  {{
    "signal_type": "variant_winner|audience_segment|content_pattern|diminishing_returns|interaction_effect|seasonal_lift",
    "description": "...",
    "magnitude": 0.34,
    "confidence": 0.97,
    "metric": "ctr",
    "affected_variable": "hook_type",
    "audience_segment": {{"description": "SaaS founders 30-45"}},
    "content_attributes": {{"hook": "emotional", "format": "carousel", "cta": "urgency"}}
  }}
]
"""
    response = await llm.ainvoke([HumanMessage(content=prompt)])
    signals = _parse_json_array(response.content if hasattr(response, "content") else str(response))

    for s in signals:
        s["id"] = str(uuid.uuid4())
        s["campaign_id"] = campaign_id

    logger.info("growth_signal_detector | completed campaign=%s signals=%d",
                campaign_id, len(signals))
    return {"growth_signals": signals, "status": "writing_kb"}


# ─────────────────────────────────────────────────────────────────────────────
# Node 6 — KB Writer
# Writes to Neo4j — closes the growth loop.
# Also writes growth_signals + campaign_performance_summary to Postgres.
# Returns only kb_write_result + status
# ─────────────────────────────────────────────────────────────────────────────

async def kb_writer_node(state: CampaignState) -> dict:
    campaign_id = state.get("campaign_id", "")
    logger.info("kb_writer | campaign=%s starting", campaign_id)

    workspace_id = state.get("workspace_id", "")
    analysis = state.get("marginal_analysis", {})
    signals = state.get("growth_signals", [])
    variants = state.get("variants", [])
    experiment_id = state.get("experiment_id", "")

    write_results: dict = {"signals_written": 0, "variants_written": 0, "errors": []}

    # Neo4j writes
    try:
        write_campaign_to_kb(
            campaign_id=campaign_id,
            campaign_name=(state.get("content_brief") or {}).get("topic", "Campaign"),
            workspace_id=workspace_id,
            hypothesis=state.get("hypothesis", ""),
            status="completed",
            performance_summary=analysis,
        )
        logger.debug("kb_writer | neo4j campaign node written campaign=%s", campaign_id)
    except Exception as e:
        write_results["errors"].append(f"campaign: {e}")
        logger.warning("kb_writer | neo4j campaign write failed campaign=%s: %s", campaign_id, e)

    for signal in signals:
        try:
            node_id = write_growth_signal_to_kb(campaign_id=campaign_id, signal=signal)
            signal["kb_node_id"] = node_id
            write_results["signals_written"] += 1
        except Exception as e:
            write_results["errors"].append(f"signal: {e}")
            logger.warning("kb_writer | neo4j signal write failed campaign=%s: %s", campaign_id, e)

    winner_name = analysis.get("winner_variant")
    lifts = analysis.get("lift_vs_control", {})
    sigs = analysis.get("statistical_significance", {})

    if winner_name and len(variants) >= 2:
        control = next((v for v in variants if v.get("is_control")), variants[0])
        winner = next((v for v in variants if v.get("name") == winner_name), variants[-1])
        try:
            write_variant_result_to_kb(
                campaign_id=campaign_id,
                winner=winner,
                loser=control,
                lift=float(lifts.get(winner_name, 0)),
                metric=state.get("primary_metric", "ctr"),
                confidence=float(sigs.get(winner_name, 0)),
            )
            write_results["variants_written"] += 1
            logger.debug("kb_writer | neo4j winner variant written campaign=%s winner=%s",
                         campaign_id, winner_name)
        except Exception as e:
            write_results["errors"].append(f"variant: {e}")
            logger.warning("kb_writer | neo4j variant write failed campaign=%s: %s", campaign_id, e)

    logger.info(
        "kb_writer | neo4j_done campaign=%s signals=%d variants=%d errors=%d",
        campaign_id, write_results["signals_written"],
        write_results["variants_written"], len(write_results["errors"]),
    )

    # Postgres writes — growth_signals + performance summary
    try:
        await asyncio.to_thread(
            _write_signals_and_summary,
            campaign_id,
            experiment_id,
            signals,
            analysis,
            write_results["errors"],
        )
        logger.info(
            "kb_writer | postgres_written campaign=%s growth_signals=%d",
            campaign_id, len(signals),
        )
    except Exception as exc:
        logger.error("kb_writer | postgres_write_failed campaign=%s: %s",
                     campaign_id, exc, exc_info=True)
        write_results["errors"].append(f"postgres: {exc}")

    logger.info("kb_writer | completed campaign=%s status=%s",
                campaign_id, "ok" if not write_results["errors"] else "partial")

    # Return ONLY changed fields
    return {"kb_write_result": write_results, "status": "completed"}


# ─────────────────────────────────────────────────────────────────────────────
# Graph wiring
# ─────────────────────────────────────────────────────────────────────────────

def build_campaign_graph():
    builder = StateGraph(CampaignState)

    builder.add_node("campaign_setup", campaign_setup_node)
    builder.add_node("post_scheduler", post_scheduler_node)
    builder.add_node("platform_publisher", platform_publisher_node)
    builder.add_node("analytics", analytics_node)
    builder.add_node("growth_signal_detector", growth_signal_detector_node)
    builder.add_node("kb_writer", kb_writer_node)

    builder.set_entry_point("campaign_setup")
    builder.add_edge("campaign_setup", "post_scheduler")
    builder.add_edge("post_scheduler", "platform_publisher")
    # Note: platform_publisher → analytics is triggered by Test Monitor (Celery)
    # after metrics are collected. For synchronous runs, wire directly:
    builder.add_edge("platform_publisher", "analytics")
    builder.add_edge("analytics", "growth_signal_detector")
    builder.add_edge("growth_signal_detector", "kb_writer")
    builder.add_edge("kb_writer", END)

    return builder.compile()


campaign_graph = build_campaign_graph()


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _parse_json(text: str) -> dict:
    import re
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            return json.loads(match.group(0))
        except Exception:
            pass
    return {}


def _parse_json_array(text: str) -> list:
    import re
    match = re.search(r"\[[\s\S]*\]", text)
    if match:
        try:
            return json.loads(match.group(0))
        except Exception:
            pass
    return []
