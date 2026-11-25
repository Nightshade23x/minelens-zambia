"""Offline Project Intelligence tests (no network, Streamlit, Ollama or local data)."""
from dataclasses import dataclass

from app.project_intelligence import (
    USGS_SOURCE_URL,
    build_catalog,
    catalog_table_rows,
    distinct_catalog_values,
    filter_catalog,
    filtered_catalog_csv,
    profile_markdown,
)

CENTROIDS = [
    {"province": "North-Western", "district": "Solwezi", "lat": -12.2, "lon": 26.4},
    {"province": "Copperbelt", "district": "Kitwe", "lat": -12.8, "lon": 28.2},
]


def facility(name="Kansanshi Mine", location="Solwezi, North-Western Province"):
    return {
        "usgs_facility_id": "ZMB0042", "facility_name": name,
        "province": "North-Western", "location_description": location,
        "major_operating_companies": ["Kansanshi Mining plc"],
        "equity_owners": [{"name": "Example Shareholder", "share_percent": 25}],
        "commodities": ["Copper", "Gold"],
        "feature_types": ["Mines and Quarries"],
        "facility_statuses": ["Assumed active"],
        "sources": ["https://example.org/facility"],
        "publication_year": 2024,
        "products": [
            {"commodity": "Copper", "global_entry": 1,
             "annual_production_capacity": 180000, "capacity_unit": "metric tons",
             "shared_capacity_entries": [1, 2], "type": "mine"},
            {"commodity": "Copper", "global_entry": 2,
             "annual_production_capacity": 180000, "capacity_unit": "metric tons",
             "shared_capacity_entries": [1, 2], "type": "mine"},
        ],
    }


@dataclass(frozen=True)
class Claim:
    kind: str = "capex"
    label: str = "Reported CapEx"
    value: str = "approximately $1.25 billion"
    qualifier: str = "approximately"
    source_title: str = "Country compact"
    document: str = "2026.pdf"
    pages: str = "8"
    source_url: str = "https://example.org/compact.pdf"
    excerpt: str = "Kansanshi mine approximately $1.25 billion"


def projects():
    return {
        "Kansanshi": {"developer": "First Quantum Minerals", "commodity": "Copper", "claims": [Claim()]},
        "Mingomba": {"developer": "KoBold Metals", "commodity": "Copper", "claims": [Claim(value="expected $2 billion")]},
    }


def catalog():
    return build_catalog([facility()], CENTROIDS, projects())


def test_builds_separate_usgs_and_project_records():
    entries = catalog()
    assert len(entries) == 3
    assert sum(x["kind"] == "USGS facility" for x in entries) == 1
    assert {x["id"] for x in entries} == {"USGS:ZMB0042:0", "PROJECT:Kansanshi", "PROJECT:Mingomba"}


def test_does_not_guess_project_location_from_similarly_named_facility():
    record = next(x for x in catalog() if x["id"] == "PROJECT:Kansanshi")
    assert record["province"] == ""
    assert record["district"] == ""
    assert record["map_lat"] is None


def test_facility_is_only_mapped_to_district_centroid():
    record = next(x for x in catalog() if x["kind"] == "USGS facility")
    assert record["district"] == "Solwezi"
    assert record["map_lat"] == -12.2
    assert "district centroid" in record["coordinate_basis"]


def test_province_mismatch_does_not_get_coordinates():
    item = build_catalog([facility(location="Kitwe")], CENTROIDS)[0]
    assert item["map_lat"] is None
    assert item["district"] == ""


def test_source_url_and_supporting_links_preserved():
    item = build_catalog([facility()], CENTROIDS)[0]
    assert item["source_url"] == USGS_SOURCE_URL
    assert item["supporting_urls"] == ["https://example.org/facility"]


def test_project_claim_evidence_preserved():
    item = next(x for x in catalog() if x["id"] == "PROJECT:Kansanshi")
    assert item["claims"][0]["pages"] == "8"
    assert item["claims"][0]["qualifier"] == "approximately"
    assert "1.25 billion" in item["claims"][0]["excerpt"]


def test_capacity_uses_existing_deduplication():
    item = build_catalog([facility()], CENTROIDS)[0]
    assert len(item["capacity_records"]) == 1
    assert item["capacity_records"][0]["capacity"] == 180000


def test_finds_both_record_types_by_project_name():
    result = filter_catalog(catalog(), query="Kansanshi")
    assert len(result) == 2
    assert {x["kind"] for x in result} == {"USGS facility", "Verified project evidence"}


def test_filters_operator_commodity_and_province():
    items = catalog()
    assert len(filter_catalog(items, query="Kansanshi Mining")) == 1
    assert len(filter_catalog(items, commodity="Gold")) == 1
    assert len(filter_catalog(items, province="North-Western")) == 1
    assert len(filter_catalog(items, commodity="Tin")) == 0


def test_kind_filter_preserves_project_facility_distinction():
    result = filter_catalog(catalog(), query="Kansanshi", kind="USGS facility")
    assert len(result) == 1
    assert result[0]["kind"] == "USGS facility"


def test_facets_are_sorted_and_ignore_unreported_province():
    assert distinct_catalog_values(catalog(), "province") == ["North-Western"]
    assert distinct_catalog_values(catalog(), "commodities") == ["Copper", "Gold"]


def test_no_input_and_owners_does_not_crash():
    item = build_catalog([{"facility_name": "Unknown"}], CENTROIDS)[0]
    assert item["operator"] == []
    assert item["owners"] == []
    assert item["district"] == ""


def test_profile_markdown_retains_caveats_and_sources():
    facility_row = next(x for x in catalog() if x["kind"] == "USGS facility")
    doc = profile_markdown(facility_row)
    assert "NOT verified live facts" in doc
    assert "shared rows" in doc
    assert "https://doi.org/10.5066/P1KEQASH" in doc
    project_row = next(x for x in catalog() if x["id"] == "PROJECT:Kansanshi")
    project_doc = profile_markdown(project_row)
    assert "2026.pdf" in project_doc
    assert "Evidence excerpt:" in project_doc


def test_csv_and_table():
    items = catalog()
    table = catalog_table_rows(items)
    assert len(table) == len(items)
    csv = filtered_catalog_csv(items)
    assert "Record type" in csv
    assert "Kansanshi Mine" in csv
