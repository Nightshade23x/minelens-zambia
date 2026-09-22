from __future__ import annotations

from collections import Counter

import pandas as pd
import streamlit as st

from frontend.utils.display import clean_text
from frontend.utils.licensing_geo import normalized_districts


# =========================================================
# HELPERS
# =========================================================

def _text_value(
    record: dict,
    key: str,
) -> str:
    return clean_text(
        record.get(key)
    )


def _canonical_decision(
    value: str,
) -> str:
    """
    Normalize equivalent decision labels for analysis.
    """

    value = clean_text(
        value
    )

    normalized = value.casefold()

    aliases = {
        "approval": "Approved",
        "approved": "Approved",
        "defer": "Deferred",
        "deferred": "Deferred",
        "reject": "Rejected",
        "rejected": "Rejected",
    }

    return aliases.get(
        normalized,
        value,
    )


def _applicant_key(
    value: str,
) -> str:
    """
    Normalize applicant names for grouping.

    Only case and whitespace differences are ignored.
    """

    return clean_text(
        value
    ).casefold()


# =========================================================
# BUILD APPLICANT ANALYTICS
# =========================================================

def build_applicant_summary(
    records: list[dict],
) -> pd.DataFrame:
    """
    Aggregate MineLens licensing records by applicant.
    """

    groups: dict[str, dict] = {}

    for record in records:

        applicant = _text_value(
            record,
            "applicant",
        )

        if not applicant:
            continue

        key = _applicant_key(
            applicant
        )

        if key not in groups:

            groups[key] = {
                "names": Counter(),
                "records": [],
            }

        groups[key]["names"][
            applicant
        ] += 1

        groups[key]["records"].append(
            record
        )

    rows: list[dict] = []

    for group in groups.values():

        applicant = (
            group["names"]
            .most_common(1)[0][0]
        )

        applicant_records = (
            group["records"]
        )

        approved = 0
        deferred = 0
        rejected = 0

        provinces: set[str] = set()
        districts: set[str] = set()

        total_area = 0.0

        for record in applicant_records:

            decision = _canonical_decision(
                _text_value(
                    record,
                    "decision",
                )
            )

            if decision == "Approved":
                approved += 1

            elif decision == "Deferred":
                deferred += 1

            elif decision == "Rejected":
                rejected += 1

            province = _text_value(
                record,
                "province",
            )

            if province:
                provinces.add(
                    province
                )

            districts.update(
                normalized_districts(
                    record
                )
            )

            area = record.get(
                "area_hectares"
            )

            if isinstance(
                area,
                (int, float),
            ):
                total_area += float(
                    area
                )

        application_count = len(
            applicant_records
        )

        approval_rate = (
            approved
            / application_count
            * 100
            if application_count
            else 0.0
        )

        rows.append(
            {
                "Applicant": applicant,
                "Applications": application_count,
                "Approved": approved,
                "Deferred": deferred,
                "Rejected": rejected,
                "Approval rate": approval_rate,
                "Recorded area (ha)": total_area,
                "Provinces": len(
                    provinces
                ),
                "Districts": len(
                    districts
                ),
            }
        )

    dataframe = pd.DataFrame(
        rows
    )

    return dataframe


# =========================================================
# TABLE DISPLAY
# =========================================================

def _display_ranking_table(
    dataframe: pd.DataFrame,
) -> None:
    """
    Render a consistent applicant ranking table.
    """

    st.dataframe(
        dataframe,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Applicant":
                st.column_config.TextColumn(
                    width="large",
                ),

            "Applications":
                st.column_config.NumberColumn(
                    format="%d",
                    width="small",
                ),

            "Approved":
                st.column_config.NumberColumn(
                    format="%d",
                    width="small",
                ),

            "Deferred":
                st.column_config.NumberColumn(
                    format="%d",
                    width="small",
                ),

            "Rejected":
                st.column_config.NumberColumn(
                    format="%d",
                    width="small",
                ),

            "Approval rate":
                st.column_config.NumberColumn(
                    format="%.1f%%",
                    width="small",
                ),

            "Recorded area (ha)":
                st.column_config.NumberColumn(
                    format="%.2f",
                    width="medium",
                ),

            "Provinces":
                st.column_config.NumberColumn(
                    format="%d",
                    width="small",
                ),

            "Districts":
                st.column_config.NumberColumn(
                    format="%d",
                    width="small",
                ),
        },
    )


