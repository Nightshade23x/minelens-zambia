from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st
from frontend.components.licensing_analytics import (
    display_licensing_analytics,
)
from frontend.components.licensing_map import (
    display_licensing_map,
)
from frontend.utils.licensing_geo import (
    normalized_districts,
)
from frontend.components.licensing_summary import (
    display_province_summary,
)
from frontend.components.licensing_compare import (
    display_licence_comparison,
)
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
from frontend.styles.theme import apply_theme  # noqa: E402
from frontend.utils.display import clean_text  # noqa: E402


# =========================================================
# PAGE CONFIGURATION
# =========================================================

st.set_page_config(
    page_title="Licensing Explorer | MineLens Zambia",
    page_icon="⛏️",
    layout="wide",
    initial_sidebar_state="expanded",
)

apply_theme()


# =========================================================
# FILTER STATE
# =========================================================

FILTER_DEFAULTS = {
    "licence_search": "",
    "licence_type_filter": [],
    "decision_filter": [],
    "province_filter": [],
    "district_filter": [],
    "commodity_filter": [],
}


def reset_filters() -> None:
    """
    Reset all Licensing Explorer search filters.
    """

    for key, value in FILTER_DEFAULTS.items():

        if isinstance(value, list):
            st.session_state[key] = value.copy()

        else:
            st.session_state[key] = value


# =========================================================
# DATA HELPERS
# =========================================================

def text_value(
    record: dict,
    key: str,
) -> str:
    """
    Return a clean string value from a licensing record.
    """

    return clean_text(
        record.get(key)
    )


def list_value(
    record: dict,
    key: str,
) -> list[str]:
    """
    Normalize a record field into a list of clean strings.
    """

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

    value_text = clean_text(
        value
    )

    if not value_text:
        return []

    return [
        value_text
    ]


def joined_value(
    record: dict,
    key: str,
) -> str:
    """
    Convert list-valued fields into readable text.
    """

    return ", ".join(
        list_value(
            record,
            key,
        )
    )


def unique_text_values(
    records: list[dict],
    key: str,
) -> list[str]:
    """
    Return sorted unique values from a text field.
    """

    values = {
        text_value(
            record,
            key,
        )
        for record in records
    }

    values.discard("")

    return sorted(
        values,
        key=str.casefold,
    )


def unique_list_values(
    records: list[dict],
    key: str,
) -> list[str]:
    """
    Return sorted unique values from a list-valued field.
    """

    values: set[str] = set()

    for record in records:
        values.update(
            list_value(
                record,
                key,
            )
        )

    return sorted(
        values,
        key=str.casefold,
    )


# =========================================================
# SEARCH / FILTER LOGIC
# =========================================================

def matches_text_search(
    record: dict,
    query: str,
) -> bool:
    """
    Match free text against useful licence fields.

    This allows users to search licence codes,
    applicants and other structured information.
    """

    query = query.strip().lower()

    if not query:
        return True

    searchable_values = [
        text_value(
            record,
            "licence_code",
        ),
        text_value(
            record,
            "applicant",
        ),
        text_value(
            record,
            "licence_type",
        ),
        text_value(
            record,
            "decision",
        ),
        text_value(
            record,
            "province",
        ),
        joined_value(
            record,
            "districts",
        ),
        joined_value(
            record,
            "commodities",
        ),
    ]

    haystack = " ".join(
        searchable_values
    ).lower()

    return query in haystack


def record_matches_filters(
    record: dict,
    *,
    search_text: str,
    licence_types: list[str],
    decisions: list[str],
    provinces: list[str],
    districts: list[str],
    commodities: list[str],
) -> bool:
    """
    Apply all active Licensing Explorer filters.
    """

    if not matches_text_search(
        record,
        search_text,
    ):
        return False

    licence_type = text_value(
        record,
        "licence_type",
    )

    decision = text_value(
        record,
        "decision",
    )

    province = text_value(
        record,
        "province",
    )

    record_districts = set(
        normalized_districts(
            record
        )
    )

    record_commodities = set(
        list_value(
            record,
            "commodities",
        )
    )

    if (
        licence_types
        and licence_type
        not in licence_types
    ):
        return False

    if (
        decisions
        and decision
        not in decisions
    ):
        return False

    if (
        provinces
        and province
        not in provinces
    ):
        return False

    if (
        districts
        and not record_districts.intersection(
            districts
        )
    ):
        return False

    if (
        commodities
        and not record_commodities.intersection(
            commodities
        )
    ):
        return False

    return True


# =========================================================
# SOURCE HELPERS
# =========================================================

def record_source_url(
    record: dict,
) -> str:
    """
    Find an official source URL from common record fields.
    """

    for key in (
        "source_url",
        "url",
        "source",
    ):

        value = clean_text(
            record.get(key)
        )

        if value.startswith(
            (
                "http://",
                "https://",
            )
        ):
            return value

    return ""


# =========================================================
# LICENCE DETAIL CARD
# =========================================================

