import os

from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable


class Neo4jConfigError(RuntimeError):
    pass


_neo4j_driver = None


def get_neo4j_driver():
    global _neo4j_driver

    if _neo4j_driver is not None:
        return _neo4j_driver

    uri = os.getenv("NEO4J_URI")
    username = os.getenv("NEO4J_USERNAME")
    password = os.getenv("NEO4J_PASSWORD")

    if not uri or not username or not password:
        raise Neo4jConfigError("NEO4J_URI, NEO4J_USERNAME, and NEO4J_PASSWORD must be set")

    _neo4j_driver = GraphDatabase.driver(uri, auth=(username, password))
    return _neo4j_driver


def close_neo4j_driver() -> None:
    global _neo4j_driver

    if _neo4j_driver is None:
        return

    _neo4j_driver.close()
    _neo4j_driver = None


def ping_neo4j() -> dict:
    driver = get_neo4j_driver()
    try:
        with driver.session() as session:
            result = session.run("RETURN 1 AS ok")
            return {"ok": result.single()["ok"] == 1}
    except ServiceUnavailable as exc:
        raise RuntimeError(f"Neo4j is unavailable: {exc}") from exc
