import pytest

from app.router import search_mine
from app.evidence import normalize_evidence
from app.rag import (
    answer_from_evidence,
    fee_query_type,
)


@pytest.mark.parametrize(
    "question, expected",
    [
        (
            "What is the mining licence application fee?",
            ("mining", "all"),
        ),
        (
            "What is the artisanal mining licence application fee?",
            ("mining", "artisanal"),
        ),
        (
            "What is the small-scale mining licence application fee?",
            ("mining", "small"),
        ),
        (
            "What is the large-scale mining licence application fee?",
            ("mining", "large"),
        ),
    ],
)
def test_fee_classification(question, expected):
    assert fee_query_type(question) == expected


@pytest.mark.parametrize(
    "question",
    [
        "What is the mining licence renewal fee?",
        "What are the mining licence area charges?",
        "What is the mining licence transfer fee?",
    ],
)
def test_other_fee_types_are_not_application_fees(question):
    assert fee_query_type(question) is None


def get_fee_answer(question):
    result = search_mine(
        query=question,
        top_k=5,
    )

    assert result["route"] == "documents"

    evidence = normalize_evidence(
        search_result=result,
        max_evidence=5,
    )

    return answer_from_evidence(
        question=question,
        evidence=evidence,
    )


def test_general_mining_fee_answer():
    answer = get_fee_answer(
        "What is the mining licence application fee?"
    )

    assert answer["generation_method"] == "deterministic-fee"
    assert answer["model"] is None

    for amount in ("K1,200", "K6,000", "K64,000"):
        assert amount in answer["answer"]

    for category in ("Artisanal", "Small-scale", "Large-scale"):
        assert category in answer["answer"]

    assert answer["citations"]
    assert answer["sources"]

    assert any(
        source.get("canonical_source_id")
        == "mining_fees_area_charges_2024"
        for source in answer["sources"]
    )

    for source_id in answer["citations"]:
        assert f"[{source_id}]" in answer["answer"]


@pytest.mark.parametrize(
    "question, expected_amount",
    [
        (
            "What is the artisanal mining licence application fee?",
            "K1,200",
        ),
        (
            "What is the small-scale mining licence application fee?",
            "K6,000",
        ),
        (
            "What is the large-scale mining licence application fee?",
            "K64,000",
        ),
    ],
)
def test_specific_mining_fee_answers(question, expected_amount):
    answer = get_fee_answer(question)

    assert answer["generation_method"] == "deterministic-fee"
    assert answer["model"] is None
    assert expected_amount in answer["answer"]
    assert answer["citations"]
    assert answer["sources"]
