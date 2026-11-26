"""Offline tests for single-record Project Intelligence PDFs (no Ollama/data/network)."""
from __future__ import annotations

from datetime import date

import pytest

from app.project_intelligence_report import (
    friendly_qualifier,
    generate_intelligence_profile_pdf,
    prepare_intelligence_profile,
)


def facility():
    return {
        "id": "USGS:ZMB0015:0", "kind": "USGS facility",
        "name": "Baluba Center (Underground) Mine", "record_id": "ZMB0015",
        "operator": ["CNMC Luanshya Copper Mines plc"],
        "commodities": ["Copper", "Cobalt"], "owners": ["Owner A (80%)", "Owner B (20%)"],
        "feature_types": ["Mines and Quarries"], "status": ["Inactive"],
        "province": "Copperbelt", "district": "Luanshya",
        "location_description": "Luanshya, Copperbelt Province",
        "map_lat": -13.0, "map_lon": 28.0, "coordinate_basis": "district centroid",
        "capacity_records": [{
            "commodity": "Copper", "capacity": 10000, "capacity_unit": "Metric tons",
            "form": "Concentrates", "capacity_notes": "Copper metal contained in concentrate.",
        }],
        "claims": [], "source_title": "USGS Zambia Minerals Yearbook 2024 facilities",
        "source_url": "https://doi.org/10.5066/P1KEQASH",
        "supporting_urls": ["https://example.org/2023-report.pdf"],
        "publication_year": 2024,
        "source_scope": "USGS source-reported facility facts, NOT verified live status.",
    }


def verified_project():
    return {
        "id": "PROJECT:Mingomba", "kind": "Verified project evidence",
        "name": "Mingomba", "record_id": "", "operator": ["KoBold Metals"],
        "commodities": ["Copper"], "owners": [], "feature_types": [], "status": [],
        "province": "", "district": "", "location_description": "",
        "map_lat": None, "map_lon": None, "publication_year": "2024 / 2026",
        "capacity_records": [], "claims": [
            {
                "project": "Mingomba", "kind": "capex", "label": "Reported CapEx",
                "value": "expected $2 billion", "qualifier": "expected",
                "source_title": "Zambia Metals and Minerals Country Compact",
                "document": "zambia_metals_minerals_country_compact_2026.pdf",
                "pages": "8", "excerpt": "Mingomba property with an expected CapEx of $2 billion",
                "source_url": "https://example.org/compact.pdf", "source_date": "2026",
            },
            {
                "project": "Mingomba", "kind": "capex", "label": "Reported CapEx",
                "value": ">$2.0B", "qualifier": "lower_bound_strict",
                "source_title": "Zambia Metals and Minerals Country Compact",
                "document": "zambia_metals_minerals_country_compact_2026.pdf",
                "pages": "25-26", "excerpt": "300ktpa production potential >$2.0B",
                "source_url": "", "source_date": "2026",
            },
        ],
        "source_title": "MineLens verified project comparison evidence",
        "source_url": "", "supporting_urls": [],
        "source_scope": "Source-backed estimates, not current status.",
    }


def test_facility_profile_preserves_capacity_and_history_caveat():
    prepared = prepare_intelligence_profile(facility())
    assert prepared["kind"] == "USGS facility"
    assert len(prepared["capacities"]) == 1
    assert not prepared["claims"]
    assert "NOT verified" in prepared["record"]["source_scope"]
    assert prepared["record"]["map_lat"] == -13.0  # PDF must *not* print site coords


def test_verified_project_keeps_strict_bound_distinct():
    p = prepare_intelligence_profile(verified_project())
    assert len(p["claims"]) == 2
    assert p["claims"][1]["value"] == ">$2.0B"
    assert friendly_qualifier(p["claims"][1]["qualifier"]) == "Greater than (strict lower bound)"
    assert not p["capacities"]


@pytest.mark.parametrize("bad", ["", "x"*111])
def test_bad_title_refused(bad):
    with pytest.raises(ValueError, match="title"):
        prepare_intelligence_profile(facility(), report_title=bad)


def test_notes_length_guard():
    with pytest.raises(ValueError, match="notes"):
        prepare_intelligence_profile(facility(), analyst_notes="n"*1201)


def test_wrong_source_type_fails_without_merging():
    row = facility()
    row["id"] = "PROJECT:Baluba"
    with pytest.raises(ValueError):
        prepare_intelligence_profile(row)


def test_project_requires_verifiable_cited_passage():
    project = verified_project()
    project["claims"][0]["excerpt"] = ""
    with pytest.raises(ValueError, match="provenance"):
        prepare_intelligence_profile(project)


def test_project_cannot_claim_another_project():
    project = verified_project()
    project["claims"][0]["project"] = "Kansanshi"
    with pytest.raises(ValueError, match="another project"):
        prepare_intelligence_profile(project)


def test_facility_requires_source():
    row = facility()
    row["source_url"] = "javascript:alert(1)"
    with pytest.raises(ValueError, match="source URL"):
        prepare_intelligence_profile(row)


def test_does_not_mix_facility_claim_types():
    row = facility()
    row["claims"] = verified_project()["claims"]
    with pytest.raises(ValueError):
        prepare_intelligence_profile(row)


def test_does_not_mix_project_capacity_types():
    project = verified_project()
    project["capacity_records"] = facility()["capacity_records"]
    with pytest.raises(ValueError):
        prepare_intelligence_profile(project)


@pytest.mark.parametrize("example", [facility, verified_project])
def test_pdf_renders_with_source_notes(example):
    pdf = generate_intelligence_profile_pdf(
        example(), generated_on=date(2026, 11, 26),
        analyst_notes="Unverified note: <b>do not infer</b> & keep sources.",
    )
    assert pdf.startswith(b"%PDF-")
    assert b"%%EOF" in pdf[-256:]
    assert len(pdf) > 2800


def test_pdf_is_source_backed_and_preserves_source_specific_wording():
    fitz = pytest.importorskip("fitz")
    project_pdf = generate_intelligence_profile_pdf(verified_project())
    project_text = "\n".join(p.get_text() for p in fitz.open(stream=project_pdf, filetype="pdf"))
    assert "Greater than (strict lower bound)" in project_text
    assert "expected $2 billion" in project_text
    assert "25-26" in project_text
    assert "Source register" in project_text
    facility_pdf = generate_intelligence_profile_pdf(facility())
    facility_text = "\n".join(p.get_text() for p in fitz.open(stream=facility_pdf, filetype="pdf"))
    assert "Baluba Center" in facility_text
    assert "10000" in facility_text
    assert "district" in facility_text.lower()
    assert "Source register" in facility_text
