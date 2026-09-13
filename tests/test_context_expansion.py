from __future__ import annotations

from app.context_expansion import (
    expand_document_results,
    get_following_chunks,
    is_list_query,
)


def make_chunk(
    number: int,
    document: str = "strategy.pdf",
) -> dict:

    return {
        "document": document,
        "chunk_id": (
            f"chunk_{number:05d}"
        ),
        "page_start": number,
        "page_end": number,
        "text": (
            f"Chunk {number}"
        ),
    }


def test_what_are_is_list_query() -> None:

    assert is_list_query(
        "what are Zambia's critical minerals"
    )


def test_normal_fact_question_is_not_list_query() -> None:

    assert not is_list_query(
        "how much does a mining licence cost"
    )


def test_following_chunks_are_sequential() -> None:

    corpus = [
        make_chunk(
            17
        ),
        make_chunk(
            18
        ),
        make_chunk(
            19
        ),
        make_chunk(
            20
        ),
    ]

    following = get_following_chunks(
        primary_chunk=corpus[
            1
        ],
        corpus=corpus,
        count=2,
    )

    assert [
        chunk[
            "chunk_id"
        ]
        for chunk in following
    ] == [
        "chunk_00019",
        "chunk_00020",
    ]


def test_following_chunks_do_not_cross_documents() -> None:

    primary = make_chunk(
        18,
        document="strategy.pdf",
    )

    corpus = [
        primary,
        make_chunk(
            19,
            document="other.pdf",
        ),
    ]

    following = get_following_chunks(
        primary_chunk=primary,
        corpus=corpus,
        count=2,
    )

    assert following == []


def test_list_query_expands_top_result_only() -> None:

    chunk_18 = make_chunk(
        18
    )

    chunk_19 = make_chunk(
        19
    )

    chunk_20 = make_chunk(
        20
    )

    results = [
        {
            "chunk": chunk_18,
            "rrf_score": 0.03,
        },
        {
            "chunk": make_chunk(
                7
            ),
            "rrf_score": 0.02,
        },
    ]

    expanded = expand_document_results(
        query=(
            "what are Zambia's "
            "critical minerals"
        ),
        results=results,
        corpus=[
            chunk_18,
            chunk_19,
            chunk_20,
        ],
    )

    assert [
        chunk[
            "chunk_id"
        ]
        for chunk in expanded[
            0
        ][
            "context_chunks"
        ]
    ] == [
        "chunk_00019",
        "chunk_00020",
    ]

    assert (
        "context_chunks"
        not in expanded[
            1
        ]
    )