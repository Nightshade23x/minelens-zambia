from __future__ import annotations

import re

import streamlit as st

from app.evidence import normalize_evidence
from app.rag import answer_from_evidence
from app.router import search_documents
from frontend.components.documents import (
    display_document_evidence,
)
from frontend.utils.display import clean_text


# =========================================================
# COMMODITY NAMES
# =========================================================

COMMODITY_NAMES = {
    "Ag": "Silver",
    "Al": "Aluminium",
    "Au": "Gold",
    "Bi": "Bismuth",
    "Co": "Cobalt",
    "Cu": "Copper",
    "Fe": "Iron",
    "Li": "Lithium",
    "Mn": "Manganese",
    "Ni": "Nickel",
    "Pb": "Lead",
    "Sn": "Tin",
    "U": "Uranium",
    "Zn": "Zinc",
    "REE": "Rare Earth Elements",
    "REEs": "Rare Earth Elements",
    "Graphite": "Graphite",
    "Coltan": "Coltan",
}


# =========================================================
# HELPERS
# =========================================================

def commodity_name(
    commodity: str,
) -> str:
    """
    Convert common commodity codes into readable names.
    """

    return COMMODITY_NAMES.get(
        commodity,
        commodity,
    )


def canonical_decision(
    value: str,
) -> str:
    """
    Normalize decision labels used in the licensing data.
    """

    value = clean_text(
        value
    )

    aliases = {
        "approval": "Approved",
        "approved": "Approved",
        "defer": "Deferred",
        "deferred": "Deferred",
        "reject": "Rejected",
        "rejected": "Rejected",
    }

    return aliases.get(
        value.casefold(),
        value,
    )


def total_recorded_area(
    records: list[dict],
) -> float:
    """
    Calculate recorded licensing area.
    """

    total = 0.0

    for record in records:

        value = record.get(
            "area_hectares"
        )

        if isinstance(
            value,
            (int, float),
        ):
            total += float(
                value
            )

    return total


def licensing_snapshot(
    records: list[dict],
) -> dict:
    """
    Produce deterministic statistics from the structured
    licensing dataset.
    """

    approved = sum(
        canonical_decision(
            clean_text(
                record.get(
                    "decision"
                )
            )
        )
        == "Approved"
        for record in records
    )

    applicants = {
        clean_text(
            record.get(
                "applicant"
            )
        )
        for record in records
        if clean_text(
            record.get(
                "applicant"
            )
        )
    }

    provinces = {
        clean_text(
            record.get(
                "province"
            )
        )
        for record in records
        if clean_text(
            record.get(
                "province"
            )
        )
    }

    return {
        "records": len(
            records
        ),
        "approved": approved,
        "applicants": len(
            applicants
        ),
        "provinces": len(
            provinces
        ),
        "area": total_recorded_area(
            records
        ),
    }


def build_document_query(
    commodity: str,
) -> str:
    """
    Build a retrieval query for official MineLens documents.
    """

    name = commodity_name(
        commodity
    )

    if name.casefold() == commodity.casefold():

        return (
            f"{name} Zambia mining policy strategy "
            f"legislation statistics critical minerals"
        )

    return (
        f"{name} {commodity} Zambia mining policy strategy "
        f"legislation statistics critical minerals"
    )


def build_brief_question(
    commodity: str,
) -> str:
    """
    Build the question supplied to the grounded RAG system.
    """

    name = commodity_name(
        commodity
    )

    return (
        f"What do the available official Zambian mining "
        f"documents say about {name} ({commodity})? "
        f"Summarize its policy or strategic importance, "
        f"development context, priorities, and any other "
        f"relevant mining-sector information supported by "
        f"the evidence. Do not invent information that is "
        f"not contained in the supplied sources."
    )


def state_key(
    commodity: str,
) -> str:
    """
    Produce a safe Streamlit widget key.
    """

    safe_value = re.sub(
        r"[^A-Za-z0-9]+",
        "_",
        commodity,
    )

    return (
        f"commodity_brief_{safe_value}"
    )


# =========================================================
# INTELLIGENCE BRIEF
# =========================================================