def display_record_card(
    record: dict,
) -> None:
    """
    Render one structured licence record.
    """

    licence_code = text_value(
        record,
        "licence_code",
    )

    licence_type = text_value(
        record,
        "licence_type",
    )

    applicant = text_value(
        record,
        "applicant",
    )

    decision = text_value(
        record,
        "decision",
    )

    province = text_value(
        record,
        "province",
    )

    districts = joined_value(
        record,
        "districts",
    )

    commodities = joined_value(
        record,
        "commodities",
    )

    area_text = text_value(
        record,
        "area_text",
    )

    deadline = text_value(
        record,
        "deadline",
    )

    source_url = record_source_url(
        record
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
                f"### {licence_code or 'Licence record'}"
            )

            if licence_type:
                st.caption(
                    licence_type
                )

        with status_column:

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

            st.markdown(
                f"**Commodities**  \n"
                f"{commodities or '—'}"
            )

        with right_column:

            st.markdown(
                f"**Province**  \n"
                f"{province or '—'}"
            )

            st.markdown(
                f"**District**  \n"
                f"{districts or '—'}"
            )

            st.markdown(
                f"**Stipulated timeframe**  \n"
                f"{deadline or '—'}"
            )

        if source_url:

            st.divider()

            st.link_button(
                "View official source",
                source_url,
            )


# =========================================================
# TABLE HELPERS
# =========================================================
def export_rows(
    records: list[dict],
) -> list[dict]:
    """
    Convert the full filtered licensing records into
    export-friendly rows.
    """

    rows: list[dict] = []

    for record in records:

        rows.append(
            {
                "Licence Code": text_value(
                    record,
                    "licence_code",
                ),
                "Applicant": text_value(
                    record,
                    "applicant",
                ),
                "Licence Type": text_value(
                    record,
                    "licence_type",
                ),
                "Licence Type Code": text_value(
                    record,
                    "licence_type_code",
                ),
                "Decision": text_value(
                    record,
                    "decision",
                ),
                "Province": text_value(
                    record,
                    "province",
                ),
                "Districts": joined_value(
                    record,
                    "districts",
                ),
                "Commodities": joined_value(
                    record,
                    "commodities",
                ),
                "Area (ha)": record.get(
                    "area_hectares"
                ),
                "Area": text_value(
                    record,
                    "area_text",
                ),
                "Stipulated Timeframe": text_value(
                    record,
                    "deadline",
                ),
                "Deadline ISO": text_value(
                    record,
                    "deadline_iso",
                ),
                "Source": text_value(
                    record,
                    "source_url",
                ),
            }
        )

    return rows

def table_rows(
    records: list[dict],
) -> list[dict]:
    """
    Convert licence records into table-friendly rows.
    """

    rows: list[dict] = []

    for record in records:

        rows.append(
            {
                "Licence code": (
                    text_value(
                        record,
                        "licence_code",
                    )
                ),
                "Applicant": (
                    text_value(
                        record,
                        "applicant",
                    )
                ),
                "Licence type": (
                    text_value(
                        record,
                        "licence_type",
                    )
                ),
                "Decision": (
                    text_value(
                        record,
                        "decision",
                    )
                ),
                "Province": (
                    text_value(
                        record,
                        "province",
                    )
                ),
                "District": (
                    joined_value(
                        record,
                        "districts",
                    )
                ),
                "Commodities": (
                    joined_value(
                        record,
                        "commodities",
                    )
                ),
                "Area": (
                    text_value(
                        record,
                        "area_text",
                    )
                ),
            }
        )

    return rows


# =========================================================
# LOAD RECORDS
# =========================================================

@st.cache_data(
    show_spinner=False,
)
def load_records() -> list[dict]:
    """
    Load MineLens structured licensing records.
    """

    return load_licensing_records()


with st.spinner(
    "Loading licensing records..."
):

    records = load_records()


# =========================================================
# HEADER
# =========================================================

