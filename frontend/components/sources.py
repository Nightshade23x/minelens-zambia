from __future__ import annotations

from pathlib import Path

import streamlit as st

from frontend.utils.display import (
    clean_text,
    friendly_source_title,
    source_agency,
    source_authority_label,
)


def display_source(
    source: dict,
) -> None:
    """
    Render one MineLens source card.
    """

    source_id = clean_text(
        source.get("source_id")
    )

    title = friendly_source_title(
        source
    )

    agency = source_agency(
        source
    )

    authority_label = (
        source_authority_label(
            source
        )
    )

    document = clean_text(
        source.get("document")
    )

    pages = clean_text(
        source.get("pages")
    )

    source_url = clean_text(
        source.get("source_url")
    )

    with st.container(
        border=True,
    ):

        header = title

        if source_id:
            header = (
                f"[{source_id}] {header}"
            )

        st.markdown(
            f"**{header}**"
        )

        if authority_label:
            st.caption(
                authority_label
            )

        if agency:
            st.caption(
                agency
            )

        details: list[str] = []

        if document:

            document_name = (
                Path(
                    document
                ).name
            )

            if (
                clean_text(
                    document_name
                ).casefold()
                != clean_text(
                    title
                ).casefold()
            ):
                details.append(
                    document_name
                )

        if pages:
            details.append(
                f"Pages {pages}"
            )

        if details:
            st.caption(
                " · ".join(
                    details
                )
            )

        if source_url:
            st.link_button(
                "View source",
                source_url,
            )


def display_sources(
    sources: list[dict],
) -> None:
    """
    Render the complete MineLens sources section.
    """

    if not sources:
        return

    st.subheader(
        "Sources"
    )

    for source in sources:
        display_source(
            source
        )