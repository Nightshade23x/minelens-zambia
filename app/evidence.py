from __future__ import annotations

from typing import Any


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

DEFAULT_MAX_EVIDENCE = 5

DEFAULT_MAX_TEXT_CHARS = 1800


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def clean_text(
    value: Any,
) -> str:
    """
    Convert a value to clean single-spaced text.
    """

    if value is None:
        return ""

    return " ".join(
        str(value).split()
    )


def format_pages(
    page_start: Any,
    page_end: Any,
) -> str | None:
    """
    Convert page metadata into a readable page label.
    """

    if page_start is None:
        return None

    if (
        page_end is None
        or page_start == page_end
    ):

        return str(
            page_start
        )

    return (
        f"{page_start}-"
        f"{page_end}"
    )


def truncate_text(
    text: str,
    max_chars: int,
) -> str:
    """
    Limit evidence size while preserving readable text.
    """

    cleaned = clean_text(
        text
    )

    if len(
        cleaned
    ) <= max_chars:

        return cleaned

    shortened = cleaned[
        :max_chars
    ].rstrip()

    return (
        shortened
        + " ..."
    )


# ---------------------------------------------------------
# Document evidence
# ---------------------------------------------------------

def document_result_to_evidence(
    result: dict,
    source_number: int,
    max_text_chars: int = (
        DEFAULT_MAX_TEXT_CHARS
    ),
) -> dict:
    """
    Convert one hybrid document result into the common
    MineLens evidence format.
    """

    chunk = result.get(
        "chunk",
        {},
    )

    page_display = format_pages(
        chunk.get(
            "page_start"
        ),
        chunk.get(
            "page_end"
        ),
    )

    return {
        "source_id": (
            f"S{source_number}"
        ),
        "evidence_type": (
            "document"
        ),
        "title": clean_text(
            chunk.get(
                "source_title"
            )
            or chunk.get(
                "title"
            )
            or chunk.get(
                "document"
            )
            or "Unknown document"
        ),
        "document": clean_text(
            chunk.get(
                "document"
            )
        ),
        "pages": (
            page_display
        ),
        "chunk_id": clean_text(
            chunk.get(
                "chunk_id"
            )
        ),
        "source_url": clean_text(
            chunk.get(
                "source_url"
            )
        ),
        "published_date": clean_text(
            chunk.get(
                "published_date"
            )
        ),
        "source_status": clean_text(
            chunk.get(
                "source_status"
            )
        ),
        "text": truncate_text(
            chunk.get(
                "text",
                "",
            ),
            max_chars=(
                max_text_chars
            ),
        ),
        "retrieval": {
            "hybrid_score": (
                result.get(
                    "rrf_score"
                )
            ),
            "bm25_rank": (
                result.get(
                    "bm25_rank"
                )
            ),
            "bm25_score": (
                result.get(
                    "bm25_score"
                )
            ),
            "semantic_rank": (
                result.get(
                    "semantic_rank"
                )
            ),
            "semantic_score": (
                result.get(
                    "semantic_score"
                )
            ),
        },
    }


# ---------------------------------------------------------
# Licensing evidence
# ---------------------------------------------------------

def licensing_result_to_evidence(
    result: dict,
    source_number: int,
    max_text_chars: int = (
        DEFAULT_MAX_TEXT_CHARS
    ),
) -> dict:
    """
    Convert one structured licensing result into the
    common MineLens evidence format.
    """

    record = result.get(
        "chunk",
        {},
    )

    licence_code = clean_text(
        record.get(
            "licence_code"
        )
    )

    licence_type = clean_text(
        record.get(
            "licence_type"
        )
    )

    applicant = clean_text(
        record.get(
            "applicant"
        )
    )

    decision = clean_text(
        record.get(
            "decision"
        )
    )

    province = clean_text(
        record.get(
            "province"
        )
    )

    districts = [
        clean_text(
            value
        )
        for value in record.get(
            "districts",
            [],
        )
        if clean_text(
            value
        )
    ]

    commodities = [
        clean_text(
            value
        )
        for value in record.get(
            "commodities",
            [],
        )
        if clean_text(
            value
        )
    ]

    return {
        "source_id": (
            f"S{source_number}"
        ),
        "evidence_type": (
            "licensing_record"
        ),
        "title": (
            f"{licence_code} - "
            f"{applicant}"
            if applicant
            else licence_code
        ),
        "document": clean_text(
            record.get(
                "document"
            )
            or (
                "Mining and Non-Mining Rights "
                "Licensing Committee Results"
            )
        ),
        "pages": None,
        "chunk_id": clean_text(
            record.get(
                "chunk_id"
            )
        ),
        "source_url": clean_text(
            record.get(
                "source_url"
            )
        ),
        "published_date": clean_text(
            record.get(
                "published_date"
            )
        ),
        "source_status": clean_text(
            record.get(
                "source_status"
            )
        ),
        "text": truncate_text(
            record.get(
                "text",
                "",
            ),
            max_chars=(
                max_text_chars
            ),
        ),
        "record": {
            "licence_code": (
                licence_code
            ),
            "licence_type": (
                licence_type
            ),
            "licence_type_code": (
                clean_text(
                    record.get(
                        "licence_type_code"
                    )
                )
            ),
            "applicant": (
                applicant
            ),
            "decision": (
                decision
            ),
            "province": (
                province
            ),
            "districts": (
                districts
            ),
            "commodities": (
                commodities
            ),
            "area_hectares": (
                record.get(
                    "area_hectares"
                )
            ),
            "area_text": clean_text(
                record.get(
                    "area_text"
                )
            ),
            "deadline": clean_text(
                record.get(
                    "deadline"
                )
            ),
            "deadline_iso": clean_text(
                record.get(
                    "deadline_iso"
                )
            ),
        },
        "retrieval": {
            "score": (
                result.get(
                    "score"
                )
            ),
        },
    }


