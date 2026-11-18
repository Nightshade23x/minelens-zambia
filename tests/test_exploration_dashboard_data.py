"""Regression guards for a new, read-only exploration dashboard."""

from app.exploration_dashboard_data import (
    filter_intervals,
    highest_interval,
    hole_comparison,
    load_phase4_report,
    peak_individual_assays,
)


def test_load_real_mushima_release():
    report = load_phase4_report()
    assert len(report.holes) == 8
    assert len(report.intervals) == 18
    assert report.summary["announcement_date"] == "2026-11-09"


def test_interval_grade_is_not_individual_assay():
    report = load_phase4_report()
    top = highest_interval(report.intervals, "ag_gpt")
    assert top["hole_id"] == "26TMNRC-078"
    assert top["ag_gpt"] == 84
    assert top["interval_m"] == 6
    individual = peak_individual_assays(report.holes, "ag_gpt")
    assert individual[0]["grade"] == 139
    assert individual[0]["hole_id"] == "26TMNRC-077"


def test_individual_copper_peaks():
    report = load_phase4_report()
    top = peak_individual_assays(report.holes, "cu_pct")[0]
    assert top["grade"] == 1.08
    assert top["hole_id"] == "26TMNRC-078"


def test_zone_and_hole_filters():
    report = load_phase4_report()
    rows = filter_intervals(
        report.intervals, {"Western Zone"}, {"26TMNRC-076"}
    )
    assert len(rows) == 2
    assert all(row["hole_id"] == "26TMNRC-076" for row in rows)


def test_nested_intervals_can_be_hidden_without_adding_widths():
    report = load_phase4_report()
    intervals = filter_intervals(
        report.intervals, {"Discovery Zone"}, {"26TMNRC-078"}, include_nested=False
    )
    assert len(intervals) == 1
    assert intervals[0]["interval_m"] == 70


def test_hole_comparison_keeps_interval_max_not_peak_assay():
    report = load_phase4_report()
    rows = hole_comparison(report, "cu_pct")
    hole = next(row for row in rows if row["hole_id"] == "26TMNRC-078")
    assert hole["max_interval_grade"] == 0.32
    assert hole["reported_intervals"] == 2


def test_no_data_and_invalid_metal():
    assert highest_interval([], "ag_gpt") is None
    try:
        highest_interval([], "gold")
    except ValueError:
        pass
    else:
        raise AssertionError("Unexpected support for gold")
