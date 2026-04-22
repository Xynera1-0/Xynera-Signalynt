"""
KB Writer — closes the growth loop.
Called by the KB Writer Agent after Analytics Agent produces GrowthSignals.
Writes campaign results, winning patterns, and growth signals to Neo4j.
"""
from __future__ import annotations
import uuid
from typing import Any
from app.neo4j_db import get_neo4j_driver


def write_campaign_to_kb(
    campaign_id: str,
    campaign_name: str,
    workspace_id: str,
    hypothesis: str,
    status: str,
    performance_summary: dict,
) -> str:
    """Creates/merges a Campaign node. Returns Neo4j node id."""
    driver = get_neo4j_driver()
    with driver.session() as session:
        result = session.run(
            """
            MERGE (c:Campaign {id: $id})
            SET c.name = $name,
                c.workspace_id = $workspace_id,
                c.hypothesis = $hypothesis,
                c.status = $status,
                c.total_impressions = $impressions,
                c.blended_ctr = $ctr,
                c.blended_roas = $roas,
                c.hypothesis_validated = $validated
            RETURN elementId(c) AS node_id
            """,
            id=campaign_id,
            name=campaign_name,
            workspace_id=workspace_id,
            hypothesis=hypothesis,
            status=status,
            impressions=performance_summary.get("total_impressions", 0),
            ctr=performance_summary.get("blended_ctr", 0),
            roas=performance_summary.get("blended_roas", 0),
            validated=performance_summary.get("hypothesis_validated", False),
        )
        return result.single()["node_id"]


def write_growth_signal_to_kb(
    campaign_id: str,
    signal: dict,
) -> str:
    """
    Creates a GrowthSignal node and links it to the Campaign.
    Returns Neo4j node id.
    """
    driver = get_neo4j_driver()
    signal_id = signal.get("id") or str(uuid.uuid4())

    with driver.session() as session:
        result = session.run(
            """
            MERGE (s:GrowthSignal {id: $id})
            SET s.signal_type = $signal_type,
                s.description = $description,
                s.magnitude = $magnitude,
                s.confidence = $confidence,
                s.metric = $metric,
                s.affected_variable = $affected_variable,
                s.audience_segment = $audience_segment,
                s.content_attributes = $content_attributes

            WITH s
            MATCH (c:Campaign {id: $campaign_id})
            MERGE (s)-[:DETECTED_IN]->(c)

            RETURN elementId(s) AS node_id
            """,
            id=signal_id,
            campaign_id=campaign_id,
            signal_type=signal.get("signal_type", "unknown"),
            description=signal.get("description", ""),
            magnitude=float(signal.get("magnitude", 0)),
            confidence=float(signal.get("confidence", 0)),
            metric=signal.get("metric", ""),
            affected_variable=signal.get("affected_variable", ""),
            audience_segment=str(signal.get("audience_segment", {})),
            content_attributes=str(signal.get("content_attributes", {})),
        )
        return result.single()["node_id"]


def write_variant_result_to_kb(
    campaign_id: str,
    winner: dict,
    loser: dict,
    lift: float,
    metric: str,
    confidence: float,
) -> None:
    """
    Creates ContentVariant nodes and an OUTPERFORMED relationship.
    This is the core pattern memory — future loops read this.
    """
    driver = get_neo4j_driver()
    with driver.session() as session:
        session.run(
            """
            MERGE (w:ContentVariant {id: $winner_id})
            SET w.name = $winner_name,
                w.hook_type = $winner_hook,
                w.cta_type = $winner_cta,
                w.format = $winner_format,
                w.platform = $platform,
                w.topic = $topic

            MERGE (l:ContentVariant {id: $loser_id})
            SET l.name = $loser_name,
                l.hook_type = $loser_hook,
                l.cta_type = $loser_cta,
                l.format = $loser_format,
                l.platform = $platform,
                l.topic = $topic

            MERGE (w)-[r:OUTPERFORMED]->(l)
            SET r.lift = $lift,
                r.metric = $metric,
                r.confidence = $confidence

            WITH w
            MATCH (c:Campaign {id: $campaign_id})
            MERGE (w)-[:BELONGS_TO]->(c)
            """,
            winner_id=winner.get("id", str(uuid.uuid4())),
            winner_name=winner.get("name", ""),
            winner_hook=winner.get("hook_type", ""),
            winner_cta=winner.get("cta_type", ""),
            winner_format=winner.get("format", ""),
            loser_id=loser.get("id", str(uuid.uuid4())),
            loser_name=loser.get("name", ""),
            loser_hook=loser.get("hook_type", ""),
            loser_cta=loser.get("cta_type", ""),
            loser_format=loser.get("format", ""),
            platform=winner.get("platform", ""),
            topic=winner.get("topic", ""),
            campaign_id=campaign_id,
            lift=float(lift),
            metric=metric,
            confidence=float(confidence),
        )


def write_performance_pattern_to_kb(
    pattern_name: str,
    description: str,
    metric: str,
    avg_lift: float,
    platforms: list[str],
    topic_slugs: list[str],
) -> str:
    """
    Upserts a PerformancePattern node — generalised insight extracted from
    multiple campaigns (written by Analytics Agent when pattern repeats).
    """
    driver = get_neo4j_driver()
    pattern_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, pattern_name))

    with driver.session() as session:
        result = session.run(
            """
            MERGE (p:PerformancePattern {id: $id})
            SET p.pattern_name = $pattern_name,
                p.description = $description,
                p.metric = $metric,
                p.avg_lift = $avg_lift

            WITH p
            UNWIND $platforms AS pname
            MERGE (pl:Platform {name: pname})
            MERGE (p)-[:VALID_ON]->(pl)

            WITH p
            UNWIND $topic_slugs AS slug
            MERGE (t:Topic {slug: slug})
            MERGE (p)-[:RELEVANT_TO]->(t)

            RETURN elementId(p) AS node_id
            """,
            id=pattern_id,
            pattern_name=pattern_name,
            description=description,
            metric=metric,
            avg_lift=float(avg_lift),
            platforms=platforms,
            topic_slugs=topic_slugs,
        )
        return result.single()["node_id"]
