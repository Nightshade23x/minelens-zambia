from app.rag import (
    _critical_skills_from_evidence,
    answer_from_evidence,
)


QUESTION = (
    "what skills and expertise does Zambia need "
    "for its critical minerals industry"
)

EVIDENCE = [{
    "source_id": "S1",
    "evidence_type": "document",
    "canonical_source_id": "national_critical_minerals_strategy_2024_2028",
    "document": "zambia_national_critical_minerals_strategy_2024_2028.pdf",
    "title": "National Critical Minerals Strategy",
    "source_url": "https://example.org/National-Critical-Minerals-Strategy.pdf",
    "text": (
        "Government needs to develop the skills and expertise to: "
        "Identify and restrict areas of potential deposits for bids "
        "by viable investors; Meet the technical challenges of "
        "exploration, production, processing and refining; and "
        "Manage the sustainability of the critical minerals industry."
    ),
}]


def test_skills_answer_is_grounded_and_deterministic():
    result = answer_from_evidence(
        question=QUESTION,
        evidence=EVIDENCE,
    )

    assert result["generation_method"] == "deterministic-critical-skills"
    assert result["citations"] == ["S1"]
    assert result["sources"]

    for phrase in (
        "Identify and restrict areas of potential deposits",
        "technical challenges",
        "Manage the sustainability",
    ):
        assert phrase in result["answer"]


def test_incomplete_evidence_does_not_trigger_deterministic_answer():
    incomplete = [
        {**EVIDENCE[0], "text": "Technical skills are important."}
    ]

    assert _critical_skills_from_evidence(
        QUESTION, incomplete
    ) is None


def test_unrelated_question_does_not_trigger_skills_answer():
    assert _critical_skills_from_evidence(
        "What was Zambia's copper production in 2024?",
        EVIDENCE,
    ) is None
