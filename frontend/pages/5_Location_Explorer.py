from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

import pandas as pd
import streamlit as st


# =========================================================
# PROJECT PATH
# =========================================================

ROOT_DIR = Path(__file__).resolve().parents[2]

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(ROOT_DIR),
    )


# =========================================================
# MINELENS IMPORTS
# =========================================================

from app.licensing_search import load_licensing_records  # noqa: E402
from frontend.components.licensing import (  # noqa: E402
    display_licensing_record,
)
from frontend.components.licensing_map import (  # noqa: E402
    display_licensing_map,
)
from frontend.styles.theme import apply_theme  # noqa: E402
from frontend.utils.display import clean_text  # noqa: E402
from frontend.utils.licensing_geo import (  # noqa: E402
    normalized_districts,
)


# =========================================================
# PAGE CONFIG
# =========================================================

st.set_page_config(
    page_title="Location Explorer | MineLens Zambia",
    page_icon="📍",
    layout="wide",
    initial_sidebar_state="expanded",
)

apply_theme()


# =========================================================
# HELPERS
# =========================================================

def text_value(
    record: dict,
    key: str,
) -> str:

    return clean_text(
        record.get(key)
    )


def list_value(
    record: dict,
    key: str,
) -> list[str]:

    value = record.get(
        key,
        [],
    )

    if value is None:
        return []

    if isinstance(
        value,
        list,
    ):
        return [
            clean_text(item)
            for item in value
            if clean_text(item)
        ]

    value = clean_text(
        value
    )

    if not value:
        return []

    return [
        value
    ]


def canonical_decision(
    value: str,
) -> str:

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


def total_area(
    records: list[dict],
) -> float:

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


def province_options(
    records: list[dict],
) -> list[str]:

    values = {
        text_value(
            record,
            "province",
        )
        for record in records
        if text_value(
            record,
            "province",
        )
    }

    return sorted(
        values,
        key=str.casefold,
    )


def district_options(
    records: list[dict],
) -> list[str]:

    values = {
        district
        for record in records
        for district in normalized_districts(
            record
        )
        if district
    }

    return sorted(
        values,
        key=str.casefold,
    )


def records_for_province(
    records: list[dict],
    province: str,
) -> list[dict]:

    return [
        record
        for record in records
        if (
            text_value(
                record,
                "province",
            )
            == province
        )
    ]


def records_for_district(
    records: list[dict],
    district: str,
) -> list[dict]:

    return [
        record
        for record in records
        if district
        in normalized_districts(
            record
        )
    ]


def count_values(
    values: list[str],
) -> Counter:

    return Counter(
        value
        for value in values
        if value
    )


def top_table(
    counter: Counter,
    label: str,
    top_n: int = 10,
) -> pd.DataFrame:

    return pd.DataFrame(
        counter.most_common(
            top_n
        ),
        columns=[
            label,
            "Records",
        ],
    )


def licence_dataframe(
    records: list[dict],
) -> pd.DataFrame:

    rows: list[dict] = []

    for record in records:

        rows.append(
            {
                "Licence code":
                    text_value(
                        record,
                        "licence_code",
                    ),

                "Applicant":
                    text_value(
                        record,
                        "applicant",
                    ),

                "Licence type":
                    text_value(
                        record,
                        "licence_type",
                    ),

                "Decision":
                    canonical_decision(
                        text_value(
                            record,
                            "decision",
                        )
                    ),

                "Province":
                    text_value(
                        record,
                        "province",
                    ),

                "District":
                    ", ".join(
                        normalized_districts(
                            record
                        )
                    ),

                "Area (ha)":
                    record.get(
                        "area_hectares"
                    ),

                "Commodities":
                    ", ".join(
                        list_value(
                            record,
                            "commodities",
                        )
                    ),

                "Source":
                    text_value(
                        record,
                        "source_url",
                    ),
            }
        )

    return pd.DataFrame(
        rows
    )


# =========================================================
# DATA
# =========================================================

@st.cache_data(
    show_spinner=False,
)
def load_records() -> list[dict]:

    return load_licensing_records()


with st.spinner(
    "Loading location intelligence..."
):

    records = load_records()


provinces = province_options(
    records
)

districts = district_options(
    records
)


# =========================================================
# HEADER
# =========================================================

