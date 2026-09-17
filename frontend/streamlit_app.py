from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any
from frontend.styles.theme import apply_theme
import streamlit as st
from frontend.utils.display import (
    clean_text,
    friendly_source_title,
    generation_label,
    looks_like_filename,
    prettify_filename,
    route_label,
    source_agency,
)
from frontend.components.licensing import (
    display_licensing_record,
    licensing_answer_summary,
)
from frontend.components.sources import (
    display_sources,
)
from frontend.components.sidebar import (
    render_sidebar,
)
from frontend.components.retrieval import (
    display_retrieval_details,
)
from frontend.components.documents import (
    display_document_evidence,
)
# =========================================================
# PROJECT PATH
# =========================================================

ROOT_DIR = Path(__file__).resolve().parents[1]

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(ROOT_DIR),
    )


# =========================================================
# MINELENS IMPORTS
# =========================================================

from app.evidence import normalize_evidence  # noqa: E402
from app.rag import (  # noqa: E402
    answer_from_evidence,
    
)
from app.router import (  # noqa: E402
    ROUTE_DOCUMENTS,
    ROUTE_LICENSING,
    route_query,
    search_mine,
)


# =========================================================
# PAGE CONFIGURATION
# =========================================================

st.set_page_config(
    page_title="MineLens Zambia",
    page_icon="⛏️",
    layout="wide",
    initial_sidebar_state="expanded",
)


# =========================================================
# SESSION STATE
# =========================================================

if "query_input" not in st.session_state:
    st.session_state["query_input"] = ""

if "last_result" not in st.session_state:
    st.session_state["last_result"] = None


# =========================================================
# STYLING
# =========================================================

apply_theme()

# =========================================================
# BASIC HELPERS
# =========================================================




def clear_search() -> None:
    st.session_state["query_input"] = ""
    st.session_state["last_result"] = None


@st.cache_data(
    ttl=15,
    show_spinner=False,
)

# =========================================================
# LICENSING SUMMARY
# =========================================================

def licensing_answer_summary(
    evidence: list[dict],
) -> str | None:
    """
    Build a concise frontend summary for an exact
    structured licence result.

    The complete structured record is displayed below,
    so there is no need to repeat every field in the
    main answer.
    """

    licensing_items = [
        item
        for item in evidence
        if (
            item.get(
                "evidence_type"
            )
            == "licensing_record"
        )
    ]

    if len(
        licensing_items
    ) != 1:
        return None

    item = licensing_items[0]

    record = item.get(
        "record",
        {},
    )

    source_id = clean_text(
        item.get(
            "source_id"
        )
    ) or "S1"

    licence_code = clean_text(
        record.get(
            "licence_code"
        )
    )

    applicant = clean_text(
        record.get(
            "applicant"
        )
    )

    decision = clean_text(
        record.get(
            "decision"
        )
    )

    licence_type = clean_text(
        record.get(
            "licence_type"
        )
    )

    province = clean_text(
        record.get(
            "province"
        )
    )

    districts = record.get(
        "districts",
        [],
    )

    if isinstance(
        districts,
        list,
    ):
        district = ", ".join(
            clean_text(value)
            for value in districts
            if clean_text(value)
        )

    else:
        district = clean_text(
            districts
        )

    if not licence_code:
        return None

    first_sentence = (
        f"Licence {licence_code}"
    )

    if applicant:
        first_sentence += (
            f" for {applicant}"
        )

    if decision:
        first_sentence += (
            f" was {decision.lower()}."
        )

    else:
        first_sentence += "."

    second_parts: list[str] = []

    if licence_type:
        second_parts.append(
            f"It is a {licence_type}"
        )

    location_parts = [
        part
        for part in [
            district,
            province,
        ]
        if part
    ]

    if location_parts:

        if second_parts:
            second_parts[
                0
            ] += (
                " in "
                + ", ".join(
                    location_parts
                )
            )

        else:
            second_parts.append(
                "The recorded location is "
                + ", ".join(
                    location_parts
                )
            )

    if second_parts:
        second_sentence = (
            second_parts[0]
            + "."
        )

    else:
        second_sentence = ""

    return clean_text(
        f"{first_sentence} "
        f"{second_sentence} "
        f"[{source_id}]"
    )


# =========================================================
# LICENSING DISPLAY
# =========================================================

