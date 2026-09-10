from __future__ import annotations

import json

from app.search import (
    BM25Index,
    load_chunks,
    make_snippet,
    tokenize,
)


SAMPLE_CHUNKS = [
    {
        "chunk_id": "chunk_00001",
        "document": "sample.pdf",
        "page_start": 1,
        "page_end": 1,
        "text": (
            "Copper production increased significantly "
            "in Zambia during the year."
        ),
        "source_url": (
            "https://example.com/sample.pdf"
        ),
    },
    {
        "chunk_id": "chunk_00002",
        "document": "sample.pdf",
        "page_start": 2,
        "page_end": 2,
        "text": (
            "Gold production declined because of "
            "lower ore grades and operational "
            "challenges."
        ),
        "source_url": (
            "https://example.com/sample.pdf"
        ),
    },
    {
        "chunk_id": "chunk_00003",
        "document": "sample.pdf",
        "page_start": 3,
        "page_end": 3,
        "text": (
            "Mining employment increased following "
            "the opening of several new projects."
        ),
        "source_url": (
            "https://example.com/sample.pdf"
        ),
    },
    {
        "chunk_id": "chunk_00004",
        "document": "sample.pdf",
        "page_start": 4,
        "page_end": 4,
        "text": (
            "Large scale exploration licences were "
            "issued to mining companies."
        ),
        "source_url": (
            "https://example.com/sample.pdf"
        ),
    },
]


# ---------------------------------------------------------
# Tokenization
# ---------------------------------------------------------

def test_tokenize_lowercases_text() -> None:

    tokens = tokenize(
        "COPPER Production"
    )

    assert tokens == [
        "copper",
        "production",
    ]


def test_tokenize_removes_stopwords() -> None:

    tokens = tokenize(
        "The copper is in the mine"
    )

    assert "the" not in tokens
    assert "is" not in tokens
    assert "in" not in tokens

    assert "copper" in tokens
    assert "mine" in tokens


def test_tokenize_handles_numbers() -> None:

    tokens = tokenize(
        "Copper production increased "
        "by 12.5 percent"
    )

    assert "12" in tokens
    assert "5" not in tokens

    assert "copper" in tokens
    assert "production" in tokens


# ---------------------------------------------------------
# BM25 ranking
# ---------------------------------------------------------

def test_copper_query_ranks_copper_chunk_first() -> None:

    index = BM25Index(
        SAMPLE_CHUNKS
    )

    results = index.search(
        "copper production",
        top_k=3,
    )

    assert results

    assert (
        results[0][
            "chunk"
        ][
            "chunk_id"
        ]
        == "chunk_00001"
    )


def test_gold_query_ranks_gold_chunk_first() -> None:

    index = BM25Index(
        SAMPLE_CHUNKS
    )

    results = index.search(
        "gold production",
        top_k=3,
    )

    assert results

    assert (
        results[0][
            "chunk"
        ][
            "chunk_id"
        ]
        == "chunk_00002"
    )


def test_employment_query_ranks_employment_chunk_first() -> None:

    index = BM25Index(
        SAMPLE_CHUNKS
    )

    results = index.search(
        "mining employment",
        top_k=3,
    )

    assert results

    assert (
        results[0][
            "chunk"
        ][
            "chunk_id"
        ]
        == "chunk_00003"
    )


def test_licence_query_ranks_licence_chunk_first() -> None:

    index = BM25Index(
        SAMPLE_CHUNKS
    )

    results = index.search(
        "exploration licences",
        top_k=3,
    )

    assert results

    assert (
        results[0][
            "chunk"
        ][
            "chunk_id"
        ]
        == "chunk_00004"
    )


def test_search_respects_top_k() -> None:

    index = BM25Index(
        SAMPLE_CHUNKS
    )

    results = index.search(
        "production",
        top_k=1,
    )

    assert len(
        results
    ) == 1


def test_unknown_query_returns_no_results() -> None:

    index = BM25Index(
        SAMPLE_CHUNKS
    )

    results = index.search(
        "uranium",
        top_k=5,
    )

    assert results == []


def test_stopword_only_query_returns_no_results() -> None:

    index = BM25Index(
        SAMPLE_CHUNKS
    )

    results = index.search(
        "the and of",
        top_k=5,
    )

    assert results == []


