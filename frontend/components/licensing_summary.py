from __future__ import annotations

from collections import Counter

import pandas as pd
import streamlit as st

from frontend.utils.display import clean_text


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


def _list_value(
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


# =========================================================
# PROVINCE AGGREGATION
# =========================================================

def build_province_summary(
    records: list[dict],
) -> pd.DataFrame:
    """
    Build province-level licensing statistics from
    the currently filtered licensing records.
    """

    province_records: dict[
        str,
        list[dict],
    ] = {}

    for record in records:

        province = _text_value(
            record,
            "province",
        )

        if not province:
            continue

        province_records.setdefault(
            province,
            [],
        ).append(
            record
        )

    rows: list[dict] = []

    for province, province_items in (
        province_records.items()
    ):

        total_records = len(
            province_items
        )

        approved_records = sum(
            _canonical_decision(
                _text_value(
                    record,
                    "decision",
                )
            )
            == "Approved"
            for record in province_items
        )

        if total_records:

            approval_rate = (
                approved_records
                / total_records
                * 100
            )

        else:

            approval_rate = 0.0

        area_values: list[float] = []

        commodities: Counter = Counter()

        for record in province_items:

            area = record.get(
                "area_hectares"
            )

            if isinstance(
                area,
                (int, float),
            ):
                area_values.append(
                    float(area)
                )

            for commodity in set(
                _list_value(
                    record,
                    "commodities",
                )
            ):
                commodities[
                    commodity
                ] += 1

        total_area = sum(
            area_values
        )

        if commodities:

            top_commodity, top_count = (
                commodities.most_common(
                    1
                )[0]
            )

            top_commodity_text = (
                f"{top_commodity} "
                f"({top_count:,})"
            )

        else:

            top_commodity_text = "—"

        rows.append(
            {
                "Province": province,
                "Records": total_records,
                "Approved": approved_records,
                "Approval rate": approval_rate,
                "Recorded area (ha)": total_area,
                "Top commodity": top_commodity_text,
            }
        )

    dataframe = pd.DataFrame(
        rows
    )

    if dataframe.empty:
        return dataframe

    dataframe = (
        dataframe
        .sort_values(
            "Records",
            ascending=False,
        )
        .reset_index(
            drop=True
        )
    )

    return dataframe


# =========================================================
# DISPLAY
# =========================================================

def display_province_summary(
    records: list[dict],
) -> None:
    """
    Render province-level MineLens licensing intelligence.
    """

    st.subheader(
        "Province summary"
    )

    st.caption(
        "Province-level statistics for the licensing "
        "records matching the current Explorer filters."
    )

    if not records:

        st.info(
            "No records are available "
            "for province analysis."
        )

        return

    dataframe = build_province_summary(
        records
    )

    if dataframe.empty:

        st.info(
            "The matching records do not contain "
            "province information."
        )

        return

    # -----------------------------------------------------
    # TABLE
    # -----------------------------------------------------

    st.dataframe(
        dataframe,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Province":
                st.column_config.TextColumn(
                    width="medium",
                ),

            "Records":
                st.column_config.NumberColumn(
                    format="%d",
                    width="small",
                ),

            "Approved":
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

            "Top commodity":
                st.column_config.TextColumn(
                    width="medium",
                ),
        },
    )

    st.caption(
        "Recorded area is the sum of the area values "
        "reported in the matching licensing records. "
        "Top commodity shows the commodity appearing "
        "in the most records for each province."
    )