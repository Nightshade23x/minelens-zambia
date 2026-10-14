from __future__ import annotations

import re

import streamlit as st

from frontend.utils.display import clean_text


MONTH_NUMBERS = {
    "january": "01",
    "february": "02",
    "march": "03",
    "april": "04",
    "may": "05",
    "june": "06",
    "july": "07",
    "august": "08",
    "september": "09",
    "october": "10",
    "november": "11",
    "december": "12",
}


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

def licensing_history_answer_summary(
    evidence: list[dict],
) -> str | None:
    """
    Build a concise summary for a licensing
    decision-history query.
    """

    licensing_items = [
        item
        for item in evidence
        if (
            item.get(
                "evidence_type"
            )
            == "licensing_record"
        )
    ]

    if len(
        licensing_items
    ) < 2:
        return None

    ordered = sorted(
        licensing_items,
        key=(
            licensing_history_sort_key
        ),
    )

    first_record = (
        ordered[
            0
        ].get(
            "record",
            {},
        )
    )

    latest_item = ordered[
        -1
    ]

    latest_record = (
        latest_item.get(
            "record",
            {},
        )
    )

    licence_code = clean_text(
        latest_record.get(
            "licence_code"
        )
    )

    first_decision = clean_text(
        first_record.get(
            "decision"
        )
    )

    latest_decision = clean_text(
        latest_record.get(
            "decision"
        )
    )

    latest_source = clean_text(
        latest_item.get(
            "source_id"
        )
    )

    if not licence_code:
        return None

    if (
        first_decision
        and latest_decision
        and first_decision
        != latest_decision
    ):

        answer = (
            f"{licence_code} changed from "
            f"{first_decision} to "
            f"{latest_decision}. "
            f"Latest committee decision: "
            f"{latest_decision}."
        )

    else:

        answer = (
            f"Latest committee decision for "
            f"{licence_code}: "
            f"{latest_decision or 'Not recorded'}."
        )

    if latest_source:

        answer += (
            f" [{latest_source}]"
        )

    return answer

