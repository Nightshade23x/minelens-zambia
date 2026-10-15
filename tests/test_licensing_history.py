from __future__ import annotations

from app.evidence import normalize_evidence
from app.licensing_search import (
    latest_licensing_records,
    load_licensing_records,
    search_licensing_records,
    wants_licensing_history,
)
from app.rag import answer_from_evidence
from app.router import search_mine


LICENCE_CODE = "43225-HQ-LML"


def decisions_from_results(
    results: list[dict],
) -> list[str]:
    """
    Extract committee decisions from licensing results.
    """

    decisions: list[str] = []

    for result in results:

        record = result.get(
            "chunk",
            {},
        )

        decision = str(
            record.get(
                "decision"
            )
            or ""
        ).strip()

        if decision:
            decisions.append(
                decision
            )

    return decisions


def test_history_intent_detection() -> None:
    """
    History wording must activate event-history mode.
    """

    assert wants_licensing_history(
        (
            "show the decision history "
            f"for {LICENCE_CODE}"
        )
    )

    assert wants_licensing_history(
        (
            "show previous decisions "
            f"for {LICENCE_CODE}"
        )
    )

    assert not wants_licensing_history(
        LICENCE_CODE
    )


def test_latest_records_collapses_duplicate_codes() -> None:
    """
    Normal-state views must retain only the newest
    event for each licence/application code.
    """

    records = [
        {
            "licence_code": LICENCE_CODE,
            "decision": "Deferred",
            "published_date": "2026-08-25",
            "effective_date": None,
        },
        {
            "licence_code": LICENCE_CODE,
            "decision": "Approved",
            "published_date": "2026-10-10",
            "effective_date": "2026-09-28",
        },
    ]

    latest = latest_licensing_records(
        records
    )

    assert len(
        latest
    ) == 1

    assert latest[0][
        "decision"
    ] == "Approved"


def test_real_dataset_contains_both_committee_events() -> None:
    """
    The known Ezra Energy application must preserve
    both June and September committee events.
    """

    records = load_licensing_records()

    matching = [
        record
        for record in records
        if (
            record.get(
                "licence_code"
            )
            == LICENCE_CODE
        )
    ]

    assert len(
        matching
    ) == 2

    decisions = {
        record.get(
            "decision"
        )
        for record in matching
    }

    assert decisions == {
        "Deferred",
        "Approved",
    }


def test_plain_lookup_returns_latest_decision_only() -> None:
    """
    A normal exact-code lookup must represent the
    latest known committee decision only.
    """

    records = load_licensing_records()

    (
        results,
        filters,
    ) = search_licensing_records(
        query=LICENCE_CODE,
        records=records,
        top_k=5,
    )

    assert (
        filters.get(
            "history"
        )
        is False
    )

    assert len(
        results
    ) == 1

    assert decisions_from_results(
        results
    ) == [
        "Approved"
    ]


def test_history_lookup_returns_both_events() -> None:
    """
    A history query must preserve both committee
    events for the exact licence/application code.
    """

    records = load_licensing_records()

    (
        results,
        filters,
    ) = search_licensing_records(
        query=(
            "show the decision history "
            f"for {LICENCE_CODE}"
        ),
        records=records,
        top_k=5,
    )

    assert (
        filters.get(
            "history"
        )
        is True
    )

    decisions = decisions_from_results(
        results
    )

    assert decisions == [
        "Approved",
        "Deferred",
    ]


def test_full_plain_lookup_uses_latest_event() -> None:
    """
    Router + evidence normalization must still expose
    only the latest event for a plain lookup.
    """

    search_result = search_mine(
        query=LICENCE_CODE,
        top_k=5,
    )

    assert (
        search_result.get(
            "route"
        )
        == "licensing"
    )

    evidence = normalize_evidence(
        search_result=search_result,
        max_evidence=5,
    )

    assert len(
        evidence
    ) == 1

    assert evidence[0][
        "record"
    ][
        "decision"
    ] == "Approved"