st.markdown(
    """
    <div class="minelens-eyebrow">
        MineLens Zambia
    </div>

    <div class="minelens-title">
        Licensing Explorer
    </div>

    <div class="minelens-subtitle">
        Browse and filter structured mining licensing
        committee records by licence type, decision,
        location, commodity, applicant or licence code.
    </div>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# DATASET SUMMARY
# =========================================================

total_records = len(
    records
)

st.metric(
    "Licensing records",
    f"{total_records:,}",
)


# =========================================================
# FILTER OPTIONS
# =========================================================

licence_type_options = unique_text_values(
    records,
    "licence_type",
)

decision_options = unique_text_values(
    records,
    "decision",
)

province_options = unique_text_values(
    records,
    "province",
)

district_options = sorted(
    {
        district
        for record in records
        for district in normalized_districts(record)
    },
    key=str.casefold,
)

commodity_options = unique_list_values(
    records,
    "commodities",
)


# =========================================================
# SEARCH FILTERS
# =========================================================

st.subheader(
    "Search licences"
)


search_text = st.text_input(
    "Licence code or applicant",
    placeholder=(
        "e.g. 42553-HQ-LML or Nisco Industries"
    ),
    key="licence_search",
)


filter_row_1 = st.columns(
    3
)


with filter_row_1[0]:

    selected_types = st.multiselect(
        "Licence type",
        options=licence_type_options,
        key="licence_type_filter",
    )


with filter_row_1[1]:

    selected_decisions = st.multiselect(
        "Decision",
        options=decision_options,
        key="decision_filter",
    )


with filter_row_1[2]:

    selected_provinces = st.multiselect(
        "Province",
        options=province_options,
        key="province_filter",
    )


filter_row_2 = st.columns(
    2
)


with filter_row_2[0]:

    selected_districts = st.multiselect(
        "District",
        options=district_options,
        key="district_filter",
    )


with filter_row_2[1]:

    selected_commodities = st.multiselect(
        "Commodity",
        options=commodity_options,
        key="commodity_filter",
    )


reset_column, spacer_column = st.columns(
    [1, 4]
)


with reset_column:

    st.button(
        "Reset filters",
        use_container_width=True,
        on_click=reset_filters,
    )


# =========================================================
# APPLY FILTERS
# =========================================================

filtered_records = [
    record
    for record in records
    if record_matches_filters(
        record,
        search_text=search_text,
        licence_types=selected_types,
        decisions=selected_decisions,
        provinces=selected_provinces,
        districts=selected_districts,
        commodities=selected_commodities,
    )
]
export_dataframe = pd.DataFrame(
    export_rows(
        filtered_records
    )
)

export_csv = export_dataframe.to_csv(
    index=False
).encode(
    "utf-8"
)

# =========================================================
# DASHBOARD METRICS
# =========================================================

approved_matches = sum(
    text_value(
        record,
        "decision",
    ).lower()
    == "approved"
    for record in filtered_records
)


matching_provinces = {
    text_value(
        record,
        "province",
    )
    for record in filtered_records
    if text_value(
        record,
        "province",
    )
}


matching_licence_types = {
    text_value(
        record,
        "licence_type",
    )
    for record in filtered_records
    if text_value(
        record,
        "licence_type",
    )
}


st.divider()


metric_1, metric_2, metric_3, metric_4 = (
    st.columns(
        4
    )
)


with metric_1:

    st.metric(
        "Matching records",
        f"{len(filtered_records):,}",
    )


with metric_2:

    st.metric(
        "Approved",
        f"{approved_matches:,}",
    )


with metric_3:

    st.metric(
        "Provinces",
        f"{len(matching_provinces):,}",
    )


with metric_4:

    st.metric(
        "Licence types",
        f"{len(matching_licence_types):,}",
    )

# =========================================================
# LICENSING ANALYTICS
# =========================================================

st.divider()

display_licensing_analytics(
    filtered_records
)
# =========================================================
# LICENSING MAP
# =========================================================

st.divider()

display_licensing_map(
    filtered_records,
    selected_districts=selected_districts,
)
# =========================================================
# PROVINCE SUMMARY
# =========================================================

st.divider()

display_province_summary(
    filtered_records
)
# =========================================================
# RESULTS HEADER
# =========================================================

results_column, export_column, limit_column = st.columns(
    [3, 1.2, 1]
)


with results_column:

    st.subheader(
        "Results"
    )

    st.caption(
        f"{len(filtered_records):,} "
        f"of {total_records:,} records "
        f"match the current filters."
    )

with export_column:

    st.download_button(
        "Download CSV",
        data=export_csv,
        file_name="minelens_licensing_results.csv",
        mime="text/csv",
        use_container_width=True,
        disabled=not filtered_records,
    )
with limit_column:

    result_limit = st.selectbox(
        "Records shown",
        options=[
            25,
            50,
            100,
            250,
            500,
        ],
        index=1,
    )


# =========================================================
# NO RESULTS
# =========================================================

if not filtered_records:

    st.info(
        "No licensing records match "
        "the current search and filters."
    )

    st.stop()


# =========================================================
# VISIBLE RECORDS
# =========================================================

visible_records = filtered_records[
    :result_limit
]


# =========================================================
# RESULTS TABLE
# =========================================================

# =========================================================
# RESULTS TABLE
# =========================================================

rows = table_rows(
    visible_records
)

dataframe = pd.DataFrame(
    rows
)


table_event = st.dataframe(
    dataframe,
    use_container_width=True,
    hide_index=True,
    key="licence_results_table",
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

        "Commodities":
            st.column_config.TextColumn(
                width="large",
            ),

        "Area":
            st.column_config.TextColumn(
                width="medium",
            ),
    },
)


if (
    len(filtered_records)
    > result_limit
):

    st.caption(
        f"Showing the first "
        f"{result_limit:,} records. "
        f"Narrow the filters to inspect "
        f"the remaining matches."
    )

# =========================================================
# LICENCE COMPARISON
# =========================================================

st.divider()

display_licence_comparison(
    filtered_records
)
# =========================================================
# LICENCE DETAILS
# =========================================================

st.subheader(
    "Licence details"
)


selected_rows = (
    table_event.selection.rows
)


if not selected_rows:

    st.info(
        "Select a row in the results table "
        "to view the complete licence record."
    )

else:

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

        display_record_card(
            selected_record
        )

    else:

        st.warning(
            "The selected row is no longer "
            "available. Select another record."
        )