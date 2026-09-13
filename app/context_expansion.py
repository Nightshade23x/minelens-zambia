from __future__ import annotations

import re


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

DEFAULT_FOLLOWING_NEIGHBORS = 2


CHUNK_ID_PATTERN = re.compile(
    r"^chunk_(\d+)$",
    flags=re.IGNORECASE,
)


# ---------------------------------------------------------
# Query classification
# ---------------------------------------------------------

def is_list_query(
    query: str,
) -> bool:
    """
    Detect questions that are likely to require multiple
    items from a document section.

    Examples:
        what are Zambia's critical minerals
        which documents are required
        list the strategic objectives
        name the mining licence categories
    """

    normalized = " ".join(
        query.lower().split()
    )

    patterns = (
        r"^\s*what\s+are\b",
        r"^\s*which\b",
        r"^\s*list\b",
        r"^\s*name\b",
        r"^\s*identify\b",
        r"^\s*what\s+(?:documents|requirements|"
        r"objectives|minerals|categories|types)\b",
    )

    return any(
        re.search(
            pattern,
            normalized,
        )
        is not None
        for pattern in patterns
    )


# ---------------------------------------------------------
# Chunk identity
# ---------------------------------------------------------

def chunk_number(
    chunk: dict,
) -> int | None:
    """
    Extract the numeric part of chunk_00018 -> 18.
    """

    chunk_id = str(
        chunk.get(
            "chunk_id",
            "",
        )
    ).strip()

    match = CHUNK_ID_PATTERN.match(
        chunk_id
    )

    if match is None:

        return None

    return int(
        match.group(
            1
        )
    )


def same_document(
    first: dict,
    second: dict,
) -> bool:
    """
    Check whether two chunks belong to the same source
    document.
    """

    first_document = first.get(
        "document"
    )

    second_document = second.get(
        "document"
    )

    if (
        first_document
        and second_document
    ):

        return (
            first_document
            == second_document
        )

    first_file = first.get(
        "_chunk_file"
    )

    second_file = second.get(
        "_chunk_file"
    )

    return (
        bool(
            first_file
        )
        and first_file
        == second_file
    )


# ---------------------------------------------------------
# Neighbour retrieval
# ---------------------------------------------------------

def get_following_chunks(
    primary_chunk: dict,
    corpus: list[dict],
    count: int = DEFAULT_FOLLOWING_NEIGHBORS,
) -> list[dict]:
    """
    Return immediately following sequential chunks from
    the same document.

    Expansion stops if the sequence is broken rather than
    jumping over missing chunks.
    """

    if count <= 0:

        return []

    primary_number = chunk_number(
        primary_chunk
    )

    if primary_number is None:

        return []

    by_number: dict[
        int,
        dict,
    ] = {}

    for chunk in corpus:

        if not same_document(
            primary_chunk,
            chunk,
        ):

            continue

        number = chunk_number(
            chunk
        )

        if number is None:

            continue

        by_number[
            number
        ] = chunk

    following: list[
        dict
    ] = []

    for offset in range(
        1,
        count + 1,
    ):

        expected_number = (
            primary_number
            + offset
        )

        candidate = by_number.get(
            expected_number
        )

        if candidate is None:

            break

        following.append(
            candidate
        )

    return following


# ---------------------------------------------------------
# Search-result expansion
# ---------------------------------------------------------

def expand_document_results(
    query: str,
    results: list[dict],
    corpus: list[dict],
    following_neighbors: int = (
        DEFAULT_FOLLOWING_NEIGHBORS
    ),
) -> list[dict]:
    """
    Attach neighbouring chunks to the top hybrid result
    for list-style document questions.

    The primary ranking is NOT changed.

    Additional chunks are stored in:
        result["context_chunks"]

    Raw search therefore still represents the ranked
    retrieval result, while the RAG evidence layer gains
    enough surrounding context to answer complete lists.
    """

    if not results:

        return results

    if not is_list_query(
        query
    ):

        return results

    expanded = [
        dict(
            result
        )
        for result in results
    ]

    top_result = expanded[
        0
    ]

    primary_chunk = top_result.get(
        "chunk"
    )

    if not isinstance(
        primary_chunk,
        dict,
    ):

        return expanded

    context_chunks = (
        get_following_chunks(
            primary_chunk=(
                primary_chunk
            ),
            corpus=corpus,
            count=(
                following_neighbors
            ),
        )
    )

    if context_chunks:

        top_result[
            "context_chunks"
        ] = context_chunks

    return expanded