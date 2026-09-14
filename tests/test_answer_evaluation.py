from __future__ import annotations

from unittest.mock import patch

from evaluation.evaluate_answers import (
    evaluate_question,
)


def test_generation_failure_becomes_failed_result() -> None:

    case = {
        "id": "generation_failure",
        "question": "example question",
        "expected_route": "documents",
        "expected_generation_method": "ollama",
        "expected_facts": [],
        "expected_concepts": [
            {
                "name": "example concept",
                "any_of": [
                    "example"
                ],
            }
        ],
        "minimum_concept_recall": 1.0,
        "forbidden_facts": [],
        "required_source_contains": "example.pdf",
        "requires_ollama": True,
    }

    fake_search_result = {
        "route": "documents",
        "results": [],
    }

    fake_evidence = [
        {
            "source_id": "S1",
            "evidence_type": "document",
            "title": "Example",
            "document": "example.pdf",
            "text": "Example evidence.",
        }
    ]

    with patch(
        "evaluation.evaluate_answers.search_mine",
        return_value=fake_search_result,
    ), patch(
        "evaluation.evaluate_answers.normalize_evidence",
        return_value=fake_evidence,
    ), patch(
        "evaluation.evaluate_answers.answer_from_evidence",
        side_effect=RuntimeError(
            "Generated factual answer "
            "contains no evidence citation."
        ),
    ):

        result = evaluate_question(
            case
        )

    assert result["passed"] is False

    assert (
        result["generation"]["actual"]
        == "error"
    )

    assert (
        "no evidence citation"
        in result["error"]
    )

    assert (
        result["citations"]["present"]
        is False
    )