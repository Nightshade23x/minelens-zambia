"""Muntanga North retrieval, provenance and existing pipeline regression tests."""

import pytest

from app.muntanga_exploration import (
    SOURCE_ID,
    answer_muntanga,
    is_muntanga_query,
    query_muntanga,
)


def _wrap(raw_rows):
    return [{"source_id": f"S{index}", "record": row} for index, row in enumerate(raw_rows, 1)]


def test_project_and_drill_hole_detection_is_narrow():
    assert is_muntanga_query("Muntanga North uranium drill results")
    assert is_muntanga_query("What is the eU3O8 grade at MNDTH2421?")
    assert not is_muntanga_query("Mushima North silver grade 26TMNRC-078")
    assert not is_muntanga_query("Kabwe drill hole KBDD009")
    assert not is_muntanga_query("Namakande part of Muntanga Uranium Project")


def test_84_holes_29_intercepts_and_source():
    holes = query_muntanga("List Muntanga North drill holes", top_k=100)
    grades = query_muntanga("Muntanga North radiometric intercepts", top_k=100)
    assert len(holes["results"]) == 84
    assert len(grades["results"]) == 29
    assert len({r["hole_id"] for r in holes["results"]}) == 84
    assert all(r["canonical_source_id"] == SOURCE_ID for r in grades["results"])


def test_highest_radiometric_grade_is_not_lab_assay():
    question = "What is the highest uranium interval grade at Muntanga North?"
    search = query_muntanga(question, top_k=5)
    assert search["intent"] == "highest_radiometric_grade"
    assert search["results"][0]["hole_id"] == "MNDTH2421"
    assert search["results"][0]["eu3o8_ppm"] == 380
    result = answer_muntanga(question, _wrap(search["results"]))
    assert "380 ppm eU3O8" in result["answer"]
    assert "5.18 m" in result["answer"]
    assert "NOT laboratory assays" in result["answer"]
    assert "[S1]" in result["answer"]
    assert result["sources"][0]["canonical_source_id"] == SOURCE_ID


def test_explicit_hole_returns_only_its_intervals():
    rows = query_muntanga("Show all radiometric intercepts for MNDTH2456", top_k=20)["results"]
    assert len(rows) == 2
    assert {r["hole_id"] for r in rows} == {"MNDTH2456"}
    assert {r["eu3o8_ppm"] for r in rows} == {230, 311}


def test_unknown_hole_must_not_return_nearby_records():
    search = query_muntanga("Show MNDTH9999 at Muntanga North", top_k=5)
    assert search["results"] == []
    result = answer_muntanga("Show MNDTH9999 at Muntanga North", [])
    assert result["citations"] == []
    assert "No matching" in result["answer"]
    assert "zero" in result["answer"]


def test_no_significant_intercept_is_not_zero_grade():
    question = "Which Muntanga North holes had no significant intercept?"
    search = query_muntanga(question, top_k=100)
    assert search["intent"] == "no_significant_intercepts"
    assert len(search["results"]) == 66
    assert all(r["intercept_reporting_status"] == "no_significant_intercept" for r in search["results"])
    result = answer_muntanga(question, _wrap(search["results"][:5]))
    assert "No Significant Intercept" in result["answer"]
    assert "not a measured zero" in result["answer"]


def test_ask_for_laboratory_assays_abstains():
    question = "What laboratory-confirmed assays are available at Muntanga North?"
    search = query_muntanga(question)
    assert search["results"] == []
    result = answer_muntanga(question, [])
    assert "does not establish laboratory-confirmed" in result["answer"]
    assert result["citations"] == []


def test_resources_not_inferred_from_exploration_intercepts():
    question = "What new mineral resource estimate is reported for Muntanga North?"
    search = query_muntanga(question)
    assert search["results"] == []
    assert "do not establish" in answer_muntanga(question, [])["answer"]


def test_target_comparison_respects_explicit_table1_labels():
    query = "Compare Target 5 and Target 6 intercepts at Muntanga North"
    result = query_muntanga(query, top_k=50)
    assert result["target_ids"] == [5, 6]
    assert result["results"]
    assert all(r["target_id"] in (5, 6) for r in result["results"])
    assert all(r["highlighted_in_table_1"] for r in result["results"])
    answer = answer_muntanga(query, _wrap(result["results"]))
    assert "not a complete comparison" in answer["answer"]


def test_reported_utm_coordinates_not_fabricated_lat_lon():
    question = "MNDTH2421 collar coordinates"
    search = query_muntanga(question)
    assert search["results"][0]["easting_m"] == 682462
    assert search["results"][0]["northing_m"] == 8209207
    answer = answer_muntanga(question, _wrap(search["results"]))
    assert "UTM" in answer["answer"]
    assert "682462" in answer["answer"]
    assert "8209207" in answer["answer"]
    assert "not latitude/longitude" in answer["answer"]


def test_real_search_answer_and_normalized_evidence():
    from app.router import search_mine
    from app.evidence import normalize_evidence
    from app.rag import answer_from_evidence
    from app.citation_validation import validate_citation_integrity

    question = "Which Muntanga North hole has the highest radiometric uranium interval grade?"
    search = search_mine(query=question, top_k=5)
    assert search["route"] == "exploration", search
    evidence = normalize_evidence(search_result=search, max_evidence=5)
    assert evidence
    assert evidence[0]["record"]["eu3o8_ppm"] == 380
    final = answer_from_evidence(question, evidence)
    assert final["generation_method"] == "structured-exploration"
    assert "MNDTH2421" in final["answer"]
    assert "380 ppm eU3O8" in final["answer"]
    assert "[S1]" in final["answer"]
    assert validate_citation_integrity(final)["valid"]


def test_router_isolation_for_kabwe_and_mushima():
    from app.router import search_mine
    for question in (
        "Show results for Kabwe drill hole KBDD999",
        "Mushima North drilling intervals for 26TMNRC-078",
    ):
        result = search_mine(query=question, top_k=5)
        assert result["route"] == "exploration"
        assert all(r.get("project") != "Muntanga North" for r in result.get("results", []))


def test_source_document_pages_and_metadata():
    question = "Muntanga North intervals for MNDTH2421"
    raw = query_muntanga(question)["results"]
    final = answer_muntanga(question, _wrap(raw))
    source = final["sources"][0]
    assert source["document"].endswith(".pdf")
    assert source["source_url"].startswith("https://")
    assert source["published_date"] == "2026-11-20"
    assert source["pages"] == "12"
