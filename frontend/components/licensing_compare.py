from __future__ import annotations

from typing import Any

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


def _joined_value(
    record: dict,
    key: str,
) -> str:
    """
    Convert list-valued fields into readable text.
    """

    return ", ".join(
        _list_value(
            record,
            key,
        )
    )


def _source_url(
    record: dict,
) -> str:
    """
    Return an official source URL if present.
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


def _record_label(
    record: dict,
) -> str:
    """
    Build a useful searchable selectbox label.
    """

    code = _text_value(
        record,
        "licence_code",
    )

    applicant = _text_value(
        record,
        "applicant",
    )

    if code and applicant:
        return (
            f"{code} — {applicant}"
        )

    return (
        code
        or applicant
        or "Unknown licence"
    )


def _format_area(
    record: dict,
) -> str:
    """
    Prefer the human-readable area field.
    """

    area_text = _text_value(
        record,
        "area_text",
    )

    if area_text:
        return area_text

    area = record.get(
        "area_hectares"
    )

    if isinstance(
        area,
        (int, float),
    ):
        return (
            f"{area:,.4f} ha"
        )

    return "—"


def _field_values(
    record: dict,
) -> dict[str, str]:
    """
    Convert a licence record into comparison fields.
    """

    return {
        "Licence code": (
            _text_value(
                record,
                "licence_code",
            )
            or "—"
        ),

        "Applicant": (
            _text_value(
                record,
                "applicant",
            )
            or "—"
        ),

        "Licence type": (
            _text_value(
                record,
                "licence_type",
            )
            or "—"
        ),

        "Decision": (
            _text_value(
                record,
                "decision",
            )
            or "—"
        ),

        "Province": (
            _text_value(
                record,
                "province",
            )
            or "—"
        ),

        "District": (
            _joined_value(
                record,
                "districts",
            )
            or "—"
        ),

        "Area": _format_area(
            record
        ),

        "Commodities": (
            _joined_value(
                record,
                "commodities",
            )
            or "—"
        ),

        "Stipulated timeframe": (
            _text_value(
                record,
                "deadline",
            )
            or "—"
        ),
    }


def _decision_display(
    decision: str,
) -> None:
    """
    Render a decision using the same status style
    as the rest of MineLens.
    """

    if not decision:
        return

    if decision.lower() == "approved":
        st.success(
            decision
        )

    elif decision.lower() == "rejected":
        st.error(
            decision
        )

    else:
        st.info(
            decision
        )


# =========================================================
# SUMMARY CARD
# =========================================================

def _display_comparison_card(
    record: dict,
    heading: str,
) -> None:
    """Render a compact licence comparison card."""

    fields = _field_values(record)

    code = fields["Licence code"]
    applicant = fields["Applicant"]
    licence_type = fields["Licence type"]
    decision = fields["Decision"]

    location_parts = [
        value
        for value in (
            fields["District"],
            fields["Province"],
        )
        if value and value != "?"
    ]

    location = ", ".join(location_parts) or "?"
    area = fields["Area"]
    source_url = _source_url(record)

    decision_colors = {
        "approved": "green",
        "approval": "green",
        "rejected": "red",
        "reject": "red",
        "deferred": "orange",
        "defer": "orange",
    }

    with st.container(border=True):
        st.caption(heading)

        st.markdown(
            f"#### {code}"
        )

        st.markdown(
            f"**{applicant}**"
        )

        if licence_type != "?":
            st.caption(licence_type)

        if decision != "?":
            color = decision_colors.get(
                decision.casefold()
            )

            if color:
                st.markdown(
                    f":{color}[**{decision}**]"
                )
            else:
                st.markdown(
                    f"**{decision}**"
                )

        st.divider()

        location_col, area_col = st.columns(2)

        with location_col:
            st.caption("Location")
            st.write(location)

        with area_col:
            st.caption("Recorded area")
            st.write(area)

        if source_url:
            st.link_button(
                "Official source",
                source_url,
            )


# =========================================================
# COMPARISON TABLE
# =========================================================

def _comparison_dataframe(
    record_a: dict,
    record_b: dict,
) -> pd.DataFrame:
    """
    Build a field-by-field comparison table.
    """

    values_a = _field_values(
        record_a
    )

    values_b = _field_values(
        record_b
    )

    rows: list[dict] = []

    for field in values_a:

        value_a = values_a[
            field
        ]

        value_b = values_b[
            field
        ]

        rows.append(
            {
                "Field": field,
                "Licence A": value_a,
                "Licence B": value_b,
                "Match": (
                    "Same"
                    if value_a == value_b
                    else "Different"
                ),
            }
        )

    return pd.DataFrame(
        rows
    )


# =========================================================
# MAIN COMPONENT
# =========================================================

def display_licence_comparison(
    records: list[dict],
) -> None:
    """
    Render a side-by-side comparison tool for MineLens
    licensing records.

    The comparison population follows the current
    Licensing Explorer filters.
    """

    st.subheader(
        "Compare licences"
    )

    st.caption(
        "Select two licensing records from the current "
        "filtered result set and compare them side by side."
    )

    if len(records) < 2:

        st.info(
            "At least two matching licence records "
            "are required for comparison."
        )

        return

    # -----------------------------------------------------
    # BUILD UNIQUE OPTIONS
    # -----------------------------------------------------

    labels: list[str] = []

    lookup: dict[
        str,
        dict,
    ] = {}

    for index, record in enumerate(
        records
    ):

        base_label = _record_label(
            record
        )

        label = (
            f"{base_label} [{index + 1}]"
        )

        labels.append(
            label
        )

        lookup[
            label
        ] = record

    # -----------------------------------------------------
    # SELECTORS
    # -----------------------------------------------------

    selector_a, selector_b = (
        st.columns(
            2
        )
    )

    with selector_a:

        selected_a = st.selectbox(
            "Licence A",
            options=labels,
            index=0,
            key="compare_licence_a",
        )

    with selector_b:

        default_b = (
            1
            if len(labels) > 1
            else 0
        )

        selected_b = st.selectbox(
            "Licence B",
            options=labels,
            index=default_b,
            key="compare_licence_b",
        )

    record_a = lookup[
        selected_a
    ]

    record_b = lookup[
        selected_b
    ]

    # -----------------------------------------------------
    # SAME RECORD WARNING
    # -----------------------------------------------------

    if selected_a == selected_b:

        st.warning(
            "Select two different licence records "
            "to make the comparison useful."
        )

    # -----------------------------------------------------
    # SIDE-BY-SIDE CARDS
    # -----------------------------------------------------

    left_column, right_column = (
        st.columns(
            2
        )
    )

    with left_column:

        _display_comparison_card(
            record_a,
            "Licence A",
        )

    with right_column:

        _display_comparison_card(
            record_b,
            "Licence B",
        )

    # -----------------------------------------------------
    # FIELD COMPARISON
    # -----------------------------------------------------

    st.markdown(
        "#### Field comparison"
    )

    comparison = (
        _comparison_dataframe(
            record_a,
            record_b,
        )
    )

    st.dataframe(
        comparison,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Field":
                st.column_config.TextColumn(
                    width="medium",
                ),

            "Licence A":
                st.column_config.TextColumn(
                    width="large",
                ),

            "Licence B":
                st.column_config.TextColumn(
                    width="large",
                ),

            "Match":
                st.column_config.TextColumn(
                    width="small",
                ),
        },
    )

    # -----------------------------------------------------
    # DIFFERENCE SUMMARY
    # -----------------------------------------------------

    differences = comparison[
        comparison["Match"]
        == "Different"
    ]

    same_fields = comparison[
        comparison["Match"]
        == "Same"
    ]

    metric_1, metric_2 = st.columns(
        2
    )

    with metric_1:

        st.metric(
            "Different fields",
            len(
                differences
            ),
        )

    with metric_2:

        st.metric(
            "Matching fields",
            len(
                same_fields
            ),
        )