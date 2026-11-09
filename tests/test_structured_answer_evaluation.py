import pytest

from evaluation.evaluate_answers import evaluate_question


@pytest.mark.parametrize(
    "question,route,method,fact",
    [
        (
            "Who operates Kansanshi Mine?",
            "facilities",
            "structured-facilities",
            "Kansanshi Mining plc",
        ),
        (
            "What was Zambia's copper production in 2024?",
            "mining_statistics",
            "structured-statistics",
            "822,824",
        ),
    ],
)
def test_structured_answer_pipeline(question, route, method, fact):
    result = evaluate_question({
        "id": "structured_smoke",
        "question": question,
        "expected_route": route,
        "expected_generation_method": method,
        "expected_facts": [fact],
        "forbidden_facts": [],
    })

    assert result["passed"], result
    assert result["citations"]["present"]
