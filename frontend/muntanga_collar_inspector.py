"""Click-to-inspect detail panel for the existing Muntanga PyDeck map."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from app.muntanga_collar_detail import get_collar_profile, selected_hole_from_map_event
from app.muntanga_linked_profile import choose_visible_hole
from app.muntanga_dashboard_data import MuntangaReport


_CHOOSE = "(Click a collar, or choose a hole below)"


def _display_number(value: object, decimals: int = 2) -> str:
    return f"{float(value):,.{decimals}f}" if value is not None else "Not recorded"


def render_collar_inspector(
    report: MuntangaReport,
    mapped: list[dict],
    event: object,
) -> str | None:
    """Render source-backed details and return the current visible hole selection."""
    visible_ids = {point["hole_id"] for point in mapped}
    map_id = selected_hole_from_map_event(event, visible_ids)
    available = sorted(visible_ids)

    st.markdown("#### Inspect a drill collar")
    st.caption(
        "Click a blue or grey marker to inspect its hole. Where nearby collars "
        "overlap, choose the hole ID below. A manual choice overrides the map "
        "until you clear the selector."
    )
    manually_selected = st.selectbox(
        "Choose a drill hole (optional)",
        options=[_CHOOSE, *available],
        index=0,
        key="muntanga_inspected_hole_override",
    )
    hole_id = choose_visible_hole(manually_selected, map_id, visible_ids, _CHOOSE)
    if hole_id is None:
        st.info("Select a map marker or a hole ID to see its drilling details.")
        return

    details = get_collar_profile(report, hole_id)
    hole = details["hole"]
    intervals = details["intercepts"]
    best = details["best"]
    point = next(p for p in mapped if p["hole_id"] == hole_id)

    st.markdown(f"**{hole_id}** — {details['status_label']}")
    first, second, third = st.columns(3)
    first.metric("Hole depth (m)", _display_number(hole.get("hole_depth_m")))
    second.metric("Reported intervals", len(intervals))
    third.metric(
        "Best reported interval (ppm eU3O8)",
        f"{float(best['eu3o8_ppm']):g}" if best else "Not reported",
    )

    target = hole.get("target_id")
    target_label = f"Target {target}" if target is not None else "Not assigned in Table 1"
    st.write(f"**Target:** {target_label} | **Operator:** Atomic Eagle Limited")
    st.caption(
        f"Reported WGS84 UTM 35S collar: E {_display_number(hole.get('easting_m'), 0)} m, "
        f"N {_display_number(hole.get('northing_m'), 0)} m. "
        f"Converted WGS84 position: {point['latitude']:.6f}, {point['longitude']:.6f}. "
        "These coordinates identify the surface collar, not a mineralised-area boundary."
    )
    if intervals:
        frame = pd.DataFrame([{
            "From (m)": r["from_m"],
            "To (m)": r["to_m"],
            "Length (m)": r["interval_m"],
            "Radiometric eU3O8 (ppm)": r["eu3o8_ppm"],
            "Source page": r.get("source_page"),
        } for r in intervals])
        st.dataframe(frame, hide_index=True, use_container_width=True)
        st.download_button(
            "Export this hole's intercepts (CSV)",
            data=frame.to_csv(index=False).encode("utf-8"),
            file_name=f"muntanga_north_{hole_id}_radiometric_intervals.csv",
            mime="text/csv",
        )
    else:
        st.info(
            "This hole is marked 'No Significant Intercept' in the release. "
            "That does not mean its uranium grade is zero."
        )
    pages = sorted({int(r["source_page"]) for r in intervals if r.get("source_page") is not None})
    pages = pages or ([hole["source_page"]] if hole.get("source_page") is not None else [])
    st.caption(
        f"Atomic Eagle Limited | {details['source_date']} | "
        f"Source page(s): {', '.join(str(p) for p in pages) or 'Not recorded'}. "
        "eU3O8 values are downhole-gamma estimates, NOT laboratory assays or mineral resources."
    )
    if details["source_url"]:
        st.markdown(f"[Open original ASX announcement]({details['source_url']})")
    return hole_id
