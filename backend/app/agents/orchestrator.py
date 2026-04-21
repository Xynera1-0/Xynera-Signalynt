"""
Orchestrator — LLM reasons freely about the query, returns list[Send].
Dispatches only the agents relevant to the query dimensions.
"""
from __future__ import annotations
import json

from langgraph.types import Send
from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.base import get_llm
from app.agents.prompts import ORCHESTRATOR_PROMPT
from app.agents.schemas import OrchestratorPlan, AgentDispatch
from app.agents.state import ResearchState


async def orchestrator_node(state: ResearchState) -> list[Send]:
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
    llm_text = response.content if hasattr(response, "content") else str(response)

    plan = _parse_plan(llm_text)

    # Store plan in state for audit
    state_update = {"orchestrator_plan": plan.model_dump()}

    sends = []
    for dispatch in plan.dispatches:
        node_name = _agent_to_node(dispatch.agent_name)
        sends.append(Send(node_name, {
            **dict(state),
            "focus": dispatch.focus,
            "priority": dispatch.priority,
        }))

    if plan.temporal_needed:
        sends.append(Send("temporal_agent_node", {**dict(state), "focus": state["user_query"]}))

    return sends


def _agent_to_node(agent_name: str) -> str:
    mapping = {
        "trend_scout": "trend_scout",
        "spy_scout": "spy_scout",
        "anthropologist": "anthropologist",
        "contextual_scout": "contextual_scout",
    }
    return mapping.get(agent_name, agent_name)


def _parse_plan(text: str) -> OrchestratorPlan:
    import re
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
