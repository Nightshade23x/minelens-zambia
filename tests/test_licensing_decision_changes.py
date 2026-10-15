from collections import Counter

from app.evidence import normalize_evidence
from app.licensing_search import (
    licensing_decision_change_records,
    load_licensing_records,
    search_licensing_records,
    wants_licensing_decision_changes,
)
from app.rag import answer_from_evidence
from app.router import search_mine


QUERY = (
    "show licences whose decisions "
    "changed between committee meetings"
)


def test_decision_change_intent_detection():
    assert wants_licensing_decision_changes(
        QUERY
    )


def test_decision_change_count_and_transitions():
    records = load_licensing_records()

    changes = (
        licensing_decision_change_records(
            records
        )
    )

    assert len(changes) == 44

    transitions = Counter(
        (
            item.get(
                "previous_decision"
            ),
            item.get(
                "latest_decision"
            ),
        )
        for item in changes
    )

    assert transitions == Counter(
        {
            (
                "Deferred",
                "Approved",
            ): 35,
            (
                "Deferred",
                "Rejected",
            ): 5,
            (
                "Rejected",
                "Approved",
            ): 4,
        }
    )


def test_decision_change_search_mode():
    records = load_licensing_records()

    results, filters = (
        search_licensing_records(
            query=QUERY,
            records=records,
            top_k=5,
        )
    )

    assert filters.get(
        "decision_changes"
    ) is True

    assert filters.get(
        "history"
    ) is True

    assert len(results) == 5

    for result in results:

        record = result.get(
            "chunk",
            {}
        )

        assert (
            record.get(
                "decision_change"
            )
            is True
        )

        assert (
            record.get(
                "decision_change_total"
            )
            == 44
        )


def test_decision_change_evidence_preserves_metadata():
    search_result = search_mine(
        query=QUERY,
        top_k=5,
    )

    evidence = normalize_evidence(
        search_result=search_result,
        max_evidence=5,
    )

    assert evidence

    record = evidence[
        0
    ].get(
        "record",
        {},
    )

    assert (
        record.get(
            "decision_change"
        )
        is True
    )

    assert (
        record.get(
            "decision_change_total"
        )
        == 44
    )

    assert record.get(
        "previous_decision"
    )

    assert record.get(
        "latest_decision"
    )

    assert (
        record.get(
            "decision_change_transition_counts"
        )
        == {
            "Deferred -> Rejected": 5,
            "Deferred -> Approved": 35,
            "Rejected -> Approved": 4,
        }
    )


def test_decision_change_answer_is_deterministic():
    search_result = search_mine(
        query=QUERY,
        top_k=5,
    )

    evidence = normalize_evidence(
        search_result=search_result,
        max_evidence=5,
    )

    answer = answer_from_evidence(
        question=QUERY,
        evidence=evidence,
    )

    assert (
        answer.get(
            "generation_method"
        )
        == (
            "deterministic-licensing-"
            "decision-changes"
        )
    )

    assert answer.get(
        "model"
    ) is None

    text = answer.get(
        "answer",
        "",
    )

    assert (
        "44 applications changed "
        "committee decision"
        in text
    )

    assert (
        "Deferred → Approved: 35"
        in text
    )

    assert (
        "Deferred → Rejected: 5"
        in text
    )

    assert (
        "Rejected → Approved: 4"
        in text
    )


def test_decision_change_answer_does_not_claim_active_licence():
    search_result = search_mine(
        query=QUERY,
        top_k=5,
    )

    evidence = normalize_evidence(
        search_result=search_result,
        max_evidence=5,
    )

    answer = answer_from_evidence(
        question=QUERY,
        evidence=evidence,
    )

    text = answer.get(
        "answer",
        "",
    ).casefold()

    assert (
        "proof that a mining right has "
        "been issued or is currently active"
        in text
    )

    assert (
        "active licence"
        not in text
    )

    assert (
        "active license"
        not in text
    )
