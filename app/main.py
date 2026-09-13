from __future__ import annotations

import argparse

from app.evidence import (
    normalize_evidence,
)

from app.hybrid import (
    DEFAULT_CANDIDATE_K,
    display_results as display_hybrid_results,
)

from app.licensing_search import (
    display_results as display_licensing_results,
)

from app.rag import (
    display_answer,
    answer_from_evidence,
)

from app.router import (
    ROUTE_DOCUMENTS,
    ROUTE_LICENSING,
    route_query,
    search_mine,
)


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

DEFAULT_TOP_K = 5

DEFAULT_EVIDENCE_K = 3


# ---------------------------------------------------------
# Display
# ---------------------------------------------------------

def display_route(
    query: str,
    route: str,
    reason: str,
) -> None:

    print()

    print(
        "=" * 72
    )

    print(
        "MINELENS ZAMBIA"
    )

    print(
        "=" * 72
    )

    print()

    print(
        f'Query: "{query}"'
    )

    print()

    print(
        f"Route:  {route}"
    )

    print(
        f"Reason: {reason}"
    )

    print()


# ---------------------------------------------------------
# CLI
# ---------------------------------------------------------

def main() -> None:

    parser = argparse.ArgumentParser(
        description=(
            "MineLens Zambia mining "
            "intelligence assistant."
        )
    )

    parser.add_argument(
        "query",
        nargs="+",
        help=(
            "Mining question"
        ),
    )

    parser.add_argument(
        "--top-k",
        type=int,
        default=DEFAULT_TOP_K,
        help=(
            "Number of retrieval "
            "results"
        ),
    )

    parser.add_argument(
        "--evidence-k",
        type=int,
        default=DEFAULT_EVIDENCE_K,
        help=(
            "Number of retrieved "
            "items supplied to RAG"
        ),
    )

    parser.add_argument(
        "--candidate-k",
        type=int,
        default=DEFAULT_CANDIDATE_K,
        help=(
            "Hybrid retrieval "
            "candidate count"
        ),
    )

    parser.add_argument(
        "--route",
        choices=[
            "auto",
            ROUTE_DOCUMENTS,
            ROUTE_LICENSING,
        ],
        default="auto",
    )

    parser.add_argument(
        "--model",
        help=(
            "Explicit installed "
            "Ollama model"
        ),
    )

    parser.add_argument(
        "--raw",
        action="store_true",
        help=(
            "Show raw retrieval "
            "results instead of "
            "generating an answer"
        ),
    )

    parser.add_argument(
        "--include-superseded",
        action="store_true",
    )

    args = parser.parse_args()

    if args.top_k <= 0:

        raise ValueError(
            "--top-k must be "
            "greater than zero."
        )

    if args.evidence_k <= 0:

        raise ValueError(
            "--evidence-k must be "
            "greater than zero."
        )

    if args.candidate_k <= 0:

        raise ValueError(
            "--candidate-k must be "
            "greater than zero."
        )

    query = " ".join(
        args.query
    )

    # -----------------------------------------------------
    # Route
    # -----------------------------------------------------

    if args.route == "auto":

        route_info = route_query(
            query
        )

        force_route = None

    else:

        route_info = {
            "route": (
                args.route
            ),
            "reason": (
                "Route selected manually "
                "using --route."
            ),
        }

        force_route = (
            args.route
        )

    display_route(
        query=query,
        route=route_info[
            "route"
        ],
        reason=route_info[
            "reason"
        ],
    )

    # -----------------------------------------------------
    # Retrieval
    # -----------------------------------------------------

    result = search_mine(
        query=query,
        top_k=args.top_k,
        candidate_k=(
            args.candidate_k
        ),
        include_superseded=(
            args.include_superseded
        ),
        force_route=(
            force_route
        ),
    )

    # -----------------------------------------------------
    # Raw/debug mode
    # -----------------------------------------------------

    if args.raw:

        if (
            result[
                "route"
            ]
            == ROUTE_LICENSING
        ):

            display_licensing_results(
                query=query,
                results=result[
                    "results"
                ],
                filters=result[
                    "filters"
                ],
            )

        else:

            display_hybrid_results(
                query=query,
                results=result[
                    "results"
                ],
            )

        return

    # -----------------------------------------------------
    # Evidence normalization
    # -----------------------------------------------------

    evidence = normalize_evidence(
        search_result=result,
        max_evidence=(
            args.evidence_k
        ),
    )

    # -----------------------------------------------------
    # Grounded answer generation
    # -----------------------------------------------------

    rag_result = (
        answer_from_evidence(
            question=query,
            evidence=evidence,
            model=args.model,
        )
    )

    display_answer(
        rag_result
    )


if __name__ == "__main__":
    main()