import app.reliability_gate as gate

from app.project_estimate_support import (
    validate_project_estimate_support,
)


QUESTION = "What is the estimated CapEx for Lumwana?"

EVIDENCE = [
    {
        "source_id": "S1",
        "document": "compact.pdf",
        "pages": "8",
        "text": (
            "Lumwana mine expansion estimated at $2 billion CapEx."
        ),
    },
    {
        "source_id": "S2",
        "document": "other.pdf",
        "pages": "4",
        "text": (
            "Lumwana mine expansion investment ~$2.0B."
        ),
    },
]


def make_answer(
    text="Lumwana has approximately $2 billion CapEx [S1] [S2].",
    citations=None,
):
    return {
        "answer": text,
        "citations": (
            ["S1", "S2"] if citations is None else citations
        ),
        "sources": [],
    }


def test_correct_project_estimate_supported():
    result = validate_project_estimate_support(
        QUESTION, EVIDENCE, make_answer()
    )

    assert result["checked"] is True
    assert result["supported"] is True


def test_wrong_amount_rejected():
    result = validate_project_estimate_support(
        QUESTION,
        EVIDENCE,
        make_answer(
            "Lumwana has approximately $3 billion CapEx [S1] [S2]."
        ),
    )

    assert result["supported"] is False
    assert "project_estimate_amount_mismatch" in result["issues"]


def test_missing_project_rejected():
    result = validate_project_estimate_support(
        QUESTION,
        EVIDENCE,
        make_answer(
            "The expansion has approximately $2 billion CapEx "
            "[S1] [S2]."
        ),
    )

    assert result["supported"] is False


def test_missing_supporting_citation_rejected():
    result = validate_project_estimate_support(
        QUESTION,
        EVIDENCE,
        make_answer(citations=["S1"]),
    )

    assert result["supported"] is False


def test_approximation_qualifier_required():
    result = validate_project_estimate_support(
        QUESTION,
        EVIDENCE,
        make_answer("Lumwana has $2 billion CapEx [S1] [S2]."),
    )

    assert result["supported"] is False
    assert "approximate_estimate_not_qualified" in result["issues"]


def test_conflicting_amounts_remain_unchecked():
    conflicting = [
        EVIDENCE[0],
        dict(
            EVIDENCE[1],
            text="Lumwana mine expansion investment $3 billion.",
        ),
    ]

    result = validate_project_estimate_support(
        QUESTION, conflicting, make_answer()
    )

    assert result["checked"] is False
    assert result["supported"] is None


def test_strict_inequality_remains_unchecked():
    evidence = [
        EVIDENCE[0],
        dict(
            EVIDENCE[1],
            text="Lumwana mine expansion investment >$2.0B.",
        ),
    ]

    result = validate_project_estimate_support(
        QUESTION, evidence, make_answer()
    )

    assert result["checked"] is False


def test_reliability_gate_uses_specialized_support(monkeypatch):
    monkeypatch.setattr(
        gate,
        "validate_factual_support",
        lambda **kwargs: {
            "checked": False,
            "supported": None,
            "issues": [],
        },
    )

    monkeypatch.setattr(
        gate,
        "validate_citation_integrity",
        lambda answer: {"valid": True},
    )

    monkeypatch.setattr(
        gate,
        "audit_answer_reliability",
        lambda **kwargs: {
            "ok": True,
            "warnings": [],
        },
    )

    result = gate.assess_answer_quality(
        question=QUESTION,
        search_result={"route": "documents"},
        evidence=EVIDENCE,
        answer_result=make_answer(),
    )

    assert result["status"] == "checks_passed"
    assert result["factual_support"]["checked"] is True
    assert result["factual_support"]["supported"] is True
