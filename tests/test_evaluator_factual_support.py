import pytest

import evaluation.evaluate_answers as evaluator


@pytest.mark.parametrize(
    "operator,should_pass",
    [
        ("Kansanshi Mining plc", True),
        ("Imaginary Mining Ltd.", False),
    ],
)
def test_evaluator_rejects_unsupported_operator(
    monkeypatch, operator, should_pass
):
    search_result = {
        "route": "facilities",
        "results": [
            {
                "facility": {
                    "facility_name": "Kansanshi Mine",
                    "major_operating_companies": [
                        "Kansanshi Mining plc"
                    ],
                },
            }
        ],
    }

    monkeypatch.setattr(
        evaluator,
        "search_mine",
        lambda query, top_k: search_result,
    )

    monkeypatch.setattr(
        evaluator,
        "answer_facility_result",
        lambda *args, **kwargs: {
            "answer": (
                "Kansanshi Mine is operated by "
                f"{operator}. [S1]"
            ),
            "generation_method": "structured-facilities",
            "citations": ["S1"],
            "sources": [{"source_id": "S1"}],
        },
    )

    result = evaluator.evaluate_question({
        "id": "operator_support_regression",
        "question": "Who operates Kansanshi Mine?",
        "expected_route": "facilities",
        "expected_generation_method": "structured-facilities",
        "expected_facts": [],
        "forbidden_facts": [],
    })

    assert result["passed"] is should_pass
    assert result["citation_integrity"]["valid"] is True
    assert result["factual_support"]["checked"] is True
    assert result["factual_support"]["supported"] is should_pass
