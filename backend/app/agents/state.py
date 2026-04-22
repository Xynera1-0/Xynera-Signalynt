"""
LangGraph state for the research graph.
operator.add on agent_findings allows parallel Send() results to merge safely.
"""
from __future__ import annotations
import operator
from typing import Annotated
from langgraph.graph import MessagesState
from app.agents.schemas import (
    AgentFinding,
    OrchestratorPlan,
    SynthesisResult,
    UserReport,
    ContentBrief,
)


class ResearchState(MessagesState):
    # ── Input ──────────────────────────────────────────────────────────────
    user_query: str = ""
    workspace_context: dict = {}
    alert_context: dict | None = None          # injected by Temporal Poller if triggered

    # ── KB context (injected by KB Reader before orchestrator) ─────────────
    kb_context: dict = {}                      # growth signals + patterns from Neo4j

    # ── Parallel agent outputs (operator.add merges lists) ─────────────────
    agent_findings: Annotated[list[AgentFinding], operator.add] = []

    # ── Orchestrator plan (stored for audit) ──────────────────────────────
    orchestrator_plan: dict | None = None

    # ── Synthesis ─────────────────────────────────────────────────────────
    synthesis_result: SynthesisResult | None = None

    # ── Routing decision set by synthesis node ────────────────────────────
    routing: str | None = None                 # "to_user" | "to_content_agent"

    # ── Final outputs ─────────────────────────────────────────────────────
    user_report: UserReport | None = None
    content_brief: ContentBrief | None = None
