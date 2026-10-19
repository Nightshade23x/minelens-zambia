from __future__ import annotations

from typing import Any

import streamlit as st


def clean_text(
    value: Any,
) -> str:
    if value is None:
        return ""

    return " ".join(
        str(
            value
        ).split()
    )


def format_number(
    value: Any,
) -> str:
    if value is None:
        return ""

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
        return str(
            int(
                number
            )
        )

    return (
        f"{number:.4f}"
        .rstrip("0")
        .rstrip(".")
    )


def exploration_intent_label(
    value: str | None,
) -> str:
    labels = {
        "highest_intersection":
            "Highest interval grade",

        "highest_individual_assay":
            "Maximum assay",

        "no_reportable_intersections":
            "No reportable intersection",

        "compare_holes":
            "Hole comparison",

        "intersections":
            "Drill intersections",
    }

    return labels.get(
        clean_text(
            value
        ),
        clean_text(
            value
        ).replace(
            "_",
            " ",
        ).title()
        or "Exploration results",
    )


def display_exploration_results(
    search_result: dict,
) -> None:
    """
    Render structured exploration/drilling records.
    """

    results = search_result.get(
        "results",
        [],
    )

    st.subheader(
        "Exploration results"
    )

    st.caption(
        (
            "Structured laboratory drilling results "
            "from the Kabwe exploration programme."
        )
    )

    if not results:

        st.info(
            "No exploration records matched the query."
        )

        return

    hole_ids = sorted(
        {
            clean_text(
                record.get(
                    "hole_id"
                )
            )
            for record in results
            if clean_text(
                record.get(
                    "hole_id"
                )
            )
        }
    )

    targets = sorted(
        {
            clean_text(
                record.get(
                    "target"
                )
            )
            for record in results
            if clean_text(
                record.get(
                    "target"
                )
            )
        }
    )

    metric_1, metric_2, metric_3, metric_4 = (
        st.columns(
            4
        )
    )

    with metric_1:
        st.metric(
            "Results shown",
            len(
                results
            ),
        )

    with metric_2:
        st.metric(
            "Drill holes",
            len(
                hole_ids
            ),
        )

    with metric_3:

        if len(
            targets
        ) == 1:
            target_display = (
                targets[
                    0
                ]
            )

        elif targets:
            target_display = "Multiple"

        else:
            target_display = "—"

        st.metric(
            "Target",
            target_display,
        )

    with metric_4:
        st.metric(
            "Result type",
            exploration_intent_label(
                search_result.get(
                    "exploration_intent"
                )
            ),
        )

    record_types = {
        clean_text(
            record.get(
                "record_type"
            )
        )
        for record in results
    }

    if record_types == {
        "hole_maximum_assay"
    }:

        rows = []

        for record in results:

            rows.append(
                {
                    "Hole":
                        clean_text(
                            record.get(
                                "hole_id"
                            )
                        ),

                    "Target":
                        clean_text(
                            record.get(
                                "target"
                            )
                        ),

                    "Maximum Zn assay (%)":
                        record.get(
                            "maximum_assay_pct"
                        ),

                    "Laboratory":
                        clean_text(
                            record.get(
                                "laboratory"
                            )
                        ),
                }
            )

    else:

        rows = []

        for record in results:

            status = clean_text(
                record.get(
                    "status"
                )
            )

            if (
                status
                == "no_reportable_intersection"
            ):
                status_display = (
                    "No significant reportable intersection"
                )

            else:
                status_display = (
                    "Reported intersection"
                )

            rows.append(
                {
                    "Hole":
                        clean_text(
                            record.get(
                                "hole_id"
                            )
                        ),

                    "Target":
                        clean_text(
                            record.get(
                                "target"
                            )
                        ),

                    "From (m)":
                        record.get(
                            "from_m"
                        ),

                    "To (m)":
                        record.get(
                            "to_m"
                        ),

                    "Width (m)":
                        record.get(
                            "width_m"
                        ),

                    "Zn (%)":
                        record.get(
                            "zinc_pct"
                        ),

                    "Pb (%)":
                        record.get(
                            "lead_pct"
                        ),

                    "Zn cut-off (%)":
                        record.get(
                            "cutoff_zinc_pct"
                        ),

                    "Status":
                        status_display,
                }
            )

    st.dataframe(
        rows,
        use_container_width=True,
        hide_index=True,
    )

    st.caption(
        (
            "Shuka Minerals Plc company disclosure; "
            "laboratory results reported from ALS Laboratories. "
            "These drill intersections and assays are "
            "exploration results, not mineral resource or "
            "reserve estimates."
        )
    )
