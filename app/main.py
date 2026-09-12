from __future__ import annotations

import argparse

from app.hybrid import (
    DEFAULT_CANDIDATE_K,
    display_results as display_hybrid_results,
)

from app.licensing_search import (
    display_results as display_licensing_results,
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


# ---------------------------------------------------------
# Display
# ---------------------------------------------------------

def display_route(
    query: str,
    route: str,
    reason: str,
) -> None:
    """
    Display the routing decision before retrieval.
    """

    print()
    print("=" * 72)
    print("MINELENS ZAMBIA")
    print("=" * 72)

    print()
    print(f'Query: "{query}"')

    print()
    print(f"Route:  {route}")
    print(f"Reason: {reason}")
    print()


# ---------------------------------------------------------
# CLI
# ---------------------------------------------------------

def main() -> None:

    parser = argparse.ArgumentParser(
        description=(
            "MineLens Zambia unified mining "
            "intelligence search."
        )
    )

    parser.add_argument(
        "query",
        nargs="+",
        help=(
            "Mining question or search query"
        ),
    )

    parser.add_argument(
        "--top-k",
        type=int,
        default=DEFAULT_TOP_K,
        help=(
            "Maximum number of results "
            f"(default: {DEFAULT_TOP_K})"
        ),
    )

    parser.add_argument(
        "--candidate-k",
        type=int,
        default=DEFAULT_CANDIDATE_K,
        help=(
            "Document candidates retrieved "
            "from BM25 and semantic search "
            "before hybrid fusion"
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
        help=(
            "Override automatic routing "
            "(default: auto)"
        ),
    )

    parser.add_argument(
        "--include-superseded",
        action="store_true",
        help=(
            "Include superseded historical "
            "documents when the query routes "
            "to document search."
        ),
    )

    args = parser.parse_args()

    if args.top_k <= 0:
        raise ValueError(
            "--top-k must be greater than zero."
        )

    if args.candidate_k <= 0:
        raise ValueError(
            "--candidate-k must be greater than zero."
        )

    query = " ".join(
        args.query
    )

    # -----------------------------------------------------
    # Determine route for display
    # -----------------------------------------------------

    if args.route == "auto":

        route_info = route_query(
            query
        )

        force_route = None

    else:

        route_info = {
            "route": args.route,
            "reason": (
                "Route selected manually "
                "using --route."
            ),
        }

        force_route = args.route

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
    # Execute search
    # -----------------------------------------------------

    result = search_mine(
        query=query,
        top_k=args.top_k,
        candidate_k=args.candidate_k,
        include_superseded=(
            args.include_superseded
        ),
        force_route=force_route,
    )

    # -----------------------------------------------------
    # Display subsystem results
    # -----------------------------------------------------

    if (
        result["route"]
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


if __name__ == "__main__":
    main()