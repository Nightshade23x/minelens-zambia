from app.router import search_mine
from app.evidence import normalize_evidence
from app.facility_answers import answer_facility_result
from app.mining_statistics import answer_statistics_result
from app.rag import answer_from_evidence


def test_missing_production_year():
    question = "What was Zambia's copper production in 2099?"
    result = search_mine(question)

    assert result["route"] == "mining_statistics"
    assert result["results"] == []
    assert result["years"] == [2099]

    answer = answer_statistics_result(result)
    assert "822,824" not in answer["answer"]
    assert answer["citations"] == []


def test_existing_production_year():
    result = search_mine(
        "What was Zambia's copper production in 2024?"
    )
    assert result["results"]
    assert all(
        record["year"] == 2024
        for record in result["results"]
    )


def test_unknown_facility_name():
    question = "Who operates the imaginary Copper Moon Mine?"
    result = search_mine(question)

    assert result["route"] == "facilities"
    assert result["results"] == []

    answer = answer_facility_result(question, result)
    assert answer["citations"] == []
    assert "No matching" in answer["answer"]


def test_existing_facility_name():
    question = "Who operates Kansanshi Mine?"
    result = search_mine(question)

    assert result["results"]
    assert (
        result["results"][0]["facility"]["facility_name"]
        == "Kansanshi Mine"
    )


def test_unknown_drill_hole():
    question = "What is the zinc assay in drill hole KBDD999?"
    result = search_mine(question)

    assert result["route"] == "exploration"
    assert result["hole_ids"] == ["KBDD999"]
    assert result["results"] == []

    evidence = normalize_evidence(
        search_result=result,
        max_evidence=3,
    )

    answer = answer_from_evidence(
        question=question,
        evidence=evidence,
    )

    assert answer["generation_method"] == "no-evidence"
    assert answer["citations"] == []


def test_existing_drill_hole():
    result = search_mine(
        "What is the zinc assay in drill hole KBDD10?"
    )

    assert result["route"] == "exploration"
    assert result["results"]
    assert all(
        record["hole_id"] == "KBDD10"
        for record in result["results"]
    )
