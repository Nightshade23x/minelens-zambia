import pytest

import evaluation.evaluate_answers as evaluator


@pytest.mark.parametrize(
    "inline,declared,source_ids,should_pass",
    [
        ("S1", ["S1"], ["S1"], True),
        ("S2", ["S2"], ["S1"], False),
        ("S2", ["S1"], ["S1"], False),
    ],
)
def test_evaluator_enforces_citation_integrity(
    monkeypatch, inline, declared, source_ids, should_pass
):
    monkeypatch.setattr(
        evaluator,
        "search_mine",
        lambda query, top_k: {
            "route": "licensing",
            "results": [{"record_id": "test"}],
        },
    )

    monkeypatch.setattr(
        evaluator,
        "normalize_evidence",
        lambda **kwargs: [{"evidence_type": "licensing_record"}],
    )

    monkeypatch.setattr(
        evaluator,
        "answer_from_evidence",
        lambda **kwargs: {
            "answer": f"A test fact is 100. [{inline}]",
            "generation_method": "deterministic-licensing",
            "citations": declared,
            "sources": [
                {"source_id": source_id}
                for source_id in source_ids
            ],
        },
    )

    result = evaluator.evaluate_question({
        "id": "citation_integrity_regression",
        "question": "Test licence record",
        "expected_route": "licensing",
        "expected_generation_method": "deterministic-licensing",
        "expected_facts": ["100"],
        "forbidden_facts": [],
    })

    assert result["passed"] is should_pass
    assert result["citation_integrity"]["valid"] is should_pass
