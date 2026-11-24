"""Muntanga North view for the existing multi-project Exploration Dashboard."""
from pathlib import Path

# MINELENS_MUNTANGA_COLLAR_CLICK_20261124
from frontend.muntanga_collar_inspector import render_collar_inspector

import pandas as pd
import streamlit as st

from app.muntanga_dashboard_data import (
    best_by_hole, collar_map_rows, load_muntanga_report, visible_records,
)


def _interval_table(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame([{
        "Hole": r["hole_id"],
        "Target": r.get("target_id"),
        "From (m)": r["from_m"],
        "To (m)": r["to_m"],
        "Length (m)": r["interval_m"],
        "eU3O8 (ppm)": r["eu3o8_ppm"],
        "Highlighted in Table 1": bool(r.get("highlighted_in_table_1")),
        "Source page": r.get("source_page"),
        "Source URL": r.get("source_url"),
    } for r in sorted(rows, key=lambda r: (r["hole_id"], float(r["from_m"])))])


def render_muntanga_dashboard(root: Path) -> None:
    try:
        report = load_muntanga_report(root)
    except (OSError, ValueError) as exc:
        st.error(f"Muntanga North dataset is missing or invalid: {exc}")
        st.code("python -m ingestion.ingest_atomic_eagle_muntanga", language="powershell")
        return

    summary = report.summary
    st.title("Exploration Dashboard")
    st.caption("Muntanga North | Atomic Eagle Limited | 20 November 2026")
    st.markdown(
        "Explore reported uranium radiometric intercepts and drill-hole collars. "
        f"[Original ASX announcement]({summary['source_url']})."
    )

    all_ids = sorted(h["hole_id"] for h in report.holes)
    st.sidebar.subheader("Muntanga North filters")
    target_labels = {"Target 5": 5, "Target 6": 6, "Unassigned in Table 1": None}
    target_choice = st.sidebar.multiselect("Target classification", list(target_labels), default=list(target_labels))
    target_values = {target_labels[label] for label in target_choice}
    only_significant = st.sidebar.checkbox("Only holes with reported intervals", value=False)
    selected_holes = st.sidebar.multiselect(
        "Specific drill holes (blank = all)", all_ids, default=[],
    )
    holes, intervals = visible_records(
        report,
        hole_ids=set(selected_holes) if selected_holes else None,
        target_ids=target_values,
        include_no_significant=not only_significant,
    )

    highest = max(intervals, key=lambda r: float(r["eu3o8_ppm"])) if intervals else None
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Collars visible", f"{len(holes)} / {len(report.holes)}")
    c2.metric("Reported intervals visible", f"{len(intervals)} / {len(report.intervals)}")
    c3.metric("No significant intercept", sum(h["intercept_reporting_status"] == "no_significant_intercept" for h in holes))
    c4.metric("Highest visible interval (ppm eU3O8)", f"{highest['eu3o8_ppm']:g}" if highest else "Not reported")
    st.caption(
        "All grades are downhole-gamma radiometric equivalent uranium (ppm eU3O8), NOT laboratory assays. "
        "No significant intercept is not a zero measurement."
    )

    map_tab, intervals_tab, comparison_tab, provenance_tab = st.tabs(
        ["Drill-collar map", "Intervals by depth", "Compare drill holes", "Source & limitations"]
    )

    with map_tab:
        st.subheader("Reported drill-hole collar positions")
        st.caption(
            "Coordinates are surveyed/reported collar positions converted from WGS84 UTM Zone 35S "
            "to latitude and longitude. They do not describe subsurface orebody boundaries."
        )
        try:
            mapped = collar_map_rows(holes, intervals)
        except (ValueError, RuntimeError) as exc:
            st.error(str(exc))
            mapped = []
        if mapped:
            map_event = None
            try:
                import pydeck as pdk
            except ImportError:
                st.warning("Install pydeck (usually supplied with Streamlit) to see the map.")
            else:
                latitude = sum(p["latitude"] for p in mapped) / len(mapped)
                longitude = sum(p["longitude"] for p in mapped) / len(mapped)
                layer = pdk.Layer(
                    "ScatterplotLayer",
                    data=mapped,
                    id="muntanga-north-collars",
                    get_position="[longitude, latitude]",
                    get_fill_color="color",
                    get_line_color=[245, 246, 249, 210],
                    get_radius=15,
                    radius_min_pixels=3,
                    radius_max_pixels=7,
                    line_width_min_pixels=1,
                    stroked=True,
                    pickable=True,
                )
                map_event = st.pydeck_chart(pdk.Deck(
                    layers=[layer],
                    initial_view_state=pdk.ViewState(latitude=latitude, longitude=longitude, zoom=10, pitch=0),
                    tooltip={"html": "<b>{hole_id}</b><br/>Target: {target}<br/>Status: {reporting_status}<br/>{best_grade_label}<br/>Collar (WGS84): {latitude}, {longitude}", "style": {"color": "white"}},
                    map_style="https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
                ), use_container_width=True, on_select="rerun",
                   selection_mode="single-object", key="muntanga_north_collar_map")
            st.caption("Blue = at least one reported radiometric interval; grey = no significant intercept reported.")
            render_collar_inspector(report, mapped, map_event)
            coordinates = pd.DataFrame([{key: value for key, value in p.items() if key != "color"} for p in mapped])
            st.download_button("Export filtered collars (CSV)", coordinates.to_csv(index=False).encode("utf-8"), "muntanga_north_20261120_collars.csv", "text/csv")
        else:
            st.info("No collars match these filters.")

    with intervals_tab:
        st.subheader("Radiometric intervals by downhole depth")
        st.caption("Depth increases downward. Charts show downhole intervals, not true orebody widths.")
        frame = _interval_table(intervals)
        if frame.empty:
            st.info("No reported radiometric intervals match the current filters.")
        else:
            try:
                import altair as alt
            except ImportError:
                st.info("Altair is unavailable; interval records remain in the table.")
            else:
                chart_data = pd.DataFrame([{
                    "hole": r["hole_id"], "from_m": r["from_m"], "to_m": r["to_m"],
                    "grade_ppm": r["eu3o8_ppm"], "target": str(r.get("target_id") or "Unassigned"),
                    "length_m": r["interval_m"], "page": r.get("source_page"),
                } for r in intervals])
                chart = alt.Chart(chart_data).mark_bar(size=20, opacity=0.85).encode(
                    x=alt.X("hole:N", title="Drill hole", sort=sorted(frame["Hole"].unique())),
                    y=alt.Y("from_m:Q", title="Downhole depth (m)", scale=alt.Scale(reverse=True)),
                    y2="to_m:Q",
                    color=alt.Color("grade_ppm:Q", title="ppm eU3O8"),
                    tooltip=["hole:N", "from_m:Q", "to_m:Q", "length_m:Q", "grade_ppm:Q", "target:N", "page:Q"],
                ).properties(height=390)
                st.altair_chart(chart, use_container_width=True)
            st.dataframe(frame.drop(columns=["Source URL"]), use_container_width=True, hide_index=True)
            st.download_button("Export filtered intervals (CSV)", frame.to_csv(index=False).encode("utf-8"), "muntanga_north_20261120_intervals.csv", "text/csv")

    with comparison_tab:
        st.subheader("Highest reported interval grade per hole")
        st.caption(
            "These are maxima of reported intervals, not whole-hole average grades. "
            "No significant intercepts are excluded, not assigned zero."
        )
        best = best_by_hole(intervals)
        if not best:
            st.info("No interval grades available under the current filters.")
        else:
            comparison = pd.DataFrame([{
                "Hole": r["hole_id"], "Best interval (ppm eU3O8)": r["eu3o8_ppm"],
                "From (m)": r["from_m"], "To (m)": r["to_m"],
                "Length (m)": r["interval_m"], "Source page": r.get("source_page"),
            } for r in best])
            st.bar_chart(comparison.set_index("Hole")[["Best interval (ppm eU3O8)"]])
            st.dataframe(comparison, use_container_width=True, hide_index=True)

    with provenance_tab:
        st.subheader("Source and methodology")
        st.markdown(f"**Source:** Atomic Eagle Limited, 20 November 2026, [22-page ASX announcement]({summary['source_url']}).")
        st.write(
            f"Release-only dataset: {len(report.holes)} collars and {len(report.intervals)} intervals. "
            f"The wider 2026 programme reported {summary.get('2026_program_muntanga_north_and_namakande_holes')} "
            "holes across Muntanga North and Namakande; those are NOT represented as additional collars here."
        )
        st.markdown(
            "- Grade basis: **downhole gamma radiometric equivalent uranium, ppm eU3O8**, not chemical assay.\n"
            "- No significant reported intercept does **not** imply zero uranium grade.\n"
            "- Collars are WGS84 UTM Zone 35S; plotted points are collars, not mineralised-area footprints.\n"
            "- Target classification is included only where explicitly reported in the headline table; unassigned is not a new exploration target.\n"
            "- Drill intervals are downhole lengths; geological true widths are not independently verified.\n"
            "- These new exploration intervals are **not** a mineral resource or reserve.\n"
            "- September and November disclosures are not merged or deduplicated here; this is the 20 November release only."
        )
        st.caption(f"Source SHA-256: {summary.get('source_sha256', 'Unavailable')}")
