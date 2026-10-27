import json
import os
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Module 9 Grounding & Evaluation Audit",
    layout="wide"
)

st.title("📊 Module 9: Grounding & Structure-Aware Retrieval Audit")
st.caption("Author: Hemant Thapa | Branch: hemant-retrieval-changes")

EVAL_FILE = "data/eval_results.jsonl"

if not os.path.exists(EVAL_FILE):
    st.error(f"Evaluation file `{EVAL_FILE}` not found. Please run `python3 -m scripts.05_eval_grounding` first.")
    st.stop()

# Load evaluation results
results = []
with open(EVAL_FILE, "r") as f:
    for line in f:
        if line.strip():
            results.append(json.loads(line))

total_queries = len(results)
passed_queries = sum(1 for r in results if r.get("passed", False))
failed_queries = total_queries - passed_queries

# Metric Cards
col1, col2, col3 = st.columns(3)
col1.metric("Total Benchmark Queries", total_queries)
col2.metric("Passed Checks", passed_queries)
col3.metric("Failed Checks", failed_queries, delta=f"-{failed_queries}" if failed_queries > 0 else "0", delta_color="inverse")

st.divider()

# Strategy Contrast & Failure Analysis
st.subheader("🔍 Query Audit Details & Grounding Check Failure Modes")

data_rows = []
for r in results:
    data_rows.append({
        "Query": r.get("query"),
        "Passed": "✅ Pass" if r.get("passed") else "❌ Fail",
        "Failed Checks": ", ".join(r.get("failed_checks", [])) if r.get("failed_checks") else "None",
        "Chunk IDs Referenced": len(r.get("grounding_chunks", []))
    })

df = pd.DataFrame(data_rows)
st.dataframe(df, use_container_width=True)

st.divider()

# Grounding Structure Comparison
st.subheader("💡 Reranking & Structure-Aware Analysis")
st.markdown("""
### Strategic Findings:
* **Baseline Bottleneck:** Hardcoded similarity thresholds (`min_score=0.65`) drop low-similarity candidate chunks prior to LLM reasoning, resulting in `0` referenced `chunk_id` metadata.
* **Impact of Reranking Strategy:** Retaining a wider candidate set (`top_k=25`) coupled with cross-encoder reranking restores ground-truth context and preserves necessary attribution metadata.
""")
