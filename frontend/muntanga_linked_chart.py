"""Source-grounded depth visualization for a selected Muntanga drill collar."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from app.muntanga_linked_profile import depth_profile
from app.muntanga_dashboard_data import MuntangaReport


def render_linked_depth_profile(
    report: MuntangaReport,
    hole_id: str,
    *,
    placement: str = "map",
) -> None:
    """Render the active collar profile; do not alter the existing all-hole chart."""
    profile = depth_profile(report, hole_id)
    if placement == "map":
        st.markdown("##### Selected-hole depth chart")
    else:
        st.markdown("##### Linked collar selection")
    st.caption(
        f"{hole_id} | total drilled depth {profile['hole_depth_m']:g} m. "
        "Selected using the collar map or drill-hole chooser."
    )
    if not profile["rows"]:
        st.info(
            "No significant radiometric intercept was reported for this hole "
            "in the 20 November release. This does not establish a zero uranium grade."
        )
        return

    frame = pd.DataFrame(profile["rows"])
    try:
        import altair as alt
    except ImportError:
        st.warning("Altair is unavailable; the selected-hole interval table remains accessible.")
    else:
        chart = (
            alt.Chart(frame)
            .mark_bar(size=56, opacity=0.9)
            .encode(
                x=alt.X("Hole:N", title="Selected drill hole", axis=alt.Axis(labelAngle=0)),
                y=alt.Y(
                    "From (m):Q",
                    title="Downhole depth (m)",
                    scale=alt.Scale(domain=[0, profile["hole_depth_m"]], reverse=True),
                ),
                y2="To (m):Q",
                color=alt.Color(
                    "eU3O8 (ppm):Q",
                    title="ppm eU3O8",
                    scale=alt.Scale(domain=[0, max(float(v) for v in frame["eU3O8 (ppm)"])]),
                    legend=alt.Legend(format=",.0f", tickCount=4),
                ),
                tooltip=[
                    "Hole:N", "From (m):Q", "To (m):Q", "Length (m):Q",
                    alt.Tooltip("eU3O8 (ppm):Q", format=",.0f"), "Source page:Q",
                ],
            )
            .properties(height=340)
        )
        st.altair_chart(chart, use_container_width=True)

    st.dataframe(frame, hide_index=True, use_container_width=True)
    st.caption(
        "Radiometric equivalent uranium (ppm eU3O8) from downhole gamma data; "
        "not a laboratory assay or mineral-resource estimate. "
        "Intervals represent downhole lengths, not established true widths."
    )