st.markdown(
    """
    <div class="minelens-eyebrow">
        MineLens Zambia
    </div>

    <div class="minelens-title">
        Location Explorer
    </div>

    <div class="minelens-subtitle">
        Explore mining licensing activity by province or
        district, including applicants, commodities,
        decisions, recorded area and licence records.
    </div>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# LOCATION SELECTION
# =========================================================

st.subheader(
    "Select location"
)


location_level = st.radio(
    "Geographic level",
    options=[
        "Province",
        "District",
    ],
    horizontal=True,
    key="location_level",
)


if location_level == "Province":

    default_index = (
        provinces.index(
            "North Western"
        )
        if "North Western"
        in provinces
        else 0
    )

    selected_location = st.selectbox(
        "Province",
        options=provinces,
        index=default_index,
        key="location_province",
    )

    matching_records = (
        records_for_province(
            records,
            selected_location,
        )
    )

else:

    default_index = (
        districts.index(
            "Solwezi"
        )
        if "Solwezi"
        in districts
        else 0
    )

    selected_location = st.selectbox(
        "District",
        options=districts,
        index=default_index,
        key="location_district",
    )

    matching_records = (
        records_for_district(
            records,
            selected_location,
        )
    )


# =========================================================
# SUMMARY METRICS
# =========================================================

approved = sum(
    canonical_decision(
        text_value(
            record,
            "decision",
        )
    )
    == "Approved"
    for record in matching_records
)


applicants = {
    text_value(
        record,
        "applicant",
    )
    for record in matching_records
    if text_value(
        record,
        "applicant",
    )
}


commodities = {
    commodity
    for record in matching_records
    for commodity in list_value(
        record,
        "commodities",
    )
}


metric_1, metric_2, metric_3, metric_4 = (
    st.columns(
        4
    )
)


with metric_1:

    st.metric(
        "Licence records",
        f"{len(matching_records):,}",
    )


with metric_2:

    st.metric(
        "Approved",
        f"{approved:,}",
    )


with metric_3:

    st.metric(
        "Applicants",
        f"{len(applicants):,}",
    )


with metric_4:

    st.metric(
        "Commodities",
        f"{len(commodities):,}",
    )


st.metric(
    "Total recorded area",
    f"{total_area(matching_records):,.2f} ha",
)


# =========================================================
# MAP
# =========================================================

st.divider()

if location_level == "District":

    display_licensing_map(
        matching_records,
        selected_districts=[
            selected_location
        ],
    )

else:

    display_licensing_map(
        matching_records
    )


# =========================================================
# LOCATION INTELLIGENCE
# =========================================================

st.divider()

st.subheader(
    "Location intelligence"
)


decision_counter = count_values(
    [
        canonical_decision(
            text_value(
                record,
                "decision",
            )
        )
        for record in matching_records
    ]
)


applicant_counter = count_values(
    [
        text_value(
            record,
            "applicant",
        )
        for record in matching_records
    ]
)


licence_type_counter = count_values(
    [
        text_value(
            record,
            "licence_type",
        )
        for record in matching_records
    ]
)


commodity_counter = count_values(
    [
        commodity
        for record in matching_records
        for commodity in set(
            list_value(
                record,
                "commodities",
            )
        )
    ]
)


if location_level == "Province":

    district_counter = count_values(
        [
            district
            for record in matching_records
            for district in set(
                normalized_districts(
                    record
                )
            )
        ]
    )

else:

    province_counter = count_values(
        [
            text_value(
                record,
                "province",
            )
            for record in matching_records
        ]
    )


(
    overview_tab,
    applicants_tab,
    commodities_tab,
) = st.tabs(
    [
        "Activity",
        "Applicants",
        "Commodities",
    ]
)


# ---------------------------------------------------------
# ACTIVITY
# ---------------------------------------------------------

with overview_tab:

    col_1, col_2 = st.columns(
        2
    )

    with col_1:

        st.markdown(
            "#### Decisions"
        )

        st.dataframe(
            top_table(
                decision_counter,
                "Decision",
            ),
            use_container_width=True,
            hide_index=True,
        )

    with col_2:

        st.markdown(
            "#### Licence types"
        )

        st.dataframe(
            top_table(
                licence_type_counter,
                "Licence type",
            ),
            use_container_width=True,
            hide_index=True,
        )

    st.markdown(
        "#### Source province labels"
    )

    if location_level == "Province":

        st.markdown(
            "#### District distribution"
        )

        st.dataframe(
            top_table(
                district_counter,
                "District",
                top_n=15,
            ),
            use_container_width=True,
            hide_index=True,
        )

    else:

        st.markdown(
            "#### Source province labels"
        )

        st.caption(
            "Province values are shown exactly as recorded "
            "in the licensing source. Differences may reflect "
            "source inconsistencies or multi-location records."
        )

        st.dataframe(
            top_table(
                province_counter,
                "Province",
            ),
            use_container_width=True,
            hide_index=True,
        )

# ---------------------------------------------------------
# APPLICANTS
# ---------------------------------------------------------

with applicants_tab:

    st.markdown(
        "#### Applicants with the most licence records"
    )

    st.dataframe(
        top_table(
            applicant_counter,
            "Applicant",
            top_n=15,
        ),
        use_container_width=True,
        hide_index=True,
    )


# ---------------------------------------------------------
# COMMODITIES
# ---------------------------------------------------------

with commodities_tab:

    st.markdown(
        "#### Most frequently recorded commodities"
    )

    st.dataframe(
        top_table(
            commodity_counter,
            "Commodity",
            top_n=20,
        ),
        use_container_width=True,
        hide_index=True,
    )


# =========================================================
# LICENCE SEARCH
# =========================================================

st.divider()

st.subheader(
    "Licence records"
)


licence_search = st.text_input(
    "Search licence or applicant within this location",
    placeholder=(
        "e.g. 42553-HQ-LML or Nisco Industries"
    ),
    key="location_licence_search",
)


if licence_search.strip():

    search_value = (
        licence_search
        .strip()
        .casefold()
    )

    visible_records = [
        record
        for record in matching_records
        if (
            search_value
            in text_value(
                record,
                "licence_code",
            ).casefold()
            or
            search_value
            in text_value(
                record,
                "applicant",
            ).casefold()
        )
    ]

else:

    visible_records = (
        matching_records
    )


licence_table = licence_dataframe(
    visible_records
)


if licence_search.strip():

    st.caption(
        f"{len(visible_records):,} matching records "
        f"within {len(matching_records):,} "
        f"{selected_location} records."
    )

else:

    st.caption(
        f"{len(matching_records):,} licensing records "
        f"for {selected_location}."
    )


# =========================================================
# LICENCE TABLE
# =========================================================

table_event = st.dataframe(
    licence_table,
    use_container_width=True,
    hide_index=True,
    key="location_licence_results_table",
    on_select="rerun",
    selection_mode="single-row",
    column_config={
        "Licence code":
            st.column_config.TextColumn(
                width="medium",
            ),

        "Applicant":
            st.column_config.TextColumn(
                width="large",
            ),

        "Licence type":
            st.column_config.TextColumn(
                width="large",
            ),

        "Decision":
            st.column_config.TextColumn(
                width="medium",
            ),

        "Province":
            st.column_config.TextColumn(
                width="medium",
            ),

        "District":
            st.column_config.TextColumn(
                width="medium",
            ),

        "Area (ha)":
            st.column_config.NumberColumn(
                format="%.4f",
            ),

        "Commodities":
            st.column_config.TextColumn(
                width="large",
            ),

        "Source":
            st.column_config.LinkColumn(
                display_text="Official source",
            ),
    },
)


# =========================================================
# SELECTED LICENCE
# =========================================================

selected_rows = (
    table_event.selection.rows
)

selected_record = None


if selected_rows:

    selected_index = (
        selected_rows[0]
    )

    if (
        0
        <= selected_index
        < len(visible_records)
    ):

        selected_record = (
            visible_records[
                selected_index
            ]
        )


if selected_record is not None:

    st.markdown(
        "### Selected licence"
    )

    display_licensing_record(
        {
            "record":
                selected_record
        }
    )

    source = text_value(
        selected_record,
        "source_url",
    )

    if source:

        st.link_button(
            "Open official licensing source",
            source,
        )


    # =====================================================
    # CROSS NAVIGATION
    # =====================================================

    st.markdown(
        "#### Explore this record"
    )


    licence_code = text_value(
        selected_record,
        "licence_code",
    )

    applicant = text_value(
        selected_record,
        "applicant",
    )

    record_commodities = sorted(
        set(
            list_value(
                selected_record,
                "commodities",
            )
        ),
        key=str.casefold,
    )


    nav_col_1, nav_col_2 = st.columns(
        2
    )


    with nav_col_1:

        if applicant:

            if st.button(
                "Open applicant profile",
                use_container_width=True,
                key=(
                    f"location_to_applicant_"
                    f"{licence_code}"
                ),
            ):

                st.session_state[
                    "applicant_search"
                ] = applicant

                st.switch_page(
                    "pages/2_Applicant_Explorer.py"
                )


    with nav_col_2:

        if record_commodities:

            selected_nav_commodity = (
                st.selectbox(
                    "Explore commodity",
                    options=record_commodities,
                    key=(
                        f"location_commodity_"
                        f"{licence_code}"
                    ),
                )
            )

            if st.button(
                "Open Commodity Explorer",
                use_container_width=True,
                key=(
                    f"location_to_commodity_"
                    f"{licence_code}"
                ),
            ):

                st.session_state[
                    "commodity_selector"
                ] = selected_nav_commodity

                st.session_state[
                    "commodity_licence_search"
                ] = licence_code

                st.switch_page(
                    "pages/4_Commodity_Explorer.py"
                )


    if licence_code:

        if st.button(
            "Open in Licensing Explorer",
            use_container_width=True,
            key=(
                f"location_to_licence_"
                f"{licence_code}"
            ),
        ):

            st.session_state[
                "licence_search"
            ] = licence_code

            st.switch_page(
                "pages/1_Licensing_Explorer.py"
            )


# =========================================================
# EXPORT
# =========================================================

csv_data = (
    licence_table
    .to_csv(
        index=False
    )
    .encode(
        "utf-8"
    )
)


st.download_button(
    "Download location records",
    data=csv_data,
    file_name=(
        "minelens_"
        f"{selected_location.lower().replace(' ', '_')}"
        "_licensing_records.csv"
    ),
    mime="text/csv",
)