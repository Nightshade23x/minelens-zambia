"""Optional visual-layout regression tests (PyMuPDF not required for core operation)."""
from datetime import date

import pytest

from app.project_comparison_data import load_comparison
from app.project_intelligence_report import generate_intelligence_profile_pdf
from app.research_report import generate_project_report_pdf


def test_comparison_heading_moves_with_its_table():
    fitz = pytest.importorskip("fitz")
    pdf = generate_project_report_pdf(
        load_comparison(), ["Kansanshi", "Lumwana", "Mingomba"],
        generated_on=date(2026, 11, 26),
    )
    pages = [page.get_text() for page in fitz.open(stream=pdf, filetype="pdf")]
    heading_pages = [i for i, body in enumerate(pages) if "Project detail and historical output" in body]
    assert len(heading_pages) == 1
    heading_page = heading_pages[0]
    # The section must not be orphaned at the end of page 1.
    assert "Developer / commodity" in pages[heading_page]
    assert "Kansanshi" in pages[heading_page]


def test_short_facility_report_does_not_have_an_orphan_limitations_page():
    fitz = pytest.importorskip("fitz")
    # Realistic Baluba profile, matching the exported field lengths and four links.
    facility = {
        "id": "USGS:ZMB0015:0", "kind": "USGS facility", "name": "Baluba Center (Underground) Mine",
        "record_id": "ZMB0015", "operator": ["CNMC Luanshya Copper Mines plc"],
        "commodities": ["Copper", "Cobalt"],
        "owners": ["China Nonferrous Metal Mining (Group) Corp., Ltd. (80.0%)",
                   "ZCCM Investments Holdings plc (ZCCM-IH) (20.0%)"],
        "feature_types": ["Mines and Quarries"], "status": ["Inactive"],
        "province": "Copperbelt", "district": "Luanshya", "location_description": "Luanshya, Copperbelt Province",
        "map_lat": -13., "map_lon": 28., "publication_year": 2024,
        "capacity_records": [{"commodity": "Copper", "capacity": 10000, "capacity_unit": "Metric tons",
                              "form": "Concentrates", "capacity_notes": "Copper metal contained in concentrate."}],
        "claims": [], "source_title": "U.S. Geological Survey — Zambia Minerals Yearbook 2024 facilities",
        "source_url": "https://doi.org/10.5066/P1KEQASH",
        "supporting_urls": ["https://example.com/source1", "https://example.com/source2", "https://example.com/source3"],
        "source_scope": "USGS source-reported facility information. Historical status and capacity, NOT verified live facts.",
    }
    pdf = generate_intelligence_profile_pdf(facility, generated_on=date(2026, 11, 26))
    document = fitz.open(stream=pdf, filetype="pdf")
    assert len(document) == 1
    assert "Method and limitations" in document[0].get_text()
