from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

import pandas as pd
import streamlit as st
from frontend.components.applicant_rankings import (
    display_applicant_rankings,
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
from frontend.components.licensing_map import display_licensing_map  # noqa: E402
from frontend.styles.theme import apply_theme  # noqa: E402
from frontend.utils.display import clean_text  # noqa: E402
from frontend.utils.licensing_geo import normalized_districts  # noqa: E402


# =========================================================
# PAGE CONFIG
# =========================================================

st.set_page_config(
    page_title="Applicant Explorer | MineLens Zambia",
    page_icon="⛏️",
    layout="wide",
    initial_sidebar_state="expanded",
)

apply_theme()


# =========================================================
# HELPERS
# =========================================================
def clear_applicant_search() -> None:
    """
    Clear the Applicant Explorer search field.
    """

    st.session_state["applicant_search"] = ""
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


def joined_value(
    record: dict,
    key: str,
) -> str:

    return ", ".join(
        list_value(
            record,
            key,
        )
    )


def canonical_decision(
    value: str,
) -> str:
    """
    Normalize equivalent source decision labels
    for applicant-level analytics.
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


def applicant_key(
    value: str,
) -> str:
    """
    Normalize applicant names for grouping.

    This only ignores differences in letter case
    and extra whitespace.
    """

    return clean_text(
        value
    ).casefold()


def build_applicant_groups(
    records: list[dict],
) -> dict[str, dict]:
    """
    Group records by normalized applicant name.

    The most frequently occurring original spelling
    is retained as the display name.
    """

    grouped: dict[str, dict] = {}

    for record in records:

        applicant = text_value(
            record,
            "applicant",
        )

        if not applicant:
            continue

        key = applicant_key(
            applicant
        )

        if key not in grouped:

            grouped[key] = {
                "records": [],
                "names": Counter(),
            }

        grouped[key][
            "records"
        ].append(
            record
        )

        grouped[key][
            "names"
        ][applicant] += 1

    result: dict[str, dict] = {}

    for key, group in grouped.items():

        display_name = (
            group["names"]
            .most_common(1)[0][0]
        )

        result[key] = {
            "display_name": display_name,
            "records": group["records"],
        }

    return result


def top_commodity(
    records: list[dict],
) -> tuple[str, int]:

    counter: Counter = Counter()

    for record in records:

        for commodity in set(
            list_value(
                record,
                "commodities",
            )
        ):
            counter[
                commodity
            ] += 1

    if not counter:
        return (
            "—",
            0,
        )

    return counter.most_common(
        1
    )[0]


def total_area(
    records: list[dict],
) -> float:

    total = 0.0

    for record in records:

        area = record.get(
            "area_hectares"
        )

        if isinstance(
            area,
            (int, float),
        ):
            total += float(
                area
            )

    return total


def records_dataframe(
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

                "Commodities": joined_value(
                    record,
                    "commodities",
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
    "Loading licensing records..."
):

    records = load_records()


applicant_groups = (
    build_applicant_groups(
        records
    )
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
        Applicant Explorer
    </div>

    <div class="minelens-subtitle">
        Explore the licensing activity of mining companies,
        organisations and individual applicants across the
        structured MineLens licensing dataset.
    </div>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# DATASET METRICS
# =========================================================

metric_1, metric_2 = st.columns(
    2
)

with metric_1:

    st.metric(
        "Licensing records",
        f"{len(records):,}",
    )


with metric_2:

    st.metric(
        "Unique applicants",
        f"{len(applicant_groups):,}",
    )


st.divider()


# =========================================================
# APPLICANT SEARCH
# =========================================================

st.subheader(
    "Find an applicant"
)


search_column, clear_column = st.columns(
    [5, 1]
)


with search_column:

    search_query = st.text_input(
        "Search company or applicant",
        placeholder=(
            "e.g. Nisco Industries, "
            "Fountain, Keki Mining..."
        ),
        key="applicant_search",
    )


with clear_column:

    # Adds vertical space so the button aligns
    # with the search input rather than its label.
    st.markdown(
        "<div style='height: 28px;'></div>",
        unsafe_allow_html=True,
    )

    st.button(
        "Clear",
        key="clear_applicant_search_button",
        use_container_width=True,
        on_click=clear_applicant_search,
    )


matching_groups: list[
    tuple[str, dict]
] = []


for key, group in (
    applicant_groups.items()
):

    name = group[
        "display_name"
    ]

    if (
        not search_query
        or search_query.casefold()
        in name.casefold()
    ):

        matching_groups.append(
            (
                key,
                group,
            )
        )


matching_groups.sort(
    key=lambda item: (
        item[1][
            "display_name"
        ].casefold()
    )
)


if not matching_groups:

    st.info(
        "No applicants match that search."
    )

    st.stop()


option_labels: list[str] = []

option_lookup: dict[
    str,
    dict,
] = {}


for key, group in matching_groups:

    count = len(
        group[
            "records"
        ]
    )

    label = (
        f"{group['display_name']} "
        f"({count:,} record"
        f"{'s' if count != 1 else ''})"
    )

    option_labels.append(
        label
    )

    option_lookup[
        label
    ] = group


selected_label = st.selectbox(
    "Select applicant",
    options=option_labels,
)


selected_group = (
    option_lookup[
        selected_label
    ]
)

applicant_name = (
    selected_group[
        "display_name"
    ]
)

applicant_records = (
    selected_group[
        "records"
    ]
)


# =========================================================
# APPLICANT PROFILE
# =========================================================

st.divider()

st.subheader(
    applicant_name
)


decision_counts: Counter = Counter(
    canonical_decision(
        text_value(
            record,
            "decision",
        )
    )
    for record in applicant_records
)


approved = decision_counts.get(
    "Approved",
    0,
)

deferred = decision_counts.get(
    "Deferred",
    0,
)

rejected = decision_counts.get(
    "Rejected",
    0,
)


province_set = {
    text_value(
        record,
        "province",
    )
    for record in applicant_records
    if text_value(
        record,
        "province",
    )
}


district_set = {
    district
    for record in applicant_records
    for district in normalized_districts(
        record
    )
}


commodity_set = {
    commodity
    for record in applicant_records
    for commodity in list_value(
        record,
        "commodities",
    )
}


top_commodity_name, top_commodity_count = (
    top_commodity(
        applicant_records
    )
)


profile_metric_1, profile_metric_2, profile_metric_3, profile_metric_4 = (
    st.columns(
        4
    )
)


with profile_metric_1:

    st.metric(
        "Applications",
        f"{len(applicant_records):,}",
    )


with profile_metric_2:

    st.metric(
        "Approved",
        f"{approved:,}",
    )


with profile_metric_3:

    st.metric(
        "Total recorded area",
        f"{total_area(applicant_records):,.2f} ha",
    )


with profile_metric_4:

    st.metric(
        "Top commodity",
        (
            f"{top_commodity_name} "
            f"({top_commodity_count:,})"
        ),
    )


# =========================================================
# DECISION PROFILE
# =========================================================

st.markdown(
    "### Decision profile"
)


decision_1, decision_2, decision_3 = (
    st.columns(
        3
    )
)


with decision_1:

    st.metric(
        "Approved",
        approved,
    )


with decision_2:

    st.metric(
        "Deferred",
        deferred,
    )


with decision_3:

    st.metric(
        "Rejected",
        rejected,
    )


# =========================================================
# FOOTPRINT
# =========================================================

st.markdown(
    "### Geographic and commodity footprint"
)


footprint_1, footprint_2, footprint_3 = (
    st.columns(
        3
    )
)


with footprint_1:

    st.metric(
        "Provinces",
        len(
            province_set
        ),
    )

    if province_set:

        st.caption(
            ", ".join(
                sorted(
                    province_set
                )
            )
        )


with footprint_2:

    st.metric(
        "Districts",
        len(
            district_set
        ),
    )

    if district_set:

        st.caption(
            ", ".join(
                sorted(
                    district_set
                )
            )
        )


with footprint_3:

    st.metric(
        "Commodities",
        len(
            commodity_set
        ),
    )

    if commodity_set:

        st.caption(
            ", ".join(
                sorted(
                    commodity_set
                )
            )
        )


# =========================================================
# MAP
# =========================================================

st.divider()

display_licensing_map(
    applicant_records
)


# =========================================================
# LICENCE RECORDS
# =========================================================

st.divider()

st.subheader(
    "Licence records"
)


applicant_dataframe = (
    records_dataframe(
        applicant_records
    )
)


st.dataframe(
    applicant_dataframe,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Licence code":
            st.column_config.TextColumn(
                width="medium",
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
# EXPORT
# =========================================================

csv_data = (
    applicant_dataframe
    .to_csv(
        index=False
    )
    .encode(
        "utf-8"
    )
)


safe_filename = (
    applicant_name
    .replace(
        " ",
        "_",
    )
    .replace(
        "/",
        "_",
    )
)


st.download_button(
    "Download applicant records",
    data=csv_data,
    file_name=(
        f"minelens_{safe_filename}_licences.csv"
    ),
    mime="text/csv",
)
# =========================================================
# APPLICANT RANKINGS
# =========================================================

st.divider()

display_applicant_rankings(
    records
)