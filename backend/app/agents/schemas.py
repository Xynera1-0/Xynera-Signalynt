"""
All typed contracts for the research agent system.
Every agent produces AgentFinding. Everything flows through these schemas.
"""
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Literal


# ─────────────────────────────────────────────────────────────────────────────
# Evidence & Finding
# ─────────────────────────────────────────────────────────────────────────────

class Evidence(BaseModel):
    source_url: str | None = None
    source_name: str | None = None              # human-readable, e.g. "Reddit r/marketing"
    markdown_link: str | None = None            # pre-rendered "[source_name](url)" for user output
    quote: str | None = None                    # verbatim excerpt
    tool_used: str                              # which tool retrieved this
    retrieved_at: str                           # ISO timestamp
    recency: Literal["24h", "7d", "30d", "90d", "older"] = "30d"
    confidence_score: float = 0.5              # 0.0–1.0 from calculate_confidence()
    confidence_breakdown: dict = Field(default_factory=dict)

    def build_markdown_link(self) -> str:
        if self.source_url and self.source_name:
            return f"[{self.source_name}]({self.source_url})"
        return self.source_name or self.source_url or self.tool_used


class Finding(BaseModel):
    category: str                               # e.g. "Political", "Competitor Ad Spend"
    claim: str                                  # single, falsifiable statement
    evidence: list[Evidence] = Field(default_factory=list)
    confidence: float = 0.5                    # aggregate across evidence items
    signal_strength: Literal["strong", "moderate", "weak"] = "moderate"
    tags: list[str] = Field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# Agent Output
# ─────────────────────────────────────────────────────────────────────────────

class AgentFinding(BaseModel):
    agent_name: str
    focus_question: str                         # the scoped sub-question this agent was given
    query_relevance: float = 1.0               # 0.0–1.0: did agent stay on topic?
    confidence_overall: float = 0.5
    findings: list[Finding] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)       # searched but not found
    deviation_notes: list[str] = Field(default_factory=list)
    raw_sources_count: int = 0
    timestamp: str = ""


# ─────────────────────────────────────────────────────────────────────────────
# Orchestrator
# ─────────────────────────────────────────────────────────────────────────────

class AgentDispatch(BaseModel):
    agent_name: Literal["trend_scout", "spy_scout", "anthropologist", "contextual_scout"]
    focus: str                                  # scoped sub-question for this agent
    priority: Literal["primary", "supporting"] = "primary"


class OrchestratorPlan(BaseModel):
    reasoning: str                              # LLM chain-of-thought — stored in agent_runs.orchestrator_plan
    intent_labels: list[str]                   # e.g. ["competitive_analysis", "audience_insight"]
    dispatches: list[AgentDispatch]
    temporal_needed: bool = False


# ─────────────────────────────────────────────────────────────────────────────
# Synthesis
# ─────────────────────────────────────────────────────────────────────────────

class SynthesisResult(BaseModel):
    query_answered: bool
    coverage_score: float = 0.0               # 0.0–1.0: how completely query was addressed
    key_findings: list[Finding] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    flagged_deviations: list[str] = Field(default_factory=list)
    agent_confidence_map: dict[str, float] = Field(default_factory=dict)
    ready_for_content: bool = False             # synthesis node decides routing


# ─────────────────────────────────────────────────────────────────────────────
# Final Outputs
# ─────────────────────────────────────────────────────────────────────────────

class SourceLink(BaseModel):
    name: str
    url: str

    def as_markdown(self) -> str:
        return f"[{self.name}]({self.url})"


class UserReport(BaseModel):
    summary: str                                # 3-5 sentence executive summary
    key_insights: list[str]                    # max 7 bullets, highest-confidence only
    gaps: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    sources: list[SourceLink] = Field(default_factory=list)   # hyperlinked [name](url)
    query_answered: bool = True

    def sources_as_markdown(self) -> str:
        return "\n".join(f"- {s.as_markdown()}" for s in self.sources)


class ContentBrief(BaseModel):
    synthesis: SynthesisResult
    workspace_context: dict
    temporal_context: dict | None = None        # from temporal_agent if called
