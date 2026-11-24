"""Test the map's source-scoped click selection and drill-hole details."""
import pytest

from app.muntanga_collar_detail import (
    LAYER_ID, get_collar_profile, selected_hole_from_map_event,
)
from app.muntanga_dashboard_data import MuntangaReport, SOURCE_ID


def _report():
    def hole(hole_id, status):
        return {
            "hole_id": hole_id, "source_id": SOURCE_ID, "project": "Muntanga North",
            "intercept_reporting_status": status,
            "easting_m": 682462, "northing_m": 8209207,
            "hole_depth_m": 100, "source_page": 8,
        }
    def interval(hole_id, grade, depth):
        return {
            "hole_id": hole_id, "project": "Muntanga North", "source_id": SOURCE_ID,
            "grade_unit": "ppm eU3O8", "grade_basis": "downhole_gamma_equivalent_uranium",
            "is_laboratory_assay": False, "is_mineral_resource": False,
            "from_m": depth, "to_m": depth + 2, "interval_m": 2,
            "eu3o8_ppm": grade, "source_page": 12,
        }
    return MuntangaReport(
        {"source_id": SOURCE_ID, "source_url": "https://example.org/release.pdf", "reported_date": "2026-11-20"},
        (hole("MNDTH2421", "reported_radiometric_intercept"),
         hole("MNDTH2370", "no_significant_intercept")),
        (interval("MNDTH2421", 380, 38.79), interval("MNDTH2421", 140, 45.0)),
    )


def test_click_selects_visible_hole():
    state = {"selection": {"objects": {LAYER_ID: [{"hole_id": "MNDTH2421"}]}}}
    assert selected_hole_from_map_event(state, {"MNDTH2421"}) == "MNDTH2421"


def test_click_does_not_select_filtered_hole():
    state = {"selection": {"objects": {LAYER_ID: [{"hole_id": "MNDTH2421"}]}}}
    assert selected_hole_from_map_event(state, {"MNDTH2370"}) is None


def test_untrusted_hole_not_selected():
    state = {"selection": {"objects": {LAYER_ID: [{"hole_id": "UNKNOWN"}]}}}
    assert selected_hole_from_map_event(state, {"MNDTH2421"}) is None


def test_empty_event_is_safe():
    assert selected_hole_from_map_event(None, {"MNDTH2421"}) is None
    assert selected_hole_from_map_event({"selection": {}}, {"MNDTH2421"}) is None


def test_profile_intercepts_are_depth_ordered():
    p = get_collar_profile(_report(), "MNDTH2421")
    assert p["best"]["eu3o8_ppm"] == 380
    assert len(p["intercepts"]) == 2
    assert p["intercepts"][0]["from_m"] == 38.79
    assert p["source_url"].endswith("release.pdf")


def test_no_significant_is_not_zero():
    p = get_collar_profile(_report(), "MNDTH2370")
    assert p["best"] is None
    assert p["intercepts"] == []
    assert p["status_label"] == "No significant intercept reported"


def test_unknown_hole_rejected():
    with pytest.raises(ValueError, match="Unknown"):
        get_collar_profile(_report(), "MNDTH9999")


def test_unsafe_assay_label_rejected():
    report = _report()
    report.intervals[0]["is_laboratory_assay"] = True
    with pytest.raises(ValueError, match="Unverified"):
        get_collar_profile(report, "MNDTH2421")


def test_wrong_source_rejected():
    report = _report()
    report.summary["source_id"] = "unrelated"
    with pytest.raises(ValueError, match="Unexpected source"):
        get_collar_profile(report, "MNDTH2421")


def test_contradictory_status_rejected():
    report = _report()
    report.holes[1]["intercept_reporting_status"] = "reported_radiometric_intercept"
    with pytest.raises(ValueError, match="contradicts"):
        get_collar_profile(report, "MNDTH2370")
