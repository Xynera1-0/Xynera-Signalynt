"""
Orchestrator — LLM reasons freely about the query, returns list[Send].
Dispatches only the agents relevant to the query dimensions.
"""
from __future__ import annotations
import json
import logging

from langgraph.types import Send
from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.base import get_llm, coerce_llm_content
from app.agents.prompts import ORCHESTRATOR_PROMPT
from app.agents.schemas import OrchestratorPlan, AgentDispatch
from app.agents.state import ResearchState

logger = logging.getLogger(__name__)


async def orchestrator_node(state: ResearchState) -> dict:
    """Runs the LLM planner and stores the plan in state.
    Fan-out to parallel agents is handled by dispatch_to_agents() which is
    wired as a conditional edge — LangGraph requires Send() to come from an
    edge function, not from a node return value.
    """
    logger.info("orchestrator | START query=%r", state["user_query"][:80])
    llm = get_llm(temperature=0.2)

    prompt = ORCHESTRATOR_PROMPT.format(
        query=state["user_query"],
        workspace_context=json.dumps(state.get("workspace_context", {}), indent=2)[:1000],
        alert_context=json.dumps(state.get("alert_context") or {}, indent=2),
    )

    schema_hint = """
Return a JSON object:
{
  "reasoning": "your chain of thought",
  "intent_labels": ["competitive_analysis", ...],
  "dispatches": [
    {"agent_name": "spy_scout", "focus": "specific sub-question", "priority": "primary"},
    ...
  ],
  "temporal_needed": true
}
Valid agent_name values: trend_scout, spy_scout, anthropologist, contextual_scout
"""
    response = await llm.ainvoke([
        SystemMessage(content=prompt + schema_hint),
        HumanMessage(content=f"Plan the research for: {state['user_query']}"),
    ])
    llm_text = coerce_llm_content(response.content) if hasattr(response, "content") else str(response)

    plan = _parse_plan(llm_text)
    agent_names = [d.agent_name for d in plan.dispatches]
    logger.info("orchestrator | PLAN intents=%s agents=%s temporal=%s reasoning=%r",
                plan.intent_labels, agent_names, plan.temporal_needed, plan.reasoning[:120])
    return {"orchestrator_plan": plan.model_dump()}


def dispatch_to_agents(state: ResearchState) -> list[Send]:
    """Conditional edge function — reads the stored orchestrator plan and fans
    out to the relevant agent nodes in parallel using Send().
    """
    plan_dict = state.get("orchestrator_plan") or {}
    dispatches = plan_dict.get("dispatches") or []

    sends = []
    for dispatch in dispatches:
        node_name = _agent_to_node(dispatch.get("agent_name", ""))
        if node_name:
            logger.info("orchestrator | DISPATCH agent=%s focus=%r priority=%s",
                        node_name, dispatch.get("focus", "")[:80], dispatch.get("priority"))
            sends.append(Send(node_name, {
                **dict(state),
                "focus": dispatch.get("focus", ""),
                "priority": dispatch.get("priority", "primary"),
            }))

    if plan_dict.get("temporal_needed"):
        logger.info("orchestrator | DISPATCH agent=temporal_agent_node")
        sends.append(Send("temporal_agent_node", {
            **dict(state),
            "focus": state.get("user_query", ""),
        }))

    # Fallback: full sweep if orchestrator produced nothing
    if not sends:
        logger.warning("orchestrator | no dispatches from plan — falling back to full sweep")
        query = state.get("user_query", "")
        for agent, focus in [
            ("trend_scout", "General market and PESTEL analysis"),
            ("spy_scout", "Competitive landscape overview"),
            ("anthropologist", "Audience sentiment and pain points"),
        ]:
            sends.append(Send(agent, {**dict(state), "focus": focus, "priority": "primary"}))

    logger.info("orchestrator | total sends=%d", len(sends))
    return sends


def _agent_to_node(agent_name: str) -> str:
    mapping = {
        "trend_scout": "trend_scout",
        "spy_scout": "spy_scout",
        "anthropologist": "anthropologist",
        "contextual_scout": "contextual_scout",
    }
    return mapping.get(agent_name, agent_name)


def _parse_plan(text) -> OrchestratorPlan:
    import re
    text = coerce_llm_content(text)
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        # Fallback: full sweep
        return OrchestratorPlan(
            reasoning="Failed to parse orchestrator plan — falling back to full sweep",
            intent_labels=["full_sweep"],
            dispatches=[
                AgentDispatch(agent_name="trend_scout", focus="General market and PESTEL analysis", priority="primary"),
                AgentDispatch(agent_name="spy_scout", focus="Competitive landscape overview", priority="primary"),
                AgentDispatch(agent_name="anthropologist", focus="Audience sentiment and pain points", priority="primary"),
                AgentDispatch(agent_name="contextual_scout", focus="Adjacent threats and opportunities", priority="supporting"),
            ],
            temporal_needed=False,
        )
    try:
        data = json.loads(match.group(0))
        dispatches = [AgentDispatch(**d) for d in data.get("dispatches", [])]
        return OrchestratorPlan(
            reasoning=data.get("reasoning", ""),
            intent_labels=data.get("intent_labels", []),
            dispatches=dispatches,
            temporal_needed=data.get("temporal_needed", False),
        )
    except Exception:
        return _parse_plan("")  # recurse into fallback
