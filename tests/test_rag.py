from __future__ import annotations

import os

import pytest

from app.rag import (
    build_user_prompt,
    extract_citations,
    format_source,
    select_ollama_model,
    validate_citations,
)


SAMPLE_EVIDENCE = [
    {
        "source_id": "S1",
        "evidence_type": (
            "document"
        ),
        "title": (
            "Mining Fees 2024"
        ),
        "document": (
            "fees.pdf"
        ),
        "pages": "1-2",
        "published_date": (
            "2024-06-19"
        ),
        "source_url": (
            "https://example.com/"
            "fees.pdf"
        ),
        "text": (
            "The large-scale mining "
            "licence application fee "
            "is K64,000."
        ),
    },
    {
        "source_id": "S2",
        "evidence_type": (
            "document"
        ),
        "title": (
            "Mining Requirements"
        ),
        "document": (
            "requirements.html"
        ),
        "pages": "1",
        "published_date": "",
        "source_url": (
            "https://example.com/"
            "requirements"
        ),
        "text": (
            "Applicants must submit "
            "the required documents."
        ),
    },
]


def test_prompt_contains_question() -> None:

    prompt = build_user_prompt(
        question=(
            "How much is the licence?"
        ),
        evidence=(
            SAMPLE_EVIDENCE
        ),
    )

    assert (
        "How much is the licence?"
        in prompt
    )


def test_prompt_contains_evidence_labels() -> None:

    prompt = build_user_prompt(
        question="Question",
        evidence=(
            SAMPLE_EVIDENCE
        ),
    )

    assert "[S1]" in prompt

    assert "[S2]" in prompt

    assert (
        "K64,000"
        in prompt
    )


def test_extracts_unique_citations() -> None:

    citations = extract_citations(
        (
            "The fee is K64,000 "
            "[S1]. The same source "
            "confirms it [S1]. "
            "Requirements appear "
            "in [S2]."
        )
    )

    assert citations == [
        "S1",
        "S2",
    ]


def test_valid_citations_pass() -> None:

    citations = validate_citations(
        answer=(
            "The fee is "
            "K64,000 [S1]."
        ),
        evidence=(
            SAMPLE_EVIDENCE
        ),
    )

    assert citations == [
        "S1"
    ]


def test_invalid_citation_is_rejected() -> None:

    with pytest.raises(
        RuntimeError
    ):

        validate_citations(
            answer=(
                "The answer is "
                "supported by [S9]."
            ),
            evidence=(
                SAMPLE_EVIDENCE
            ),
        )


def test_requested_model_is_selected() -> None:

    result = select_ollama_model(
        installed_models=[
            "model-a",
            "model-b",
        ],
        requested_model=(
            "model-b"
        ),
    )

    assert result == "model-b"


def test_missing_requested_model_is_rejected() -> None:

    with pytest.raises(
        RuntimeError
    ):

        select_ollama_model(
            installed_models=[
                "model-a",
            ],
            requested_model=(
                "model-b"
            ),
        )


def test_first_model_is_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:

    monkeypatch.delenv(
        "MINELENS_OLLAMA_MODEL",
        raising=False,
    )

    result = select_ollama_model(
        installed_models=[
            "custom-model:latest",
            "another-model:latest",
        ],
    )

    assert (
        result
        == "custom-model:latest"
    )


def test_source_formatting() -> None:

    formatted = format_source(
        {
            "source_id": "S1",
            "title": (
                "Mining Fees 2024"
            ),
            "pages": "1-2",
            "source_url": (
                "https://example.com"
            ),
        }
    )

    assert (
        "[S1]"
        in formatted
    )

    assert (
        "Mining Fees 2024"
        in formatted
    )

    assert (
        "pp. 1-2"
        in formatted
    )