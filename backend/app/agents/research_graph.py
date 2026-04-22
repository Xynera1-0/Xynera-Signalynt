"""
Research Graph — full LangGraph wiring.
KB Reader → Orchestrator → parallel Send fan-out → synthesis (+ report) → done.
Synthesis node now handles both structured synthesis and user-facing report in one LLM call.
"""
from __future__ import annotations
import logging

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app.agents.state import ResearchState
from app.agents.orchestrator import orchestrator_node, dispatch_to_agents
from app.agents.synthesis import synthesis_node
from app.agents.trend_scout import trend_scout_node
from app.agents.spy_scout import spy_scout_node
from app.agents.anthropologist import anthropologist_node
from app.agents.contextual_scout import contextual_scout_node
from app.agents.temporal_agent import temporal_agent_research_node
from app.db.kb_reader import read_relevant_kb_context

logger = logging.getLogger(__name__)


async def kb_reader_node(state: ResearchState) -> dict:
    """Pre-step: enrich state with past growth signals from Neo4j before research starts."""
    topic = state.get("user_query", "")
    workspace_id = state.get("workspace_context", {}).get("workspace_id", "")
    logger.info("kb_reader | starting topic=%r workspace=%s", topic[:60], workspace_id)
    kb_context = read_relevant_kb_context(topic=topic, workspace_id=workspace_id)
    logger.info("kb_reader | completed signals=%d", len(kb_context.get("growth_signals", [])))
    return {"kb_context": kb_context}


def build_research_graph(checkpointer=None):
    builder = StateGraph(ResearchState)

    # Register all nodes
    builder.add_node("kb_reader", kb_reader_node)
    builder.add_node("orchestrator", orchestrator_node)
    builder.add_node("trend_scout", trend_scout_node)
    builder.add_node("spy_scout", spy_scout_node)
    builder.add_node("anthropologist", anthropologist_node)
    builder.add_node("contextual_scout", contextual_scout_node)
    builder.add_node("temporal_agent_node", temporal_agent_research_node)
    builder.add_node("synthesis", synthesis_node)

    # Entry: KB Reader → orchestrator → conditional fan-out via Send()
    builder.set_entry_point("kb_reader")
    builder.add_edge("kb_reader", "orchestrator")
    builder.add_conditional_edges("orchestrator", dispatch_to_agents)

    # All parallel agent nodes converge to synthesis
    for agent_node in ("trend_scout", "spy_scout", "anthropologist", "contextual_scout", "temporal_agent_node"):
        builder.add_edge(agent_node, "synthesis")

    # Synthesis writes user_report to state and decides routing internally;
    # both paths end here — supervisor_graph reads user_report or content_brief as needed.
    builder.add_edge("synthesis", END)

    return builder.compile(checkpointer=checkpointer)


async def get_research_graph(db_url: str):
    """
    Factory used at startup. Creates the graph with a PostgresSaver checkpointer.
    db_url must be a sync postgresql:// URL (psycopg2).
    """
    async with AsyncPostgresSaver.from_conn_string(db_url) as checkpointer:
        await checkpointer.setup()
        return build_research_graph(checkpointer=checkpointer)


# Default instance without checkpointing (for testing / simple invocations)
research_graph = build_research_graph()
