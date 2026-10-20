from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path


from typing import Any


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

DEFAULT_MAX_EVIDENCE = 5

DEFAULT_MAX_TEXT_CHARS = 1800

EXPANDED_MAX_TEXT_CHARS = 5000
# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------


ROOT_DIR = (
    Path(__file__)
    .resolve()
    .parents[1]
)

SOURCES_CONFIG_PATH = (
    ROOT_DIR
    / "config"
    / "sources.json"
)


@lru_cache(
    maxsize=1,
)
def load_source_registry() -> dict[str, dict]:
    """
    Load MineLens source metadata by canonical source id.

    This lets evidence created from older processed files
    inherit newer metadata such as source_authority without
    requiring immediate re-ingestion.
    """

    if not SOURCES_CONFIG_PATH.exists():
        return {}

    sources = json.loads(
        SOURCES_CONFIG_PATH.read_text(
            encoding="utf-8"
        )
    )

    return {
        str(
            source.get(
                "id",
                "",
            )
        ).strip():
            source
        for source in sources
        if source.get(
            "id"
        )
    }


def canonical_source_id_from_result(
    result: dict,
) -> str:
    """
    Recover the config/sources.json id from a raw
    retrieval result.
    """

    candidates = [
        result,
        result.get(
            "chunk",
            {},
        ),
        result.get(
            "record",
            {},
        ),
    ]

    for candidate in candidates:

        if not isinstance(
            candidate,
            dict,
        ):
            continue

        value = (
            candidate.get(
                "canonical_source_id"
            )
            or candidate.get(
                "source_id"
            )
        )

        if not value:
            continue

        value = str(
            value
        ).strip()

        # S1, S2, ... are answer citation ids,
        # not canonical registry ids.
        if (
            value.startswith(
                "S"
            )
            and value[
                1:
            ].isdigit()
        ):
            continue

        return value

    # Fallback: identify the configured source by URL.
    source_url = ""

    for candidate in candidates:

        if not isinstance(
            candidate,
            dict,
        ):
            continue

        source_url = str(
            candidate.get(
                "source_url",
                "",
            )
        ).strip()

        if source_url:
            break

    if source_url:

        for (
            source_id,
            metadata,
        ) in load_source_registry().items():

            if (
                str(
                    metadata.get(
                        "url",
                        "",
                    )
                ).strip()
                == source_url
            ):
                return source_id

    return ""


