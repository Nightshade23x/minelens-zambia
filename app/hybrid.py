from __future__ import annotations

import argparse

from app.embeddings import (
    SemanticIndex,
    load_embedding_cache,
    save_embedding_cache,
)

from app.search import (
    BM25Index,
    load_chunks,
    make_snippet,
)


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

DEFAULT_TOP_K = 5

DEFAULT_CANDIDATE_K = 20

RRF_K = 60


# ---------------------------------------------------------
# Result identity
# ---------------------------------------------------------

def chunk_key(
    chunk: dict,
) -> tuple:
    """
    Create a unique identifier for a chunk.

    chunk_id alone is not enough because different
    documents may both contain chunk_00001.
    """

    return (
        chunk.get("document"),
        chunk.get("chunk_id"),
        chunk.get("document_sha256"),
    )


# ---------------------------------------------------------
# Reciprocal Rank Fusion
# ---------------------------------------------------------

def reciprocal_rank(
    rank: int,
    rrf_k: int = RRF_K,
) -> float:
    """
    Calculate the RRF contribution for one ranking.

    Rank starts at 1.
    """

    return 1.0 / (
        rrf_k + rank
    )


def hybrid_search(
    query: str,
    bm25_index: BM25Index,
    semantic_index: SemanticIndex,
    top_k: int = DEFAULT_TOP_K,
    candidate_k: int = DEFAULT_CANDIDATE_K,
) -> list[dict]:
    """
    Combine BM25 and semantic search using
    Reciprocal Rank Fusion.
    """

    if not query.strip():
        return []

    if top_k <= 0:
        raise ValueError(
            "top_k must be greater than zero."
        )

    candidate_k = max(
        candidate_k,
        top_k,
    )

    # -----------------------------------------------------
    # Retrieve candidates independently
    # -----------------------------------------------------

    bm25_results = bm25_index.search(
        query=query,
        top_k=candidate_k,
    )

    semantic_results = semantic_index.search(
        query=query,
        top_k=candidate_k,
    )

    # -----------------------------------------------------
    # Fuse rankings
    # -----------------------------------------------------

    fused: dict[tuple, dict] = {}

    for rank, result in enumerate(
        bm25_results,
        start=1,
    ):

        chunk = result["chunk"]

        key = chunk_key(
            chunk
        )

        if key not in fused:

            fused[key] = {
                "chunk": chunk,
                "rrf_score": 0.0,
                "bm25_rank": None,
                "bm25_score": None,
                "semantic_rank": None,
                "semantic_score": None,
            }

        fused[key]["bm25_rank"] = rank

        fused[key]["bm25_score"] = (
            result["score"]
        )

        fused[key]["rrf_score"] += (
            reciprocal_rank(rank)
        )

    for rank, result in enumerate(
        semantic_results,
        start=1,
    ):

        chunk = result["chunk"]

        key = chunk_key(
            chunk
        )

        if key not in fused:

            fused[key] = {
                "chunk": chunk,
                "rrf_score": 0.0,
                "bm25_rank": None,
                "bm25_score": None,
                "semantic_rank": None,
                "semantic_score": None,
            }

        fused[key]["semantic_rank"] = rank

        fused[key]["semantic_score"] = (
            result["score"]
        )

        fused[key]["rrf_score"] += (
            reciprocal_rank(rank)
        )

    # -----------------------------------------------------
    # Final ranking
    # -----------------------------------------------------

    results = list(
        fused.values()
    )

    results.sort(
        key=lambda result: result[
            "rrf_score"
        ],
        reverse=True,
    )

    return results[:top_k]


# ---------------------------------------------------------
# Display
# ---------------------------------------------------------

def display_results(
    query: str,
    results: list[dict],
) -> None:

    print()
    print("=" * 70)

    print(
        "MINELENS ZAMBIA HYBRID SEARCH"
    )

    print("=" * 70)

    print()
    print(
        f'Query: "{query}"'
    )

    if not results:

        print()
        print(
            "No results found."
        )

        return

    for rank, result in enumerate(
        results,
        start=1,
    ):

        chunk = result[
            "chunk"
        ]

        page_start = chunk.get(
            "page_start"
        )

        page_end = chunk.get(
            "page_end"
        )

        if page_start == page_end:

            pages = str(
                page_start
            )

        else:

            pages = (
                f"{page_start}-{page_end}"
            )

        print()
        print("-" * 70)

        print(
            f"RESULT {rank}"
        )

        print(
            f"Hybrid score: "
            f"{result['rrf_score']:.6f}"
        )

        if (
            result["bm25_rank"]
            is not None
        ):

            print(
                "BM25:       "
                f"rank #{result['bm25_rank']} "
                f"| score "
                f"{result['bm25_score']:.4f}"
            )

        else:

            print(
                "BM25:       not in candidates"
            )

        if (
            result["semantic_rank"]
            is not None
        ):

            print(
                "Semantic:   "
                f"rank #{result['semantic_rank']} "
                f"| similarity "
                f"{result['semantic_score']:.4f}"
            )

        else:

            print(
                "Semantic:   not in candidates"
            )

        print(
            f"Document:   "
            f"{chunk.get('document')}"
        )

        print(
            f"Pages:      {pages}"
        )

        print(
            f"Chunk:      "
            f"{chunk.get('chunk_id')}"
        )

        print()

        print(
            make_snippet(
                text=chunk["text"],
                query=query,
            )
        )

        source_url = chunk.get(
            "source_url"
        )

        if source_url:

            print()
            print(
                f"Source: {source_url}"
            )

    print()
    print("-" * 70)


# ---------------------------------------------------------
# CLI
# ---------------------------------------------------------

def main() -> None:

    parser = argparse.ArgumentParser(
        description=(
            "Search MineLens using hybrid "
            "BM25 + semantic retrieval."
        )
    )

    parser.add_argument(
        "query",
        nargs="+",
        help="Search query",
    )

    parser.add_argument(
        "--top-k",
        type=int,
        default=DEFAULT_TOP_K,
        help=(
            "Number of results to return "
            f"(default: {DEFAULT_TOP_K})"
        ),
    )

    parser.add_argument(
        "--candidate-k",
        type=int,
        default=DEFAULT_CANDIDATE_K,
        help=(
            "Candidates retrieved from each "
            "search system before fusion"
        ),
    )

    args = parser.parse_args()

    query = " ".join(
        args.query
    )

    print(
        "Loading MineLens chunks..."
    )

    chunks = load_chunks()

    print(
        f"Loaded {len(chunks)} chunks."
    )

    # -----------------------------------------------------
    # BM25
    # -----------------------------------------------------

    print(
        "Building BM25 index..."
    )

    bm25_index = BM25Index(
        chunks
    )

    # -----------------------------------------------------
    # Semantic
    # -----------------------------------------------------

    semantic_index = SemanticIndex(
        chunks
    )

    if not load_embedding_cache(
        semantic_index
    ):

        semantic_index.build()

        save_embedding_cache(
            semantic_index
        )

    # -----------------------------------------------------
    # Hybrid retrieval
    # -----------------------------------------------------

    results = hybrid_search(
        query=query,
        bm25_index=bm25_index,
        semantic_index=semantic_index,
        top_k=args.top_k,
        candidate_k=args.candidate_k,
    )

    display_results(
        query=query,
        results=results,
    )


if __name__ == "__main__":
    main()