def display_decision_status(
    decision: str,
) -> None:
    """
    Render a committee decision using a consistent
    Streamlit status element.
    """

    normalized = clean_text(
        decision
    ).lower()

    if normalized == "approved":

        st.success(
            decision
        )

    elif normalized == "rejected":

        st.error(
            decision
        )

    elif normalized == "deferred":

        st.info(
            decision
        )

    elif decision:

        st.warning(
            decision
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

    deadline = normalize_deadline_text(
        record.get(
            "deadline"
        )
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
                f"### "
                f"{licence_code or 'Licence record'}"
            )

            if licence_type:

                st.caption(
                    licence_type
                )

        with top_right:

            if decision:

                display_decision_status(
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
                "**Stipulated timeframe**  \n"
                f"{deadline or '—'}"
            )

def normalize_deadline_text(
    value: str | None,
) -> str:
    """
    Clean minor spacing artifacts in displayed
    licensing deadlines without changing stored data.
    """

    text = clean_text(
        value
    )

    if not text:
        return ""

    text = re.sub(
        r"\b(\d{1,2})\s+(st|nd|rd|th)\b",
        r"\1\2",
        text,
        flags=re.IGNORECASE,
    )

    return text

def format_event_date(
    value: str | None,
) -> str:
    """
    Format an ISO date as a human-readable date.
    """

    text = clean_text(
        value
    )

    if not text:
        return ""

    match = re.fullmatch(
        r"(\d{4})-(\d{2})-(\d{2})",
        text,
    )

    if match is None:
        return text

    year = match.group(
        1
    )

    month_number = int(
        match.group(
            2
        )
    )

    day = int(
        match.group(
            3
        )
    )

    month_names = (
        "",
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    )

    if not (
        1
        <= month_number
        <= 12
    ):
        return text

    return (
        f"{day} "
        f"{month_names[month_number]} "
        f"{year}"
    )


def licensing_batch_from_document(
    evidence_item: dict,
) -> tuple[
    str,
    str,
]:
    """
    Infer a committee batch label and sortable date
    from a dated licensing filename.
    """

    document = clean_text(
        evidence_item.get(
            "document"
        )
    ).lower()

    pattern = (
        r"_("
        + "|".join(
            MONTH_NUMBERS.keys()
        )
        + r")_(20\d{2})"
    )

    match = re.search(
        pattern,
        document,
    )

    if match is None:

        return (
            "",
            "",
        )

    month = match.group(
        1
    )

    year = match.group(
        2
    )

    label = (
        f"{month.title()} "
        f"{year} committee batch"
    )

    sort_date = (
        f"{year}-"
        f"{MONTH_NUMBERS[month]}-01"
    )

    return (
        label,
        sort_date,
    )


def licensing_history_sort_key(
    evidence_item: dict,
) -> str:
    """
    Sort licensing events chronologically.
    """

    effective_date = clean_text(
        evidence_item.get(
            "effective_date"
        )
    )

    if effective_date:
        return effective_date

    (
        _,
        batch_date,
    ) = licensing_batch_from_document(
        evidence_item
    )

    if batch_date:
        return batch_date

    published_date = clean_text(
        evidence_item.get(
            "published_date"
        )
    )

    return published_date


def licensing_history_event_label(
    evidence_item: dict,
) -> str:
    """
    Build the most accurate human-readable label for
    one licensing committee event.
    """

    effective_date = (
        format_event_date(
            evidence_item.get(
                "effective_date"
            )
        )
    )

    if effective_date:
        return effective_date

    (
        batch_label,
        _,
    ) = licensing_batch_from_document(
        evidence_item
    )

    if batch_label:
        return batch_label

    published_date = (
        format_event_date(
            evidence_item.get(
                "published_date"
            )
        )
    )

    if published_date:

        return (
            f"Published "
            f"{published_date}"
        )

    return "Committee record"


def display_licensing_history(
    evidence: list[dict],
) -> None:
    """
    Render a chronological licensing-decision timeline.
    """

    licensing_items = [
        item
        for item in evidence
        if (
            item.get(
                "evidence_type"
            )
            == "licensing_record"
        )
    ]

    if not licensing_items:
        return

    if len(
        licensing_items
    ) == 1:

        display_licensing_record(
            licensing_items[
                0
            ]
        )

        return

    ordered = sorted(
        licensing_items,
        key=(
            licensing_history_sort_key
        ),
    )

    latest_item = ordered[
        -1
    ]

    latest_record = (
        latest_item.get(
            "record",
            {},
        )
    )

    licence_code = clean_text(
        latest_record.get(
            "licence_code"
        )
    )

    applicant = clean_text(
        latest_record.get(
            "applicant"
        )
    )

    licence_type = clean_text(
        latest_record.get(
            "licence_type"
        )
    )

    latest_decision = clean_text(
        latest_record.get(
            "decision"
        )
    )

    with st.container(
        border=True,
    ):

        header_left, header_right = (
            st.columns(
                [4, 1.3]
            )
        )

        with header_left:

            st.markdown(
                f"### "
                f"{licence_code or 'Licence history'}"
            )

            details = [
                value
                for value in (
                    applicant,
                    licence_type,
                )
                if value
            ]

            if details:

                st.caption(
                    " · ".join(
                        details
                    )
                )

        with header_right:

            st.caption(
                "Latest decision"
            )

            if latest_decision:

                display_decision_status(
                    latest_decision
                )

    st.markdown(
        "#### Decision timeline"
    )

    decisions: list[str] = []

    for index, item in enumerate(
        ordered
    ):

        record = item.get(
            "record",
            {},
        )

        decision = clean_text(
            record.get(
                "decision"
            )
        )

        deadline = normalize_deadline_text(
            record.get(
                "deadline"
            )
        )

        source_id = clean_text(
            item.get(
                "source_id"
            )
        )

        event_label = (
            licensing_history_event_label(
                item
            )
        )

        if decision:

            decisions.append(
                decision
            )

        is_latest = (
            index
            == len(
                ordered
            )
            - 1
        )

        with st.container(
            border=True,
        ):

            event_left, event_right = (
                st.columns(
                    [4, 1]
                )
            )

            with event_left:

                st.markdown(
                    f"**{event_label}**"
                )

            with event_right:

                if is_latest:

                    st.caption(
                        "LATEST"
                    )

            if decision:

                display_decision_status(
                    decision
                )

            if deadline:

                st.markdown(
                    "**Stipulated timeframe**  \n"
                    f"{deadline}"
                )

            if source_id:

                source_label = (
                    event_label
                    .replace(
                        " committee batch",
                        "",
                    )
                )

                st.caption(
                    "Official committee source"
                    f" · {source_label}"
                    f" · {source_id}"
                )

        if not is_latest:

            st.markdown(
                (
                    "<div style='"
                    "text-align:center;"
                    "font-size:1.6rem;"
                    "line-height:1.2;"
                    "'>↓</div>"
                ),
                unsafe_allow_html=True,
            )

    if (
        len(decisions) >= 2
        and decisions[0]
        != decisions[-1]
    ):

        st.info(
            "Decision changed from "
            f"**{decisions[0]}** "
            "to "
            f"**{decisions[-1]}**."
        )

    st.caption(
        "These are licensing committee decisions. "
        "An Approved decision is not treated by "
        "MineLens as proof that a mining right has "
        "been issued or is currently active."
    )