def display_commodity_intelligence_brief(
    commodity: str,
    records: list[dict],
    model: str | None = None,
) -> None:
    """
    Display an integrated MineLens commodity intelligence
    brief.

    Licensing statistics come directly from the structured
    licensing dataset.

    Policy and strategy context is generated only from
    retrieved MineLens document evidence.
    """

    name = commodity_name(
        commodity
    )

    snapshot = licensing_snapshot(
        records
    )

    st.subheader(
        "MineLens intelligence brief"
    )

    st.caption(
        "Combines structured licensing data with "
        "evidence retrieved from official mining documents."
    )

    # =====================================================
    # STRUCTURED LICENSING SNAPSHOT
    # =====================================================

    with st.container(
        border=True,
    ):

        st.markdown(
            f"### {name}"
        )

        if (
            name.casefold()
            != commodity.casefold()
        ):

            st.caption(
                f"Commodity code: {commodity}"
            )

        (
            metric_1,
            metric_2,
            metric_3,
            metric_4,
        ) = st.columns(
            4
        )

        with metric_1:

            st.metric(
                "Licence records",
                f"{snapshot['records']:,}",
            )

        with metric_2:

            st.metric(
                "Approved",
                f"{snapshot['approved']:,}",
            )

        with metric_3:

            st.metric(
                "Applicants",
                f"{snapshot['applicants']:,}",
            )

        with metric_4:

            st.metric(
                "Provinces",
                f"{snapshot['provinces']:,}",
            )

        st.caption(
            "Total recorded licensing area: "
            f"{snapshot['area']:,.2f} ha"
        )

    # =====================================================
    # SESSION CACHE
    # =====================================================

    cache = st.session_state.get(
        "commodity_intelligence_briefs",
        {},
    )

    existing_result = cache.get(
        commodity
    )

    button_label = (
        "Refresh official-context brief"
        if existing_result
        else "Generate official-context brief"
    )

    generate = st.button(
        button_label,
        key=state_key(
            commodity
        ),
        type="primary",
    )

    # =====================================================
    # GENERATE
    # =====================================================

    if generate:

        retrieval_query = (
            build_document_query(
                commodity
            )
        )

        question = (
            build_brief_question(
                commodity
            )
        )

        try:

            with st.spinner(
                f"Searching official documents for "
                f"{name}..."
            ):

                search_result = (
                    search_documents(
                        query=retrieval_query,
                        top_k=6,
                        candidate_k=20,
                        include_superseded=False,
                    )
                )

                evidence = (
                    normalize_evidence(
                        search_result=search_result,
                        max_evidence=5,
                    )
                )

            if not evidence:

                st.warning(
                    "MineLens did not find enough "
                    "document evidence to generate "
                    "an official-context brief."
                )

                return

            with st.spinner(
                "Generating grounded intelligence brief..."
            ):

                answer_result = (
                    answer_from_evidence(
                        question=question,
                        evidence=evidence,
                        model=model,
                    )
                )

            updated_cache = dict(
                cache
            )

            updated_cache[
                commodity
            ] = {
                "retrieval_query":
                    retrieval_query,

                "question":
                    question,

                "evidence":
                    evidence,

                "answer_result":
                    answer_result,
            }

            st.session_state[
                "commodity_intelligence_briefs"
            ] = updated_cache

            existing_result = (
                updated_cache[
                    commodity
                ]
            )

        except Exception as error:

            st.error(
                "MineLens could not generate "
                "the commodity intelligence brief."
            )

            st.caption(
                str(
                    error
                )
            )

            return

    # =====================================================
    # DISPLAY GENERATED BRIEF
    # =====================================================

    if not existing_result:

        st.info(
            "Generate the brief to connect this "
            "commodity's licensing activity with "
            "MineLens policy, strategy, legislation "
            "and statistical documents."
        )

        return

    evidence = existing_result[
        "evidence"
    ]

    answer_result = existing_result[
        "answer_result"
    ]

    answer = clean_text(
        answer_result.get(
            "answer"
        )
    )

    st.markdown(
        "### Official policy and strategy context"
    )

    if answer:

        st.markdown(
            answer
        )

    else:

        st.warning(
            "No grounded answer was generated."
        )

    # =====================================================
    # GENERATION INFORMATION
    # =====================================================

    generation_method = clean_text(
        answer_result.get(
            "generation_method"
        )
    )

    model_used = clean_text(
        answer_result.get(
            "model"
        )
    )

    information: list[str] = []

    if generation_method:

        information.append(
            f"Method: {generation_method}"
        )

    if model_used:

        information.append(
            f"Model: {model_used}"
        )

    if information:

        st.caption(
            " · ".join(
                information
            )
        )

    # =====================================================
    # SUPPORTING EVIDENCE
    # =====================================================

    with st.expander(
        "View supporting document evidence",
        expanded=False,
    ):

        st.caption(
            "The generated context above is restricted "
            "to this retrieved MineLens evidence."
        )

        display_document_evidence(
            evidence
        )

    # =====================================================
    # RETRIEVAL TRANSPARENCY
    # =====================================================

    with st.expander(
        "Retrieval details",
        expanded=False,
    ):

        st.markdown(
            "**Document search query**"
        )

        st.code(
            existing_result[
                "retrieval_query"
            ]
        )

        st.markdown(
            "**Question sent to the grounded "
            "answer generator**"
        )

        st.write(
            existing_result[
                "question"
            ]
        )