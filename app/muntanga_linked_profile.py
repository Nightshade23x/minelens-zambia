"""Pure helpers for linking the Muntanga collar map and radiometric depth profile.

This module never turns missing/no-significant intercepts into measured zero grades.
"""
from __future__ import annotations

from collections.abc import Iterable

from app.muntanga_collar_detail import get_collar_profile
from app.muntanga_dashboard_data import MuntangaReport


def choose_visible_hole(
    manual_selection: str | None,
    map_selection: str | None,
    visible_hole_ids: Iterable[str],
    placeholder: str,
) -> str | None:
    """Manual selection wins; never return a hole hidden by sidebar filters."""
    visible = set(visible_hole_ids)
    if manual_selection and manual_selection != placeholder:
        return manual_selection if manual_selection in visible else None
    return map_selection if map_selection in visible else None


def depth_profile(report: MuntangaReport, hole_id: str) -> dict:
    """Return a validated, source-backed profile for one selected drill collar."""
    profile = get_collar_profile(report, hole_id)
    hole = profile["hole"]
    full_depth = float(hole["hole_depth_m"])
    if full_depth <= 0:
        raise ValueError("Invalid drill-hole depth")

    rows = []
    for item in profile["intercepts"]:
        from_m = float(item["from_m"])
        to_m = float(item["to_m"])
        ppm = float(item["eu3o8_ppm"])
        if not (0 <= from_m < to_m <= full_depth + 0.1):
            raise ValueError("Intercept lies outside recorded drill-hole depth")
        if ppm < 0:
            raise ValueError("Invalid reported radiometric grade")
        rows.append({
            "Hole": hole_id,
            "From (m)": from_m,
            "To (m)": to_m,
            "Length (m)": float(item["interval_m"]),
            "eU3O8 (ppm)": ppm,
            "Source page": item.get("source_page"),
        })

    return {
        "hole_id": hole_id,
        "hole_depth_m": full_depth,
        "status": profile["status_label"],
        "rows": rows,
        "source_url": profile["source_url"],
    }


def map_hover_rows(mapped: Iterable[dict]) -> list[dict]:
    """Decorate map tooltip metadata without changing original map positions."""
    output = []
    for point in mapped:
        status = point["reporting_status"]
        if status == "no_significant_intercept":
            friendly = "No significant intercept reported"
        elif status == "reported_radiometric_intercept":
            friendly = "Reported radiometric intercepts"
        else:
            raise ValueError("Unrecognised collar reporting status")
        row = dict(point)
        row["display_status"] = friendly
        row["coordinate_label"] = (
            f"{float(point['latitude']):.6f}, "
            f"{float(point['longitude']):.6f}"
        )
        output.append(row)
    return output
