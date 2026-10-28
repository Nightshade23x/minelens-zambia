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
    display_licensing_decision_changes,
    display_licensing_history,
    display_licensing_record,
    licensing_answer_summary,
    licensing_history_answer_summary,
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



from frontend.components.exploration import (
    display_exploration_results,
)

from app.evidence import normalize_evidence  # noqa: E402
from app.facility_answers import (  # noqa: E402
    answer_facility_result,
)
from app.rag import (  # noqa: E402

    answer_from_evidence,



)

from app.router import (  # noqa: E402
    ROUTE_DOCUMENTS,
    ROUTE_LICENSING,
    ROUTE_MINING_STATISTICS,
    ROUTE_FACILITIES,
    ROUTE_EXPLORATION,
    route_query,
    search_mine,
)

from app.mining_statistics import (  # noqa: E402

    answer_statistics_result,

)

from frontend.components.statistics import (

    display_statistics_results,

)
from frontend.components.facilities import (
    display_facility_results,
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








# =========================================================

# LICENSING SUMMARY

# =========================================================








# =========================================================

# LICENSING DISPLAY

# =========================================================








# =========================================================

# RAW RETRIEVAL DISPLAY

# =========================================================





# =========================================================

# HEADER

# =========================================================



st.markdown(
    (
        '<div class="minelens-eyebrow">'
        'Zambia Mining Intelligence'
        '</div>'
        '<div class="minelens-title">'
        'MineLens Zambia'
        '</div>'
        '<div class="minelens-subtitle">'
        'Search official Zambian mining legislation, '
        'policy, licensing decisions, fees and strategic '
        'documents using evidence-grounded retrieval and '
        'local AI.'
        '</div>'
    ),
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


def fill_example_query(value: str) -> None:
    st.session_state["query_input"] = value
    st.session_state["last_result"] = None


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

    st.rerun()





# Homepage content below the search form.
if (
    not submitted
    and st.session_state.get("last_result") is None
):
    st.markdown("#### Try a question")

    example_questions = [
        (
            "Advanced mining projects",
            "Which mining projects are at advanced development in Zambia?",
        ),
        (
            "Mining licence fees",
            "What is the large-scale mining licence fee?",
        ),
        (
            "Copper production trends",
            "Zambia copper production from 2020 to 2024",
        ),
        (
            "Mine operators",
            "Who operates Kansanshi Mine?",
        ),
    ]

    left, right = st.columns(2)

    for index, (label, question) in enumerate(example_questions):
        column = left if index % 2 == 0 else right

        with column:
            st.button(
                label,
                key=f"example_question_{index}",
                use_container_width=True,
                on_click=fill_example_query,
                args=(question,),
            )

    st.divider()

    st.subheader("Explore the data")
    st.caption(
        "Access the MineLens data explorers."
    )

    explorers = [
        (
            "Licensing Explorer",
            "pages/1_Licensing_Explorer.py",
            "Browse mining licence applications and decisions.",
        ),
        (
            "Applicant Explorer",
            "pages/2_Applicant_Explorer.py",
            "Explore companies and their licensing activity.",
        ),
        (
            "Document Explorer",
            "pages/3_Document_Explorer.py",
            "Search official mining publications.",
        ),
        (
            "Commodity Explorer",
            "pages/4_Commodity_Explorer.py",
            "Analyze mineral commodities and licensing activity.",
        ),
        (
            "Location Explorer",
            "pages/5_Location_Explorer.py",
            "Explore province and district-level mining activity.",
        ),
    ]

    columns = st.columns(3)

    for index, (label, page, description) in enumerate(explorers):
        with columns[index % 3]:
            with st.container(border=True):
                st.page_link(
                    page,
                    label=label,
                )
                st.caption(description)


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

    elif route_choice == "Mining Statistics":

        force_route = (
            ROUTE_MINING_STATISTICS
        )

        route_info = {
            "route": ROUTE_MINING_STATISTICS,
            "reason": (
                "Mining statistics search "
                "selected manually."
            ),
        }

    elif route_choice == "Facilities":

        force_route = (
            ROUTE_FACILITIES
        )

        route_info = {
            "route": ROUTE_FACILITIES,
            "reason": (
                "Facility intelligence search "
                "selected manually."
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

            if (
                search_result.get(
                    "route"
                )
                in {
                    ROUTE_MINING_STATISTICS,
                    ROUTE_FACILITIES,
                }
            ):

                evidence = []

            else:

           

                effective_evidence_k = (
                    evidence_k
                )

                if search_result.get(
                    "preferred_source_ids"
                ):

                    effective_evidence_k = max(
                        effective_evidence_k,
                        5,
                    )

                # Document questions need enough candidates
                # for query-focused evidence selection.
                if search_result.get("route") == ROUTE_DOCUMENTS:
                    effective_evidence_k = max(
                        effective_evidence_k,
                        5,
                    )

                # Structured exploration answers should use
                # the same result set displayed in the table.
                if (
                    search_result.get(
                        "route"
                    )
                    == ROUTE_EXPLORATION
                ):
                    effective_evidence_k = max(
                        effective_evidence_k,
                        len(
                            search_result.get(
                                "results",
                                [],
                            )
                        ),
                    )

                evidence = normalize_evidence(
                    search_result=search_result,
                    max_evidence=effective_evidence_k,
                )

                # Keep document answers consistent with the CLI.
                if search_result.get("route") == ROUTE_DOCUMENTS:
                    from app.document_answer_selection import (
                        select_document_answer_evidence,
                    )

                    evidence = select_document_answer_evidence(
                        question=query,
                        evidence=evidence,
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

            if (
                search_result.get(
                    "route"
                )
                == ROUTE_MINING_STATISTICS
            ):

                answer_result = (
                    answer_statistics_result(
                        search_result
                    )
                )

            elif (
                search_result.get(
                    "route"
                )
                == ROUTE_FACILITIES
            ):

                answer_result = (
                    answer_facility_result(
                        query=query,
                        search_result=search_result,
                    )
                )

            else:

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
            in {
                ROUTE_MINING_STATISTICS,
                ROUTE_FACILITIES,
            }
        ):

            frontend_answer = str(
                answer_result.get(
                    "answer",
                    ""
                )
                or ""
            ).strip()

        elif (
            route_info.get(
                "route"
            )
            == ROUTE_LICENSING
        ):

            licensing_filters = (
                search_result.get(
                    "filters",
                    {},
                )
            )

            decision_change_mode = bool(
                licensing_filters.get(
                    "decision_changes"
                )
            )

            history_mode = bool(
                licensing_filters.get(
                    "history"
                )
            )

            if decision_change_mode:

                frontend_answer = None

            elif history_mode:

                frontend_answer = (
                    licensing_history_answer_summary(
                        evidence
                    )
                )

            else:

                frontend_answer = (
                    licensing_answer_summary(
                        evidence
                    )
                )

        if not frontend_answer:

            frontend_answer = str(
                answer_result.get(
                    "answer"
                )
                or ""
            ).strip()

        with st.container(
            border=True,
        ):

            answer_lines = (
                frontend_answer.rstrip().splitlines()
            )

            if len(answer_lines) > 1:
                last_line = answer_lines[-1].strip()

                is_source_id = (
                    last_line.startswith("[S")
                    and last_line.endswith("]")
                    and last_line[2:-1].isdigit()
                )

                preceding = "\n".join(
                    answer_lines[:-1]
                ).rstrip()

                if is_source_id and last_line in preceding:
                    frontend_answer = preceding

            st.markdown(frontend_answer)

        with st.popover("Copy answer"):
            st.code(
                frontend_answer,
                language=None,
                wrap_lines=True,
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

    # Compact technical details, hidden by default.
    if route_info.get("route") in {
        ROUTE_MINING_STATISTICS,
        ROUTE_FACILITIES,
    }:
        count_label = "Records"
        count_value = len(
            search_result.get("results", [])
        )
    else:
        count_label = "Evidence sources"
        count_value = len(evidence)

    with st.expander(
        "Search details",
        expanded=False,
    ):
        st.markdown(
            "**Search route:** "
            + route_label(route_info["route"])
        )

        st.markdown(
            f"**{count_label}:** {count_value}"
        )

        st.markdown(
            "**Answer mode:** "
            + generation_label(generation_method)
        )

        reason = route_info.get("reason", "")

        if reason:
            st.caption(reason)

        if model_name:
            st.caption(
                f"Local model: {model_name}"
            )
        elif answer_result:
            st.caption(
                "Language model not required "
                "for this answer."
            )

    # =====================================================
    # MINING STATISTICS
    # =====================================================

    if (
        route_info.get(
            "route"
        )
        == ROUTE_MINING_STATISTICS
    ):

        display_statistics_results(
            search_result
        )

    # =====================================================
    # FACILITIES
    # =====================================================

    if (
        route_info.get(
            "route"
        )
        == ROUTE_FACILITIES
    ):

        display_facility_results(
            search_result
        )
    # =====================================================
# LICENSING RECORDS
# =====================================================

    # =====================================================
    # EXPLORATION RESULTS
    # =====================================================

    if (
        search_result.get(
            "route"
        )
        == ROUTE_EXPLORATION
    ):

        display_exploration_results(
            search_result
        )

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

        licensing_filters = (
            search_result.get(
                "filters",
                {},
            )
        )

        decision_change_mode = bool(
            licensing_filters.get(
                "decision_changes"
            )
        )

        history_mode = bool(
            licensing_filters.get(
                "history"
            )
        )

        if decision_change_mode:

            display_licensing_decision_changes(
                licensing_evidence
            )

        elif history_mode:

            st.subheader(
                "Licence decision history"
            )

            display_licensing_history(
                licensing_evidence
            )

        else:

            st.subheader(
                (
                    "Licence record"
                    if len(
                        licensing_evidence
                    ) == 1
                    else "Licence records"
                )
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

    # Combined references, collapsed by default.
    document_evidence = [
        item
        for item in evidence
        if item.get("evidence_type") == "document"
    ]

    if sources or document_evidence:
        with st.expander(
            "Sources and supporting evidence",
            expanded=False,
        ):
            st.caption(
                f"{len(sources)} cited source(s) ? "
                f"{len(document_evidence)} document excerpt(s)"
            )

            if sources:
                display_sources(sources)

            if document_evidence:
                st.markdown("#### Supporting excerpts")

                for item in document_evidence:
                    source_id = str(
                        item.get("source_id") or ""
                    ).strip()

                    title = str(
                        item.get("title")
                        or item.get("document")
                        or "Document"
                    ).strip()

                    pages = str(
                        item.get("pages") or ""
                    ).strip()

                    excerpt = str(
                        item.get("text") or ""
                    ).strip()

                    with st.container(border=True):
                        label = (
                            f"[{source_id}] {title}"
                            if source_id
                            else title
                        )

                        st.markdown(f"**{label}**")

                        if pages:
                            st.caption(f"Pages {pages}")

                        st.markdown(
                            excerpt
                            or "No text excerpt is available."
                        )


    # =====================================================
    # DEBUG / RETRIEVAL DETAILS
    # =====================================================

    if show_raw:

        display_retrieval_details(
            search_result
        )
