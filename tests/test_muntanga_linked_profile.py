"""Focused tests for linking an active collar to the reported radiometric depth chart."""
from copy import deepcopy
from pathlib import Path

import pytest

from app.muntanga_dashboard_data import MuntangaReport, SOURCE_ID
from app.muntanga_linked_profile import (
    choose_visible_hole, depth_profile, map_hover_rows,
)


def sample_report():
    holes = (
        {
            "hole_id": "MNDTH2421", "project": "Muntanga North", "source_id": SOURCE_ID,
            "hole_depth_m": 100, "intercept_reporting_status": "reported_radiometric_intercept",
        },
        {
            "hole_id": "MNDTH2371", "project": "Muntanga North", "source_id": SOURCE_ID,
            "hole_depth_m": 102, "intercept_reporting_status": "no_significant_intercept",
        },
    )
    intervals = (
        {
            "hole_id": "MNDTH2421", "project": "Muntanga North", "source_id": SOURCE_ID,
            "grade_unit": "ppm eU3O8", "grade_basis": "downhole_gamma_equivalent_uranium",
            "is_laboratory_assay": False, "is_mineral_resource": False,
            "from_m": 38.79, "to_m": 43.97, "interval_m": 5.18,
            "eu3o8_ppm": 380, "source_page": 12,
        },
    )
    return MuntangaReport(
        summary={"source_id": SOURCE_ID, "source_url": "https://example.org/asx.pdf", "reported_date": "2026-11-20"},
        holes=holes,
        intervals=intervals,
    )


def test_manual_selection_precedes_map():
    assert choose_visible_hole("MNDTH2371", "MNDTH2421", {"MNDTH2421", "MNDTH2371"}, "Choose") == "MNDTH2371"


def test_map_selection_when_manual_is_placeholder():
    assert choose_visible_hole("Choose", "MNDTH2421", {"MNDTH2421"}, "Choose") == "MNDTH2421"


def test_filtered_or_untrusted_selection_cannot_link():
    assert choose_visible_hole("Choose", "MNDTH2421", {"MNDTH2371"}, "Choose") is None
    assert choose_visible_hole("MNDTH2421", "MNDTH2371", {"MNDTH2371"}, "Choose") is None


def test_depth_profile_uses_actual_reported_intercept():
    result = depth_profile(sample_report(), "MNDTH2421")
    assert result["hole_depth_m"] == 100
    assert len(result["rows"]) == 1
    assert result["rows"][0]["eU3O8 (ppm)"] == 380
    assert result["rows"][0]["From (m)"] == 38.79
    assert result["rows"][0]["To (m)"] == 43.97
    assert result["rows"][0]["Source page"] == 12


def test_no_significant_intercept_is_missing_not_zero():
    result = depth_profile(sample_report(), "MNDTH2371")
    assert result["rows"] == []
    assert result["status"] == "No significant intercept reported"


def test_bad_reported_interval_outside_hole_is_rejected():
    report = deepcopy(sample_report())
    report.intervals[0]["to_m"] = 110
    with pytest.raises(ValueError, match="outside"):
        depth_profile(report, "MNDTH2421")


def test_lab_assays_cannot_enter_linked_radiometric_chart():
    report = deepcopy(sample_report())
    report.intervals[0]["is_laboratory_assay"] = True
    with pytest.raises(ValueError, match="Unverified"):
        depth_profile(report, "MNDTH2421")


def test_hover_has_readable_status_and_rounded_coordinates():
    original = [{
        "hole_id": "MNDTH2371", "reporting_status": "no_significant_intercept",
        "latitude": -16.2600165234, "longitude": 28.6321154078,
    }]
    result = map_hover_rows(original)
    assert result[0]["display_status"] == "No significant intercept reported"
    assert result[0]["coordinate_label"] == "-16.260017, 28.632115"
    assert original[0].get("display_status") is None
    assert result[0]["latitude"] == original[0]["latitude"]


def test_hover_rejects_unknown_status():
    with pytest.raises(ValueError, match="Unrecognised"):
        map_hover_rows([{
            "reporting_status": "resource_estimate", "latitude": -16, "longitude": 28,
        }])


def test_linked_profile_integrated_in_current_view():
    # Verify the installed product, rather than a disposable installer.
    root = Path(__file__).resolve().parents[1]
    view = (root / "frontend/muntanga_exploration_view.py").read_text(encoding="utf-8")
    inspector = (root / "frontend/muntanga_collar_inspector.py").read_text(encoding="utf-8")
    assert "# MINELENS_MUNTANGA_LINKED_PROFILE_V1" in view
    assert "selected_collar_id = render_collar_inspector" in view
    assert 'render_linked_depth_profile(report, selected_collar_id, placement="map")' in view
    assert 'render_linked_depth_profile(report, selected_collar_id, placement="intervals")' in view
    assert "    return hole_id" in inspector


def test_installed_linked_view_and_inspector_compile():
    import ast
    root = Path(__file__).resolve().parents[1]
    for name in (
        "frontend/muntanga_exploration_view.py",
        "frontend/muntanga_collar_inspector.py",
    ):
        file_path = root / name
        ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