def test_full_history_answer_is_chronological() -> None:
    """
    The deterministic answer must describe the change
    Deferred -> Approved and mark Approved as latest.
    """

    query = (
        "show the decision history "
        f"for {LICENCE_CODE}"
    )

    search_result = search_mine(
        query=query,
        top_k=5,
    )

    evidence = normalize_evidence(
        search_result=search_result,
        max_evidence=5,
    )

    assert len(
        evidence
    ) == 2

    answer_result = answer_from_evidence(
        question=query,
        evidence=evidence,
    )

    answer = str(
        answer_result.get(
            "answer"
        )
        or ""
    )

    assert (
        answer_result.get(
            "generation_method"
        )
        == "deterministic-licensing-history"
    )

    assert (
        "June 2026 committee batch: Deferred"
        in answer
    )

    assert (
        "28 September 2026: Approved"
        in answer
    )

    assert (
        "Decision changed from Deferred to Approved."
        in answer
    )

    assert (
        "Latest decision: Approved."
        in answer
    )


def test_history_does_not_claim_active_licence() -> None:
    """
    Committee approval must not be converted into an
    active/issued licence claim.
    """

    query = (
        "show the decision history "
        f"for {LICENCE_CODE}"
    )

    search_result = search_mine(
        query=query,
        top_k=5,
    )

    evidence = normalize_evidence(
        search_result=search_result,
        max_evidence=5,
    )

    answer_result = answer_from_evidence(
        question=query,
        evidence=evidence,
    )

    answer = str(
        answer_result.get(
            "answer"
        )
        or ""
    ).lower()

    assert "active licence" not in answer
    assert "active license" not in answer
    assert "licence is active" not in answer
    assert "license is active" not in answer

import pytest


@pytest.mark.parametrize(
    (
        "licence_code",
        "old_decision",
        "new_decision",
    ),
    [
        (
            "08561-HQ-SML",
            "Deferred",
            "Approved",
        ),
        (
            "41170-HQ-SML",
            "Deferred",
            "Rejected",
        ),
        (
            "42055-HQ-SML",
            "Deferred",
            "Rejected",
        ),
        (
            "43138-HQ-SML",
            "Deferred",
            "Approved",
        ),
        (
            "43225-HQ-LML",
            "Deferred",
            "Approved",
        ),
    ],
)
def test_known_committee_decision_changes(
    licence_code: str,
    old_decision: str,
    new_decision: str,
) -> None:
    """
    Known applications appearing in both committee
    batches must preserve their chronological decisions.
    """

    records = load_licensing_records()

    matching = [
        record
        for record in records
        if (
            record.get(
                "licence_code"
            )
            == licence_code
        )
    ]

    assert len(
        matching
    ) >= 2

    ordered = sorted(
        matching,
        key=lambda record: (
            record.get(
                "effective_date"
            )
            or record.get(
                "published_date"
            )
            or ""
        ),
    )

    assert ordered[0][
        "decision"
    ] == old_decision

    assert ordered[-1][
        "decision"
    ] == new_decision


@pytest.mark.parametrize(
    (
        "licence_code",
        "latest_decision",
    ),
    [
        (
            "08561-HQ-SML",
            "Approved",
        ),
        (
            "41170-HQ-SML",
            "Rejected",
        ),
        (
            "42055-HQ-SML",
            "Rejected",
        ),
        (
            "43138-HQ-SML",
            "Approved",
        ),
        (
            "43225-HQ-LML",
            "Approved",
        ),
    ],
)
def test_plain_lookup_uses_latest_for_changed_records(
    licence_code: str,
    latest_decision: str,
) -> None:
    """
    Plain licence-code lookup must never surface a stale
    earlier decision as the current committee state.
    """

    records = load_licensing_records()

    (
        results,
        filters,
    ) = search_licensing_records(
        query=licence_code,
        records=records,
        top_k=5,
    )

    assert (
        filters.get(
            "history"
        )
        is False
    )

    assert len(
        results
    ) == 1

    assert decisions_from_results(
        results
    ) == [
        latest_decision
    ]