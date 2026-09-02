from __future__ import annotations

from contextlib import redirect_stdout
from datetime import datetime
from pathlib import Path

from app.embeddings import (
    SemanticIndex,
    load_embedding_cache,
    save_embedding_cache,
)

from app.hybrid import hybrid_search

from app.search import (
    BM25Index,
    load_chunks,
    make_snippet,
)


# ---------------------------------------------------------
# Paths
# ---------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]

LOG_DIR = (
    PROJECT_ROOT
    / "logs"
)


# ---------------------------------------------------------
# Queries
# ---------------------------------------------------------

QUERIES = [
    "what information is required when applying for a mining right",
    "how much does a large scale mining licence application cost",
    "how much does an exploration licence cost",
    "which minerals are considered critical in Zambia",
    "Zambia critical minerals strategy",
    "mineral beneficiation and value addition",
    "government mining sector development policy",
    "mineral exploration targets",
    "mining rights issued to citizens",
    "Zambia mining investment policy",
]


# ---------------------------------------------------------
# Display helpers
# ---------------------------------------------------------

def print_results(
    name: str,
    query: str,
    results: list[dict],
) -> None:

    print()
    print(name)
    print("-" * 72)

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
        print(
            f"{rank}. "
            f"{chunk.get('document')}"
        )

        print(
            f"   Chunk: "
            f"{chunk.get('chunk_id')}"
        )

        print(
            f"   Pages: "
            f"{pages}"
        )

        print()

        snippet = make_snippet(
            text=chunk["text"],
            query=query,
        )

        print(
            f"   {snippet}"
        )

        print()


# ---------------------------------------------------------
# Inspection
# ---------------------------------------------------------

def run_inspection() -> None:

    chunks = load_chunks()

    print(
        f"Loaded {len(chunks)} chunks."
    )

    print()

    bm25 = BM25Index(
        chunks
    )

    semantic = SemanticIndex(
        chunks
    )

    if not load_embedding_cache(
        semantic
    ):

        semantic.build()

        save_embedding_cache(
            semantic
        )

    for query in QUERIES:

        print()
        print("=" * 72)

        print(
            f'QUERY: "{query}"'
        )

        print("=" * 72)

        # -------------------------------------------------
        # BM25
        # -------------------------------------------------

        bm25_results = bm25.search(
            query=query,
            top_k=3,
        )

        # -------------------------------------------------
        # Semantic
        # -------------------------------------------------

        semantic_results = semantic.search(
            query=query,
            top_k=3,
        )

        # -------------------------------------------------
        # Hybrid
        # -------------------------------------------------

        hybrid_results = hybrid_search(
            query=query,
            bm25_index=bm25,
            semantic_index=semantic,
            top_k=3,
            candidate_k=20,
        )

        # -------------------------------------------------
        # Output
        # -------------------------------------------------

        print_results(
            name="BM25",
            query=query,
            results=bm25_results,
        )

        print_results(
            name="SEMANTIC",
            query=query,
            results=semantic_results,
        )

        print_results(
            name="HYBRID",
            query=query,
            results=hybrid_results,
        )


# ---------------------------------------------------------
# Log creation
# ---------------------------------------------------------

def create_log_path() -> Path:

    LOG_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    return (
        LOG_DIR
        / f"retrieval_inspection_{timestamp}.txt"
    )


# ---------------------------------------------------------
# Main
# ---------------------------------------------------------

def main() -> None:

    log_path = create_log_path()

    with log_path.open(
        "w",
        encoding="utf-8",
    ) as log_file:

        with redirect_stdout(
            log_file
        ):

            print(
                "MINELENS RETRIEVAL INSPECTION"
            )

            print(
                f"Generated: "
                f"{datetime.now().isoformat()}"
            )

            print()

            run_inspection()

    print()
    print(
        "Retrieval inspection complete."
    )

    print(
        "Full results saved to:"
    )

    print(
        f"  {log_path}"
    )


if __name__ == "__main__":
    main()