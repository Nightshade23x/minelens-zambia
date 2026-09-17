from __future__ import annotations

import streamlit as st

from frontend.utils.display import (
    clean_text,
    friendly_source_title,
)


def _evidence_title(
    item: dict,
) -> str:
    """
    Return the best display title for document evidence.
    """

    return friendly_source_title(
        {
            "title": item.get("title"),
            "document": item.get("document"),
        }
    )


def _evidence_excerpt(
    item: dict,
    max_chars: int = 1100,
) -> str:
    """
    Return a readable excerpt from normalized evidence.
    """

    text = clean_text(
        item.get("text")
    )

    if not text:
        return "No text excerpt is available."

    if len(text) <= max_chars:
        return text

    return (
        text[:max_chars].rstrip()
        + "..."
    )


def display_document_evidence(
    evidence: list[dict],
) -> None:
    """
    Render the document evidence used to prepare
    a MineLens answer.

    Only document evidence is shown here.
    """

    document_evidence = [
        item
        for item in evidence
        if (
            item.get("evidence_type")
            == "document"
        )
    ]

    if not document_evidence:
        return

    st.subheader(
        "Evidence used"
    )

    st.caption(
        "Relevant excerpts retrieved from official "
        "documents before answer generation."
    )

    for item in document_evidence:

        source_id = clean_text(
            item.get("source_id")
        )

        title = _evidence_title(
            item
        )

        pages = clean_text(
            item.get("pages")
        )

        excerpt = _evidence_excerpt(
            item
        )

        label_parts: list[str] = []

        if source_id:
            label_parts.append(
                f"[{source_id}]"
            )

        label_parts.append(
            title
        )

        if pages:
            label_parts.append(
                f"Pages {pages}"
            )

        label = " · ".join(
            label_parts
        )

        with st.expander(
            label,
            expanded=False,
        ):

            st.markdown(
                excerpt
            )

            context_chunk_ids = (
                item.get(
                    "context_chunk_ids",
                    [],
                )
            )

            if context_chunk_ids:

                if isinstance(
                    context_chunk_ids,
                    list,
                ):
                    context_text = ", ".join(
                        clean_text(value)
                        for value
                        in context_chunk_ids
                        if clean_text(value)
                    )

                else:
                    context_text = clean_text(
                        context_chunk_ids
                    )

                if context_text:
                    st.caption(
                        "Expanded context chunks: "
                        + context_text
                    )