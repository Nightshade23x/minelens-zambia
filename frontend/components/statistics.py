from __future__ import annotations

import pandas as pd
import streamlit as st

from app.mining_statistics import (
    format_number,
    human_unit,
    ordinal,
)


def display_statistics_results(
    search_result: dict,
) -> None:
    """
    Display structured mining-statistics records.
    """

    records = search_result.get(
        "results",
        [],
    )

    if not records:
        return


    intent = search_result.get(
        "statistics_intent",
    )


    st.subheader(
        "Mining statistics"
    )


    # =====================================================
    # TREND
    # =====================================================

    if intent == "trend":

        ordered = sorted(
            records,
            key=lambda record:
                record["year"],
        )

        first = ordered[0]
        last = ordered[-1]

        first_value = float(
            first["production"]
        )

        last_value = float(
            last["production"]
        )

        change = (
            last_value
            - first_value
        )

        percentage = (
            (
                change
                / first_value
            )
            * 100
            if first_value
            else None
        )

        unit = human_unit(
            last.get(
                "unit"
            )
        )


        metric_1, metric_2, metric_3 = (
            st.columns(
                3
            )
        )


        with metric_1:

            st.metric(
                str(
                    first["year"]
                ),
                (
                    f"{format_number(first_value)} "
                    f"{unit}"
                ),
            )


        with metric_2:

            st.metric(
                str(
                    last["year"]
                ),
                (
                    f"{format_number(last_value)} "
                    f"{unit}"
                ),
            )


        with metric_3:

            st.metric(
                "Overall change",
                (
                    f"{format_number(change)} "
                    f"{unit}"
                ),
                (
                    f"{percentage:+.2f}%"
                    if percentage is not None
                    else None
                ),
            )


        dataframe = pd.DataFrame(
            [
                {
                    "Year":
                        record["year"],

                    "Production":
                        record["production"],
                }
                for record in ordered
            ]
        )


        st.line_chart(
            dataframe.set_index(
                "Year"
            ),
            y="Production",
        )


        st.dataframe(
            dataframe,
            use_container_width=True,
            hide_index=True,
        )

        return


    # =====================================================
    # ONE RECORD
    # =====================================================

    if len(records) == 1:

        record = records[0]

        metric_1, metric_2, metric_3 = (
            st.columns(
                3
            )
        )


        with metric_1:

            st.metric(
                "Production",
                (
                    f"{format_number(record['production'])} "
                    f"{human_unit(record.get('unit'))}"
                ),
            )


        with metric_2:

            rank = record.get(
                "rank_2024"
            )

            st.metric(
                "World rank",
                (
                    ordinal(
                        rank
                    )
                    if rank is not None
                    else "—"
                ),
            )


        with metric_3:

            share = record.get(
                "world_share_percent"
            )

            st.metric(
                "World share",
                (
                    f"{share:.2f}%"
                    if share is not None
                    else "—"
                ),
            )


        quality = record.get(
            "data_quality"
        )

        if quality:

            st.caption(
                f"Data quality: "
                f"{quality.title()}"
            )


        return


    # =====================================================
    # MULTIPLE RECORDS
    # =====================================================

    rows = []

    for record in records:

        rows.append(
            {
                "Rank":
                    record.get(
                        "rank_2024"
                    ),

                "Country":
                    record.get(
                        "country"
                    ),

                "Production":
                    record.get(
                        "production"
                    ),

                "Unit":
                    human_unit(
                        record.get(
                            "unit"
                        )
                    ),

                "World share (%)":
                    record.get(
                        "world_share_percent"
                    ),
            }
        )


    dataframe = pd.DataFrame(
        rows
    )


    st.dataframe(
        dataframe,
        use_container_width=True,
        hide_index=True,
    )