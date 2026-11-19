"""Read-only checks for project comparison provenance and safe numerical use."""
import copy
import json
from pathlib import Path

import pytest

from app.project_comparison_data import (
    load_comparison, comparison_rows, claim_rows, COUNTRY_COMPACT,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/processed/project_comparison_evidence_20261119.json"


def test_three_projects_and_fact_counts():
    data = load_comparison(SOURCE)
    assert set(data) == {"Kansanshi", "Lumwana", "Mingomba"}
    assert [len(data[n]["claims"]) for n in data] == [4, 4, 3]


def test_2026_capex_comparison_and_mingomba_lower_bound():
    data = load_comparison(SOURCE)
    amounts = {
        name: [(c.usd_billions, c.qualifier) for c in project["claims"] if c.kind == "capex"]
        for name, project in data.items()
    }
    assert amounts["Kansanshi"] == [(1.25, "approximately"), (1.25, "approximately")]
    assert amounts["Lumwana"] == [(2.0, "estimated"), (2.0, "approximately")]
    assert amounts["Mingomba"] == [(2.0, "expected"), (2.0, "lower_bound_strict")]


def test_no_fabricated_historical_mingomba_output():
    data = load_comparison(SOURCE)
    assert not [c for c in data["Mingomba"]["claims"] if c.kind == "historical"]
    assert any(c.kind == "historical" for c in data["Kansanshi"]["claims"])
    assert any(c.kind == "historical" for c in data["Lumwana"]["claims"])


def test_targets_not_mislabelled_as_actual_production():
    data = load_comparison(SOURCE)
    assert [next(c.capacity_tpa for c in data[n]["claims"] if c.kind == "capacity") for n in data] == [200000, 240000, 300000]
    assert next(c.qualifier for c in data["Mingomba"]["claims"] if c.kind == "capacity") == "production potential"


def test_provenance_entries_have_pages_and_supporting_excerpt():
    data = load_comparison(SOURCE)
    for project in data.values():
        for c in project["claims"]:
            assert c.document and c.pages and c.excerpt and c.source_title
            if c.kind == "capex":
                assert c.document == COUNTRY_COMPACT


def test_declaration_and_annex_are_same_document():
    data = load_comparison(SOURCE)
    for project in data.values():
        capex = [c for c in project["claims"] if c.kind == "capex"]
        assert capex[0].document == capex[1].document
        assert {c.pages for c in capex} == {"8", "25-26"}


def test_data_rows_include_unknown_instead_of_false_zero():
    data = load_comparison(SOURCE)
    row = next(row for row in comparison_rows(data) if row["Project"] == "Mingomba")
    assert "Not established" in row["2024 reported output"]


def test_csv_view_can_select_one_project():
    data = load_comparison(SOURCE)
    rows = comparison_rows(data, ["Lumwana"])
    assert [r["Project"] for r in rows] == ["Lumwana"]
    assert all(r["Project"] == "Lumwana" for r in claim_rows(data, ["Lumwana"]))


def test_unsupported_capex_claim_is_rejected(tmp_path):
    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    for row in data:
        if row["project"] == "Kansanshi":
            for item in row["evidence"]:
                item["text"] = item["text"].replace(
                    "Kansanshi mine (approximately $1.25 billion CapEx)",
                    "Kansanshi mine (unknown CapEx)",
                )
    invalid = tmp_path / "invalid.json"
    invalid.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="lacks a matching cited passage"):
        load_comparison(invalid)


def test_unexpected_project_snapshot_rejected(tmp_path):
    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    data[0]["project"] = "Some other mine"
    invalid = tmp_path / "invalid.json"
    invalid.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="Unexpected project set"):
        load_comparison(invalid)
