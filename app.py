"""Streamlit front‑end for L2‑Support Production Alert Investigation"""

import os
import tempfile
import pandas as pd
import streamlit as st
from neo4j import GraphDatabase

from sop_loader import parse_sop
from graph_builder import ingest_sops
from rag.chain import investigate

# ---------------------------------------------------------------------
#  Streamlit page setup
# ---------------------------------------------------------------------
st.set_page_config(page_title="L2 Support Investigator", layout="wide")

# ---------------------------------------------------------------------
#  Neo4j connection
# ---------------------------------------------------------------------
NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

driver = GraphDatabase.driver(
    NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD), encrypted=False
)

# ---------------------------------------------------------------------
#  Helper: fetch alert types
# ---------------------------------------------------------------------
@st.cache_data
def get_alert_types():
    with driver.session() as session:
        result = session.run(
            "MATCH (a:AlertType) RETURN a.name AS name ORDER BY name"
        )
        return [r["name"] for r in result]

# ---------------------------------------------------------------------
#  UI layout: two tabs
# ---------------------------------------------------------------------
tab_investigate, tab_upload = st.tabs(["🔍 Investigate Alert", "📥 Upload SOPs"])

# =====================================================================
#  📥  Tab: SOP upload & ingestion
# =====================================================================
with tab_upload:
    st.title("📥 SOP Upload & Ingestion")
    st.write("Upload plain‑text or Markdown SOP files. They will be parsed, "
             "embedded, and saved to Neo4j.")

    files = st.file_uploader(
        "Select SOP files", type=["txt", "md"], accept_multiple_files=True
    )

    if st.button("Ingest SOPs") and files:
        sop_dicts = []
        progress = st.progress(0, text="Parsing SOPs …")
        for i, file in enumerate(files, 1):
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tmp:
                    tmp.write(file.read())
                    tmp_path = tmp.name
                sop = parse_sop(tmp_path)
                sop_dicts.append(sop)
                st.success(f"Parsed: {sop['title']}")
            except Exception as e:
                st.error(f"Failed to parse {file.name}: {e}")
            progress.progress(i / len(files))
        if sop_dicts:
            ingest_sops(sop_dicts)
            get_alert_types.clear()        # refresh cache
            st.success("Ingestion to Neo4j completed successfully ✅")
            st.experimental_rerun()
        progress.empty()

# =====================================================================
#  🔍  Tab: investigation workflow
# =====================================================================
with tab_investigate:
    st.title("🚨 Production Alert Investigator")

    alert_types = get_alert_types()
    if not alert_types:
        st.info("No SOPs ingested yet. Please upload SOPs first.")
    else:
        alert = st.selectbox("Choose alert type", alert_types, index=0)
        csv_file = st.file_uploader("Upload discrepancy CSV", type=["csv"])

        if st.button("Investigate") and csv_file is not None:
            # Save CSV to a temp file
            with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
                tmp.write(csv_file.read())
                tmp_path = tmp.name

            # Spinner with live status messages
            with st.status("Running investigation …", expanded=True) as status:
                answer = investigate(alert, tmp_path, report=status.write)
                status.update(label="Investigation complete ✅", state="complete")

            # ----------------------------------------------------------
            # Parse answer into numbered sections (keep full content)
            # ----------------------------------------------------------
            import re

            sections, current = [], []
            for line in answer.splitlines():
                if re.match(r"^\s*\d+\.", line):          # new top‑level step
                    if current:
                        sections.append("\n".join(current).strip())
                    current = [line]
                else:
                    current.append(line)
            if current:
                sections.append("\n".join(current).strip())
            if not sections:                              # fallback
                sections = [answer.strip()]

            # ----------------------------------------------------------
            # Vertical stepper styling
            # ----------------------------------------------------------
            st.markdown(
                """
                <style>
                .step-wrapper {position: relative; margin-left: 22px;}
                .step-wrapper::before {
                    content:""; position:absolute; left:9px; top:0;
                    width:2px; height:100%; background:#1f77be33;
                }
                .step-num {
                    width:26px; height:26px; border-radius:50%;
                    background:#1f77be; color:#fff; font-size:12px;
                    display:flex; align-items:center; justify-content:center;
                    font-weight:600; margin-right:8px;
                }
                </style>
                """,
                unsafe_allow_html=True,
            )

            # ----------------------------------------------------------
            # Render stepper (no numbered badge)
            # ----------------------------------------------------------
            st.subheader("Investigation Checklist")
            st.markdown('<div class="step-wrapper">', unsafe_allow_html=True)

            for block in sections:
                st.markdown(block)      # full Markdown (already numbered by GPT)
                st.markdown("<br>", unsafe_allow_html=True)  # light spacing

            st.markdown("</div>", unsafe_allow_html=True)



            # ----------------------------------------------------------
            # Show CSV preview
            # ----------------------------------------------------------
            df = pd.read_csv(tmp_path)
            st.subheader("CSV Preview (first 10 rows)")
            st.dataframe(df.head(10))
