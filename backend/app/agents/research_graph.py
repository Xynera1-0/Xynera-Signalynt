"""
Research Graph — full LangGraph wiring.
Orchestrator → parallel Send fan-out → synthesis → conditional routing.
"""
from __future__ import annotations

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app.agents.state import ResearchState
from app.agents.orchestrator import orchestrator_node
from app.agents.synthesis import synthesis_node
from app.agents.summarizer import summarizer_node
from app.agents.trend_scout import trend_scout_node
from app.agents.spy_scout import spy_scout_node
from app.agents.anthropologist import anthropologist_node
from app.agents.contextual_scout import contextual_scout_node
from app.agents.temporal_agent import temporal_agent_research_node


def routing_condition(state: ResearchState) -> str:
    return state.get("routing", "to_user")


def build_research_graph(checkpointer=None):
    builder = StateGraph(ResearchState)

    # Register all nodes
    builder.add_node("orchestrator", orchestrator_node)
    builder.add_node("trend_scout", trend_scout_node)
    builder.add_node("spy_scout", spy_scout_node)
    builder.add_node("anthropologist", anthropologist_node)
    builder.add_node("contextual_scout", contextual_scout_node)
    builder.add_node("temporal_agent_node", temporal_agent_research_node)
    builder.add_node("synthesis", synthesis_node)
    builder.add_node("summarizer", summarizer_node)

    # Entry: orchestrator fans out via Send()
    builder.set_entry_point("orchestrator")

    # Parallel agent nodes all converge to synthesis
    # (The Send() API routes to these nodes; they write into agent_findings via reducer)
    for agent_node in ("trend_scout", "spy_scout", "anthropologist", "contextual_scout", "temporal_agent_node"):
        builder.add_edge(agent_node, "synthesis")

    # Synthesis → conditional routing
    builder.add_conditional_edges(
        "synthesis",
        routing_condition,
        {
            "to_user": "summarizer",
            "to_content_agent": END,
        },
    )

    # Summarizer → done
    builder.add_edge("summarizer", END)

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
