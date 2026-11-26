"""Optional source-candidate panel on MineLens Project Intelligence Explorer."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from app.project_evidence_discovery import (
    candidate_passages_csv, find_candidate_passages, suggested_search_term,
)


def render_candidate_search(record: dict) -> None:
    """Search local ingested text without claiming entity resolution."""
    st.subheader("Related document mentions")
    st.caption(
        "Search ingested MineLens document chunks for **candidate mentions**. "
        "A keyword match does not prove that a passage refers to this exact facility or "
        "investment project. Results are not added to verified project facts or PDF claims. "
        "No web requests or language-model calls are made."
    )
    record_id = str(record["id"])
    with st.form(key=f"ml_source_discovery_{record_id}"):
        term = st.text_input(
            "Exact term or phrase to look for",
            value=suggested_search_term(record),
            max_chars=90,
            help="A short name such as Baluba or Kansanshi usually works better than a full USGS facility label.",
        )
        limit = st.select_slider("Maximum passages", options=[5, 10, 15, 25], value=10)
        requested = st.form_submit_button("Find matching document passages")

    if requested:
        try:
            with st.spinner("Scanning local text chunks..."):
                result = find_candidate_passages(term, limit=limit)
        except (OSError, ValueError) as exc:
            st.error(f"Could not search local documents: {exc}")
            return
        st.session_state["ml_source_discovery_result"] = {
            "record_id": record_id,
            "query": term,
            "result": result,
        }

    stored = st.session_state.get("ml_source_discovery_result")
    if not isinstance(stored, dict) or stored.get("record_id") != record_id:
        return
    result = stored["result"]
    hits = result["matches"]
    col1, col2, col3 = st.columns(3)
    col1.metric("Candidate passages", len(hits))
    col2.metric("Document files scanned", result["files_scanned"])
    col3.metric("Text chunks checked", result["chunks_scanned"])
    for warning in result["warnings"]:
        st.warning(warning)
    if not hits:
        st.info("No exact text match found in the scanned local chunks. Try a shorter or different project name; this is not evidence that the project is absent from the documents.")
        return

    st.dataframe(pd.DataFrame([
        {"Document": r["document"], "Page (if recorded)": r["page"],
         "Matched term": r["matched_term"], "Excerpt": r["excerpt"]}
        for r in hits
    ]), hide_index=True, use_container_width=True)
    for n, hit in enumerate(hits, 1):
        with st.expander(f"Candidate {n}: {hit['document']} | page {hit['page']}"):
            st.write(hit["excerpt"])
            st.caption(
                f"Chunk file: {hit['file']} | JSONL row: {hit['source_row']} | "
                "Lexical match only; project identity and factual claims are unverified."
            )
    st.download_button(
        "Download candidate passages (CSV)",
        data=candidate_passages_csv(hits),
        file_name="minelens_candidate_project_mentions.csv",
        mime="text/csv",
        key=f"ml_discovery_download_{record_id}",
    )
