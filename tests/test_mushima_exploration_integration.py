"""Real-asset and routing regression tests for Mushima North Phase 4.

Requires the Phase 4 ingestion dataset already generated under data/processed.
"""

from app.mushima_exploration import (
    SOURCE_ID,
    answer_mushima,
    is_mushima_query,
    query_mushima,
)
from app.citation_validation import validate_citation_integrity
from app.exploration_search import has_exploration_intent


def _wrap(records):
    return [{"source_id": f"S{i}", "record": row} for i, row in enumerate(records, start=1)]


def test_project_and_hole_routes_but_not_kabwe():
    assert is_mushima_query("Mushima North silver assay grades")
    assert is_mushima_query("highest copper in 26TMNRC-076")
    assert not is_mushima_query("Which KBDD09 hole has the highest zinc grade?")
    assert has_exploration_intent("Mushima North Phase 4 silver intervals")


def test_real_data_has_eight_holes_and_eighteen_intervals():
    result = query_mushima("List all Mushima North drill holes", top_k=20)
    assert result["intersection_record_count"] == 18
    assert len(result["results"]) == 8
    assert len({row["hole_id"] for row in result["results"]}) == 8


def test_explicit_hole_retains_nested_interval_without_other_holes():
    result = query_mushima("Show Mushima North intervals for 26TMNRC-078", top_k=20)
    assert result["results"]
    assert {r["hole_id"] for r in result["results"]} == {"26TMNRC-078"}
    assert any(r["interval_m"] == 70 and r["ag_gpt"] == 31 for r in result["results"])


def test_highest_silver_interval_is_a_reported_interval():
    question = "Which Mushima North hole has the highest silver interval grade?"
    result = query_mushima(question)
    best = result["results"][0]
    assert best["ag_gpt"] == max(r["ag_gpt"] for r in query_mushima("Mushima North intervals", 50)["results"])
    answer = answer_mushima(question, _wrap(result["results"]))
    assert best["hole_id"] in answer["answer"]
    assert "interval grade" in answer["answer"]
    assert "[S1]" in answer["answer"]
    assert validate_citation_integrity(answer)["valid"]


def test_individual_peaks_not_mixed_with_interval_averages():
    question = "What was the highest individual copper assay at Mushima North?"
    result = query_mushima(question)
    assert result["intent"] == "highest_individual_assay"
    best = result["results"][0]
    assert best["record_type"] == "exploration_drill_hole"
    assert best["reported_peak_individual_assays"]["cu_pct"] == 1.08
    answer = answer_mushima(question, _wrap(result["results"]))
    assert "individual" in answer["answer"]
    assert "1.08" in answer["answer"]


def test_unknown_hole_is_not_replaced_with_kabwe_or_nearby():
    result = query_mushima("What are the assays for 26TMNRC-999?")
    assert result["hole_ids"] == ["26TMNRC-999"]
    assert result["results"] == []
    answer = answer_mushima("26TMNRC-999 assays", [])
    assert answer["citations"] == []
    assert "No matching" in answer["answer"]


def test_phase5_has_no_reported_assay_results():
    result = query_mushima("Mushima North Phase 5 assay results")
    assert result["intent"] == "not_yet_reported"
    assert result["results"] == []


def test_project_company_source_metadata():
    result = query_mushima("Mushima North holes", top_k=1)
    row = result["results"][0]
    assert row["canonical_source_id"] == SOURCE_ID
    assert row["agency"] == "Tertiary Minerals plc"
    assert row["source_url"].startswith("https://")


def test_public_pipeline_source_and_answer():
    from app.router import search_mine
    from app.evidence import normalize_evidence
    from app.rag import answer_from_evidence

    question = "Which Mushima North hole had the highest silver interval grade?"
    search = search_mine(question, top_k=5)
    assert search["route"] == "exploration", search
    evidence = normalize_evidence(search_result=search, max_evidence=5)
    assert evidence
    answer = answer_from_evidence(question, evidence)
    assert answer["generation_method"] == "structured-exploration"
    assert "[S1]" in answer["answer"]
    assert validate_citation_integrity(answer)["valid"]


def test_normalized_mushima_interval_fields():
    from app.router import search_mine
    from app.evidence import normalize_evidence
    from app.rag import answer_from_evidence

    question = (
        "Which Mushima North hole had the "
        "highest silver interval grade?"
    )

    search = search_mine(question, top_k=5)
    evidence = normalize_evidence(
        search_result=search,
        max_evidence=5,
    )

    assert evidence

    row = evidence[0]["record"]

    assert row["project"] == "Mushima North"
    assert row["hole_id"] == "26TMNRC-078"
    assert row["ag_gpt"] == 84
    assert row["interval_m"] == 6
    assert row["from_m"] == 34
    assert row["to_m"] == 40

    answer = answer_from_evidence(question, evidence)

    assert "84 g/t Ag" in answer["answer"]
    assert "26TMNRC-078" in answer["answer"]
    assert validate_citation_integrity(answer)["valid"]


def test_normalized_mushima_individual_assays():
    from app.router import search_mine
    from app.evidence import normalize_evidence
    from app.rag import answer_from_evidence

    question = (
        "What was the highest individual "
        "copper assay at Mushima North?"
    )

    search = search_mine(question, top_k=5)
    evidence = normalize_evidence(
        search_result=search,
        max_evidence=5,
    )

    assert evidence

    row = evidence[0]["record"]

    assert row["record_type"] == "exploration_drill_hole"
    assert row["reported_peak_individual_assays"]["cu_pct"] == 1.08

    answer = answer_from_evidence(question, evidence)

    assert "1.08" in answer["answer"]
    assert "26TMNRC-078" in answer["answer"]
    assert "individual" in answer["answer"].lower()
    assert validate_citation_integrity(answer)["valid"]
