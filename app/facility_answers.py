from __future__ import annotations

import re
from typing import Any


# =========================================================
# TEXT HELPERS
# =========================================================

def clean_text(
    value: Any,
) -> str:
    """
    Normalize arbitrary text for display.
    """

    if value is None:
        return ""

    return " ".join(
        str(value).split()
    )


def normalize_text(
    value: Any,
) -> str:
    """
    Normalize arbitrary text for matching.
    """

    return clean_text(
        value
    ).casefold()


def human_number(
    value: Any,
) -> str:
    """
    Format numeric values without unnecessary decimals.
    """

    if value is None:
        return "unknown"

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

        return f"{int(number):,}"


    return f"{number:,.2f}".rstrip(
        "0"
    ).rstrip(
        "."
    )


def natural_list(
    values: list[str],
) -> str:
    """
    Human-readable list formatting.
    """

    values = [
        clean_text(
            value
        )
        for value in values
        if clean_text(
            value
        )
    ]


    if not values:
        return ""


    if len(
        values
    ) == 1:

        return values[0]


    if len(
        values
    ) == 2:

        return (
            f"{values[0]} and "
            f"{values[1]}"
        )


    return (
        ", ".join(
            values[:-1]
        )
        + f", and {values[-1]}"
    )


# =========================================================
# QUERY INTENT
# =========================================================

def infer_facility_answer_intent(
    query: str,
) -> str:
    """
    Infer what the user wants to know about facilities.
    """

    normalized = normalize_text(
        query
    )


    operator_terms = (
        "who operates",
        "who operate",
        "operator",
        "operated by",
        "operating company",
    )


    ownership_terms = (
        "who owns",
        "owner",
        "owners",
        "ownership",
        "equity",
        "shareholder",
        "shareholders",
    )


    capacity_terms = (
        "capacity",
        "production capacity",
        "annual capacity",
        "how much can",
    )


    location_terms = (
        "where is",
        "where are",
        "located",
        "location",
        "province",
    )


    list_terms = (
        "show",
        "list",
        "which",
        "what mines",
        "what facilities",
        "which mines",
        "which facilities",
    )


    if any(
        term in normalized
        for term in operator_terms
    ):

        return "operator"


    if any(
        term in normalized
        for term in ownership_terms
    ):

        return "ownership"


    if any(
        term in normalized
        for term in capacity_terms
    ):

        return "capacity"


    if any(
        term in normalized
        for term in location_terms
    ):

        return "location"


    if any(
        term in normalized
        for term in list_terms
    ):

        return "list"


    return "summary"


# =========================================================
# SOURCE HELPERS
# =========================================================

def facility_source(
    facility: dict,
    source_id: str,
) -> dict:
    """
    Build one frontend-compatible source record.
    """

    return {
        "source_id": source_id,
        "title": (
            "USGS Minerals Yearbook 2024 "
            "— Zambia Facilities"
        ),
        "document": (
            "2024MYBv3_Facilities_table.csv"
        ),
        "pages": None,
        "source_url": (
            "https://doi.org/10.5066/P1KEQASH"
        ),
        "agency": (
            "U.S. Geological Survey"
        ),
        "supporting_urls": facility.get(
            "sources",
            [],
        ),
    }

# =========================================================
# FACILITY FORMATTING
# =========================================================

def facility_status(
    facility: dict,
) -> str:
    """
    Present grouped facility statuses conservatively.
    """

    statuses = [
        clean_text(
            value
        )
        for value in facility.get(
            "facility_statuses",
            [],
        )
        if clean_text(
            value
        )
    ]


    unique = []

    seen = set()


    for status in statuses:

        key = status.casefold()

        if key in seen:
            continue

        seen.add(
            key
        )

        unique.append(
            status
        )


    if not unique:
        return "Unknown"


    if len(
        unique
    ) == 1:

        return unique[0]


    return "Mixed"


def owner_text(
    facility: dict,
) -> str:
    """
    Format facility ownership.
    """

    owners = facility.get(
        "equity_owners",
        [],
    )

    formatted: list[str] = []

    for owner in owners:

        name = clean_text(
            owner.get(
                "name"
            )
        )

        share = owner.get(
            "share_percent"
        )

        if not name:
            continue

        if share is None:

            formatted.append(
                name
            )

        else:

            formatted.append(
                f"{name} ({human_number(share)}%)"
            )

    return natural_list(
        formatted
    )

