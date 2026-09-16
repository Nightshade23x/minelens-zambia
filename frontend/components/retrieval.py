from __future__ import annotations

import streamlit as st

from app.router import ROUTE_LICENSING
from frontend.utils.display import (
    clean_text,
    looks_like_filename,
    prettify_filename,
)


def display_raw_document_results(
    results: list[dict],
) -> None:
    """
    Developer view for document retrieval results.
    """

    for index, result in enumerate(
        results,
        start=1,
    ):
        chunk = result.get(
            "chunk",
            {},
        )

        title = clean_text(
            chunk.get("source_title")
            or chunk.get("document")
            or "Document"
        )

        if looks_like_filename(
            title
        ):
            title = prettify_filename(
                title
            )

        page_start = chunk.get(
            "page_start"
        )

        page_end = chunk.get(
            "page_end"
        )

        if (
            page_start is not None
            and page_end is not None
        ):
            if page_start == page_end:
                pages = str(
                    page_start
                )
            else:
                pages = (
                    f"{page_start}-{page_end}"
                )
        else:
            pages = "—"

        text = clean_text(
            chunk.get("text")
        )

        if len(text) > 900:
            text = (
                text[:900]
                + "..."
            )

        with st.expander(
            f"{index}. {title} · pages {pages}"
        ):
            if "rrf_score" in result:
                st.caption(
                    "Hybrid score: "
                    f"{result.get('rrf_score', 0):.6f}"
                )

            st.markdown(
                text
            )

            context_chunks = result.get(
                "context_chunks",
                [],
            )

            if context_chunks:
                context_ids = [
                    clean_text(
                        item.get("chunk_id")
                    )
                    for item in context_chunks
                    if clean_text(
                        item.get("chunk_id")
                    )
                ]

                if context_ids:
                    st.caption(
                        "Expanded context: "
                        + ", ".join(
                            context_ids
                        )
                    )


def display_raw_licensing_results(
    results: list[dict],
) -> None:
    """
    Developer view for structured licensing results.
    """

    for index, result in enumerate(
        results,
        start=1,
    ):
        chunk = result.get(
            "chunk",
            {},
        )

        code = clean_text(
            chunk.get("licence_code")
        )

        applicant = clean_text(
            chunk.get("applicant")
        )

        decision = clean_text(
            chunk.get("decision")
        )

        label = (
            f"{index}. "
            f"{code or 'Licence'}"
        )

        if applicant:
            label += (
                f" · {applicant}"
            )

        with st.expander(
            label
        ):
            if decision:
                st.markdown(
                    f"**Decision:** {decision}"
                )

            st.json(
                chunk,
                expanded=False,
            )


def display_retrieval_details(
    search_result: dict,
) -> None:
    """
    Render MineLens retrieval diagnostics.

    Intended for development and debugging,
    not the normal user-facing result.
    """

    st.divider()

    st.subheader(
        "Retrieval details"
    )

    st.caption(
        "Developer view of the retrieved "
        "results before answer generation."
    )

    results = search_result.get(
        "results",
        [],
    )

    if (
        search_result.get("route")
        == ROUTE_LICENSING
    ):
        filters = search_result.get(
            "filters",
            {},
        )

        if filters:
            st.markdown(
                "**Structured filters**"
            )

            st.json(
                filters,
                expanded=False,
            )

        display_raw_licensing_results(
            results
        )

    else:
        display_raw_document_results(
            results
        )