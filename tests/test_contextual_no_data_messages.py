import json
from pathlib import Path

import pytest

from evaluation.evaluate_answers import evaluate_question


CASES = [
    (
        "negative_unknown_licence",
        ["99999-HQ-LML", "licensing"],
    ),
    (
        "negative_missing_year",
        ["2099", "World Mining Data"],
    ),
    (
        "negative_unknown_facility",
        ["Copper Moon Mine", "USGS"],
    ),
    (
        "negative_unknown_drillhole",
        ["KBDD999", "Kabwe"],
    ),
    (
        "negative_missing_zinc_facilities",
        ["zinc smelters", "USGS"],
    ),
]


@pytest.mark.parametrize("case_id,expected", CASES)
def test_contextual_missing_data_answer(case_id, expected):
    path = Path("evaluation/answer_questions.json")
    cases = json.loads(path.read_text(encoding="utf-8-sig"))

    case = next(
        item for item in cases
        if item["id"] == case_id
    )

    result = evaluate_question(case)

    assert result["passed"], result
    assert result["citations"]["values"] == []

    answer = result["answer"].casefold()

    for phrase in expected:
        assert phrase.casefold() in answer

    assert "no matching" in answer