def operator_text(
    facility: dict,
) -> str:
    """
    Format major operating company information.
    """

    operators = facility.get(
        "major_operating_companies",
        [],
    )


    return natural_list(
        [
            clean_text(
                operator
            )
            for operator in operators
            if clean_text(
                operator
            )
        ]
    )


def capacity_description(
    record: dict,
) -> str:
    """
    Format one deduplicated capacity record.
    """

    capacity = human_number(
        record.get(
            "capacity"
        )
    )

    unit = clean_text(
        record.get(
            "capacity_unit"
        )
    )


    detail = (
        clean_text(
            record.get(
                "form"
            )
        )
        or clean_text(
            record.get(
                "descriptor"
            )
        )
        or clean_text(
            record.get(
                "type"
            )
        )
    )


    text = " ".join(
        part
        for part in [
            capacity,
            unit,
        ]
        if part
    )


    if detail:

        text += (
            f" for {detail}"
        )


    return text


# =========================================================
# SPECIFIC ANSWERS
# =========================================================

def answer_operator(
    item: dict,
    source_id: str,
) -> str:

    facility = item[
        "facility"
    ]

    name = clean_text(
        facility.get(
            "facility_name"
        )
    )

    operator = operator_text(
        facility
    )

    if not operator:

        return (
            f"The USGS facility record does not "
            f"identify a major operating company "
            f"for {name}. [{source_id}]"
        )

    operator = operator.rstrip(
        "."
    )

    return (
        f"{name} is operated by "
        f"{operator}. [{source_id}]"
    )

def answer_ownership(
    item: dict,
    source_id: str,
) -> str:

    facility = item[
        "facility"
    ]


    name = clean_text(
        facility.get(
            "facility_name"
        )
    )


    ownership = owner_text(
        facility
    )


    if not ownership:

        return (
            f"The USGS facility record does not "
            f"provide equity ownership information "
            f"for {name}. [{source_id}]"
        )


    return (
        f"The recorded ownership of {name} is "
        f"{ownership}. [{source_id}]"
    )


def answer_location(
    item: dict,
    source_id: str,
) -> str:

    facility = item[
        "facility"
    ]


    name = clean_text(
        facility.get(
            "facility_name"
        )
    )


    location = clean_text(
        facility.get(
            "location_description"
        )
    )


    province = clean_text(
        facility.get(
            "province"
        )
    )


    if location:

        return (
            f"{name} is recorded at "
            f"{location}. [{source_id}]"
        )


    if province:

        return (
            f"{name} is recorded in "
            f"{province} Province. "
            f"[{source_id}]"
        )


    return (
        f"The USGS facility record does not "
        f"provide a usable location for "
        f"{name}. [{source_id}]"
    )


def answer_capacity(
    item: dict,
    source_id: str,
) -> str:

    facility = item[
        "facility"
    ]

    name = clean_text(
        facility.get(
            "facility_name"
        )
    )

    capacities = item.get(
        "capacity_records",
        [],
    )

    if not capacities:

        return (
            f"The USGS facility record does not "
            f"provide a numeric production capacity "
            f"for the requested product at "
            f"{name}. [{source_id}]"
        )

    descriptions = [
        capacity_description(
            capacity
        )
        for capacity in capacities
    ]

    if len(
        descriptions
    ) == 1:

        return (
            f"{name} has a recorded annual "
            f"production capacity of "
            f"{descriptions[0]}. "
            f"[{source_id}]"
        )

    bullet_text = "\n".join(
        f"- {description} [{source_id}]"
        for description in descriptions
    )

    return (
        f"{name} has multiple distinct recorded "
        f"annual production capacities:\n\n"
        f"{bullet_text}\n\n"
        f"Shared-capacity product rows are deduplicated "
        f"rather than summed."
    )

# =========================================================
# LIST ANSWERS
# =========================================================