def enrich_evidence_source_metadata(
    item: dict,
    result: dict,
) -> dict:
    """
    Attach canonical source metadata to normalized evidence.
    """

    canonical_source_id = (
        canonical_source_id_from_result(
            result
        )
    )

    if not canonical_source_id:
        return item

    metadata = (
        load_source_registry().get(
            canonical_source_id,
            {},
        )
    )

    item[
        "canonical_source_id"
    ] = canonical_source_id

    for key in (
        "agency",
        "source_authority",
        "document_type",
        "source_type",
    ):

        if (
            not item.get(
                key
            )
            and metadata.get(
                key
            )
        ):
            item[
                key
            ] = metadata[
                key
            ]

    return item


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

    If retrieval attached sequential context chunks, they
    are merged into this evidence source. This is useful
    when a list or section crosses a chunk boundary.
    """

    chunk = result.get(
        "chunk",
        {},
    )

    context_chunks = result.get(
        "context_chunks",
        [],
    )

    if not isinstance(
        context_chunks,
        list,
    ):

        context_chunks = []

    combined_chunks = [
        chunk,
        *[
            context_chunk
            for context_chunk
            in context_chunks
            if isinstance(
                context_chunk,
                dict,
            )
        ],
    ]

    page_starts = [
        item.get(
            "page_start"
        )
        for item in combined_chunks
        if item.get(
            "page_start"
        )
        is not None
    ]

    page_ends = [
        item.get(
            "page_end"
        )
        for item in combined_chunks
        if item.get(
            "page_end"
        )
        is not None
    ]

    if page_starts:

        combined_page_start = min(
            page_starts
        )

    else:

        combined_page_start = (
            chunk.get(
                "page_start"
            )
        )

    if page_ends:

        combined_page_end = max(
            page_ends
        )

    else:

        combined_page_end = (
            chunk.get(
                "page_end"
            )
        )

    page_display = format_pages(
        combined_page_start,
        combined_page_end,
    )

    text_parts = [
        clean_text(
            item.get(
                "text",
                "",
            )
        )
        for item in combined_chunks
        if clean_text(
            item.get(
                "text",
                "",
            )
        )
    ]

    combined_text = "\n\n".join(
        text_parts
    )

    effective_max_chars = (
        max_text_chars
    )

    if context_chunks:

        effective_max_chars = max(
            effective_max_chars,
            EXPANDED_MAX_TEXT_CHARS,
        )

    context_chunk_ids = [
        clean_text(
            item.get(
                "chunk_id"
            )
        )
        for item in context_chunks
        if clean_text(
            item.get(
                "chunk_id"
            )
        )
    ]

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
        "context_chunk_ids": (
            context_chunk_ids
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
            combined_text,
            max_chars=(
                effective_max_chars
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
        "effective_date": clean_text(
            record.get(
                "effective_date"
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
            "decision_change": bool(
                record.get(
                    "decision_change",
                    False,
                )
            ),

            "decision_change_total": (
                record.get(
                    "decision_change_total"
                )
            ),

            "previous_decision": clean_text(
                record.get(
                    "previous_decision"
                )
            ),

            "latest_decision": clean_text(
                record.get(
                    "latest_decision"
                )
            ),

            "previous_event_date": clean_text(
                record.get(
                    "previous_event_date"
                )
            ),

            "latest_event_date": clean_text(
                record.get(
                    "latest_event_date"
                )
            ),

            "previous_source_id": clean_text(
                record.get(
                    "previous_source_id"
                )
            ),

            "previous_source_url": clean_text(
                record.get(
                    "previous_source_url"
                )
            ),

            "previous_title": clean_text(
                record.get(
                    "previous_title"
                )
            ),

            "latest_source_id": clean_text(
                record.get(
                    "latest_source_id"
                )
            ),

            "latest_source_url": clean_text(
                record.get(
                    "latest_source_url"
                )
            ),

            "latest_title": clean_text(
                record.get(
                    "latest_title"
                )
            ),
            "decision_change_transition_counts": (
                record.get(
                    "decision_change_transition_counts",
                    {},
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


def exploration_result_to_evidence(
    result: dict,
    source_number: int,
    max_text_chars: int = (
        DEFAULT_MAX_TEXT_CHARS
    ),
) -> dict:
    """
    Convert one structured exploration result into the
    common MineLens evidence format.
    """

    record = result

    record_type = clean_text(
        record.get(
            "record_type"
        )
    )

    hole_id = clean_text(
        record.get(
            "hole_id"
        )
    )

    target = clean_text(
        record.get(
            "target"
        )
    )

    project = clean_text(
        record.get(
            "project"
        )
    )

    source_title = clean_text(
        record.get(
            "source_title"
        )
    )

    if (
        record_type
        == "hole_maximum_assay"
    ):

        title = (
            f"{hole_id} - "
            "Maximum individual zinc assay"
        )

        maximum_assay_pct = (
            record.get(
                "maximum_assay_pct"
            )
        )

        text = (
            f"{hole_id} at {target or project}. "
            f"Maximum individual zinc assay: "
            f"{maximum_assay_pct}% Zn. "
            f"Reporting basis: "
            f"{clean_text(record.get('reporting_basis'))}. "
            f"Laboratory: "
            f"{clean_text(record.get('laboratory'))}."
        )

    else:

        title = (
            f"{hole_id} - "
            f"{target or 'Drill intersection'}"
        )

        status = clean_text(
            record.get(
                "status"
            )
        )

        if (
            status
            == "no_reportable_intersection"
        ):

            text = (
                f"{hole_id} at "
                f"{target or project}. "
                f"{clean_text(record.get('comment'))}"
            )

        else:

            text = (
                f"{hole_id} at "
                f"{target or project}. "
                f"From {record.get('from_m')} m "
                f"to {record.get('to_m')} m. "
                f"Width {record.get('width_m')} m. "
                f"Zinc grade "
                f"{record.get('zinc_pct')}%. "
                f"Lead grade "
                f"{record.get('lead_pct')}%. "
                f"Cut-off "
                f"{record.get('cutoff_zinc_pct')}% Zn. "
                f"Laboratory: "
                f"{clean_text(record.get('laboratory'))}."
            )

    search_text = clean_text(
        record.get(
            "search_text"
        )
    )

    if search_text:
        text = (
            text
            + "\n\n"
            + search_text
        )

    chunk_id_parts = [
        "exploration",
        record_type,
        hole_id,
    ]

    sequence_number = record.get(
        "sequence_number"
    )

    if sequence_number is not None:
        chunk_id_parts.append(
            str(
                sequence_number
            )
        )

    chunk_id = "_".join(
        part
        for part in chunk_id_parts
        if part
    ).casefold()

    return {
        "source_id": (
            f"S{source_number}"
        ),

        "evidence_type": (
            "exploration_result"
        ),

        "title": title,

        "document": (
            source_title
            or (
                "Kabwe Drilling Results "
                "from ALS Laboratories"
            )
        ),

        "pages": None,

        "chunk_id": (
            chunk_id
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

        "source_status": "current",

        "text": truncate_text(
            text,
            max_chars=(
                max_text_chars
            ),
        ),

        "record": {
            "record_type": (
                record_type
            ),

            "project": (
                project
            ),

            "project_alias": clean_text(
                record.get(
                    "project_alias"
                )
            ),

            "project_area": clean_text(
                record.get(
                    "project_area"
                )
            ),

            "target": (
                target
            ),

            "hole_id": (
                hole_id
            ),

            "status": clean_text(
                record.get(
                    "status"
                )
            ),

            "from_m": (
                record.get(
                    "from_m"
                )
            ),

            "to_m": (
                record.get(
                    "to_m"
                )
            ),

            "width_m": (
                record.get(
                    "width_m"
                )
            ),

            "calculated_width_m": (
                record.get(
                    "calculated_width_m"
                )
            ),

            "width_matches_depths": (
                record.get(
                    "width_matches_depths"
                )
            ),

            "zinc_pct": (
                record.get(
                    "zinc_pct"
                )
            ),

            "lead_pct": (
                record.get(
                    "lead_pct"
                )
            ),

            "cutoff_zinc_pct": (
                record.get(
                    "cutoff_zinc_pct"
                )
            ),

            "cutoff_text": clean_text(
                record.get(
                    "cutoff_text"
                )
            ),

            "comment": clean_text(
                record.get(
                    "comment"
                )
            ),

            "commodity": clean_text(
                record.get(
                    "commodity"
                )
            ),

            "commodity_symbol": clean_text(
                record.get(
                    "commodity_symbol"
                )
            ),

            "maximum_assay_pct": (
                record.get(
                    "maximum_assay_pct"
                )
            ),

            "reporting_basis": clean_text(
                record.get(
                    "reporting_basis"
                )
            ),

            "laboratory": clean_text(
                record.get(
                    "laboratory"
                )
            ),

            "assay_method": clean_text(
                record.get(
                    "assay_method"
                )
            ),

            "company": clean_text(
                record.get(
                    "company"
                )
            ),

            "source_type": clean_text(
                record.get(
                    "source_type"
                )
            ),
        },

        "retrieval": {
            "structured": True,
        },
    }


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

        elif route == "exploration":

            item = (
                exploration_result_to_evidence(
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

        item = enrich_evidence_source_metadata(
            item=item,
            result=result,
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
                "source_id":
                    item.get(
                        "source_id"
                    ),

                "canonical_source_id":
                    item.get(
                        "canonical_source_id"
                    ),

                "title":
                    item.get(
                        "title"
                    ),

                "document":
                    item.get(
                        "document"
                    ),

                "pages":
                    item.get(
                        "pages"
                    ),

                "source_url":
                    item.get(
                        "source_url"
                    ),

                "published_date":
                    item.get(
                        "published_date"
                    ),

                "agency":
                    item.get(
                        "agency"
                    ),

                "source_authority":
                    item.get(
                        "source_authority"
                    ),

                "document_type":
                    item.get(
                        "document_type"
                    ),
            }
        )

    return sources
