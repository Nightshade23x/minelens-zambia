from __future__ import annotations

import streamlit as st

from app.rag import get_installed_models


@st.cache_data(
    ttl=15,
    show_spinner=False,
)
def installed_models() -> tuple[list[str], str | None]:
    """
    Retrieve locally installed Ollama models.

    Deterministic MineLens answers can still work
    if Ollama is unavailable.
    """

    try:
        return (
            get_installed_models(),
            None,
        )

    except Exception as error:
        return (
            [],
            str(error),
        )


def render_sidebar() -> dict:
    """
    Render the MineLens search configuration sidebar.

    Returns the selected frontend settings.
    """

    with st.sidebar:

        st.title(
            "MineLens"
        )

        st.caption(
            "Search configuration"
        )

        st.divider()

        models, model_error = (
            installed_models()
        )

        model_options = [
            "Auto"
        ]

        model_options.extend(
            models
        )

        selected_model = st.selectbox(
            "Answer model",
            options=model_options,
            index=0,
            help=(
                "Auto uses MineLens' preferred "
                "local Ollama model."
            ),
        )

        route_choice = st.selectbox(
            "Search route",
            options=[
                "Auto",
                "Documents",
                "Licensing",
            ],
            index=0,
            help=(
                "Auto lets MineLens decide "
                "whether to search documents "
                "or structured licensing data."
            ),
        )

        with st.expander(
            "Advanced retrieval",
            expanded=False,
        ):

            top_k = st.slider(
                "Retrieval results",
                min_value=1,
                max_value=10,
                value=5,
            )

            evidence_k = st.slider(
                "Evidence sources",
                min_value=1,
                max_value=5,
                value=3,
            )

            show_raw = st.toggle(
                "Show retrieval details",
                value=False,
            )

        if model_error:

            st.warning(
                "Ollama is not reachable. "
                "Deterministic MineLens answers "
                "can still work."
            )

        st.divider()

        st.caption(
            "MineLens only generates answers "
            "from retrieved evidence. "
            "High-confidence structured queries "
            "may bypass the language model."
        )

    return {
        "selected_model": (
            selected_model
        ),
        "route_choice": (
            route_choice
        ),
        "top_k": (
            top_k
        ),
        "evidence_k": (
            evidence_k
        ),
        "show_raw": (
            show_raw
        ),
    }