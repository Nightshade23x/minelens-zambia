from __future__ import annotations

import re
from pathlib import Path
from typing import Any


SPECIAL_SOURCE_TITLES = {
    "zambia_national_critical_minerals_strategy_2024_2028.pdf":
        "Zambia National Critical Minerals Strategy 2024–2028",

    "zambia_mining_fees_area_charges_2024.pdf":
        "Prescribed Application Fees and Area Charges 2024",

    "zambia_licensing_committee_results_june_2026.html":
        "Mining Licensing Committee Results — June 2026",
}


SPECIAL_SOURCE_AGENCIES = {
    "zambia_licensing_committee_results_june_2026.html":
        "Ministry of Mines and Minerals Development",
}


def clean_text(value: Any) -> str:
    """
    Convert arbitrary values into clean one-line text.
    """

    if value is None:
        return ""

    return " ".join(
        str(value).split()
    )


def route_label(route: str) -> str:
    """
    Convert internal route names into readable labels.
    """

    if route == "licensing":
        return "Licensing"

    if route == "documents":
        return "Documents"

    return clean_text(route)


def generation_label(
    generation_method: str | None,
) -> str:
    """
    Convert answer generation identifiers
    into user-friendly labels.
    """

    labels = {
        "deterministic-fee": "Fee extraction",
        "deterministic-licensing": "Structured licence",
        "deterministic-critical-minerals": "Mineral extraction",
        "ollama": "Grounded local LLM",
        "no-evidence": "No evidence",
        "error": "Generation error",
    }

    if not generation_method:
        return "Unknown"

    return labels.get(
        generation_method,
        generation_method,
    )


def looks_like_filename(
    value: str,
) -> bool:
    """
    Return True when a string appears to be a raw filename.
    """

    value_lower = value.lower()

    return (
        value_lower.endswith(".pdf")
        or value_lower.endswith(".html")
        or value_lower.endswith(".htm")
        or "_" in value
    )


def prettify_filename(
    value: str,
) -> str:
    """
    Convert a raw source filename into readable text.
    """

    value = clean_text(
        value
    )

    if not value:
        return "Official source"

    raw_name = Path(
        value
    ).name

    if (
        raw_name
        in SPECIAL_SOURCE_TITLES
    ):
        return (
            SPECIAL_SOURCE_TITLES[
                raw_name
            ]
        )

    stem = Path(
        raw_name
    ).stem

    stem = (
        stem
        .replace("_", " ")
        .replace("-", " ")
    )

    stem = re.sub(
        r"\b(\d{4})\s+(\d{4})\b",
        r"\1–\2",
        stem,
    )

    return stem.title()


def friendly_source_title(
    source: dict,
) -> str:
    """
    Choose the most readable title available
    for a MineLens source.
    """

    document = clean_text(
        source.get(
            "document"
        )
    )

    if document:

        raw_name = Path(
            document
        ).name

        if (
            raw_name
            in SPECIAL_SOURCE_TITLES
        ):
            return (
                SPECIAL_SOURCE_TITLES[
                    raw_name
                ]
            )

    title = clean_text(
        source.get(
            "title"
        )
    )

    if (
        title
        and not looks_like_filename(
            title
        )
    ):
        return title

    if title:
        return prettify_filename(
            title
        )

    if document:
        return prettify_filename(
            document
        )

    return "Official source"


def source_agency(
    source: dict,
) -> str:
    """
    Return a readable source agency when available.
    """

    agency = clean_text(
        source.get(
            "agency"
        )
    )

    if agency:
        return agency

    document = clean_text(
        source.get(
            "document"
        )
    )

    if document:

        raw_name = Path(
            document
        ).name

        return (
            SPECIAL_SOURCE_AGENCIES.get(
                raw_name,
                "",
            )
        )

    return ""