# =========================================================
# MAIN COMPONENT
# =========================================================

def display_applicant_rankings(
    records: list[dict],
) -> None:
    """
    Display applicant-level licensing rankings.
    """

    st.subheader(
        "Applicant rankings"
    )

    st.caption(
        "Compare applicants across the structured "
        "MineLens licensing dataset."
    )

    dataframe = build_applicant_summary(
        records
    )

    if dataframe.empty:

        st.info(
            "No applicant data is available."
        )

        return

    ranking_limit = st.selectbox(
        "Applicants shown",
        options=[
            10,
            25,
            50,
            100,
        ],
        index=1,
        key="applicant_ranking_limit",
    )

    (
        applications_tab,
        area_tab,
        footprint_tab,
        approval_tab,
    ) = st.tabs(
        [
            "Most applications",
            "Largest recorded area",
            "Widest footprint",
            "Approval rate",
        ]
    )

    # -----------------------------------------------------
    # MOST APPLICATIONS
    # -----------------------------------------------------

    with applications_tab:

        ranked = (
            dataframe
            .sort_values(
                [
                    "Applications",
                    "Approved",
                ],
                ascending=[
                    False,
                    False,
                ],
            )
            .head(
                ranking_limit
            )
            .reset_index(
                drop=True
            )
        )

        _display_ranking_table(
            ranked
        )

    # -----------------------------------------------------
    # LARGEST AREA
    # -----------------------------------------------------

    with area_tab:

        ranked = (
            dataframe
            .sort_values(
                "Recorded area (ha)",
                ascending=False,
            )
            .head(
                ranking_limit
            )
            .reset_index(
                drop=True
            )
        )

        _display_ranking_table(
            ranked
        )

        st.caption(
            "Recorded area is the sum of area values "
            "reported across each applicant's licensing records."
        )

    # -----------------------------------------------------
    # WIDEST FOOTPRINT
    # -----------------------------------------------------

    with footprint_tab:

        ranked = (
            dataframe
            .sort_values(
                [
                    "Districts",
                    "Provinces",
                    "Applications",
                ],
                ascending=[
                    False,
                    False,
                    False,
                ],
            )
            .head(
                ranking_limit
            )
            .reset_index(
                drop=True
            )
        )

        _display_ranking_table(
            ranked
        )

        st.caption(
            "Footprint counts the distinct districts and "
            "provinces associated with an applicant's records."
        )

    # -----------------------------------------------------
    # APPROVAL RATE
    # -----------------------------------------------------

    with approval_tab:

        minimum_applications = st.slider(
            "Minimum applications",
            min_value=1,
            max_value=10,
            value=2,
            key="approval_rate_minimum_applications",
            help=(
                "Avoids ranking a one-record applicant "
                "above applicants with a larger history."
            ),
        )

        eligible = dataframe[
            dataframe[
                "Applications"
            ]
            >= minimum_applications
        ]

        ranked = (
            eligible
            .sort_values(
                [
                    "Approval rate",
                    "Applications",
                ],
                ascending=[
                    False,
                    False,
                ],
            )
            .head(
                ranking_limit
            )
            .reset_index(
                drop=True
            )
        )

        _display_ranking_table(
            ranked
        )

        st.caption(
            "Approval rate uses normalized decision labels. "
            "The minimum-application threshold can be adjusted "
            "to avoid misleading rankings from very small samples."
        )