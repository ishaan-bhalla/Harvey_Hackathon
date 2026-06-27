import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

URI = os.getenv("NEO4J_URI")
USERNAME = os.getenv("NEO4J_USERNAME")
PASSWORD = os.getenv("NEO4J_PASSWORD")

driver = GraphDatabase.driver(URI, auth=(USERNAME, PASSWORD))

def test_connection():
    with driver.session() as session:
        result = session.run("RETURN 1 AS test")
        return result.single()["test"] == 1

def clear_graph():
    with driver.session() as session:
        session.run("MATCH (n) DETACH DELETE n")

def create_witness_node(tx, witness_name: str, statement_id: str, organisation: str):
    tx.run("""
        MERGE (w:Witness {name: $name})
        SET w.statement_id = $statement_id,
            w.organisation = $organisation
    """, name=witness_name, statement_id=statement_id, organisation=organisation)

def create_allegation_node(tx, allegation_id: int, allegation: str, topic: str):
    tx.run("""
        MERGE (a:Allegation {id: $id})
        SET a.text = $allegation,
            a.topic = $topic
    """, id=allegation_id, allegation=allegation, topic=topic)

def create_relationship(tx, witness_name: str, allegation_id: int, verdict: str, confidence: str, passage: str):
    tx.run("""
        MATCH (w:Witness {name: $witness_name})
        MATCH (a:Allegation {id: $allegation_id})
        MERGE (w)-[r:RELATES_TO {verdict: $verdict}]->(a)
        SET r.confidence = $confidence,
            r.passage = $passage
    """, witness_name=witness_name, allegation_id=allegation_id,
         verdict=verdict, confidence=confidence, passage=passage or "")

def build_graph_from_analysis(result: dict):
    """
    Takes the pleading analysis result and builds a Neo4j graph.
    Witnesses → allegations with SUPPORTS/CONTRADICTS/NOT_ADDRESSED relationships.
    """
    clear_graph()

    # Infer organisation from witness name patterns
    def get_organisation(name: str) -> str:
        fujitsu_witnesses = ["rowley", "peach", "bansal", "welsh", "boic", "evans-jones", "mcniven"]
        name_lower = name.lower()
        if any(fw in name_lower for fw in fujitsu_witnesses):
            return "Fujitsu"
        elif any(w in name_lower for w in ["clarke", "bourke", "ismay", "dilley", "bogerd"]):
            return "Post Office"
        else:
            return "Other"

    with driver.session() as session:
        # Create witness nodes
        for witness_name in result["documents_analysed"]:
            org = get_organisation(witness_name)
            session.execute_write(
                create_witness_node,
                witness_name,
                witness_name,
                org
            )

        # Create allegation nodes
        for row in result["matrix"]:
            session.execute_write(
                create_allegation_node,
                row["allegation_id"],
                row["allegation"],
                row["topic"]
            )

        # Create relationships
        for row in result["matrix"]:
            for s in row["supporting"]:
                session.execute_write(
                    create_relationship,
                    s["witness"],
                    row["allegation_id"],
                    "SUPPORTS",
                    s.get("confidence", "MEDIUM"),
                    s.get("relevant_passage", "")
                )
            for c in row["contradicting"]:
                session.execute_write(
                    create_relationship,
                    c["witness"],
                    row["allegation_id"],
                    "CONTRADICTS",
                    c.get("confidence", "MEDIUM"),
                    c.get("relevant_passage", "")
                )

    print(f"Graph built: {len(result['documents_analysed'])} witnesses, {len(result['matrix'])} allegations")
    return True

def get_graph_data() -> dict:
    """
    Returns all nodes and relationships for frontend visualisation.
    """
    with driver.session() as session:
        witnesses = session.run("MATCH (w:Witness) RETURN w.name as name, w.organisation as org").data()
        allegations = session.run("MATCH (a:Allegation) RETURN a.id as id, a.text as text, a.topic as topic").data()
        relationships = session.run("""
            MATCH (w:Witness)-[r:RELATES_TO]->(a:Allegation)
            RETURN w.name as witness, a.id as allegation_id, r.verdict as verdict, r.confidence as confidence
        """).data()

    return {
        "witnesses": witnesses,
        "allegations": allegations,
        "relationships": relationships
    }
