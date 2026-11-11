import app.rag as rag

from app.citation_validation import validate_citation_integrity


LUMWANA = [
    {
        "source_id": "S1",
        "evidence_type": "document",
        "canonical_source_id": "compact",
        "document": "compact.pdf",
        "pages": "8",
        "text": (
            "Barrick's Lumwana mine "
            "(estimated at $2 billion CapEx)."
        ),
    },
    {
        "source_id": "S2",
        "evidence_type": "document",
        "canonical_source_id": "usgs",
        "document": "usgs.html",
        "pages": "1",
        "text": (
            "The Lumwana mine expansion project "
            "has a $2 billion capital expenditure estimate."
        ),
    },
]

KANSHANSHI = [
    {
        "source_id": "S1",
        "evidence_type": "document",
        "canonical_source_id": "compact",
        "document": "compact.pdf",
        "pages": "8",
        "text": (
            "Kansanshi mine "
            "(approximately $1.25 billion CapEx)."
        ),
    },
    {
        "source_id": "S3",
        "evidence_type": "document",
        "canonical_source_id": "compact",
        "document": "compact.pdf",
        "pages": "25-26",
        "text": (
            "Kansanshi Copper First Quantum Minerals "
            "Expansion and mine life extension ~$1.25B "
            "Lumwana Copper Barrick Gold"
        ),
    },
]

MINGOMBA = [
    {
        "source_id": "S1",
        "evidence_type": "document",
        "canonical_source_id": "compact",
        "document": "compact.pdf",
        "pages": "8",
        "text": (
            "Mingomba property "
            "(with an expected CapEx of $2 billion)."
        ),
    },
    {
        "source_id": "S2",
        "evidence_type": "document",
        "canonical_source_id": "compact",
        "document": "compact.pdf",
        "pages": "25-26",
        "text": (
            "Mingomba Copper KoBold Metals "
            "production potential >$2.0B Enterprise Nickel"
        ),
    },
]


def test_lumwana_answer():
    result = rag._consistent_project_estimate_from_evidence(
        "What is the estimated capital expenditure for Lumwana?",
        LUMWANA,
    )

    assert result is not None
    assert result["generation_method"] == (
        "deterministic-project-estimate"
    )
    assert "$2 billion" in result["answer"]
    assert result["citations"] == ["S1", "S2"]


def test_kansanshi_answer():
    result = rag._consistent_project_estimate_from_evidence(
        "What is the estimated CapEx for Kansanshi?",
        KANSHANSHI,
    )

    assert result is not None
    assert "approximately $1.25 billion" in result["answer"]
    assert "same document" in result["answer"]
    assert result["citations"] == ["S1", "S3"]


def test_citation_integrity():
    result = rag._consistent_project_estimate_from_evidence(
        "What is the capital expenditure for Lumwana?",
        LUMWANA,
    )

    assert validate_citation_integrity(result)["valid"]


def test_source_metadata_preserved():
    result = rag._consistent_project_estimate_from_evidence(
        "What is the capital expenditure for Lumwana?",
        LUMWANA,
    )

    assert result["sources"][0]["document"] == "compact.pdf"
    assert result["sources"][0]["pages"] == "8"
    assert result["sources"][1]["document"] == "usgs.html"


def test_single_estimate_not_intercepted():
    result = rag._consistent_project_estimate_from_evidence(
        "What is the capital expenditure for Lumwana?",
        LUMWANA[:1],
    )

    assert result is None


def test_conflicting_estimates_not_intercepted():
    evidence = [
        LUMWANA[0],
        dict(
            LUMWANA[1],
            text="Lumwana mine estimated at $3 billion.",
        ),
    ]

    result = rag._consistent_project_estimate_from_evidence(
        "What is the capital expenditure for Lumwana?",
        evidence,
    )

    assert result is None


def test_unknown_project_not_intercepted():
    result = rag._consistent_project_estimate_from_evidence(
        "What is the estimated CapEx for ImaginaryMoonMine?",
        LUMWANA,
    )

    assert result is None


def test_public_api_avoids_ollama(monkeypatch):
    def fail_if_called(**kwargs):
        raise AssertionError("Ollama should not be called.")

    monkeypatch.setattr(
        rag, "generate_ollama_answer", fail_if_called
    )

    result = rag.answer_from_evidence(
        question="What is the capital expenditure for Lumwana?",
        evidence=LUMWANA,
    )

    assert result["generation_method"] == (
        "deterministic-project-estimate"
    )


def test_existing_mingomba_comparison_preserved():
    result = rag.answer_from_evidence(
        question="What is the estimated CapEx for Mingomba?",
        evidence=MINGOMBA,
    )

    assert result["generation_method"] == (
        "deterministic-estimate-comparison"
    )
    assert result["citations"] == ["S1", "S2"]


def test_mixed_approximate_estimates():
    evidence = LUMWANA + [{
        "source_id": "S4",
        "evidence_type": "document",
        "canonical_source_id": "compact",
        "document": "compact.pdf",
        "pages": "25-26",
        "text": (
            "Lumwana Copper Barrick Gold "
            "Expansion to 240ktpa ~$2.0B "
            "Mopani Copper"
        ),
    }]

    result = rag._consistent_project_estimate_from_evidence(
        "What is the estimated capital expenditure for Lumwana?",
        evidence,
    )

    assert result is not None
    assert result["generation_method"] == (
        "deterministic-project-estimate"
    )
    assert "approximately $2 billion" in result["answer"]
    assert result["citations"] == ["S1", "S2", "S4"]
    assert validate_citation_integrity(result)["valid"]


def test_strictly_greater_estimate_does_not_equal_exact():
    evidence = LUMWANA + [{
        "source_id": "S4",
        "evidence_type": "document",
        "canonical_source_id": "compact",
        "document": "compact.pdf",
        "pages": "25-26",
        "text": (
            "Lumwana Copper Barrick Gold "
            "Expansion potential >$2.0B "
            "Mopani Copper"
        ),
    }]

    result = rag._consistent_project_estimate_from_evidence(
        "What is the estimated capital expenditure for Lumwana?",
        evidence,
    )

    assert result is None
