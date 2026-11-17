"""Protect the Mushima Phase 4 public pipeline against regressions."""

import pytest

from evaluation.mushima_phase4_benchmark import CASES, evaluate_case


@pytest.mark.parametrize("case", CASES, ids=[case["id"] for case in CASES])
def test_mushima_public_pipeline(case):
    result = evaluate_case(case)
    assert result["passed"], "\n".join(result["errors"])
