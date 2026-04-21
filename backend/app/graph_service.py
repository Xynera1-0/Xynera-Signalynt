from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .neo4j_db import get_neo4j_driver


@dataclass(frozen=True)
class SeedResult:
    nodes_created: int
    relationships_created: int


REFERENCE_GRAPH_QUERY = """
MERGE (s1:Source {name: $meta_ads_name})
  ON CREATE SET s1.priority = 7, s1.type = 'Competitor'
MERGE (s2:Source {name: $user_voice_name})
  ON CREATE SET s2.priority = 10, s2.type = 'Direct'
MERGE (s3:Source {name: $pestel_name})
  ON CREATE SET s3.priority = 5, s3.type = 'Macro'
MERGE (p:Persona {id: $persona_id})
  ON CREATE SET p.name = $persona_name
MERGE (a:AnxietyTrigger {id: $anxiety_id})
  ON CREATE SET a.description = $anxiety_description
MERGE (f:AtomicFeature {id: $feature_id})
  ON CREATE SET f.name = $feature_name
MERGE (c1:Channel {name: $linkedin_name})
MERGE (c2:Channel {name: $email_name})
MERGE (i:Insight {conclusion: $insight_conclusion})
  ON CREATE SET i.type = $insight_type
MERGE (f)-[r1:ALLEVIATES]->(a)
  ON CREATE SET r1.impact = 0.9
MERGE (a)-[:HAUNTS]->(p)
MERGE (c1)-[r3:BEST_FOR]->(p)
  ON CREATE SET r3.reason = 'Direct Professional Contact'
MERGE (c2)-[r4:BEST_FOR]->(p)
  ON CREATE SET r4.reason = 'Direct Professional Contact'
MERGE (i)-[r2:SUGGESTS_FOR_NEXT_CYCLE]->(p)
  ON CREATE SET r2.action = $retrospective_action
"""


SIGNAL_CREATE_QUERY = """
MERGE (s:Signal {id: $id})
SET s += $props
WITH s
FOREACH (source_name IN CASE WHEN $source_name IS NULL THEN [] ELSE [$source_name] END |
  MERGE (src:Source {name: source_name})
  SET src.type = COALESCE(src.type, $source_type)
  MERGE (s)-[:FROM_SOURCE]->(src)
)
RETURN s
"""


SIGNAL_FETCH_QUERY = """
MATCH (s:Signal {id: $id})
OPTIONAL MATCH (s)-[:FROM_SOURCE]->(src:Source)
RETURN s, collect(DISTINCT src) AS sources
LIMIT 1
"""


PERSONA_CONTEXT_QUERY = """
MATCH (p:Persona {id: $persona_id})
OPTIONAL MATCH (a:AnxietyTrigger)-[:HAUNTS]->(p)
OPTIONAL MATCH (f:AtomicFeature)-[:ALLEVIATES]->(a)
OPTIONAL MATCH (i:Insight)-[:SUGGESTS_FOR_NEXT_CYCLE]->(p)
OPTIONAL MATCH (c:Channel)-[:BEST_FOR]->(p)
RETURN p, collect(DISTINCT a) AS anxieties, collect(DISTINCT f) AS features, collect(DISTINCT i) AS insights, collect(DISTINCT c) AS channels
LIMIT 1
"""


class GraphNotFoundError(RuntimeError):
    pass


def seed_reference_graph() -> SeedResult:
    driver = get_neo4j_driver()
    with driver.session() as session:
        session.run(
            REFERENCE_GRAPH_QUERY,
            meta_ads_name="Meta Ads",
            user_voice_name="User Voice",
            pestel_name="PESTEL",
            persona_id="p1",
            persona_name="Startup Founder",
            anxiety_id="t1",
            anxiety_description="Burning cash with no leads",
            feature_id="f1",
            feature_name="Autonomous Prospecting",
            linkedin_name="LinkedIn",
            email_name="Email",
            insight_conclusion="Founders ignore images; they want data-heavy bullet points.",
            insight_type="Learned Information",
            retrospective_action="Reduce flyer usage",
        )
    return SeedResult(nodes_created=9, relationships_created=5)


def create_signal(signal_id: str, props: dict[str, Any]) -> dict[str, Any]:
    driver = get_neo4j_driver()
    signal_props = {
        key: value
        for key, value in props.items()
        if key not in {"source_name", "source_type"}
    }
    with driver.session() as session:
        result = session.run(
            SIGNAL_CREATE_QUERY,
            id=signal_id,
            props=signal_props,
            source_name=props.get("source_name"),
            source_type=props.get("source_type"),
        )
        record = result.single()
        return dict(record["s"])


def fetch_signal(signal_id: str) -> dict[str, Any]:
    driver = get_neo4j_driver()
    with driver.session() as session:
        result = session.run(SIGNAL_FETCH_QUERY, id=signal_id)
        record = result.single()
        if not record:
            raise GraphNotFoundError(f"Signal {signal_id} not found")

        signal = dict(record["s"])
        signal["sources"] = [dict(source) for source in record["sources"] if source]
        return signal


def fetch_persona_context(persona_id: str) -> dict[str, Any]:
    driver = get_neo4j_driver()
    with driver.session() as session:
        result = session.run(PERSONA_CONTEXT_QUERY, persona_id=persona_id)
        record = result.single()
        if not record:
            raise GraphNotFoundError(f"Persona {persona_id} not found")

        return {
            "persona": dict(record["p"]),
            "anxieties": [dict(item) for item in record["anxieties"] if item],
            "features": [dict(item) for item in record["features"] if item],
            "insights": [dict(item) for item in record["insights"] if item],
            "channels": [dict(item) for item in record["channels"] if item],
        }
