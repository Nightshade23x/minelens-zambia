"""Pure drill-collar selection and evidence detail helpers for Muntanga North.

Never infer an assay, resource estimate, grade of zero, or extra collar
coordinate from an unreported measurement.
"""
from __future__ import annotations

from collections.abc import Mapping

from app.muntanga_dashboard_data import MuntangaReport, SOURCE_ID

LAYER_ID = "muntanga-north-collars"


def selected_hole_from_map_event(event: object, visible_hole_ids: set[str]) -> str | None:
    """Return a selected, currently visible hole from a PyDeck event.

    Streamlit returns a PydeckState containing selection.objects keyed by the
    layer id. Some versions also return selected indices, so support those
    separately in the view (the object payload is preferred here).
    """
    if event is None:
        return None
    if isinstance(event, Mapping):
        selection = event.get("selection", {})
    else:
        selection = getattr(event, "selection", {})
    if not isinstance(selection, Mapping):
        return None
    objects = selection.get("objects", {})
    if not isinstance(objects, Mapping):
        return None
    matches = objects.get(LAYER_ID) or []
    if not isinstance(matches, (list, tuple)) or not matches:
        return None
    first = matches[0]
    if not isinstance(first, Mapping):
        return None
    candidate = first.get("hole_id")
    if isinstance(candidate, str) and candidate in visible_hole_ids:
        return candidate
    return None


def get_collar_profile(report: MuntangaReport, hole_id: str) -> dict:
    """Build source-backed details for one hole in the verified release."""
    if report.summary.get("source_id") != SOURCE_ID:
        raise ValueError("Unexpected source for Muntanga North collar")
    matches = [hole for hole in report.holes if hole.get("hole_id") == hole_id]
    if len(matches) != 1:
        raise ValueError(f"Unknown or duplicate Muntanga North collar: {hole_id}")
    hole = matches[0]
    if hole.get("source_id") != SOURCE_ID or hole.get("project") != "Muntanga North":
        raise ValueError("Selected collar is not sourced to the verified release")
    intervals = sorted(
        (r for r in report.intervals if r.get("hole_id") == hole_id),
        key=lambda r: (float(r["from_m"]), float(r["to_m"])),
    )
    for row in intervals:
        if (
            row.get("source_id") != SOURCE_ID
            or row.get("project") != "Muntanga North"
            or row.get("grade_unit") != "ppm eU3O8"
            or row.get("grade_basis") != "downhole_gamma_equivalent_uranium"
            or row.get("is_laboratory_assay") is not False
            or row.get("is_mineral_resource") is not False
        ):
            raise ValueError("Unverified or incorrectly labelled uranium interval")
    has_intercept = hole.get("intercept_reporting_status") == "reported_radiometric_intercept"
    if has_intercept != bool(intervals):
        raise ValueError("Collar reporting status contradicts interval records")
    best = max(intervals, key=lambda r: float(r["eu3o8_ppm"])) if intervals else None
    return {
        "hole": hole,
        "intercepts": intervals,
        "best": best,
        "status_label": (
            "Reported radiometric intercepts" if has_intercept
            else "No significant intercept reported"
        ),
        "source_url": report.summary.get("source_url", ""),
        "source_date": report.summary.get("reported_date", "2026-11-20"),
    }
