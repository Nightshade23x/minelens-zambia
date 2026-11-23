"""Focused tests: no production router or model required."""
from app.exploration_result_panels import build_project_panel


def test_muntanga_interval_has_uranium_not_zinc_columns():
    row = {
        "project": "Muntanga North", "hole_id": "MNDTH2421", "target_id": 6,
        "from_m": 38.79, "to_m": 43.97, "interval_m": 5.18,
        "eu3o8_ppm": 380, "source_page": 12,
        "source_url": "https://example.org/muntanga.pdf",
    }
    panel = build_project_panel({"results": [row]}, "Which Muntanga North hole has highest uranium grade?")
    assert panel["project"] == "muntanga"
    assert panel["intervals"][0]["eU3O8 (ppm)"] == 380
    assert "Zn (%)" not in panel["intervals"][0]
    assert "NOT laboratory assays" in panel["caution"]
    assert "Shuka" not in panel["subtitle"]


def test_no_significant_intercept_is_not_zero_grade():
    row = {
        "project": "Muntanga North", "hole_id": "MNDTH2370",
        "record_type": "uranium_drill_hole",
        "intercept_reporting_status": "no_significant_intercept",
        "easting_m": 679710, "northing_m": 8209656,
    }
    panel = build_project_panel({"results": [row]}, "MNDTH2370")
    assert not panel["intervals"]
    assert "No significant" in panel["collars"][0]["Status"]
    assert "eU3O8 (ppm)" not in panel["collars"][0]


def test_unknown_muntanga_hole_is_scoped_even_without_results():
    panel = build_project_panel({"results": []}, "Show assays for MNDTH9999")
    assert panel["project"] == "muntanga"
    assert panel["result_count"] == 0


def test_mushima_interval_has_correct_metal_fields():
    row = {
        "project": "Mushima North", "hole_id": "26TMNRC-078",
        "from_m": 34, "to_m": 40, "interval_m": 6,
        "ag_gpt": 84, "cu_pct": 0.32, "zn_pct": 0.29,
        "source_url": "https://example.org/mushima.pdf",
    }
    panel = build_project_panel({"results": [row]}, "Highest Mushima North silver interval?")
    assert panel["project"] == "mushima"
    assert panel["intervals"][0]["Ag (g/t)"] == 84
    assert "eU3O8 (ppm)" not in panel["intervals"][0]


def test_mushima_peak_assays_stay_separate():
    row = {
        "project": "Mushima North", "hole_id": "26TMNRC-078",
        "reported_peak_individual_assays": {"cu_pct": 1.08},
    }
    panel = build_project_panel({"results": [row]}, "Mushima North peak individual copper assay")
    assert panel["collars"][0]["Peak individual Cu (%)"] == 1.08
    assert not panel["intervals"]


def test_kabwe_uses_existing_renderer():
    assert build_project_panel({"results": [{"project": "Kabwe", "hole_id": "KBDD001"}]}, "Show Kabwe drill holes") is None


def test_project_rows_wrapped_in_record():
    row = {"project": "Muntanga North", "hole_id": "MNDTH2421", "from_m": 10, "eu3o8_ppm": 120}
    panel = build_project_panel({"results": [{"record": row}]}, "Muntanga North")
    assert panel["intervals"][0]["eU3O8 (ppm)"] == 120
