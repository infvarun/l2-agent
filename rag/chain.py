"""RAG chain combining Neo4j vector search and Cypher QA."""
import os
from typing import List, Dict, Any

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain.chains.graph_qa.cypher import GraphCypherQAChain
from langchain_community.graphs import Neo4jGraph
from langchain.retrievers import ContextualCompressionRetriever
from langchain.retrievers.document_compressors import LLMChainExtractor
from langchain_community.vectorstores import Neo4jVector
from typing import Callable, Optional


NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.0)
_emb = OpenAIEmbeddings()

graph = Neo4jGraph(
    url=NEO4J_URI,
    username=NEO4J_USERNAME,
    password=NEO4J_PASSWORD,
)

vector_store = Neo4jVector.from_existing_graph(
    graph=graph,                         # Neo4jGraph wrapper
    embedding=_emb,                      # OpenAIEmbeddings
    index_name="step_embedding",         # the VECTOR index built by graph_builder.py
    node_label="Step",
    text_node_property="text",           # main text prop
    text_node_properties=["text"],       # <‑‑ REQUIRED since 0.2.x
    embedding_node_property="embedding",
    search_type="hybrid",                # keyword + vector
)

retriever = ContextualCompressionRetriever(
    base_retriever=vector_store.as_retriever(search_kwargs={"k": 5}),
    base_compressor=LLMChainExtractor.from_llm(_llm),
)

# rag/chain.py  – update the Cypher‑QA construction
cypher_qa = GraphCypherQAChain.from_llm(
    graph=graph,
    cypher_llm=_llm,
    qa_llm=_llm,
    allow_dangerous_requests=True,   # ← required since LangChain 0.2.x
)


# rag/chain.py  (only the investigate function needs changing)

def investigate(
    alert_type: str,
    discrepancy_csv_path: str,
    report: Optional[Callable[[str], None]] = None
) -> str:
    """
    Return a checklist; optionally report progress via `report("msg")`.
    """
    def log(msg: str):
        if report:
            report(msg)

    # 1) Build prompt
    log("🔎 Crafting discrepancy prompt & embedding …")
    message = (
        f"Production alert type '{alert_type}'. "
        f"Discrepancy data at {discrepancy_csv_path}. "
        "Provide step‑by‑step investigation."
    )

    # 2) Vector retrieval
    log("🧠 Retrieving relevant SOP steps (vector search) …")
    docs = retriever.get_relevant_documents(message)
    context = "\n".join(d.page_content for d in docs)

    # 3) Cypher QA
    log("📈 Running Cypher QA to pull ordered steps & SQL …")
    cypher_question = (
        f"List the ordered investigation steps and SQL for alert type '{alert_type}'."
    )
    cypher_answer = cypher_qa.run(cypher_question)

    # 4) Final synthesis
    log("✍️  Synthesising final checklist with GPT …")
    final_prompt = f"""
    You are an L2 Support engineer.
    Alert type: {alert_type}
    Discrepancy file: {discrepancy_csv_path}

    ### SOP Context ###
    {context}

    ### Structured Steps & SQL ###
    {cypher_answer}

    Compose a clear, numbered checklist the engineer must follow, referencing SQL
    snippets where appropriate. Conclude with expected resolution verification.
    """
    answer = _llm.invoke(final_prompt).content
    log("✅ Checklist ready.")
    return answer

