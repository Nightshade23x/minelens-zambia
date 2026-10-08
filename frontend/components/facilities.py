from __future__ import annotations

from typing import Any

import streamlit as st

from app.facility_answers import (
    infer_facility_answer_intent,
)


# =========================================================
# HELPERS
# =========================================================

def clean_text(
    value: Any,
) -> str:
    """
    Convert arbitrary values into clean display text.
    """

    if value is None:
        return ""

    return " ".join(
        str(value).split()
    )


def human_number(
    value: Any,
) -> str:
    """
    Format numeric values for display.
    """

    if value is None:
        return "—"

    try:
        number = float(
            value
        )

    except (
        TypeError,
        ValueError,
    ):
        return clean_text(
            value
        )

    if number.is_integer():
        return f"{int(number):,}"

    return f"{number:,.2f}".rstrip(
        "0"
    ).rstrip(
        "."
    )


def natural_list(
    values: list[str],
) -> str:
    """
    Format a short list for display.
    """

    values = [
        clean_text(
            value
        )
        for value in values
        if clean_text(
            value
        )
    ]

    if not values:
        return "—"

    if len(values) == 1:
        return values[0]

    if len(values) == 2:
        return (
            f"{values[0]} and "
            f"{values[1]}"
        )

    return (
        ", ".join(
            values[:-1]
        )
        + f", and {values[-1]}"
    )


def facility_status(
    facility: dict,
) -> str:
    """
    Convert grouped product statuses into one
    facility-level status.
    """

    statuses = [
        clean_text(
            status
        )
        for status in facility.get(
            "facility_statuses",
            [],
        )
        if clean_text(
            status
        )
    ]

    unique: list[str] = []
    seen: set[str] = set()

    for status in statuses:

        key = status.casefold()

        if key in seen:
            continue

        seen.add(
            key
        )

        unique.append(
            status
        )

    if not unique:
        return "Unknown"

    if len(unique) == 1:
        return unique[0]

    return "Mixed"


def ownership_text(
    facility: dict,
) -> str:
    """
    Format facility equity ownership.
    """

    owners = facility.get(
        "equity_owners",
        [],
    )

    values: list[str] = []

    for owner in owners:

        name = clean_text(
            owner.get(
                "name"
            )
        )

        if not name:
            continue

        share = owner.get(
            "share_percent"
        )

        if share is None:

            values.append(
                name
            )

        else:

            values.append(
                f"{name} "
                f"({human_number(share)}%)"
            )

    return natural_list(
        values
    )


def operator_text(
    facility: dict,
) -> str:
    """
    Format operating companies.
    """

    return natural_list(
        facility.get(
            "major_operating_companies",
            [],
        )
    )


def feature_text(
    facility: dict,
) -> str:
    """
    Format feature types.
    """

    return natural_list(
        facility.get(
            "feature_types",
            [],
        )
    )


def commodity_text(
    facility: dict,
) -> str:
    """
    Format commodities.
    """

    return natural_list(
        facility.get(
            "commodities",
            [],
        )
    )


def capacity_table(
    item: dict,
) -> list[dict]:
    """
    Build rows for deduplicated capacity records.
    """

    rows: list[dict] = []

    for record in item.get(
        "capacity_records",
        [],
    ):

        detail = (
            clean_text(
                record.get(
                    "form"
                )
            )
            or clean_text(
                record.get(
                    "descriptor"
                )
            )
            or clean_text(
                record.get(
                    "type"
                )
            )
            or "—"
        )

        rows.append(
            {
                "Product / form":
                    detail,

                "Annual capacity":
                    human_number(
                        record.get(
                            "capacity"
                        )
                    ),

                "Unit":
                    clean_text(
                        record.get(
                            "capacity_unit"
                        )
                    )
                    or "—",
            }
        )

    return rows


# =========================================================
# FACILITY CARD
# =========================================================

def display_facility_record(
    item: dict,
) -> None:
    """
    Render one structured USGS facility result.
    """

    facility = item.get(
        "facility",
        {},
    )

    name = clean_text(
        facility.get(
            "facility_name"
        )
    )

    facility_id = clean_text(
        facility.get(
            "usgs_facility_id"
        )
    )

    province = clean_text(
        facility.get(
            "province"
        )
    )

    location = clean_text(
        facility.get(
            "location_description"
        )
    )

    status = facility_status(
        facility
    )

    operator = operator_text(
        facility
    )

    ownership = ownership_text(
        facility
    )

    commodities = commodity_text(
        facility
    )

    features = feature_text(
        facility
    )

    with st.container(
        border=True,
    ):

        title_column, status_column = (
            st.columns(
                [4, 1]
            )
        )

        with title_column:

            st.markdown(
                f"### "
                f"{name or 'Facility'}"
            )

            caption_parts = [
                value
                for value in [
                    facility_id,
                    features,
                ]
                if value
                and value != "—"
            ]

            if caption_parts:

                st.caption(
                    " · ".join(
                        caption_parts
                    )
                )

        with status_column:

            if (
                status.casefold()
                == "assumed active"
            ):

                st.success(
                    status
                )

            elif (
                status.casefold()
                == "inactive"
            ):

                st.error(
                    status
                )

            else:

                st.info(
                    status
                )

        st.divider()

        left_column, right_column = (
            st.columns(
                2
            )
        )

        with left_column:

            st.markdown(
                "**Operator**  \n"
                f"{operator}"
            )

            st.markdown(
                "**Ownership**  \n"
                f"{ownership}"
            )

            st.markdown(
                "**Commodities**  \n"
                f"{commodities}"
            )

        with right_column:

            st.markdown(
                "**Location**  \n"
                f"{location or '—'}"
            )

            st.markdown(
                "**Province**  \n"
                f"{province or '—'}"
            )

            st.markdown(
                "**USGS facility ID**  \n"
                f"{facility_id or '—'}"
            )

        capacities = capacity_table(
            item
        )

        if capacities:

            st.markdown(
                "**Recorded annual production capacity**"
            )

            st.dataframe(
                capacities,
                hide_index=True,
                use_container_width=True,
            )

            st.caption(
                "Shared-capacity product rows are "
                "deduplicated and are not summed."
            )


# =========================================================
# FACILITY RESULTS
# =========================================================

def display_facility_results(
    search_result: dict,
) -> None:
    """
    Render structured facility search results.
    """

    results = search_result.get(
        "results",
        [],
    )

    if not results:
        return

    query = clean_text(
        search_result.get(
            "query"
        )
    )

    intent = (
        infer_facility_answer_intent(
            query
        )
    )

    if intent == "list":

        display_results = results

    else:

        # Entity-specific questions can return several
        # ranked candidates, but the highest-ranked
        # facility is the relevant record.
        display_results = results[
            :1
        ]

    st.subheader(
        "Facility"
        if len(
            display_results
        ) == 1
        else "Facilities"
    )

    st.caption(
        "Structured facility information from the "
        "U.S. Geological Survey Minerals Yearbook."
    )

    for item in display_results:

        display_facility_record(
            item
        )