def display_licensing_record(
    evidence_item: dict,
) -> None:

    record = evidence_item.get(
        "record",
        {},
    )

    licence_code = clean_text(
        record.get(
            "licence_code"
        )
    )

    licence_type = clean_text(
        record.get(
            "licence_type"
        )
    )

    applicant = clean_text(
        record.get(
            "applicant"
        )
    )

    decision = clean_text(
        record.get(
            "decision"
        )
    )

    province = clean_text(
        record.get(
            "province"
        )
    )

    districts = record.get(
        "districts",
        [],
    )

    commodities = record.get(
        "commodities",
        [],
    )

    area_text = clean_text(
        record.get(
            "area_text"
        )
    )

    deadline = clean_text(
        record.get(
            "deadline"
        )
    )

    if isinstance(
        districts,
        list,
    ):
        district_text = ", ".join(
            clean_text(item)
            for item in districts
            if clean_text(item)
        )

    else:
        district_text = clean_text(
            districts
        )

    if isinstance(
        commodities,
        list,
    ):
        commodity_text = ", ".join(
            clean_text(item)
            for item in commodities
            if clean_text(item)
        )

    else:
        commodity_text = clean_text(
            commodities
        )

    with st.container(
        border=True,
    ):

        top_left, top_right = (
            st.columns(
                [4, 1]
            )
        )

        with top_left:

            st.markdown(
                f"### {licence_code or 'Licence record'}"
            )

            if licence_type:
                st.caption(
                    licence_type
                )

        with top_right:

            if decision:

                if (
                    decision.lower()
                    == "approved"
                ):
                    st.success(
                        decision
                    )

                elif (
                    decision.lower()
                    == "rejected"
                ):
                    st.error(
                        decision
                    )

                else:
                    st.info(
                        decision
                    )

        st.divider()

        left_column, right_column = (
            st.columns(
                2
            )
        )

        with left_column:

            st.markdown(
                f"**Applicant**  \n"
                f"{applicant or '—'}"
            )

            st.markdown(
                f"**Area**  \n"
                f"{area_text or '—'}"
            )

            if commodity_text:
                st.markdown(
                    f"**Commodities**  \n"
                    f"{commodity_text}"
                )

        with right_column:

            st.markdown(
                f"**Province**  \n"
                f"{province or '—'}"
            )

            st.markdown(
                f"**District**  \n"
                f"{district_text or '—'}"
            )

            st.markdown(
                f"**Stipulated timeframe**  \n"
                f"{deadline or '—'}"
            )


# =========================================================
# RAW RETRIEVAL DISPLAY
# =========================================================


# =========================================================
# HEADER
# =========================================================

st.markdown(
    """
    <div class="minelens-eyebrow">
        Zambia Mining Intelligence
    </div>

    <div class="minelens-title">
        MineLens Zambia
    </div>

    <div class="minelens-subtitle">
        Search official Zambian mining legislation,
        policy, licensing decisions, fees and strategic
        documents using evidence-grounded retrieval and
        local AI.
    </div>
    """,
    unsafe_allow_html=True,
)
# =========================================================
# SIDEBAR
# =========================================================

sidebar_settings = (
    render_sidebar()
)

selected_model = (
    sidebar_settings[
        "selected_model"
    ]
)

route_choice = (
    sidebar_settings[
        "route_choice"
    ]
)

top_k = (
    sidebar_settings[
        "top_k"
    ]
)

evidence_k = (
    sidebar_settings[
        "evidence_k"
    ]
)

show_raw = (
    sidebar_settings[
        "show_raw"
    ]
)


# =========================================================
# SEARCH AREA
# =========================================================

st.markdown(
    """
    <div class="example-text">
        Examples:
        large-scale mining licence fee ·
        42553-HQ-LML ·
        Zambia's critical minerals ·
        goal of the National Critical Minerals Strategy
    </div>
    """,
    unsafe_allow_html=True,
)


with st.form(
    "minelens_search",
    clear_on_submit=False,
):

    query = st.text_input(
        "Ask MineLens",
        placeholder=(
            "Ask about a licence, mining fee, "
            "law, policy or official mining document..."
        ),
        label_visibility="collapsed",
        key="query_input",
    )

    search_column, clear_column = (
        st.columns(
            [5, 1]
        )
    )

    with search_column:

        submitted = (
            st.form_submit_button(
                "Search MineLens",
                type="primary",
                use_container_width=True,
            )
        )

    with clear_column:

        clear_clicked = (
            st.form_submit_button(
                "Clear",
                use_container_width=True,
                on_click=clear_search,
            )
        )


if clear_clicked:
    st.stop()


# =========================================================
# EXECUTE NEW SEARCH
# =========================================================

