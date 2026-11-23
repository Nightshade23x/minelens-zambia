"""Project-aware exploration result display; leaves the original Kabwe renderer intact.

This module does not alter routing or answer generation. All information shown
comes from structured records returned by the existing exploration search.
"""

from __future__ import annotations

import re
from typing import Any


def _rows(search_result: dict) -> list[dict]:
    output = []
    for value in search_result.get("results") or []:
        if not isinstance(value, dict):
            continue
        # Some adapters wrap a raw row in a `record` object.
        row = value.get("record")
        output.append(row if isinstance(row, dict) else value)
    return output


def _project(question: str, rows: list[dict]) -> str | None:
    """Identify only the explicitly supported project types."""
    names = {str(row.get("project") or "").casefold() for row in rows}
    if "muntanga north" in names:
        return "muntanga"
    if "mushima north" in names:
        return "mushima"

    query = str(question or "").casefold()
    if "muntanga north" in query or re.search(r"\bmndth\s*\d+\b", query):
        return "muntanga"
    if "mushima north" in query or re.search(r"\b26tmnrc[- ]?\d+\b", query):
        return "mushima"
    return None


def _status(row: dict) -> str:
    raw = str(row.get("intercept_reporting_status") or row.get("status") or "")
    if raw == "no_significant_intercept":
        return "No significant intercept reported"
    if raw in {"reported_radiometric_intercept", "reported_intercept"}:
        return "Reported radiometric intercept"
    if raw:
        return raw.replace("_", " ").capitalize()
    return "Reported interval" if row.get("from_m") is not None else "Drill-hole record"


def build_project_panel(search_result: dict, question: str) -> dict[str, Any] | None:
    """Return a display model for Muntanga/Mushima, or None for the legacy renderer."""
    rows = _rows(search_result)
    project = _project(question, rows)
    if project is None:
        return None

    if project == "muntanga":
        intervals = []
        collars = []
        for row in rows:
            if row.get("from_m") is not None:
                intervals.append({
                    "Hole": row.get("hole_id"),
                    "Target": row.get("target_id"),
                    "From (m)": row.get("from_m"),
                    "To (m)": row.get("to_m"),
                    "Length (m)": row.get("interval_m"),
                    "eU3O8 (ppm)": row.get("eu3o8_ppm"),
                    "Source page": row.get("source_page"),
                })
            else:
                collars.append({
                    "Hole": row.get("hole_id"),
                    "Target": row.get("target_id"),
                    "Hole depth (m)": row.get("hole_depth_m"),
                    "Status": _status(row),
                    "Easting (m)": row.get("easting_m"),
                    "Northing (m)": row.get("northing_m"),
                    "UTM zone": row.get("utm_zone"),
                    "Source page": row.get("source_page"),
                })
        title = "Muntanga North uranium exploration results"
        subtitle = "Atomic Eagle Limited | 20 November 2026 | downhole-gamma radiometric results"
        caution = (
            "Grades are radiometric equivalent uranium (ppm eU3O8), NOT laboratory "
            "assays. Downhole intervals are not independently demonstrated true "
            "widths or mineral resources/reserves. A hole with no significant "
            "reported intercept does not have a measured zero grade."
        )
    else:
        intervals = []
        collars = []
        for row in rows:
            if row.get("from_m") is not None:
                intervals.append({
                    "Hole": row.get("hole_id"),
                    "Zone": row.get("zone"),
                    "From (m)": row.get("from_m"),
                    "To (m)": row.get("to_m"),
                    "Length (m)": row.get("interval_m") or row.get("width_m"),
                    "Ag (g/t)": row.get("ag_gpt"),
                    "Cu (%)": row.get("cu_pct"),
                    "Zn (%)": row.get("zn_pct"),
                    "Including": row.get("is_including") if "is_including" in row else row.get("including_interval"),
                    "Source page": row.get("source_page"),
                })
            else:
                peaks = row.get("reported_peak_individual_assays") or {}
                if not isinstance(peaks, dict):
                    peaks = {}
                collars.append({
                    "Hole": row.get("hole_id"),
                    "Zone": row.get("zone"),
                    "Peak individual Ag (g/t)": peaks.get("ag_gpt"),
                    "Peak individual Cu (%)": peaks.get("cu_pct"),
                    "Peak individual Zn (%)": peaks.get("zn_pct"),
                    "Source page": row.get("source_page"),
                })
        title = "Mushima North silver, copper and zinc drilling results"
        subtitle = "Tertiary Minerals plc | 9 November 2026 | Phase 4 company drilling disclosure"
        caution = (
            "Interval-average grades and peak individual assays are different "
            "measurements. Some 'including' intervals overlap wider intervals. "
            "True widths are not confirmed; these are not mineral resources/reserves."
        )

    url = next(
        (str(row.get("source_url")) for row in rows if row.get("source_url")),
        str(search_result.get("source_url") or ""),
    )
    return {
        "project": project,
        "title": title,
        "subtitle": subtitle,
        "caution": caution,
        "intervals": intervals,
        "collars": collars,
        "hole_count": len({str(row.get("hole_id")) for row in rows if row.get("hole_id")}),
        "result_count": len(rows),
        "source_url": url,
    }


def display_project_exploration_results(search_result: dict, question: str) -> bool:
    """Render a project-specific Streamlit panel; return False for Kabwe/other."""
    panel = build_project_panel(search_result, question)
    if panel is None:
        return False

    import streamlit as st

    st.subheader("Exploration results")
    st.markdown(f"**{panel['title']}**")
    st.caption(panel["subtitle"])
    c1, c2 = st.columns(2)
    c1.metric("Records shown", panel["result_count"])
    c2.metric("Drill holes in results", panel["hole_count"])

    if panel["intervals"]:
        st.markdown("**Reported drill intervals**")
        st.dataframe(panel["intervals"], hide_index=True, use_container_width=True)
    if panel["collars"]:
        if panel["project"] == "muntanga":
            st.markdown("**Hole / collar records**")
        else:
            st.markdown("**Reported individual peak assays (not interval averages)**")
        st.dataframe(panel["collars"], hide_index=True, use_container_width=True)
    if not panel["intervals"] and not panel["collars"]:
        st.info("No matching records were found in this project's ingested announcement.")

    st.caption(panel["caution"])
    if panel["source_url"].startswith(("https://", "http://")):
        st.markdown(f"[Open the original company announcement]({panel['source_url']})")
    return True
