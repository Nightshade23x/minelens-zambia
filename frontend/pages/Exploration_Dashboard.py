"""Read-only exploration dashboard for the 9 Nov 2026 Mushima North release.

Run with the existing MineLens app: python -m streamlit run frontend/MineLens_Home.py
The page appears automatically in Streamlit's navigation.
"""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import streamlit as st

from app.exploration_dashboard_data import (
    METALS,
    filter_intervals,
    highest_interval,
    hole_comparison,
    load_phase4_report,
    peak_individual_assays,
)


st.set_page_config(page_title="MineLens | Exploration Dashboard", page_icon="⛏️", layout="wide")

# MINELENS_MULTI_PROJECT_EXPLORATION_20261124
exploration_project = st.sidebar.selectbox(
    "Exploration project", ["Mushima North", "Muntanga North"]
)
if exploration_project == "Muntanga North":
    from frontend.muntanga_exploration_view import render_muntanga_dashboard
    render_muntanga_dashboard(PROJECT_ROOT)
    st.stop()


try:
    report = load_phase4_report(PROJECT_ROOT)
except (OSError, ValueError) as exc:
    st.error(f"Could not open the Mushima North drilling dataset: {exc}")
    st.code(
        "python -m ingestion.ingest_tertiary_mushima_north",
        language="powershell",
    )
    st.stop()

source = report.summary["source_url"]
all_holes = sorted(hole["hole_id"] for hole in report.holes)
all_zones = sorted({hole["zone"] for hole in report.holes})

st.title("Exploration Dashboard")
st.caption(
    "Mushima North  •  Phase 4 reverse-circulation drilling  •  "
    "Tertiary Minerals plc  •  9 November 2026"
)
st.markdown(
    "Explore released drill intervals, compare holes, inspect individual peak assays "
    f"and export your selected records. [Open the source announcement]({source})."
)

st.sidebar.header("Explore drilling")
metal_label = st.sidebar.selectbox("Compare by metal", list(METALS))
metal_key, metal_unit = METALS[metal_label]
selected_zones = st.sidebar.multiselect("Zones", all_zones, default=all_zones)
selected_holes = st.sidebar.multiselect("Drill holes", all_holes, default=all_holes)
include_nested = st.sidebar.checkbox("Show reported 'including' intervals", value=True)

visible_intervals = filter_intervals(
    report.intervals,
    zones=set(selected_zones),
    hole_ids=set(selected_holes),
    include_nested=include_nested,
)
visible_holes = [hole for hole in report.holes if hole["hole_id"] in selected_holes and hole["zone"] in selected_zones]
best = highest_interval(visible_intervals, metal_key)
peaks = peak_individual_assays(visible_holes, metal_key)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Reported holes in release", f"{len(report.holes)}")
c2.metric("Visible intervals", f"{len(visible_intervals)} / {len(report.intervals)}")
c3.metric(
    f"Highest visible interval ({metal_unit})",
    f"{best[metal_key]:g}" if best else "Not available",
)
c4.metric(
    f"Highest reported individual assay ({metal_unit})",
    f"{peaks[0]['grade']:g}" if peaks else "Not reported",
)

st.caption(
    "These are holes and intervals in this announcement, not every Phase 4 drill hole. "
    "Interval grades and individual sample assays are different measurements."
)


def format_intervals(intervals):
    rows = []
    for item in sorted(intervals, key=lambda r: (r["hole_id"], r["from_m"], r["to_m"])):
        rows.append({
            "Hole": item["hole_id"],
            "Zone": item["zone"],
            "From (m)": item["from_m"],
            "To (m)": item["to_m"],
            "Length (m)": item["interval_m"],
            "Ag (g/t)": item.get("ag_gpt"),
            "Cu (%)": item.get("cu_pct"),
            "Zn (%)": item.get("zn_pct"),
            "Including interval": bool(item.get("explicitly_marked_including", False)),
            "Record ID": item.get("record_id"),
            "Source URL": item.get("source_url", source),
        })
    return pd.DataFrame(rows)


interval_tab, compare_tab, assays_tab, source_tab = st.tabs(
    ["Interval explorer", "Compare holes", "Individual peak assays", "Source & limitations"]
)

