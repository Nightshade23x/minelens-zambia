"""Searchable source-backed explorer for USGS facilities and verified project facts."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
import streamlit as st

from app.project_intelligence import (
    catalog_table_rows,
    distinct_catalog_values,
    filter_catalog,
    filtered_catalog_csv,
    load_catalog,
    profile_markdown,
)
from frontend.styles.theme import apply_theme

st.set_page_config(
    page_title="Project Intelligence | MineLens Zambia",
    page_icon="🔎",
    layout="wide",
    initial_sidebar_state="expanded",
)
apply_theme()


@st.cache_data(show_spinner=False)
def read_catalog():
    return load_catalog()


st.title("Mining Project Intelligence Explorer")
st.caption("USGS Zambia facilities (2024) + independently verified project claims (2024/2026)")
st.markdown(
    "Search Zambian mining facility records and project-evidence profiles by name, "
    "operator/developer, commodity or province. **Facility and investment-project "
    "records are separate types**; similarly named entries are not automatically merged."
)

try:
    catalog, warnings = read_catalog()
except (OSError, ValueError, KeyError, TypeError) as exc:
    st.error(f"Could not load the source-backed facility catalog: {exc}")
    st.stop()

for message in warnings:
    st.warning(message)

with st.sidebar:
    st.header("Explore records")
    query = st.text_input("Search", placeholder="Kansanshi, copper, Kitwe, operator...")
    record_type = st.selectbox(
        "Record type", ["All record types", *distinct_catalog_values(catalog, "kind")]
    )
    province = st.selectbox(
        "Province", ["All provinces", *distinct_catalog_values(catalog, "province")]
    )
    commodity = st.selectbox(
        "Commodity", ["All commodities", *distinct_catalog_values(catalog, "commodities")]
    )
    st.caption("Source entries are historical snapshots, not live operating records.")

results = filter_catalog(
    catalog, query=query, kind=record_type, province=province, commodity=commodity
)
col1, col2, col3 = st.columns(3)
col1.metric("Matching records", len(results))
col2.metric("USGS facilities", sum(r["kind"] == "USGS facility" for r in results))
col3.metric("Verified project profiles", sum(r["kind"] == "Verified project evidence" for r in results))

st.subheader("Browse")
if not results:
    st.info("No matching records. Try a different search or filter.")
    st.stop()

st.dataframe(pd.DataFrame(catalog_table_rows(results)), use_container_width=True, hide_index=True)
st.download_button(
    "Export matching records (CSV)",
    data=filtered_catalog_csv(results),
    file_name="minelens_project_intelligence_results.csv",
    mime="text/csv",
)

select_map = {row["id"]: row for row in results}
selected_id = st.selectbox(
    "Inspect a record",
    options=list(select_map),
    format_func=lambda key: (
        f"{select_map[key]['name']} — {select_map[key]['kind']}"
        + (f" ({select_map[key]['record_id']})" if select_map[key]["record_id"] else "")
    ),
)
selected = select_map[selected_id]

st.divider()
st.header(selected["name"])
st.caption(f"{selected['kind']} | Source year: {selected['publication_year']}")

left, right = st.columns(2)
with left:
    st.markdown("**Reported operator / developer**")
    st.write(", ".join(selected["operator"]) or "Not established in source")
    st.markdown("**Commodity**")
    st.write(", ".join(selected["commodities"]) or "Not established in source")
    st.markdown("**Facility type**")
    st.write(", ".join(selected["feature_types"]) or "Not established / not applicable")
with right:
    st.markdown("**Province / district**")
    st.write(", ".join(filter(None, [selected["district"], selected["province"]])) or "Not established")
    st.markdown("**Source-reported status**")
    st.write(", ".join(selected["status"]) or "Not established in source")
    st.markdown("**Recorded equity owners**")
    st.write(", ".join(selected["owners"]) or "Not established in source")

if selected["location_description"]:
    st.markdown("**Source location description**")
    st.write(selected["location_description"])

if selected["map_lat"] is not None:
    st.info(
        f"District match: {selected['district']} ({selected['province']}). "
        "Any mapped coordinates are **district centroids, NOT the facility's exact location**."
    )
elif selected["kind"] == "USGS facility":
    st.caption("No unambiguous district location match. No coordinates have been inferred.")

st.caption(selected["source_scope"])

if selected["capacity_records"]:
    st.subheader("USGS-reported annual capacity records")
    st.caption(
        "Deduplicated capacity groups from product rows. "
        "Do not sum the values as total output or assume they are current."
    )
    capacity_rows = []
    for item in selected["capacity_records"]:
        capacity_rows.append({
            "Commodity": item.get("commodity") or "Not given",
            "Capacity": item.get("capacity"),
            "Unit": item.get("capacity_unit") or "Not specified",
            "Product / form": item.get("form") or item.get("descriptor") or item.get("type") or "",
            "Notes": item.get("capacity_notes") or "",
        })
    st.dataframe(pd.DataFrame(capacity_rows), use_container_width=True, hide_index=True)

if selected["claims"]:
    st.subheader("Verified documentary claims")
    st.caption(
        "Each claim was checked against a saved source passage. "
        "Different CapEx statements are retained separately rather than reconciled."
    )
    claim_rows = []
    for c in selected["claims"]:
        claim_rows.append({
            "Claim": c.get("label") or c.get("kind") or "",
            "Reported value": c.get("value") or "",
            "Qualification": c.get("qualifier") or "",
            "Source": c.get("source_title") or "",
            "Pages": c.get("pages") or "",
        })
    st.dataframe(pd.DataFrame(claim_rows), use_container_width=True, hide_index=True)
    for i, c in enumerate(selected["claims"], 1):
        with st.expander(f"Evidence {i}: {c.get('label') or c.get('kind')} — {c.get('value')}"):
            st.write(c.get("excerpt") or "No supporting excerpt supplied")
            st.caption(
                f"{c.get('source_title') or c.get('document')} | "
                f"{c.get('document')} | page(s): {c.get('pages')}"
            )
            url = c.get("source_url") or ""
            if url.startswith(("https://", "http://")):
                st.markdown(f"[Open cited document]({url})")

st.subheader("Sources and exports")
st.write(selected["source_title"])
if selected["source_url"].startswith(("https://", "http://")):
    st.markdown(f"[Open primary source]({selected['source_url']})")
if selected["supporting_urls"]:
    with st.expander("Additional source links"):
        for url in selected["supporting_urls"]:
            st.markdown(f"- {url}")

ex1, ex2 = st.columns(2)
with ex1:
    st.download_button(
        "Download project/facility brief (Markdown)",
        profile_markdown(selected),
        file_name="minelens_profile.md",
        mime="text/markdown",
    )
with ex2:
    st.download_button(
        "Download structured record (JSON)",
        json.dumps(selected, indent=2, ensure_ascii=False, default=str),
        file_name="minelens_profile.json",
        mime="application/json",
    )

st.caption(
    "This explorer assembles existing public evidence; it does not infer unreported "
    "production, operational status, ownership, exact coordinates or mine reserves."
)
