from __future__ import annotations

from pathlib import Path

import streamlit as st

from frontend.utils.display import (
    clean_text,
    friendly_source_title,
    source_agency,
)


def display_source(
    source: dict,
) -> None:
    """
    Render one official MineLens source card.
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

        if agency:
            st.caption(
                agency
            )

        details: list[str] = []

        if document:
            details.append(
                Path(document).name
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
                "View official source",
                source_url,
            )


def display_sources(
    sources: list[dict],
) -> None:
    """
    Render the complete official sources section.
    """

    if not sources:
        return

    st.subheader(
        "Official sources"
    )

    for source in sources:
        display_source(
            source
        )