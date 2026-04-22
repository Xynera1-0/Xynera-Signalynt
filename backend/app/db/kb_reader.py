"""
KB Reader — queries Neo4j before research runs.
Injects past growth signals and performance patterns as context
so the Research Orchestrator and agents start with prior knowledge.
"""
from __future__ import annotations
from typing import Any
from app.neo4j_db import get_neo4j_driver


def read_relevant_kb_context(
    topic: str,
    workspace_id: str | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    """
    Returns structured KB context for injection into ResearchState.
    Falls back gracefully if Neo4j is unavailable.
    """
    try:
        driver = get_neo4j_driver()
    except Exception:
        return _empty_context()

    with driver.session() as session:
        growth_signals = _get_growth_signals(session, topic, workspace_id, limit)
        winning_patterns = _get_winning_patterns(session, topic, limit)
        audience_insights = _get_audience_insights(session, topic, limit)

    return {
        "growth_signals": growth_signals,
        "winning_patterns": winning_patterns,
        "audience_insights": audience_insights,
        "source": "neo4j_kb",
    }


def _get_growth_signals(session, topic: str, workspace_id: str | None, limit: int) -> list[dict]:
    query = """
        CALL db.index.fulltext.queryNodes('growth_signal_search', $topic)
        YIELD node, score
        WHERE score > 0.3
        RETURN node.description AS description,
               node.signal_type AS signal_type,
               node.magnitude AS magnitude,
               node.confidence AS confidence,
               node.metric AS metric,
               score
        ORDER BY score DESC, node.confidence DESC
        LIMIT $limit
    """
    try:
        result = session.run(query, topic=topic, limit=limit)
        return [dict(r) for r in result]
    except Exception:
        return []


def _get_winning_patterns(session, topic: str, limit: int) -> list[dict]:
    query = """
        CALL db.index.fulltext.queryNodes('performance_pattern_search', $topic)
        YIELD node, score
        WHERE score > 0.3
        RETURN node.pattern_name AS pattern_name,
               node.description AS description,
               node.metric AS metric,
               node.avg_lift AS avg_lift,
               score
        ORDER BY score DESC
        LIMIT $limit
    """
    try:
        result = session.run(query, topic=topic, limit=limit)
        return [dict(r) for r in result]
    except Exception:
        return []


def _get_audience_insights(session, topic: str, limit: int) -> list[dict]:
    query = """
        MATCH (a:AudienceSegment)-[r:RESPONDED_TO]->(cv:ContentVariant)
        WHERE cv.topic CONTAINS $topic OR a.description CONTAINS $topic
        RETURN a.description AS segment,
               cv.content_type AS content_type,
               cv.hook_type AS hook_type,
               r.engagement_rate AS engagement_rate
        ORDER BY r.engagement_rate DESC
        LIMIT $limit
    """
    try:
        result = session.run(query, topic=topic, limit=limit)
        return [dict(r) for r in result]
    except Exception:
        return []


def _empty_context() -> dict:
    return {"growth_signals": [], "winning_patterns": [], "audience_insights": [], "source": "empty"}
