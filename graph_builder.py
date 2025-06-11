"""Create/update Neo4j graph and vector indexes for SOPs."""
import os
from typing import List, Dict, Any

from neo4j import GraphDatabase
from langchain_openai import OpenAIEmbeddings

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

embedder = OpenAIEmbeddings()

def _merge_sop(tx, sop: Dict[str, Any], embedding: List[float]):
    tx.run(
        """MERGE (a:AlertType {name:$alert})
           ON CREATE SET a.description=$summary, a.embedding=$emb
           ON MATCH  SET a.description=$summary, a.embedding=$emb
        """,
        alert=sop["alert_type"],
        summary=sop["summary"],
        emb=embedding,
    )
    tx.run(
        """MERGE (s:SOP {title:$title})
           ON CREATE SET s.summary=$summary, s.embedding=$emb
           WITH s
           MATCH (a:AlertType {name:$alert})
           MERGE (a)-[:HAS_SOP]->(s)
        """,
        title=sop["title"],
        summary=sop["summary"],
        emb=embedding,
        alert=sop["alert_type"],
    )
    # steps
    for step in sop["steps"]:
        tx.run(
            """MERGE (st:Step {text:$text})
               ON CREATE SET st.order=$order, st.embedding=$s_emb
               WITH st
               MATCH (s:SOP {title:$title})
               MERGE (s)-[:HAS_STEP {order:$order}]->(st)
            """,
            text=step["text"],
            order=step["order"],
            s_emb=embedder.embed_query(step["text"]),
            title=sop["title"],
        )
    # SQL
    for sql in sop.get("sql_queries", []):
        tx.run(
            """MERGE (q:SQL {query:$sql})
               WITH q
               MATCH (s:SOP {title:$title})
               MERGE (s)-[:EXECUTES]->(q)
            """,
            sql=sql,
            title=sop["title"],
        )

def _ensure_vector_indexes(session):
    session.run(
        """CREATE VECTOR INDEX alert_embedding IF NOT EXISTS
           FOR (a:AlertType) ON (a.embedding)
           OPTIONS {indexConfig: {`vector.dimensions`: 1536,
                                  `vector.similarity_function`: 'cosine'}}"""
    )
    session.run(
        """CREATE VECTOR INDEX sop_embedding IF NOT EXISTS
           FOR (s:SOP) ON (s.embedding)
           OPTIONS {indexConfig: {`vector.dimensions`: 1536,
                                  `vector.similarity_function`: 'cosine'}}"""
    )
    session.run(
        """CREATE VECTOR INDEX step_embedding IF NOT EXISTS
           FOR (st:Step) ON (st.embedding)
           OPTIONS {indexConfig: {`vector.dimensions`: 1536,
                                  `vector.similarity_function`: 'cosine'}}"""
    )

def ingest_sops(sop_dicts: List[Dict[str, Any]]):
    driver = GraphDatabase.driver(
        NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD), encrypted=False
    )
    with driver.session() as session:
        _ensure_vector_indexes(session)
        for sop in sop_dicts:
            emb = embedder.embed_query(sop["summary"])
            session.execute_write(_merge_sop, sop, emb)
    driver.close()