# ---------------------------------------------------------
# Unified normalization
# ---------------------------------------------------------

def normalize_evidence(
    search_result: dict,
    max_evidence: int = (
        DEFAULT_MAX_EVIDENCE
    ),
    max_text_chars: int = (
        DEFAULT_MAX_TEXT_CHARS
    ),
) -> list[dict]:
    """
    Convert a search_mine() response into a single common
    evidence representation.

    This allows the answer-generation layer to be
    independent of the retrieval subsystem.
    """

    if max_evidence <= 0:

        raise ValueError(
            "max_evidence must be "
            "greater than zero."
        )

    if max_text_chars <= 0:

        raise ValueError(
            "max_text_chars must be "
            "greater than zero."
        )

    route = search_result.get(
        "route"
    )

    raw_results = search_result.get(
        "results",
        [],
    )

    selected_results = raw_results[
        :max_evidence
    ]

    evidence: list[
        dict
    ] = []

    for source_number, result in enumerate(
        selected_results,
        start=1,
    ):

        if route == "documents":

            item = (
                document_result_to_evidence(
                    result=result,
                    source_number=(
                        source_number
                    ),
                    max_text_chars=(
                        max_text_chars
                    ),
                )
            )

        elif route == "licensing":

            item = (
                licensing_result_to_evidence(
                    result=result,
                    source_number=(
                        source_number
                    ),
                    max_text_chars=(
                        max_text_chars
                    ),
                )
            )

        else:

            raise ValueError(
                "Unknown MineLens route: "
                f"{route}"
            )

        evidence.append(
            item
        )

    return evidence


# ---------------------------------------------------------
# Prompt context formatting
# ---------------------------------------------------------

def evidence_to_context(
    evidence: list[dict],
) -> str:
    """
    Convert normalized evidence into a compact text block
    suitable for a grounded answer-generation prompt.
    """

    blocks: list[
        str
    ] = []

    for item in evidence:

        source_id = item[
            "source_id"
        ]

        lines = [
            (
                f"[{source_id}]"
            ),
            (
                "Type: "
                f"{item.get('evidence_type')}"
            ),
            (
                "Title: "
                f"{item.get('title')}"
            ),
        ]

        document = item.get(
            "document"
        )

        if document:

            lines.append(
                "Document: "
                f"{document}"
            )

        pages = item.get(
            "pages"
        )

        if pages:

            lines.append(
                "Pages: "
                f"{pages}"
            )

        published_date = item.get(
            "published_date"
        )

        if published_date:

            lines.append(
                "Published: "
                f"{published_date}"
            )

        source_url = item.get(
            "source_url"
        )

        if source_url:

            lines.append(
                "URL: "
                f"{source_url}"
            )

        record = item.get(
            "record"
        )

        if record:

            lines.append(
                "Structured record:"
            )

            for key, value in (
                record.items()
            ):

                if (
                    value is None
                    or value == ""
                    or value == []
                ):

                    continue

                if isinstance(
                    value,
                    list,
                ):

                    value = ", ".join(
                        str(
                            item_value
                        )
                        for item_value
                        in value
                    )

                lines.append(
                    f"  {key}: "
                    f"{value}"
                )

        text = item.get(
            "text"
        )

        if text:

            lines.append(
                "Evidence:"
            )

            lines.append(
                text
            )

        blocks.append(
            "\n".join(
                lines
            )
        )

    return "\n\n".join(
        blocks
    )


# ---------------------------------------------------------
# Citation helpers
# ---------------------------------------------------------

def evidence_sources(
    evidence: list[dict],
) -> list[dict]:
    """
    Return compact source metadata for final display.
    """

    sources: list[
        dict
    ] = []

    for item in evidence:

        sources.append(
            {
                "source_id": (
                    item.get(
                        "source_id"
                    )
                ),
                "title": (
                    item.get(
                        "title"
                    )
                ),
                "document": (
                    item.get(
                        "document"
                    )
                ),
                "pages": (
                    item.get(
                        "pages"
                    )
                ),
                "source_url": (
                    item.get(
                        "source_url"
                    )
                ),
            }
        )

    return sources