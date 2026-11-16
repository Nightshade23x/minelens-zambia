from ingestion.ingest_tertiary_mushima_north import (
    HOLES,
    build_hole_records,
    build_intersections,
    build_summary,
    validate,
)


def test_eight_holes_eighteen_intervals():
    assert validate()
    assert len(build_hole_records()) == 8
    assert len(build_intersections()) == 18


def test_correct_zones():
    records = build_hole_records()
    assert sum(r["zone"] == "Western Zone" for r in records) == 2
    assert sum(r["zone"] == "Discovery Zone" for r in records) == 6


def test_disc_zone_flag_and_intersection():
    row = next(r for r in build_intersections() if r["hole_id"] == "26TMNRC-078" and r["from_m"] == 10)
    assert (row["interval_m"], row["ag_gpt"], row["cu_pct"], row["zn_pct"]) == (70, 31, 0.29, 0.25)
    assert row["hole_ends_in_mineralisation"]


def test_western_copper_peak_distinguished():
    rows = [r for r in build_intersections() if r["hole_id"] == "26TMNRC-076"]
    assert any(r["from_m"] == 32 and r["to_m"] == 37 and r["cu_pct"] == 0.60 for r in rows)
    assert HOLES["26TMNRC-076"][3]["cu_pct"] == 0.65
    assert max(r["cu_pct"] for r in rows) != HOLES["26TMNRC-076"][3]["cu_pct"]


def test_missing_gram_metres_not_zero():
    r = next(r for r in build_intersections() if r["hole_id"] == "26TMNRC-080" and r["from_m"] == 48)
    assert r["ag_gram_metres_reported"] is None


def test_not_a_resource_or_phase5_result():
    summary = build_summary()
    assert summary["phase5_results_included"] is False
    assert summary["mineral_resource_estimate_included"] is False
    assert all(not r["is_mineral_resource_or_reserve"] for r in build_intersections())