def answer_facility_list(
    search_result: dict,
) -> tuple[
    str,
    list[str],
    list[dict],
]:
    """
    Build a deterministic list of matching facilities.
    """

    results = search_result.get(
        "results",
        [],
    )

    if not results:
        return (
            "No matching USGS Zambia facilities "
            "were found.",
            [],
            [],
        )

    lines: list[str] = []
    citations: list[str] = []
    sources: list[dict] = []

    for index, item in enumerate(
        results,
        start=1,
    ):
        source_id = f"S{index}"

        facility = item[
            "facility"
        ]

        name = clean_text(
            facility.get(
                "facility_name"
            )
        )

        province = clean_text(
            facility.get(
                "province"
            )
        )

        operator = operator_text(
            facility
        )

        status = facility_status(
            facility
        )

        parts: list[str] = []

        if name:
            parts.append(
                name
            )

        if province:
            parts.append(
                province
            )

        if operator:
            parts.append(
                operator
            )

        if status:
            parts.append(
                status
            )

        line_text = " — ".join(
            part.strip()
            for part in parts
            if part.strip()
        )

        lines.append(
            f"- {line_text} [{source_id}]"
        )

        citations.append(
            source_id
        )

        sources.append(
            facility_source(
                facility,
                source_id,
            )
        )

    filters = search_result.get(
        "filters",
        {},
    )

    commodity = clean_text(
        filters.get(
            "commodity"
        )
    )

    province = clean_text(
        filters.get(
            "province"
        )
    )

    status = clean_text(
        filters.get(
            "status"
        )
    )

    description_parts: list[str] = []

    if status:
        description_parts.append(
            status.lower()
        )

    if commodity:
        description_parts.append(
            commodity.lower()
        )

    description_parts.append(
        "facilities"
    )

    if province:
        description_parts.append(
            f"in {province}"
        )

    description = " ".join(
        description_parts
    )

    bullet_text = "\n".join(
        lines
    )

    answer = (
        f"USGS records the following "
        f"{description}:\n\n"
        f"{bullet_text}"
    )

    return (
        answer,
        citations,
        sources,
    )

# =========================================================
# MAIN ANSWER FUNCTION
# =========================================================

def answer_facility_result(
    query: str,
    search_result: dict,
) -> dict:
    """
    Generate a deterministic answer from structured
    USGS facility search results.
    """

    results = search_result.get(
        "results",
        [],
    )


    if not results:

        return {
            "answer":
                (
                    "No matching USGS Zambia "
                    "facilities were found."
                ),

            "model":
                None,

            "generation_method":
                "structured-facilities",

            "citations":
                [],

            "sources":
                [],
        }


    intent = infer_facility_answer_intent(
        query
    )


    # List-style queries use all returned facilities.
    if intent == "list":

        (
            answer,
            citations,
            sources,
        ) = answer_facility_list(
            search_result
        )


        return {
            "answer":
                answer,

            "model":
                None,

            "generation_method":
                "structured-facilities",

            "citations":
                citations,

            "sources":
                sources,
        }


    # Entity-specific queries answer from the strongest
    # matching facility only.
    top_item = results[0]

    facility = top_item[
        "facility"
    ]

    source_id = "S1"


    if intent == "operator":

        answer = answer_operator(
            top_item,
            source_id,
        )


    elif intent == "ownership":

        answer = answer_ownership(
            top_item,
            source_id,
        )


    elif intent == "capacity":

        answer = answer_capacity(
            top_item,
            source_id,
        )


    elif intent == "location":

        answer = answer_location(
            top_item,
            source_id,
        )


    else:

        name = clean_text(
            facility.get(
                "facility_name"
            )
        )

        province = clean_text(
            facility.get(
                "province"
            )
        )

        operator = operator_text(
            facility
        )

        commodities = natural_list(
            facility.get(
                "commodities",
                [],
            )
        )

        status = facility_status(
            facility
        )


        answer = (
            f"{name} is recorded by USGS as "
            f"{status.lower()}"
        )


        if province:

            answer += (
                f" in {province} Province"
            )


        if operator:

            answer += (
                f", operated by {operator}"
            )


        if commodities:

            answer += (
                f", with recorded commodities "
                f"including {commodities}"
            )


        answer += (
            f". [{source_id}]"
        )


    return {
        "answer":
            answer,

        "model":
            None,

        "generation_method":
            "structured-facilities",

        "citations":
            [
                source_id
            ],

        "sources":
            [
                facility_source(
                    facility,
                    source_id,
                )
            ],
    }