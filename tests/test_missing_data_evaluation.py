import pytest

from evaluation.evaluate_answers import evaluate_question


@pytest.mark.parametrize(
    "question,route,method",
    [
        (
            "99999-HQ-LML",
            "licensing",
            "no-evidence",
        ),
        (
            "What was Zambia's copper production in 2099?",
            "mining_statistics",
            "structured-statistics",
        ),
        (
            "Who operates the imaginary Copper Moon Mine?",
            "facilities",
            "structured-facilities",
        ),
        (
            "What is the zinc assay in drill hole KBDD999?",
            "exploration",
            "no-evidence",
        ),
        (
            "Which zinc smelters are in Zambia?",
            "facilities",
            "structured-facilities",
        ),
    ],
)
def test_correct_missing_data_abstention(question, route, method):
    result = evaluate_question({
        "id": "missing_data_regression",
        "question": question,
        "expected_route": route,
        "expected_generation_method": method,
        "expected_facts": [],
        "forbidden_facts": [],
        "expect_no_results": True,
    })

    assert result["passed"], result
    assert result["route"]["actual"] == route
    assert result["generation"]["actual"] == method
    assert result["citations"]["values"] == []
    assert result["answer"].strip()
