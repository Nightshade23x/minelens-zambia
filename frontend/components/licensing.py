from __future__ import annotations

import streamlit as st

from frontend.utils.display import clean_text


def licensing_answer_summary(
    evidence: list[dict],
) -> str | None:
    """
    Build a concise frontend summary for one
    structured licensing record.

    The detailed record is displayed separately,
    so the answer does not need to repeat every field.
    """

    licensing_items = [
        item
        for item in evidence
        if (
            item.get("evidence_type")
            == "licensing_record"
        )
    ]

    if len(licensing_items) != 1:
        return None

    item = licensing_items[0]

    record = item.get(
        "record",
        {},
    )

    source_id = clean_text(
        item.get("source_id")
    ) or "S1"

    licence_code = clean_text(
        record.get("licence_code")
    )

    applicant = clean_text(
        record.get("applicant")
    )

    decision = clean_text(
        record.get("decision")
    )

    licence_type = clean_text(
        record.get("licence_type")
    )

    province = clean_text(
        record.get("province")
    )

    districts = record.get(
        "districts",
        [],
    )

    if isinstance(
        districts,
        list,
    ):
        district = ", ".join(
            clean_text(value)
            for value in districts
            if clean_text(value)
        )

    else:
        district = clean_text(
            districts
        )

    if not licence_code:
        return None

    first_sentence = (
        f"Licence {licence_code}"
    )

    if applicant:
        first_sentence += (
            f" for {applicant}"
        )

    if decision:
        first_sentence += (
            f" was {decision.lower()}."
        )

    else:
        first_sentence += "."

    second_sentence = ""

    if licence_type:

        second_sentence = (
            f"It is a {licence_type}"
        )

        location_parts = [
            value
            for value in [
                district,
                province,
            ]
            if value
        ]

        if location_parts:
            second_sentence += (
                " in "
                + ", ".join(
                    location_parts
                )
            )

        second_sentence += "."

    return clean_text(
        f"{first_sentence} "
        f"{second_sentence} "
        f"[{source_id}]"
    )


def display_licensing_record(
    evidence_item: dict,
) -> None:
    """
    Render one structured MineLens licence card.
    """

    record = evidence_item.get(
        "record",
        {},
    )

    licence_code = clean_text(
        record.get("licence_code")
    )

    licence_type = clean_text(
        record.get("licence_type")
    )

    applicant = clean_text(
        record.get("applicant")
    )

    decision = clean_text(
        record.get("decision")
    )

    province = clean_text(
        record.get("province")
    )

    districts = record.get(
        "districts",
        [],
    )

    commodities = record.get(
        "commodities",
        [],
    )

    area_text = clean_text(
        record.get("area_text")
    )

    deadline = clean_text(
        record.get("deadline")
    )

    if isinstance(
        districts,
        list,
    ):
        district_text = ", ".join(
            clean_text(item)
            for item in districts
            if clean_text(item)
        )

    else:
        district_text = clean_text(
            districts
        )

    if isinstance(
        commodities,
        list,
    ):
        commodity_text = ", ".join(
            clean_text(item)
            for item in commodities
            if clean_text(item)
        )

    else:
        commodity_text = clean_text(
            commodities
        )

    with st.container(
        border=True,
    ):

        top_left, top_right = st.columns(
            [4, 1]
        )

        with top_left:

            st.markdown(
                f"### {licence_code or 'Licence record'}"
            )

            if licence_type:
                st.caption(
                    licence_type
                )

        with top_right:

            if decision:

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

        st.divider()

        left_column, right_column = (
            st.columns(2)
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

            if commodity_text:
                st.markdown(
                    f"**Commodities**  \n"
                    f"{commodity_text}"
                )

        with right_column:

            st.markdown(
                f"**Province**  \n"
                f"{province or '—'}"
            )

            st.markdown(
                f"**District**  \n"
                f"{district_text or '—'}"
            )

            st.markdown(
                f"**Stipulated timeframe**  \n"
                f"{deadline or '—'}"
            )