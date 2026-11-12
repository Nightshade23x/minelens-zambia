import pytest

from app.router import search_mine
from app.evidence import normalize_evidence
from app.document_answer_selection import (
    select_document_answer_evidence,
)
from app.project_estimates import analyze_project_estimates
from app.rag import answer_from_evidence
from app.citation_validation import validate_citation_integrity


@pytest.mark.parametrize(
    "project,question,amount,expected_text",
    [
        (
            "Lumwana",
            "What is the estimated capital expenditure for Lumwana?",
            2_000_000_000,
            "$2 billion",
        ),
        (
            "Kansanshi",
            "What is the estimated capital expenditure for Kansanshi?",
            1_250_000_000,
            "$1.25 billion",
        ),
    ],
)
def test_live_project_estimate_pipeline(
    project, question, amount, expected_text, monkeypatch
):
    import app.rag as rag

    def fail_ollama(**kwargs):
        pytest.fail(
            "A supported project estimate should not require Ollama."
        )

    monkeypatch.setattr(
        rag, "generate_ollama_answer", fail_ollama
    )

    result = search_mine(question, top_k=5)

    assert result["route"] == "documents"

    evidence = normalize_evidence(
        search_result=result,
        max_evidence=5,
    )

    evidence = select_document_answer_evidence(
        question=question,
        evidence=evidence,
    )

    analysis = analyze_project_estimates(project, evidence)

    assert len(analysis["estimates"]) >= 2

    # No retrieved estimate may belong to another project's budget.
    assert all(
        item["amount_usd"] == amount
        for item in analysis["estimates"]
    ), analysis

    answer = answer_from_evidence(
        question=question,
        evidence=evidence,
    )

    assert answer["generation_method"] == (
        "deterministic-project-estimate"
    )
    assert expected_text in answer["answer"]
    assert len(answer["citations"]) >= 2

    integrity = validate_citation_integrity(answer)

    assert integrity["valid"], integrity

    if project == "Lumwana":
        assert "$1.1 billion" not in answer["answer"]
