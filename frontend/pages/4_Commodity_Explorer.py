from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

import pandas as pd
import streamlit as st
from frontend.components.intelligence_brief import (  # noqa: E402
    display_commodity_intelligence_brief,
)
from frontend.components.licensing import (  # noqa: E402
    display_licensing_record,
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
    page_title="Commodity Explorer | MineLens Zambia",
    page_icon="⛏️",
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


def all_commodities(
    records: list[dict],
) -> list[str]:

    values = {
        commodity
        for record in records
        for commodity in list_value(
            record,
            "commodities",
        )
    }

    return sorted(
        values,
        key=str.casefold,
    )


def commodity_records(
    records: list[dict],
    commodity: str,
) -> list[dict]:

    return [
        record
        for record in records
        if commodity
        in list_value(
            record,
            "commodities",
        )
    ]


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


def count_text(
    records: list[dict],
    key: str,
) -> Counter:

    counter: Counter = Counter()

    for record in records:

        value = text_value(
            record,
            key,
        )

        if value:
            counter[
                value
            ] += 1

    return counter


def count_districts(
    records: list[dict],
) -> Counter:

    counter: Counter = Counter()

    for record in records:

        for district in set(
            normalized_districts(
                record
            )
        ):
            counter[
                district
            ] += 1

    return counter


def count_applicants(
    records: list[dict],
) -> Counter:

    counter: Counter = Counter()

    for record in records:

        applicant = text_value(
            record,
            "applicant",
        )

        if applicant:
            counter[
                applicant
            ] += 1

    return counter


def count_cooccurring_commodities(
    records: list[dict],
    selected_commodity: str,
) -> Counter:

    counter: Counter = Counter()

    for record in records:

        for commodity in set(
            list_value(
                record,
                "commodities",
            )
        ):

            if (
                commodity
                != selected_commodity
            ):
                counter[
                    commodity
                ] += 1

    return counter


def counter_dataframe(
    counter: Counter,
    *,
    top_n: int = 10,
    label: str,
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
                "Licence code": text_value(
                    record,
                    "licence_code",
                ),

                "Applicant": text_value(
                    record,
                    "applicant",
                ),

                "Licence type": text_value(
                    record,
                    "licence_type",
                ),

                "Decision": canonical_decision(
                    text_value(
                        record,
                        "decision",
                    )
                ),

                "Province": text_value(
                    record,
                    "province",
                ),

                "District": ", ".join(
                    normalized_districts(
                        record
                    )
                ),

                "Area (ha)": (
                    record.get(
                        "area_hectares"
                    )
                ),

                "Commodities": ", ".join(
                    list_value(
                        record,
                        "commodities",
                    )
                ),

                "Timeframe": text_value(
                    record,
                    "deadline",
                ),

                "Source": text_value(
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
    "Loading commodity licensing data..."
):

    records = load_records()


commodities = all_commodities(
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
        Commodity Explorer
    </div>

    <div class="minelens-subtitle">
        Explore Zambia's licensing activity by mineral
        commodity, including applicants, locations,
        decisions, recorded area and related commodities.
    </div>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# SELECT COMMODITY
# =========================================================

st.subheader(
    "Select commodity"
)


# =========================================================
# COMMODITY SELECTION STATE
# =========================================================

if (
    "commodity_selector"
    not in st.session_state
    or st.session_state[
        "commodity_selector"
    ]
    not in commodities
):

    st.session_state[
        "commodity_selector"
    ] = (
        "Cu"
        if "Cu" in commodities
        else commodities[0]
    )


selected_commodity = st.selectbox(
    "Commodity",
    options=commodities,
    key="commodity_selector",
)


matching_records = commodity_records(
    records,
    selected_commodity,
)

# =========================================================
# LICENCE / APPLICANT SEARCH
# =========================================================

licence_search = st.text_input(
    "Find licence or applicant within this commodity",
    placeholder=(
        "e.g. 42553-HQ-LML or Nisco Industries"
    ),
    key="commodity_licence_search",
)


if licence_search.strip():

    search_value = (
        licence_search
        .strip()
        .casefold()
    )

    visible_licence_records = [
        record
        for record in matching_records
        if (
            search_value
            in clean_text(
                record.get(
                    "licence_code"
                )
            ).casefold()
            or
            search_value
            in clean_text(
                record.get(
                    "applicant"
                )
            ).casefold()
        )
    ]

else:

    visible_licence_records = (
        matching_records
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


provinces = {
    text_value(
        record,
        "province",
    )
    for record in matching_records
    if text_value(
        record,
        "province",
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
        "Provinces",
        f"{len(provinces):,}",
    )


st.metric(
    "Total recorded area",
    f"{total_area(matching_records):,.2f} ha",
)


# =========================================================
# MAP
# =========================================================

st.divider()

display_licensing_map(
    matching_records
)


# =========================================================
# COMMODITY ANALYTICS
# =========================================================

st.divider()

st.subheader(
    "Commodity intelligence"
)


province_data = counter_dataframe(
    count_text(
        matching_records,
        "province",
    ),
    top_n=10,
    label="Province",
)


district_data = counter_dataframe(
    count_districts(
        matching_records
    ),
    top_n=10,
    label="District",
)


applicant_data = counter_dataframe(
    count_applicants(
        matching_records
    ),
    top_n=15,
    label="Applicant",
)


cooccurrence_data = counter_dataframe(
    count_cooccurring_commodities(
        matching_records,
        selected_commodity,
    ),
    top_n=15,
    label="Commodity",
)


(
    location_tab,
    applicant_tab,
    related_tab,
) = st.tabs(
    [
        "Locations",
        "Applicants",
        "Related commodities",
    ]
)


# ---------------------------------------------------------
# LOCATIONS
# ---------------------------------------------------------

with location_tab:

    province_column, district_column = (
        st.columns(
            2
        )
    )

    with province_column:

        st.markdown(
            "#### Top provinces"
        )

        st.dataframe(
            province_data,
            use_container_width=True,
            hide_index=True,
        )

    with district_column:

        st.markdown(
            "#### Top districts"
        )

        st.dataframe(
            district_data,
            use_container_width=True,
            hide_index=True,
        )


# ---------------------------------------------------------
# APPLICANTS
# ---------------------------------------------------------

with applicant_tab:

    st.markdown(
        "#### Applicants with the most records"
    )

    st.dataframe(
        applicant_data,
        use_container_width=True,
        hide_index=True,
    )


# ---------------------------------------------------------
# RELATED COMMODITIES
# ---------------------------------------------------------

with related_tab:

    st.markdown(
        "#### Frequently co-occurring commodities"
    )

    st.caption(
        "These commodities appear alongside "
        f"{selected_commodity} in the same licensing records."
    )

    st.dataframe(
        cooccurrence_data,
        use_container_width=True,
        hide_index=True,
    )

# =========================================================
# INTEGRATED INTELLIGENCE BRIEF
# =========================================================

st.divider()

display_commodity_intelligence_brief(
    commodity=selected_commodity,
    records=matching_records,
)
# =========================================================
# LICENCE RECORDS
# =========================================================

st.divider()

st.subheader(
    "Licence records"
)




licence_table = licence_dataframe(
    visible_licence_records
)


if licence_search.strip():

    st.caption(
        f"{len(licence_table):,} matching records "
        f"within {len(matching_records):,} "
        f"{selected_commodity} licensing records."
    )

else:

    st.caption(
        f"{len(licence_table):,} records contain "
        f"{selected_commodity}."
    )


licence_table_event = st.dataframe(
    licence_table,
    use_container_width=True,
    hide_index=True,
    key="commodity_licence_results_table",
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
                width="medium",
            ),

        "Commodities":
            st.column_config.TextColumn(
                width="large",
            ),

        "Timeframe":
            st.column_config.TextColumn(
                width="medium",
            ),

        "Source":
            st.column_config.LinkColumn(
                display_text="Official source",
                width="medium",
            ),
    },
)

# =========================================================
# SELECTED LICENCE DETAILS
# =========================================================

selected_rows = (
    licence_table_event.selection.rows
)

selected_record = None


if selected_rows:

    selected_index = selected_rows[0]

    if (
        0 <= selected_index
        < len(visible_licence_records)
    ):

        selected_record = (
            visible_licence_records[
                selected_index
            ]
        )


if selected_record is not None:

    st.markdown(
        "### Selected licence"
    )

    st.caption(
        f"Structured licence record associated with "
        f"{selected_commodity}."
    )

    display_licensing_record(
        {
            "record":
                selected_record
        }
    )

    source = clean_text(
        selected_record.get(
            "source_url"
        )
    )

    if source:

        st.link_button(
            "Open official licensing source",
            source,
        )

    # =====================================================
    # CONTEXT NAVIGATION
    # =====================================================

    st.markdown(
        "#### Explore this record"
    )

    nav_col_1, nav_col_2 = st.columns(
        2
    )

    licence_code = clean_text(
        selected_record.get(
            "licence_code"
        )
    )

    applicant = clean_text(
        selected_record.get(
            "applicant"
        )
    )

    with nav_col_1:

        if licence_code:

            if st.button(
                "Open in Licensing Explorer",
                use_container_width=True,
                key=(
                    f"open_licensing_"
                    f"{licence_code}"
                ),
            ):

                st.session_state[
                    "licence_search"
                ] = licence_code

                st.switch_page(
                    "pages/1_Licensing_Explorer.py"
                )

    with nav_col_2:

        if applicant:

            if st.button(
                "Open applicant profile",
                use_container_width=True,
                key=(
                    f"open_applicant_"
                    f"{licence_code}"
                ),
            ):

                st.session_state[
                    "applicant_search"
                ] = applicant

                st.switch_page(
                    "pages/2_Applicant_Explorer.py"
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
    "Download commodity records",
    data=csv_data,
    file_name=(
        f"minelens_{selected_commodity}_licensing_records.csv"
    ),
    mime="text/csv",
)