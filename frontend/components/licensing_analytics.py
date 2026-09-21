from __future__ import annotations

from collections import Counter
from typing import Any

import pandas as pd
import streamlit as st

from frontend.utils.display import clean_text

import altair as alt
# =========================================================
# VALUE HELPERS
# =========================================================

def _text_value(
    record: dict,
    key: str,
) -> str:
    """
    Return a clean text value from a licensing record.
    """

    return clean_text(
        record.get(key)
    )


def _list_value(
    record: dict,
    key: str,
) -> list[str]:
    """
    Normalize a licensing field into a list of strings.
    """

    value: Any = record.get(
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


# =========================================================
# DECISION NORMALIZATION
# =========================================================

def _canonical_decision(
    value: str,
) -> str:
    """
    Normalize equivalent licensing decision labels.

    The source data may contain small wording variations
    such as "Approval" and "Approved". These represent the
    same analytical category and should not appear as
    separate bars.
    """

    value = clean_text(
        value
    )

    if not value:
        return ""

    normalized = value.casefold()

    decision_aliases = {
        "approval": "Approved",
        "approved": "Approved",

        "defer": "Deferred",
        "deferred": "Deferred",

        "reject": "Rejected",
        "rejected": "Rejected",
    }

    return decision_aliases.get(
        normalized,
        value,
    )


# =========================================================
# COUNTING HELPERS
# =========================================================

def _count_text_field(
    records: list[dict],
    key: str,
) -> Counter:
    """
    Count values from a normal text field.
    """

    counter: Counter = Counter()

    for record in records:

        value = _text_value(
            record,
            key,
        )

        if value:
            counter[
                value
            ] += 1

    return counter


def _count_decisions(
    records: list[dict],
) -> Counter:
    """
    Count normalized decision categories.
    """

    counter: Counter = Counter()

    for record in records:

        decision = _canonical_decision(
            _text_value(
                record,
                "decision",
            )
        )

        if decision:
            counter[
                decision
            ] += 1

    return counter


def _count_list_field(
    records: list[dict],
    key: str,
) -> Counter:
    """
    Count values from a list-valued field.

    Each licence contributes once to each listed value.
    """

    counter: Counter = Counter()

    for record in records:

        values = set(
            _list_value(
                record,
                key,
            )
        )

        for value in values:
            counter[
                value
            ] += 1

    return counter


# =========================================================
# DATAFRAME HELPERS
# =========================================================

def _counter_dataframe(
    counter: Counter,
    *,
    top_n: int | None = None,
) -> pd.DataFrame:
    """
    Convert a Counter into a chart-friendly dataframe.
    """

    if top_n is None:
        items = counter.most_common()

    else:
        items = counter.most_common(
            top_n
        )

    return pd.DataFrame(
        items,
        columns=[
            "Category",
            "Records",
        ],
    )


# =========================================================
# CHART HELPER
# =========================================================


def _display_chart(
    title: str,
    dataframe: pd.DataFrame,
    *,
    caption: str | None = None,
) -> None:
    """
    Render one analytics bar chart with
    visible record counts above each bar.
    """

    st.markdown(
        f"#### {title}"
    )

    if dataframe.empty:

        st.info(
            "No data available for "
            "the current filters."
        )

        return

    max_records = int(
        dataframe["Records"].max()
    )

    y_max = max(
        1,
        int(
            max_records * 1.12
        ),
    )

    base = alt.Chart(
        dataframe
    ).encode(
        x=alt.X(
            "Category:N",
            sort="-y",
            title=None,
            axis=alt.Axis(
                labelAngle=-45,
            ),
        ),
        y=alt.Y(
            "Records:Q",
            title="Records",
            scale=alt.Scale(
                domain=[
                    0,
                    y_max,
                ]
            ),
        ),
    )

    bars = base.mark_bar()

    labels = base.mark_text(
        dy=-10,
        fontSize=14,
        fontWeight="bold",
        color="white",
    ).encode(
        text=alt.Text(
            "Records:Q",
            format=",",
        )
    )

    combined_chart = (
        bars
        + labels
    ).properties(
        height=380,
    )

    st.altair_chart(
        combined_chart,
        use_container_width=True,
    )

    if caption:
        st.caption(
            caption
        )
# =========================================================
# ANALYTICS COMPONENT
# =========================================================

def display_licensing_analytics(
    records: list[dict],
) -> None:
    """
    Render interactive licensing analytics.

    All charts use the current filtered Explorer
    population and therefore update automatically
    whenever filters change.
    """

    st.subheader(
        "Licensing analytics"
    )

    st.caption(
        "Charts reflect the records matching "
        "the current Explorer filters."
    )

    if not records:

        st.info(
            "No records are available "
            "for analytics."
        )

        return

    # -----------------------------------------------------
    # Counts
    # -----------------------------------------------------

    decision_counts = (
        _count_decisions(
            records
        )
    )

    licence_type_counts = (
        _count_text_field(
            records,
            "licence_type",
        )
    )

    province_counts = (
        _count_text_field(
            records,
            "province",
        )
    )

    district_counts = (
        _count_list_field(
            records,
            "districts",
        )
    )

    commodity_counts = (
        _count_list_field(
            records,
            "commodities",
        )
    )

    # -----------------------------------------------------
    # Dataframes
    # -----------------------------------------------------

    decision_frame = (
        _counter_dataframe(
            decision_counts
        )
    )

    licence_type_frame = (
        _counter_dataframe(
            licence_type_counts
        )
    )

    province_frame = (
        _counter_dataframe(
            province_counts,
            top_n=10,
        )
    )

    district_frame = (
        _counter_dataframe(
            district_counts,
            top_n=10,
        )
    )

    commodity_frame = (
        _counter_dataframe(
            commodity_counts,
            top_n=15,
        )
    )

    # -----------------------------------------------------
    # Tabs
    # -----------------------------------------------------

    (
        tab_decisions,
        tab_types,
        tab_locations,
        tab_commodities,
    ) = st.tabs(
        [
            "Decisions",
            "Licence types",
            "Locations",
            "Commodities",
        ]
    )

    # -----------------------------------------------------
    # DECISIONS
    # -----------------------------------------------------

    with tab_decisions:

        _display_chart(
            "Decision distribution",
            decision_frame,
            caption=(
                "Equivalent source labels are combined "
                "for analytics, for example "
                "\"Approval\" and \"Approved\"."
            ),
        )

        st.dataframe(
            decision_frame,
            use_container_width=True,
            hide_index=True,
        )

    # -----------------------------------------------------
    # LICENCE TYPES
    # -----------------------------------------------------

    with tab_types:

        _display_chart(
            "Licence types",
            licence_type_frame,
        )

        st.dataframe(
            licence_type_frame,
            use_container_width=True,
            hide_index=True,
        )

    # -----------------------------------------------------
    # LOCATIONS
    # -----------------------------------------------------

    with tab_locations:

        province_column, district_column = (
            st.columns(
                2
            )
        )

        with province_column:

            _display_chart(
                "Top provinces",
                province_frame,
            )

        with district_column:

            _display_chart(
                "Top districts",
                district_frame,
            )

    # -----------------------------------------------------
    # COMMODITIES
    # -----------------------------------------------------

    with tab_commodities:

        _display_chart(
            "Top commodities",
            commodity_frame,
            caption=(
                "A licence may contain multiple commodities, "
                "so commodity counts can exceed the number "
                "of matching licence records."
            ),
        )

        st.dataframe(
            commodity_frame,
            use_container_width=True,
            hide_index=True,
        )