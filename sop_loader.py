"""Parse SOP documents into structured JSON using an LLM."""
from pathlib import Path
from typing import Dict, Any
import json

from langchain_openai import ChatOpenAI
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate

TEMPLATE = """You are given an L2 Support Standard Operating Procedure (SOP) document.
Return a structured JSON with the following keys:
- title: short title of SOP
- alert_type: canonical alert name this SOP handles
- summary: one‑sentence summary
- steps: list of objects {{order:int, text:str}}
- sql_queries: list of raw SQL strings referenced in the SOP
Everything must be valid JSON, no code fences.
DOCUMENT:
{document}
"""

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.0)

prompt = PromptTemplate.from_template(TEMPLATE)
chain = LLMChain(llm=llm, prompt=prompt)

def parse_sop(file_path: str) -> Dict[str, Any]:
    """Return structured dict from SOP file (txt/markdown/pdf pre‑extracted)."""
    text = Path(file_path).read_text(encoding="utf-8")
    response = chain.run(document=text)
    return json.loads(response)