# ---------------------------------------------------------
# Snippets
# ---------------------------------------------------------

def test_short_text_is_not_truncated() -> None:

    text = (
        "Copper production increased."
    )

    snippet = make_snippet(
        text=text,
        query="copper",
        max_chars=100,
    )

    assert snippet == text


def test_long_text_is_truncated() -> None:

    text = (
        "Mining activity and investment "
        "continued. "
        * 50
    )

    snippet = make_snippet(
        text=text,
        query="investment",
        max_chars=120,
    )

    assert len(
        snippet
    ) <= 130

    assert (
        "investment"
        in snippet.lower()
    )


# ---------------------------------------------------------
# Loading chunk files
# ---------------------------------------------------------

def test_load_chunks_reads_jsonl_files(
    tmp_path,
) -> None:

    chunk_file = (
        tmp_path
        / "test.chunks.jsonl"
    )

    with chunk_file.open(
        "w",
        encoding="utf-8",
    ) as file:

        for chunk in SAMPLE_CHUNKS:

            file.write(
                json.dumps(
                    chunk
                )
            )

            file.write(
                "\n"
            )

    chunks = load_chunks(
        data_directory=(
            tmp_path
        )
    )

    assert len(
        chunks
    ) == 4

    assert (
        chunks[0][
            "chunk_id"
        ]
        == "chunk_00001"
    )


def test_load_chunks_ignores_empty_text(
    tmp_path,
) -> None:

    chunk_file = (
        tmp_path
        / "test.chunks.jsonl"
    )

    records = [
        {
            "chunk_id": "chunk_1",
            "text": (
                "Copper production"
            ),
        },
        {
            "chunk_id": "chunk_2",
            "text": "",
        },
    ]

    with chunk_file.open(
        "w",
        encoding="utf-8",
    ) as file:

        for record in records:

            file.write(
                json.dumps(
                    record
                )
            )

            file.write(
                "\n"
            )

    chunks = load_chunks(
        data_directory=(
            tmp_path
        )
    )

    assert len(
        chunks
    ) == 1


# ---------------------------------------------------------
# Freshness / supersession
# ---------------------------------------------------------

def test_load_chunks_excludes_superseded_by_default(
    tmp_path,
) -> None:

    chunk_file = (
        tmp_path
        / "test.chunks.jsonl"
    )

    records = [
        {
            "chunk_id": (
                "current_chunk"
            ),
            "text": (
                "Current mining fees"
            ),
            "source_status": (
                "current"
            ),
        },
        {
            "chunk_id": (
                "old_chunk"
            ),
            "text": (
                "Historical mining fees"
            ),
            "source_status": (
                "superseded"
            ),
        },
    ]

    with chunk_file.open(
        "w",
        encoding="utf-8",
    ) as file:

        for record in records:

            file.write(
                json.dumps(
                    record
                )
            )

            file.write(
                "\n"
            )

    chunks = load_chunks(
        data_directory=(
            tmp_path
        )
    )

    assert len(
        chunks
    ) == 1

    assert (
        chunks[0][
            "chunk_id"
        ]
        == "current_chunk"
    )


def test_load_chunks_can_include_superseded(
    tmp_path,
) -> None:

    chunk_file = (
        tmp_path
        / "test.chunks.jsonl"
    )

    records = [
        {
            "chunk_id": (
                "current_chunk"
            ),
            "text": (
                "Current mining fees"
            ),
            "source_status": (
                "current"
            ),
        },
        {
            "chunk_id": (
                "old_chunk"
            ),
            "text": (
                "Historical mining fees"
            ),
            "source_status": (
                "superseded"
            ),
        },
    ]

    with chunk_file.open(
        "w",
        encoding="utf-8",
    ) as file:

        for record in records:

            file.write(
                json.dumps(
                    record
                )
            )

            file.write(
                "\n"
            )

    chunks = load_chunks(
        data_directory=(
            tmp_path
        ),
        include_superseded=True,
    )

    chunk_ids = {
        chunk[
            "chunk_id"
        ]
        for chunk in chunks
    }

    assert chunk_ids == {
        "current_chunk",
        "old_chunk",
    }