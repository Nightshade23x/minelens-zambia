from __future__ import annotations

import json

from pathlib import Path

from app.embeddings import (
    SemanticIndex,
    load_embedding_cache,
    save_embedding_cache,
)

from app.hybrid import (
    hybrid_search,
)

from app.search import (
    BM25Index,
    load_chunks,
)


# ---------------------------------------------------------
# Project paths
# ---------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]

QUESTIONS_PATH = (
    PROJECT_ROOT
    / "evaluation"
    / "questions.json"
)


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

EVALUATION_K_VALUES = [
    1,
    3,
    5,
]


# ---------------------------------------------------------
# Question loading
# ---------------------------------------------------------

def load_questions(
    path: Path = QUESTIONS_PATH,
) -> list[dict]:
    """
    Load the MineLens retrieval benchmark.
    """

    if not path.exists():
        raise FileNotFoundError(
            f"Evaluation file not found: {path}"
        )

    with path.open(
        "r",
        encoding="utf-8",
    ) as file:

        questions = json.load(
            file
        )

    if not isinstance(
        questions,
        list,
    ):
        raise ValueError(
            "questions.json must contain a JSON list."
        )

    if not questions:
        raise ValueError(
            "No evaluation questions were found."
        )

    for question in questions:

        if "query" not in question:
            raise ValueError(
                "Every evaluation question "
                "must contain a query."
            )

        if "relevant_chunks" not in question:
            raise ValueError(
                "Every evaluation question must "
                "contain relevant_chunks."
            )

    return questions


# ---------------------------------------------------------
# Relevance
# ---------------------------------------------------------

def chunk_is_relevant(
    chunk: dict,
    relevant_chunks: list[dict],
) -> bool:
    """
    Determine whether a returned chunk has been manually
    judged relevant to an evaluation query.
    """

    document = chunk.get(
        "document"
    )

    chunk_id = chunk.get(
        "chunk_id"
    )

    return any(
        relevant.get("document") == document
        and relevant.get("chunk_id") == chunk_id
        for relevant in relevant_chunks
    )


def first_relevant_rank(
    results: list[dict],
    relevant_chunks: list[dict],
) -> int | None:

    for rank, result in enumerate(
        results,
        start=1,
    ):

        if chunk_is_relevant(
            result["chunk"],
            relevant_chunks,
        ):
            return rank

    return None
# ---------------------------------------------------------
# Metrics
# ---------------------------------------------------------

def hit_at_k(
    rank: int | None,
    k: int,
) -> float:
    """
    Hit@K = 1 when at least one relevant result appears
    within the top K results.
    """

    if rank is None:
        return 0.0

    return (
        1.0
        if rank <= k
        else 0.0
    )


def reciprocal_rank(
    rank: int | None,
) -> float:
    """
    Reciprocal rank rewards relevant results appearing
    closer to rank 1.
    """

    if rank is None:
        return 0.0

    return 1.0 / rank


# ---------------------------------------------------------
# Evaluation
# ---------------------------------------------------------

def evaluate_system(
    name: str,
    search_function,
    questions: list[dict],
) -> dict:
    """
    Evaluate one retrieval system.
    """

    totals = {
        f"hit@{k}": 0.0
        for k in EVALUATION_K_VALUES
    }

    reciprocal_rank_total = 0.0

    query_results: list[dict] = []

    max_k = max(
        EVALUATION_K_VALUES
    )

    for question in questions:

        query = question[
            "query"
        ]

        relevant_chunks = question[
            "relevant_chunks"
        ]

        results = search_function(
            query,
            max_k,
        )

        rank = first_relevant_rank(
            results,
            relevant_chunks,
        )

        for k in EVALUATION_K_VALUES:

            totals[
                f"hit@{k}"
            ] += hit_at_k(
                rank,
                k,
            )

        reciprocal_rank_total += (
            reciprocal_rank(
                rank
            )
        )

        query_results.append(
            {
                "id": question.get(
                    "id"
                ),
                "query": query,
                "first_relevant_rank": rank,
            }
        )

    question_count = len(
        questions
    )

    metrics = {
        key: round(
            value / question_count,
            4,
        )
        for key, value in totals.items()
    }

    metrics["MRR"] = round(
        reciprocal_rank_total
        / question_count,
        4,
    )

    return {
        "system": name,
        "metrics": metrics,
        "queries": query_results,
    }


# ---------------------------------------------------------
# Display
# ---------------------------------------------------------

def display_evaluation(
    evaluations: list[dict],
) -> None:
    """
    Print a compact comparison table.
    """

    print()
    print("=" * 72)
    print("MINELENS RETRIEVAL EVALUATION")
    print("=" * 72)
    print()

    header = (
        f"{'System':<14}"
        f"{'Hit@1':>10}"
        f"{'Hit@3':>10}"
        f"{'Hit@5':>10}"
        f"{'MRR':>10}"
    )

    print(
        header
    )

    print(
        "-" * len(header)
    )

    for evaluation in evaluations:

        metrics = evaluation[
            "metrics"
        ]

        print(
            f"{evaluation['system']:<14}"
            f"{metrics['hit@1']:>10.3f}"
            f"{metrics['hit@3']:>10.3f}"
            f"{metrics['hit@5']:>10.3f}"
            f"{metrics['MRR']:>10.3f}"
        )

    print()
    print("=" * 72)
    print("QUERY DETAILS")
    print("=" * 72)

    system_lookup = {
        evaluation["system"]:
        evaluation["queries"]
        for evaluation in evaluations
    }

    query_count = len(
        evaluations[0]["queries"]
    )

    for index in range(
        query_count
    ):

        query = evaluations[
            0
        ]["queries"][index]["query"]

        print()
        print(
            f'"{query}"'
        )

        for system_name, queries in (
            system_lookup.items()
        ):

            rank = queries[
                index
            ]["first_relevant_rank"]

            rank_display = (
                f"#{rank}"
                if rank is not None
                else "MISS"
            )

            print(
                f"  {system_name:<10} "
                f"{rank_display}"
            )


# ---------------------------------------------------------
# Main
# ---------------------------------------------------------

def main() -> None:

    print(
        "Loading evaluation benchmark..."
    )

    questions = load_questions()

    print(
        f"Loaded {len(questions)} questions."
    )

    print()
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

    print()
    print(
        "Preparing BM25..."
    )

    bm25_index = BM25Index(
        chunks
    )

    # -----------------------------------------------------
    # Semantic
    # -----------------------------------------------------

    print(
        "Preparing semantic index..."
    )

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
    # Search wrappers
    # -----------------------------------------------------

    def bm25_search(
        query: str,
        top_k: int,
    ) -> list[dict]:

        return bm25_index.search(
            query=query,
            top_k=top_k,
        )

    def semantic_search(
        query: str,
        top_k: int,
    ) -> list[dict]:

        return semantic_index.search(
            query=query,
            top_k=top_k,
        )

    def combined_search(
        query: str,
        top_k: int,
    ) -> list[dict]:

        return hybrid_search(
            query=query,
            bm25_index=bm25_index,
            semantic_index=semantic_index,
            top_k=top_k,
            candidate_k=20,
        )

    # -----------------------------------------------------
    # Evaluate
    # -----------------------------------------------------

    evaluations = [
        evaluate_system(
            name="BM25",
            search_function=bm25_search,
            questions=questions,
        ),
        evaluate_system(
            name="Semantic",
            search_function=semantic_search,
            questions=questions,
        ),
        evaluate_system(
            name="Hybrid",
            search_function=combined_search,
            questions=questions,
        ),
    ]

    display_evaluation(
        evaluations
    )


if __name__ == "__main__":
    main()