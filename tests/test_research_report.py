"""Offline tests for the PDF report generator, no router/Ollama changes."""
from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest

from app.project_comparison_data import load_comparison
from app.research_report import (
    prepare_report,
    generate_project_report_pdf,
    SNAPSHOT_DATE,
)


@pytest.fixture(scope="module")
def projects():
    return load_comparison()


def test_loads_three_verifiable_projects(projects):
    assert set(projects) == {"Kansanshi", "Lumwana", "Mingomba"}


def test_report_has_sequential_claim_references(projects):
    model = prepare_report(projects, list(projects))
    assert [r["n"] for r in model["references"]] == list(range(1, 12))
    assert len(model["entries"]) == 3


def test_provenance_keeps_two_same_report_passages_distinct(projects):
    data = prepare_report(projects, ["Kansanshi"])
    capex = data["entries"][0]["capex"]
    assert len(capex) == 2
    assert capex[0].document == capex[1].document
    assert capex[0].pages == "8"
    assert capex[1].pages == "25-26"


def test_mingomba_annex_remains_strict_lower_bound(projects):
    model = prepare_report(projects, ["Mingomba"])
    first, annex = model["entries"][0]["capex"]
    assert first.qualifier == "expected"
    assert annex.qualifier == "lower_bound_strict"
    assert annex.value == ">$2.0B"


def test_mingomba_has_no_invented_historical_output(projects):
    model = prepare_report(projects, ["Mingomba"])
    assert model["entries"][0]["historical"] == []


@pytest.mark.parametrize("selected", [[], ["Kansanshi", "Kansanshi"], ["Unknown"]])
def test_invalid_selections_rejected(projects, selected):
    with pytest.raises(ValueError):
        prepare_report(projects, selected)


def test_empty_and_oversized_title_rejected(projects):
    for title in ["  ", "X" * 111]:
        with pytest.raises(ValueError):
            prepare_report(projects, ["Lumwana"], report_title=title)


def test_oversized_notes_rejected(projects):
    with pytest.raises(ValueError):
        prepare_report(projects, ["Lumwana"], analyst_notes="a" * 1201)


def test_missing_claim_provenance_refused(projects):
    model = dict(projects)
    project = dict(projects["Lumwana"])
    claims = list(project["claims"])
    claims[0] = replace(claims[0], excerpt="")
    project["claims"] = claims
    model["Lumwana"] = project
    with pytest.raises(ValueError, match="provenance"):
        prepare_report(model, ["Lumwana"])


def test_one_project_pdf_generation(projects):
    pdf = generate_project_report_pdf(
        projects, ["Lumwana"], generated_on=date(2026, 11, 19)
    )
    assert pdf.startswith(b"%PDF-")
    assert b"%%EOF" in pdf[-200:]
    assert len(pdf) > 3000


def test_three_project_pdf_generation_with_escaped_notes(projects):
    pdf = generate_project_report_pdf(
        projects, list(projects), generated_on=date(2026, 11, 19),
        analyst_notes="<b>My idea</b> & tradeoff",
    )
    assert pdf.startswith(b"%PDF-")
    assert len(pdf) > 5000


def test_snapshot_label_not_misleading():
    assert SNAPSHOT_DATE == "19 November 2026"
