import app.rag as rag

from app.citation_validation import validate_citation_integrity
from app.estimate_consistency import audit_mingomba_answer
from app.factual_support import validate_factual_support


QUESTION = (
    "What is the estimated capital expenditure "
    "for the Mingomba project?"
)

EVIDENCE = [
    {
        "source_id": "S1",
        "evidence_type": "document",
        "canonical_source_id": "country_compact",
        "document": "country_compact.pdf",
        "pages": "8",
        "text": (
            "KoBold Metals' Mingomba property "
            "(with an expected CapEx of $2 billion)."
        ),
    },
    {
        "source_id": "S2",
        "evidence_type": "document",
        "canonical_source_id": "country_compact",
        "document": "country_compact.pdf",
        "pages": "25-26",
        "text": (
            "Mingomba Copper KoBold Metals "
            "AI-driven exploration; 300ktpa "
            "production potential >$2.0B "
            "Enterprise Nickel"
        ),
    },
]


def test_generates_both_estimates():
    result = rag._mingomba_comparison_from_evidence(
        QUESTION, EVIDENCE
    )

    assert result is not None
    assert result["generation_method"] == (
        "deterministic-estimate-comparison"
    )
    assert result["model"] is None
    assert "$2 billion [S1]" in result["answer"]
    assert ">$2.0B [S2]" in result["answer"]
    assert result["citations"] == ["S1", "S2"]


def test_comparison_has_valid_citations():
    result = rag._mingomba_comparison_from_evidence(
        QUESTION, EVIDENCE
    )

    assert validate_citation_integrity(result)["valid"]


def test_comparison_has_factual_support():
    result = rag._mingomba_comparison_from_evidence(
        QUESTION, EVIDENCE
    )

    support = validate_factual_support(
        question=QUESTION,
        search_result={
            "route": "documents",
            "results": [{"record_type": "document"}],
        },
        answer_result=result,
        evidence=EVIDENCE,
    )

    assert support["checked"]
    assert support["supported"] is True, support


def test_no_relevant_estimate_is_omitted():
    result = rag._mingomba_comparison_from_evidence(
        QUESTION, EVIDENCE
    )

    audit = audit_mingomba_answer(
        EVIDENCE, result["answer"]
    )

    assert audit["complete_comparison"] is True


def test_single_estimate_does_not_force_comparison():
    assert rag._mingomba_comparison_from_evidence(
        QUESTION, EVIDENCE[:1]
    ) is None


def test_unrelated_question_not_intercepted():
    assert rag._mingomba_comparison_from_evidence(
        "Who operates Kansanshi Mine?",
        EVIDENCE,
    ) is None


def test_public_answer_bypasses_ollama(monkeypatch):
    def fail_if_called(**kwargs):
        raise AssertionError("Ollama should not be needed.")

    monkeypatch.setattr(
        rag,
        "generate_ollama_answer",
        fail_if_called,
    )

    result = rag.answer_from_evidence(
        question=QUESTION,
        evidence=EVIDENCE,
    )

    assert result["generation_method"] == (
        "deterministic-estimate-comparison"
    )
    assert result["citations"] == ["S1", "S2"]