if submitted:

    query = query.strip()

    if not query:

        st.warning(
            "Enter a mining question first."
        )

        st.stop()

    st.session_state[
        "last_result"
    ] = None

    # -----------------------------------------------------
    # Model
    # -----------------------------------------------------

    if selected_model == "Auto":
        model_override = None

    else:
        model_override = (
            selected_model
        )

    # -----------------------------------------------------
    # Route
    # -----------------------------------------------------

    if route_choice == "Documents":

        force_route = (
            ROUTE_DOCUMENTS
        )

        route_info = {
            "route": ROUTE_DOCUMENTS,
            "reason": (
                "Document search selected manually."
            ),
        }

    elif route_choice == "Licensing":

        force_route = (
            ROUTE_LICENSING
        )

        route_info = {
            "route": ROUTE_LICENSING,
            "reason": (
                "Licensing search selected manually."
            ),
        }

    else:

        force_route = None

        route_info = route_query(
            query
        )

    # -----------------------------------------------------
    # Retrieval
    # -----------------------------------------------------

    with st.spinner(
        "Searching official mining sources..."
    ):

        try:

            search_result = search_mine(
                query=query,
                top_k=top_k,
                force_route=force_route,
            )

            evidence = normalize_evidence(
                search_result=search_result,
                max_evidence=evidence_k,
            )

        except Exception as error:

            st.error(
                "MineLens could not complete "
                "the search."
            )

            st.exception(
                error
            )

            st.stop()

    # -----------------------------------------------------
    # Answer generation
    # -----------------------------------------------------

    with st.spinner(
        "Preparing grounded answer..."
    ):

        try:

            answer_result = (
                answer_from_evidence(
                    question=query,
                    evidence=evidence,
                    model=model_override,
                )
            )

            generation_error = None

        except Exception as error:

            answer_result = None

            generation_error = (
                f"{type(error).__name__}: "
                f"{error}"
            )

    # -----------------------------------------------------
    # Persist result
    # -----------------------------------------------------

    st.session_state[
        "last_result"
    ] = {
        "query": query,
        "route_info": route_info,
        "search_result": search_result,
        "evidence": evidence,
        "answer_result": answer_result,
        "generation_error": generation_error,
    }


# =========================================================
# DISPLAY PERSISTED RESULT
# =========================================================

result_state = st.session_state.get(
    "last_result"
)

if result_state:

    query = result_state[
        "query"
    ]

    route_info = result_state[
        "route_info"
    ]

    search_result = result_state[
        "search_result"
    ]

    evidence = result_state[
        "evidence"
    ]

    answer_result = result_state[
        "answer_result"
    ]

    generation_error = result_state[
        "generation_error"
    ]

    st.divider()

    # =====================================================
    # ANSWER
    # =====================================================

    st.subheader(
        "Answer"
    )

    if generation_error:

        st.error(
            "MineLens retrieved evidence, "
            "but the generated answer did "
            "not pass validation."
        )

        st.caption(
            generation_error
        )

    else:

        frontend_answer = None

        if (
            route_info.get(
                "route"
            )
            == ROUTE_LICENSING
        ):
            frontend_answer = (
                licensing_answer_summary(
                    evidence
                )
            )

        if not frontend_answer:
            frontend_answer = clean_text(
                answer_result.get(
                    "answer"
                )
            )

        with st.container(
            border=True,
        ):

            st.markdown(
                frontend_answer
            )

    # =====================================================
    # RESULT METADATA
    # =====================================================

    generation_method = None
    model_name = None

    if answer_result:

        generation_method = (
            answer_result.get(
                "generation_method"
            )
        )

        model_name = (
            answer_result.get(
                "model"
            )
        )

    metadata_1, metadata_2, metadata_3 = (
        st.columns(
            3
        )
    )

    with metadata_1:

        with st.container(
            border=True,
        ):

            st.metric(
                "Search route",
                route_label(
                    route_info[
                        "route"
                    ]
                ),
            )

    with metadata_2:

        with st.container(
            border=True,
        ):

            st.metric(
                "Evidence",
                len(
                    evidence
                ),
            )

    with metadata_3:

        with st.container(
            border=True,
        ):

            st.metric(
                "Answer mode",
                generation_label(
                    generation_method
                ),
            )

    st.caption(
        route_info.get(
            "reason",
            "",
        )
    )

    if model_name:

        st.caption(
            f"Local model: "
            f"{model_name}"
        )

    elif answer_result:

        st.caption(
            "Language model not required "
            "for this answer."
        )
# =====================================================
# DOCUMENT EVIDENCE
# =====================================================

    if (
        route_info.get("route")
        == ROUTE_DOCUMENTS
    ):
        display_document_evidence(
            evidence
        )
    # =====================================================
    # LICENSING RECORDS
    # =====================================================

    licensing_evidence = [
        item
        for item in evidence
        if (
            item.get(
                "evidence_type"
            )
            == "licensing_record"
        )
    ]

    if licensing_evidence:

        st.subheader(
            "Licence record"
            if len(
                licensing_evidence
            ) == 1
            else "Licence records"
        )

        for item in licensing_evidence:

            display_licensing_record(
                item
            )

    # =====================================================
    # SOURCES
    # =====================================================

    if (
        answer_result is not None
        and answer_result.get(
            "sources"
        )
    ):

        sources = (
            answer_result[
                "sources"
            ]
        )

    else:

        sources = [
            {
                "source_id": (
                    item.get(
                        "source_id"
                    )
                ),
                "title": (
                    item.get(
                        "title"
                    )
                ),
                "document": (
                    item.get(
                        "document"
                    )
                ),
                "pages": (
                    item.get(
                        "pages"
                    )
                ),
                "source_url": (
                    item.get(
                        "source_url"
                    )
                ),
                "agency": (
                    item.get(
                        "agency"
                    )
                ),
            }
            for item in evidence
        ]

    display_sources(
        sources
    )

    # =====================================================
    # DEBUG / RETRIEVAL DETAILS
    # =====================================================

    if show_raw:
        display_retrieval_details(
            search_result
        )