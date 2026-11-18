"""Offline tests: no network, Ollama, Streamlit, or mining data required."""
from pathlib import Path

import pytest

from app.mining_map_data import (
    canonical_name, circle_radius, district_summary, distinct_values,
    load_admin_centroids, map_facilities, map_licence_records, matches_filters,
)


CENTROIDS = [
    {"province": "Copperbelt", "district": "Kitwe", "lat": -12.8, "lon": 28.2},
    {"province": "Copperbelt", "district": "Chingola", "lat": -12.5, "lon": 27.8},
    {"province": "North-Western", "district": "Solwezi", "lat": -12.2, "lon": 26.4},
]


def facility(name="Kansanshi Smelter", location="Solwezi, North-Western Province", province="North-Western"):
    return {
        "usgs_facility_id": "ZMB0042", "facility_name": name,
        "location_description": location, "province": province,
        "commodities": ["Copper", "Sulfur"],
        "major_operating_companies": ["Kansanshi Mining plc"],
        "facility_statuses": ["Assumed active"],
        "feature_types": ["Mineral Processing Plant"],
        "publication_year": 2024,
        "sources": ["https://example.org/facility"],
    }


def test_admin_loader_uses_real_columns_and_level_two(tmp_path):
    csv_path = tmp_path / "admin.csv"
    csv_path.write_text(
        "# source comment\nlevel,name.en,parent.name.en,geo.lat,geo.lon\n"
        "1,Copperbelt,Zambia,-12.1,28.0\n"
        "2,Kitwe,Copperbelt,-12.8,28.2\n"
        "2,Kitwe,Copperbelt,-12.8,28.2\n"
        "2,Nowhere,Copperbelt,0,0\n",
        encoding="utf-8",
    )
    assert load_admin_centroids(csv_path) == [{
        "province": "Copperbelt", "district": "Kitwe",
        "lat": -12.8, "lon": 28.2,
        "coordinate_basis": "district_centroid",
    }]


def test_facility_maps_unambiguous_district():
    row = map_facilities([facility()], CENTROIDS)[0]
    assert (row["district"], row["lat"], row["lon"]) == ("Solwezi", -12.2, 26.4)
    assert "district centroid" in row["coordinate_basis"]


def test_ambiguous_two_districts_not_pinned():
    row = map_facilities([facility(location="Near Chingola and Kitwe", province="Copperbelt")], CENTROIDS)[0]
    assert row["lat"] is None
    assert row["district"] == ""
    assert row["mapping_note"] == "Ambiguous district references"


def test_province_mismatch_not_geocoded():
    row = map_facilities([facility(location="Kitwe", province="North-Western")], CENTROIDS)[0]
    assert row["lat"] is None


def test_province_only_not_pinned():
    row = map_facilities([facility(location="Copperbelt Province", province="Copperbelt")], CENTROIDS)[0]
    assert row["lat"] is None


def test_province_hyphen_alias():
    row = map_facilities([facility(province="Northwestern Province")], CENTROIDS)[0]
    assert row["district"] == "Solwezi"


def test_facility_source_metadata_preserved():
    row = map_facilities([facility()], CENTROIDS)[0]
    assert row["source_url"] == "https://example.org/facility"
    assert row["reported_statuses"] == ["Assumed active"]


def test_licence_multiple_districts_one_mention_each():
    record = {
        "licence_code": "123-HQ-LML", "applicant": "Example Company",
        "province": "Copperbelt", "decision": "Approved", "commodities": ["Copper"],
    }
    rows = map_licence_records([record], CENTROIDS, lambda _: ["Kitwe", "Chingola", "Kitwe"])
    assert len(rows) == 2
    assert {x["district"] for x in rows} == {"Kitwe", "Chingola"}
    assert {x["record_index"] for x in rows} == {0}
    assert all("not licensed-area" in row["coordinate_basis"] for row in rows)


def test_licence_unrecognized_district_is_not_mapped():
    record = {"province": "Copperbelt", "licence_code": "X"}
    assert map_licence_records([record], CENTROIDS, lambda _: ["Unknown"]) == []


def test_facility_filters_commodity_status_and_operator():
    rows = map_facilities([facility()], CENTROIDS)
    assert len(matches_filters(rows, commodity="Copper", status="Assumed active", search="kansanshi")) == 1
    assert len(matches_filters(rows, commodity="Gold")) == 0
    assert len(matches_filters(rows, search="different company")) == 0


def test_district_aggregation_keeps_counts_separate():
    mapped = map_facilities([facility(), facility(name="Second facility")], CENTROIDS)
    licences = map_licence_records([{"province": "North-Western", "licence_code": "X"}], CENTROIDS, lambda _: ["Solwezi"])
    points = district_summary(mapped, licences)
    assert len(points) == 1
    assert (points[0]["facilities"], points[0]["licence_mentions"]) == (2, 1)


def test_mappings_ignore_unmapped_for_map_but_keep_tables():
    mapped = map_facilities([facility(location="unknown", province="North-Western")], CENTROIDS)
    assert len(mapped) == 1
    assert district_summary(mapped, []) == []


def test_status_filter_on_licensing_decision():
    rows = [{"decision": "Approved", "province": "Copperbelt", "commodities": ["Copper"]}]
    assert len(matches_filters(rows, status="Approved", status_key="decision")) == 1
    assert not matches_filters(rows, status="Rejected", status_key="decision")


def test_distinct_values_and_canonical_names():
    assert canonical_name("North-Western Province") == canonical_name("Northwestern")
    assert distinct_values([{"commodities": ["Copper", "Zinc"]}, {"commodities": ["Copper"]}], "commodities") == ["Copper", "Zinc"]


def test_circle_radius_scales_and_caps():
    assert circle_radius(4) > circle_radius(1)
    assert circle_radius(10000) <= 75000
    with pytest.raises(ValueError):
        circle_radius(-1)
