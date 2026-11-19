"""Source-checked project comparison page. No changes to chat or search APIs."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
import streamlit as st

from app.project_comparison_data import (
    load_comparison,
    comparison_rows,
    claim_rows,
)

try:
    from frontend.styles.theme import apply_theme
except ImportError:
    apply_theme = None

st.set_page_config(
    page_title="Project Comparison | MineLens Zambia",
    page_icon="⚒️",
    layout="wide",
)
if apply_theme is not None:
    apply_theme()


@st.cache_data(show_spinner=False)
def get_projects():
    return load_comparison()


try:
    projects = get_projects()
except (OSError, ValueError, KeyError) as exc:
    st.error(f"Could not load the sourced project comparison: {exc}")
    st.caption(
        "Required snapshot: data/processed/project_comparison_evidence_20261119.json. "
        "This page does not invent facts when source evidence is missing."
    )
    st.stop()

st.title("Mining Project Comparison")
st.caption(
    "Kansanshi · Lumwana · Mingomba | 2026 Zambia Metals and Minerals Country Compact "
    "and USGS Minerals Yearbook 2024"
)
st.markdown(
    "Compare **reported capital investment**, **announced copper capacity or potential**, "
    "and separately reported **2024 output**. Each figure is tied to a local "
    "source passage and page reference."
)

with st.sidebar:
    st.header("Compare projects")
    chosen = st.multiselect(
        "Projects", list(projects), default=list(projects),
        help="Choose one or more of the projects supported by the saved source report.",
    )
    st.caption(
        "Source snapshot: 19 November 2026. This is not a live production or "
        "investment-tracking feed."
    )

if not chosen:
    st.info("Select at least one project in the sidebar.")
    st.stop()

rows = comparison_rows(projects, chosen)
claims = claim_rows(projects, chosen)

col_a, col_b, col_c = st.columns(3)
col_a.metric("Projects selected", len(chosen))
col_b.metric("2026 CapEx source entries", 2 * len(chosen))
col_c.metric(
    "2024 output records available",
    sum(bool([c for c in projects[name]["claims"] if c.kind == "historical"]) for name in chosen),
)

st.caption(
    "Figures are documentary estimates and historical reports. They do not "
    "verify the current completion status, final cost or comparable project scope."
)

overview_tab, investment_tab, output_tab, evidence_tab = st.tabs([
    "Project overview", "Investment estimates", "Capacity & historical output", "Sources & exports"
])

with overview_tab:
    st.subheader("Side-by-side project snapshot")
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    for name in chosen:
        project = projects[name]
        capex = [c for c in project["claims"] if c.kind == "capex"]
        cap = next(c for c in project["claims"] if c.kind == "capacity")
        with st.expander(f"{name} — project details", expanded=len(chosen) == 1):
            st.markdown(f"**Developer in 2026 compact:** {project['developer']}")
            st.markdown(f"**Commodity:** {project['commodity']}")
            st.markdown(
                f"**CapEx:** {capex[0].value} (declaration, p. {capex[0].pages}); "
                f"{capex[1].value} (annex, pp. {capex[1].pages})."
            )
            st.markdown(f"**Announced capacity / potential:** {cap.value}")
            hist = [c.value for c in project["claims"] if c.kind == "historical"]
            st.markdown(
                "**2024 historical output:** " +
                ("; ".join(hist) if hist else "Not established by the retrieved evidence")
            )
            st.caption(
                "2026 declaration and annex are passages of the SAME report, "
                "not independent confirmations."
            )

with investment_tab:
    st.subheader("Reported project CapEx, USD billions")
    st.caption(
        "The bar uses the 2026 country compact's declaration estimate. "
        "It is not actual expenditure or a final confirmed project cost."
    )
    investment_data = []
    for name in chosen:
        capex = [c for c in projects[name]["claims"] if c.kind == "capex"]
        investment_data.append({
            "Project": name,
            "Declaration estimate ($bn)": capex[0].usd_billions,
        })
    st.bar_chart(pd.DataFrame(investment_data).set_index("Project"))
    st.dataframe(
        pd.DataFrame([{
            "Project": name,
            "Declaration (p. 8)": [c for c in projects[name]["claims"] if c.kind == "capex"][0].value,
            "Annex (pp. 25–26)": [c for c in projects[name]["claims"] if c.kind == "capex"][1].value,
            "Same 2026 report": "Yes",
        } for name in chosen]),
        use_container_width=True, hide_index=True,
    )
    if "Mingomba" in chosen:
        st.warning(
            "Mingomba: the declaration says expected $2 billion, but the annex says "
            "more than $2.0 billion. The bar represents the declaration estimate "
            "ONLY; the annex is a strict lower bound, not an exact $2.0B figure."
        )
    st.info(
        "The 2026 country compact's declaration describes major expansions as "
        "in progress, while its annex describes the Kansanshi and Lumwana "
        "expansions as completed. These document passages should not be "
        "treated as a verified live project-status update."
    )

with output_tab:
    st.subheader("Announced copper capacity or production potential")
    st.caption(
        "All values below are 2026 source statements about expansions or potential. "
        "They are NOT measured annual production in 2024 or 2026."
    )
    cap_rows = []
    for name in chosen:
        cap = next(c for c in projects[name]["claims"] if c.kind == "capacity")
        cap_rows.append({
            "Project": name,
            "Announced tpa": cap.capacity_tpa,
            "Description": cap.qualifier,
            "Source": f"2026 compact, p. {cap.pages}",
        })
    st.bar_chart(pd.DataFrame(cap_rows).set_index("Project")["Announced tpa"])
    st.dataframe(pd.DataFrame(cap_rows), use_container_width=True, hide_index=True)
    st.divider()
    st.subheader("2024 historical output: separate measurements")
    hist_rows = [
        {"Project": name, "2024 report says": c.value, "Source": c.source_title, "Page": c.pages}
        for name in chosen
        for c in projects[name]["claims"] if c.kind == "historical"
    ]
    if hist_rows:
        st.dataframe(pd.DataFrame(hist_rows), use_container_width=True, hide_index=True)
    else:
        st.info("No 2024 project-specific output measurements in the saved source passages.")
    st.caption(
        "Copper concentrates and copper cathode are different product categories. "
        "We do not add them together or compare them directly with the announced tpa figures."
    )

with evidence_tab:
    st.subheader("Evidence and provenance")
    st.caption(
        "The document name and page, rather than a reused [S1] search-session ID, "
        "identify each passage. Sources with no URL are in the local MineLens corpus."
    )
    evidence_df = pd.DataFrame(claims)
    st.dataframe(
        evidence_df.drop(columns=["Excerpt"], errors="ignore"),
        use_container_width=True,
        hide_index=True,
    )
    for name in chosen:
        for claim in projects[name]["claims"]:
            with st.expander(f"{name} | {claim.kind} | {claim.document} p. {claim.pages}"):
                st.write(claim.excerpt)
                st.caption(f"Source: {claim.source_title}, page(s) {claim.pages}")
                if claim.source_url:
                    st.markdown(f"[Open source website]({claim.source_url})")
                else:
                    st.caption("Local MineLens corpus; no external URL recorded in this snapshot.")

    st.download_button(
        "Export comparison (CSV)",
        data=pd.DataFrame(rows).to_csv(index=False).encode("utf-8-sig"),
        file_name="minelens_project_comparison.csv",
        mime="text/csv",
    )
    st.download_button(
        "Export source-level claims (CSV)",
        data=evidence_df.to_csv(index=False).encode("utf-8-sig"),
        file_name="minelens_project_comparison_evidence.csv",
        mime="text/csv",
    )
    st.caption(
        "This comparison is a sourced research snapshot, not investment advice, "
        "a live operational feed, or confirmation that targets have been achieved."
    )