with interval_tab:
    st.subheader("Drill intervals by depth")
    st.caption("Vertical position is reported downhole depth in metres; colour represents the selected interval grade.")
    if not visible_intervals:
        st.warning("No reported intervals match the current filters.")
    else:
        df = format_intervals(visible_intervals)
        metric_col = {"ag_gpt": "Ag (g/t)", "cu_pct": "Cu (%)", "zn_pct": "Zn (%)"}[metal_key]
        try:
            import altair as alt

            # Altair uses simple field names; the table keeps the original labels.
            chart_data = df.rename(columns={
                "From (m)": "from_m", "To (m)": "to_m",
                "Length (m)": "length_m", "Ag (g/t)": "ag_gpt",
                "Cu (%)": "cu_pct", "Zn (%)": "zn_pct",
                "Including interval": "including_interval",
            }).copy()
            chart_data["selected_grade"] = chart_data[metal_key]
            chart = (
                alt.Chart(chart_data)
                .mark_bar(size=24, opacity=0.85)
                .encode(
                    x=alt.X("Hole:N", title="Drill hole", sort=all_holes),
                    y=alt.Y("from_m:Q", title="Downhole depth (m)", scale=alt.Scale(reverse=True)),
                    y2=alt.Y2("to_m:Q"),
                    color=alt.Color("selected_grade:Q", title=metal_unit),
                    tooltip=[
                        alt.Tooltip("Hole:N", title="Drill hole"),
                        alt.Tooltip("Zone:N"),
                        alt.Tooltip("from_m:Q", title="From (m)"),
                        alt.Tooltip("to_m:Q", title="To (m)"),
                        alt.Tooltip("length_m:Q", title="Length (m)"),
                        alt.Tooltip("ag_gpt:Q", title="Ag (g/t)"),
                        alt.Tooltip("cu_pct:Q", title="Cu (%)"),
                        alt.Tooltip("zn_pct:Q", title="Zn (%)"),
                        alt.Tooltip("including_interval:N", title="Including interval"),
                    ],
                )
                .properties(height=380)
            )
            st.altair_chart(chart, use_container_width=True)
        except ImportError:
            st.info("Optional chart dependency is unavailable; the table below remains usable.")
        st.dataframe(df.drop(columns=["Record ID", "Source URL"]), use_container_width=True, hide_index=True)
        st.download_button(
            "Export selected intervals (CSV)",
            data=df.to_csv(index=False).encode("utf-8"),
            file_name="mushima_north_phase4_selected_intervals.csv",
            mime="text/csv",
        )

with compare_tab:
    st.subheader("Compare maximum reported interval grades")
    st.caption(
        "Each value is the highest reported interval grade for that hole among the visible "
        "intervals. These are not whole-hole averages, estimated resources or totals."
    )
    records = [
        item for item in hole_comparison(report, metal_key, intervals=visible_intervals)
        if item["hole_id"] in selected_holes and item["zone"] in selected_zones
    ]
    records.sort(key=lambda r: (-float(r["max_interval_grade"]) if r["max_interval_grade"] is not None else float("inf"), r["hole_id"]))
    if not records:
        st.warning("Select at least one hole and zone to compare.")
    else:
        table = pd.DataFrame([{
            "Hole": item["hole_id"],
            "Zone": item["zone"],
            "End of hole (m)": item["end_of_hole_m"],
            "Visible intervals": item["reported_intervals"],
            f"Max interval ({metal_unit})": item["max_interval_grade"],
            "Best from (m)": item["best_interval_from_m"],
            "Best to (m)": item["best_interval_to_m"],
        } for item in records])
        st.dataframe(table, use_container_width=True, hide_index=True)
        plot = table.dropna(subset=[f"Max interval ({metal_unit})"])
        if not plot.empty:
            st.bar_chart(plot.set_index("Hole")[[f"Max interval ({metal_unit})"]])
        st.download_button(
            "Export comparison (CSV)",
            data=table.to_csv(index=False).encode("utf-8"),
            file_name="mushima_north_phase4_hole_comparison.csv",
            mime="text/csv",
        )

with assays_tab:
    st.subheader("Reported peak individual assays")
    st.caption(
        "These are explicitly reported peak individual sample grades. Do not compare them "
        "directly with interval-average grades or treat missing peaks as zero."
    )
    if not peaks:
        st.info(f"No individual {metal_label.lower()} assay peaks were reported for the selected holes.")
    else:
        peak_df = pd.DataFrame([{
            "Hole": row["hole_id"], "Zone": row["zone"],
            f"Peak individual assay ({metal_unit})": row["grade"],
        } for row in peaks])
        st.dataframe(peak_df, use_container_width=True, hide_index=True)
        st.bar_chart(peak_df.set_index("Hole")[[f"Peak individual assay ({metal_unit})"]])

with source_tab:
    st.subheader("What this dashboard represents")
    st.markdown(
        f"**Source:** Tertiary Minerals plc, {report.summary['announcement_date']}, "
        f"Table 1, [official Phase 4 announcement]({source})."
    )
    st.write(
        f"This release reports {len(report.holes)} drill holes and {len(report.intervals)} "
        "listed intervals. Phase 4 has additional holes that are not represented as interval "
        "records in this dashboard."
    )
    st.markdown(
        "- All lengths are **downhole intervals**; true widths are unknown.\n"
        "- Some intervals are marked **including** and overlap longer intervals. "
        "Lengths must not be summed as independent mineralisation.\n"
        "- Individual peak assays are not interval-average grades.\n"
        "- These are company-reported exploration results, **not mineral resources or reserves**.\n"
        "- The 9 November 2026 release does **not** contain Phase 5 assay results."
    )
    st.caption("Source references are retained in the exported interval CSV.")
