import app.reliability_gate as gate


QUESTION = "What is the estimated CapEx for Lumwana?"

EVIDENCE = [{
    "source_id": "S1",
    "document": "report.pdf",
    "text": "Lumwana mine CapEx $2 billion.",
}]

ANSWER = {
    "answer": "Lumwana costs $2 billion [S1].",
    "citations": ["S1"],
}


def setup_checks(
    monkeypatch,
    *,
    citation_valid=True,
    factual_checked=True,
    factual_supported=True,
    warnings=None,
):
    monkeypatch.setattr(
        gate,
        "validate_citation_integrity",
        lambda result: {"valid": citation_valid},
    )

    monkeypatch.setattr(
        gate,
        "validate_factual_support",
        lambda **kwargs: {
            "checked": factual_checked,
            "supported": factual_supported,
            "issues": [],
        },
    )

    monkeypatch.setattr(
        gate,
        "audit_answer_reliability",
        lambda **kwargs: {
            "ok": not warnings,
            "warnings": warnings or [],
        },
    )


def assess():
    return gate.assess_answer_quality(
        question=QUESTION,
        search_result={"route": "documents"},
        evidence=EVIDENCE,
        answer_result=ANSWER,
    )


def test_all_checks_pass(monkeypatch):
    setup_checks(monkeypatch)

    result = assess()

    assert result["status"] == "checks_passed"
    assert result["issues"] == []


def test_invalid_citation_requires_review(monkeypatch):
    setup_checks(
        monkeypatch,
        citation_valid=False,
    )

    result = assess()

    assert result["status"] == "review_required"
    assert "invalid_citations" in result["issues"]


def test_unsupported_fact_requires_review(monkeypatch):
    setup_checks(
        monkeypatch,
        factual_supported=False,
    )

    result = assess()

    assert "unsupported_factual_claim" in result["issues"]


def test_unchecked_fact_requires_review(monkeypatch):
    setup_checks(
        monkeypatch,
        factual_checked=False,
        factual_supported=None,
    )

    result = assess()

    assert result["status"] == "review_required"
    assert "factual_support_not_checked" in result["issues"]


def test_audit_warning_requires_review(monkeypatch):
    setup_checks(
        monkeypatch,
        warnings=["answer_omits_distinct_estimate"],
    )

    result = assess()

    assert result["status"] == "review_required"
    assert "answer_omits_distinct_estimate" in result["issues"]


def test_no_evidence_classified_correctly():
    result = gate.assess_answer_quality(
        question=QUESTION,
        search_result={"route": "documents"},
        evidence=[],
        answer_result={
            "answer": "No evidence found.",
            "citations": [],
            "generation_method": "no-evidence",
        },
    )

    assert result["status"] == "insufficient_evidence"


def test_citation_without_evidence_requires_review():
    result = gate.assess_answer_quality(
        question=QUESTION,
        search_result={"route": "documents"},
        evidence=[],
        answer_result={
            "answer": "Lumwana costs $2 billion [S1].",
            "citations": ["S1"],
        },
    )

    assert result["status"] == "review_required"
