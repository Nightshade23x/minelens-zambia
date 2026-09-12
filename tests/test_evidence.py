from __future__ import annotations

import pytest

from app.evidence import (
    evidence_sources,
    evidence_to_context,
    normalize_evidence,
)


def test_document_results_are_normalized() -> None:

    search_result = {
        "route": "documents",
        "results": [
            {
                "rrf_score": 0.0325,
                "bm25_rank": 2,
                "bm25_score": 13.3,
                "semantic_rank": 1,
                "semantic_score": 0.63,
                "chunk": {
                    "document": (
                        "zambia_fees_2024.pdf"
                    ),
                    "page_start": 1,
                    "page_end": 2,
                    "chunk_id": (
                        "chunk_00001"
                    ),
                    "text": (
                        "Large-scale mining "
                        "licence application "
                        "fee is K64,000."
                    ),
                    "source_url": (
                        "https://example.com/"
                        "fees.pdf"
                    ),
                    "source_status": (
                        "current"
                    ),
                },
            }
        ],
    }

    evidence = normalize_evidence(
        search_result
    )

    assert len(
        evidence
    ) == 1

    assert (
        evidence[0][
            "source_id"
        ]
        == "S1"
    )

    assert (
        evidence[0][
            "evidence_type"
        ]
        == "document"
    )

    assert (
        evidence[0][
            "pages"
        ]
        == "1-2"
    )

    assert (
        "K64,000"
        in evidence[0][
            "text"
        ]
    )


def test_licensing_results_are_normalized() -> None:

    search_result = {
        "route": "licensing",
        "results": [
            {
                "score": 1.0,
                "chunk": {
                    "licence_code": (
                        "42553-HQ-LML"
                    ),
                    "licence_type_code": (
                        "LML"
                    ),
                    "licence_type": (
                        "Large-Scale "
                        "Mining Licence"
                    ),
                    "applicant": (
                        "Nisco Industries Ltd"
                    ),
                    "decision": (
                        "Approved"
                    ),
                    "province": (
                        "North Western"
                    ),
                    "districts": [
                        "Solwezi"
                    ],
                    "commodities": [
                        "Au",
                        "Cu",
                    ],
                    "area_hectares": (
                        9541.1303
                    ),
                    "area_text": (
                        "9,541.1303 ha"
                    ),
                    "deadline": (
                        "25th September 2026"
                    ),
                    "deadline_iso": (
                        "2026-09-25"
                    ),
                    "text": (
                        "Licence code "
                        "42553-HQ-LML. "
                        "Applicant Nisco "
                        "Industries Ltd."
                    ),
                    "source_url": (
                        "https://example.com/"
                        "licensing"
                    ),
                },
            }
        ],
    }

    evidence = normalize_evidence(
        search_result
    )

    record = evidence[
        0
    ][
        "record"
    ]

    assert (
        evidence[0][
            "evidence_type"
        ]
        == "licensing_record"
    )

    assert (
        record[
            "licence_code"
        ]
        == "42553-HQ-LML"
    )

    assert (
        record[
            "applicant"
        ]
        == "Nisco Industries Ltd"
    )

    assert (
        record[
            "decision"
        ]
        == "Approved"
    )

    assert (
        record[
            "districts"
        ]
        == [
            "Solwezi"
        ]
    )


def test_evidence_is_limited() -> None:

    search_result = {
        "route": "documents",
        "results": [
            {
                "chunk": {
                    "document": (
                        f"document_{index}.pdf"
                    ),
                    "chunk_id": (
                        f"chunk_{index}"
                    ),
                    "text": (
                        f"Evidence {index}"
                    ),
                }
            }
            for index in range(
                10
            )
        ],
    }

    evidence = normalize_evidence(
        search_result,
        max_evidence=3,
    )

    assert len(
        evidence
    ) == 3

    assert [
        item[
            "source_id"
        ]
        for item in evidence
    ] == [
        "S1",
        "S2",
        "S3",
    ]


def test_evidence_text_is_truncated() -> None:

    search_result = {
        "route": "documents",
        "results": [
            {
                "chunk": {
                    "document": (
                        "sample.pdf"
                    ),
                    "chunk_id": (
                        "chunk_1"
                    ),
                    "text": (
                        "A" * 500
                    ),
                }
            }
        ],
    }

    evidence = normalize_evidence(
        search_result,
        max_text_chars=100,
    )

    assert len(
        evidence[0][
            "text"
        ]
    ) <= 104

    assert evidence[
        0
    ][
        "text"
    ].endswith(
        " ..."
    )


def test_context_contains_source_labels() -> None:

    evidence = [
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
            "published_date": "",
            "source_url": (
                "https://example.com"
            ),
            "text": (
                "Large-scale mining "
                "licence fee is K64,000."
            ),
        }
    ]

    context = evidence_to_context(
        evidence
    )

    assert "[S1]" in context

    assert (
        "Mining Fees 2024"
        in context
    )

    assert (
        "K64,000"
        in context
    )


def test_source_metadata_is_preserved() -> None:

    evidence = [
        {
            "source_id": "S1",
            "title": (
                "Mining Fees 2024"
            ),
            "document": (
                "fees.pdf"
            ),
            "pages": "1-2",
            "source_url": (
                "https://example.com"
            ),
        }
    ]

    sources = evidence_sources(
        evidence
    )

    assert sources == [
        {
            "source_id": "S1",
            "title": (
                "Mining Fees 2024"
            ),
            "document": (
                "fees.pdf"
            ),
            "pages": "1-2",
            "source_url": (
                "https://example.com"
            ),
        }
    ]


def test_unknown_route_is_rejected() -> None:

    with pytest.raises(
        ValueError
    ):

        normalize_evidence(
            {
                "route": "unknown",
                "results": [
                    {
                        "chunk": {
                            "text": (
                                "sample"
                            )
                        }
                    }
                ],
            }
        )


def test_invalid_evidence_limit_is_rejected() -> None:

    with pytest.raises(
        ValueError
    ):

        normalize_evidence(
            {
                "route": (
                    "documents"
                ),
                "results": [],
            },
            max_evidence=0,
        )