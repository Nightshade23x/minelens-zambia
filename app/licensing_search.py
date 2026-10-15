from __future__ import annotations

import argparse
import json
import re

from pathlib import Path

from app.search import (
    BM25Index,
    make_snippet,
)


# ---------------------------------------------------------
# Paths
# ---------------------------------------------------------

PROJECT_ROOT = Path(
    __file__
).resolve().parents[1]

PROCESSED_DATA_DIR = (
    PROJECT_ROOT
    / "data"
    / "processed"
)

DEFAULT_LICENSING_FILE = (
    PROCESSED_DATA_DIR
    / (
        "zambia_licensing_committee_"
        "results_june_2026.licences.jsonl"
    )
)


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

DEFAULT_TOP_K = 10


SPECIFIC_LICENCE_TYPE_PHRASES = {
    "LML": (
        "large scale mining",
        "large-scale mining",
        "large scale mining licence",
        "large-scale mining licence",
        "large scale mining license",
        "large-scale mining license",
        "lml",
    ),
    "LEL": (
        "large scale exploration",
        "large-scale exploration",
        "large scale exploration licence",
        "large-scale exploration licence",
        "large scale exploration license",
        "large-scale exploration license",
        "lel",
    ),
    "SML": (
        "small scale mining",
        "small-scale mining",
        "small scale mining licence",
        "small-scale mining licence",
        "small scale mining license",
        "small-scale mining license",
        "sml",
    ),
    "SEL": (
        "small scale exploration",
        "small-scale exploration",
        "small scale exploration licence",
        "small-scale exploration licence",
        "small scale exploration license",
        "small-scale exploration license",
        "sel",
    ),
    "AMR": (
        "artisanal mining",
        "artisanal mining right",
        "artisanal mining rights",
        "amr",
    ),
    "MPL": (
        "mineral processing",
        "mineral processing licence",
        "mineral processing license",
        "mpl",
    ),
}


LICENCE_FAMILY_PHRASES = {
    "exploration": {
        "LEL",
        "SEL",
    },
    "mining": {
        "LML",
        "SML",
    },
}


DECISION_TERMS = {
    "approved": "Approved",
    "approve": "Approved",
    "rejected": "Rejected",
    "reject": "Rejected",
    "deferred": "Deferred",
    "defer": "Deferred",
}


COMMODITY_ALIASES = {
    "copper": "Cu",
    "gold": "Au",
    "silver": "Ag",
    "cobalt": "Co",
    "nickel": "Ni",
    "zinc": "Zn",
    "lead": "Pb",
    "iron": "Fe",
    "lithium": "Li",
    "manganese": "Mn",
    "uranium": "U",
    "tin": "Sn",
}


LICENCE_CODE_PATTERN = re.compile(
    r"\b\d{3,6}\s*-\s*HQ\s*-\s*[A-Z0-9]{2,6}\b",
    flags=re.IGNORECASE,
)


# ---------------------------------------------------------
# Loading
# ---------------------------------------------------------

def load_licensing_records(
    path: Path | None = None,
) -> list[dict]:
    """
    Load structured licensing committee records.

    If a specific path is supplied, only that file is
    loaded.

    Otherwise, load every dated MineLens licensing
    committee batch from the processed-data directory.

    Multiple records for the same licence code are
    intentionally preserved because a licence/application
    may appear in more than one committee meeting.
    """

    if path is not None:

        paths = [
            path
        ]

    else:

        processed_dir = (
            DEFAULT_LICENSING_FILE.parent
        )

        paths = sorted(
            processed_dir.glob(
                (
                    "zambia_licensing_committee_results_"
                    "*.licences.jsonl"
                )
            )
        )

    if not paths:

        raise FileNotFoundError(
            "No structured licensing files "
            "were found."
        )

    records: list[dict] = []

    for source_path in paths:

        if not source_path.exists():
            raise FileNotFoundError(
                "Structured licensing file "
                f"not found:\n{source_path}"
            )

        with source_path.open(
            "r",
            encoding="utf-8",
        ) as file:

            for line_number, line in enumerate(
                file,
                start=1,
            ):

                if not line.strip():
                    continue

                try:

                    record = json.loads(
                        line
                    )

                except json.JSONDecodeError as error:

                    raise ValueError(
                        "Invalid JSON on line "
                        f"{line_number} of "
                        f"{source_path}"
                    ) from error

                record[
                    "_licensing_batch_file"
                ] = source_path.name

                records.append(
                    record
                )

    if not records:

        raise ValueError(
            "Licensing files contain "
            "no records."
        )

    # Latest committee records first.
    #
    # effective_date represents the committee meeting
    # date when available. published_date is used as
    # fallback for older batches.
    records.sort(
        key=lambda record: (
            record.get(
                "effective_date"
            )
            or record.get(
                "published_date"
            )
            or ""
        ),
        reverse=True,
    )

    return records


# ---------------------------------------------------------
# Normalization
# ---------------------------------------------------------

def normalize_text(
    text: str,
) -> str:
    """
    Normalize text for case-insensitive comparisons.
    """

    return " ".join(
        text.lower().split()
    )


def normalize_licence_code(
    text: str,
) -> str:
    """
    Normalize licence-code spacing and casing.
    """

    parts = [
        part.strip()
        for part in re.split(
            r"\s*-\s*",
            text.strip(),
        )
    ]

    return "-".join(
        parts
    ).upper()


# ---------------------------------------------------------
# Query inference
# ---------------------------------------------------------

def infer_specific_licence_type(
    query: str,
) -> str | None:
    """
    Infer one specific licence type where the query
    explicitly identifies one.

    Examples:
        large-scale mining -> LML
        small-scale exploration -> SEL
        artisanal mining -> AMR
    """

    normalized = normalize_text(
        query
    )

    candidates: list[
        tuple[int, str]
    ] = []

    for code, phrases in (
        SPECIFIC_LICENCE_TYPE_PHRASES.items()
    ):

        for phrase in phrases:

            normalized_phrase = (
                normalize_text(
                    phrase
                )
            )

            if (
                normalized_phrase
                in normalized
            ):

                candidates.append(
                    (
                        len(
                            normalized_phrase
                        ),
                        code,
                    )
                )

    if not candidates:
        return None

    candidates.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    return candidates[
        0
    ][1]


def infer_licence_types(
    query: str,
) -> set[str] | None:
    """
    Infer one or more allowed licence types.

    Specific licence types take priority.

    Generic families:
        exploration licences -> LEL or SEL
        mining licences      -> LML or SML
    """

    specific = (
        infer_specific_licence_type(
            query
        )
    )

    if specific is not None:
        return {
            specific
        }

    normalized = normalize_text(
        query
    )

    exploration_patterns = (
        "exploration licence",
        "exploration licences",
        "exploration license",
        "exploration licenses",
        "exploration rights",
        "exploration applications",
    )

    for phrase in (
        exploration_patterns
    ):

        if phrase in normalized:

            return set(
                LICENCE_FAMILY_PHRASES[
                    "exploration"
                ]
            )

    mining_patterns = (
        "mining licence",
        "mining licences",
        "mining license",
        "mining licenses",
        "mining applications",
    )

    for phrase in mining_patterns:

        if phrase in normalized:

            return set(
                LICENCE_FAMILY_PHRASES[
                    "mining"
                ]
            )

    return None


def infer_decision(
    query: str,
) -> str | None:
    """
    Infer committee decision from query text.
    """

    normalized = normalize_text(
        query
    )

    for term, decision in (
        DECISION_TERMS.items()
    ):

        if re.search(
            rf"\b{re.escape(term)}\b",
            normalized,
        ):
            return decision

    return None


def infer_licence_code(
    query: str,
) -> str | None:
    """
    Extract a licence code from free text.
    """

    match = LICENCE_CODE_PATTERN.search(
        query
    )

    if match is None:
        return None

    return normalize_licence_code(
        match.group()
    )


def infer_commodity(
    query: str,
) -> str | None:
    """
    Infer common commodity abbreviations from
    natural-language mineral names.
    """

    normalized = normalize_text(
        query
    )

    for name, code in (
        COMMODITY_ALIASES.items()
    ):

        if re.search(
            rf"\b{re.escape(name)}\b",
            normalized,
        ):
            return code

    return None


def infer_location(
    query: str,
    records: list[dict],
) -> tuple[
    str | None,
    str | None,
]:
    """
    Infer province and district from locations already
    present in the structured dataset.
    """

    normalized_query = (
        normalize_text(
            query
        )
    )

    provinces: set[
        str
    ] = set()

    districts: set[
        str
    ] = set()

    for record in records:

        province = record.get(
            "province"
        )

        if province:
            provinces.add(
                province
            )

        for district in record.get(
            "districts",
            [],
        ):

            if district:
                districts.add(
                    district
                )

    matched_province = None

    for province in sorted(
        provinces,
        key=len,
        reverse=True,
    ):

        if (
            normalize_text(
                province
            )
            in normalized_query
        ):

            matched_province = (
                province
            )

            break

    matched_district = None

    for district in sorted(
        districts,
        key=len,
        reverse=True,
    ):

        if (
            normalize_text(
                district
            )
            in normalized_query
        ):

            matched_district = (
                district
            )

            break

    return (
        matched_province,
        matched_district,
    )


# ---------------------------------------------------------
# Filters
# ---------------------------------------------------------

def record_has_commodity(
    record: dict,
    commodity: str,
) -> bool:
    """
    Check commodity list using exact normalized codes.
    """

    target = (
        commodity
        .strip()
        .upper()
    )

    commodities = {
        str(
            value
        ).strip().upper()
        for value in record.get(
            "commodities",
            [],
        )
    }

    return (
        target
        in commodities
    )


def record_matches(
    record: dict,
    licence_code: str | None = None,
    licence_types: set[str] | None = None,
    decision: str | None = None,
    province: str | None = None,
    district: str | None = None,
    commodity: str | None = None,
    applicant: str | None = None,
) -> bool:
    """
    Return True if a licensing record satisfies every
    supplied structured filter.
    """

    if licence_code is not None:

        record_code = (
            normalize_licence_code(
                str(
                    record.get(
                        "licence_code",
                        "",
                    )
                )
            )
        )

        if (
            record_code
            != normalize_licence_code(
                licence_code
            )
        ):
            return False

    if licence_types is not None:

        record_type = str(
            record.get(
                "licence_type_code",
                "",
            )
        ).upper()

        allowed_types = {
            value.upper()
            for value in licence_types
        }

        if (
            record_type
            not in allowed_types
        ):
            return False

    if decision is not None:

        if (
            normalize_text(
                str(
                    record.get(
                        "decision",
                        "",
                    )
                )
            )
            != normalize_text(
                decision
            )
        ):
            return False

    if province is not None:

        if (
            normalize_text(
                str(
                    record.get(
                        "province",
                        "",
                    )
                )
            )
            != normalize_text(
                province
            )
        ):
            return False

    if district is not None:

        record_districts = [
            normalize_text(
                str(
                    value
                )
            )
            for value in record.get(
                "districts",
                [],
            )
        ]

        if (
            normalize_text(
                district
            )
            not in record_districts
        ):
            return False

    if commodity is not None:

        if not record_has_commodity(
            record,
            commodity,
        ):
            return False

    if applicant is not None:

        if (
            normalize_text(
                applicant
            )
            not in normalize_text(
                str(
                    record.get(
                        "applicant",
                        "",
                    )
                )
            )
        ):
            return False

    return True


def filter_records(
    records: list[dict],
    licence_code: str | None = None,
    licence_types: set[str] | None = None,
    decision: str | None = None,
    province: str | None = None,
    district: str | None = None,
    commodity: str | None = None,
    applicant: str | None = None,
) -> list[dict]:
    """
    Apply structured filters to licensing records.
    """

    return [
        record
        for record in records
        if record_matches(
            record=record,
            licence_code=licence_code,
            licence_types=licence_types,
            decision=decision,
            province=province,
            district=district,
            commodity=commodity,
            applicant=applicant,
        )
    ]


# ---------------------------------------------------------
# Search text
# ---------------------------------------------------------

def licensing_search_text(
    record: dict,
) -> str:
    """
    Build readable BM25 text from one structured
    licensing record.
    """

    parts = [
        (
            f"Licence code "
            f"{record.get('licence_code', '')}."
        ),
        (
            f"Licence type "
            f"{record.get('licence_type', '')}."
        ),
        (
            f"Applicant "
            f"{record.get('applicant', '')}."
        ),
    ]

    commodities = record.get(
        "commodities_text"
    )

    if commodities:

        parts.append(
            f"Commodities "
            f"{commodities}."
        )

    area = record.get(
        "area_text"
    )

    if area:

        parts.append(
            f"Area {area}."
        )

    province = record.get(
        "province"
    )

    if province:

        parts.append(
            f"Province {province}."
        )

    districts = record.get(
        "districts",
        [],
    )

    if districts:

        parts.append(
            "District "
            + ", ".join(
                districts
            )
            + "."
        )

    decision = record.get(
        "decision"
    )

    if decision:

        parts.append(
            f"Decision {decision}."
        )

    deadline = record.get(
        "deadline"
    )

    if deadline:

        parts.append(
            f"Deadline {deadline}."
        )

    return " ".join(
        parts
    )


def records_to_search_chunks(
    records: list[dict],
) -> list[dict]:
    """
    Convert structured records into BM25-compatible
    search chunks.
    """

    chunks: list[
        dict
    ] = []

    for record in records:

        text = licensing_search_text(
            record
        )

        chunk = {
            **record,
            "chunk_id": (
                "licence_"
                + normalize_licence_code(
                    str(
                        record.get(
                            "licence_code",
                            "",
                        )
                    )
                )
                .lower()
                .replace(
                    "-",
                    "_",
                )
            ),
            "document": record.get(
                "document",
                (
                    "zambia_licensing_committee_"
                    "results_june_2026.html"
                ),
            ),
            "page_start": 1,
            "page_end": 1,
            "text": text,
            "source_url": record.get(
                "source_url"
            ),
        }

        chunks.append(
            chunk
        )

    return chunks

def licensing_event_date(
    record: dict,
) -> str:
    """
    Return the best sortable date for a licensing event.

    Committee/effective date is preferred. Publication
    date is the fallback for older batches.
    """

    return str(
        record.get(
            "effective_date"
        )
        or record.get(
            "published_date"
        )
        or ""
    ).strip()


def wants_licensing_history(
    query: str,
) -> bool:
    """
    Detect requests for historical licensing decisions
    rather than only the latest known state.
    """

    normalized = " ".join(
        query.casefold().split()
    )

    history_terms = (
        "decision history",
        "licence history",
        "license history",
        "history for",
        "historical decisions",
        "previous decision",
        "previous decisions",
        "prior decision",
        "prior decisions",
        "decision changes",
        "changed decision",
        "changed from",
        "across committee meetings",
        "over time",
    )

    return any(
        term in normalized
        for term in history_terms
    )

def wants_licensing_decision_changes(
    query: str,
) -> bool:
    """
    Detect requests comparing licensing decisions
    across committee meetings.
    """

    normalized = " ".join(
        query.casefold().split()
    )

    change_terms = (
        "decision changes",
        "decisions changed",
        "changed decisions",
        "whose decision changed",
        "whose decisions changed",
        "which decision changed",
        "which decisions changed",
        "decision changed between",
        "decisions changed between",
        "changes between committee meetings",
        "changed between committee meetings",
    )

    return any(
        term in normalized
        for term in change_terms
    )


def licensing_decision_change_records(
    records: list[dict],
) -> list[dict]:
    """
    Compare consecutive committee events for each
    licence/application code and return only genuine
    decision transitions.

    Each returned record represents the later event while
    preserving details about the preceding event.
    """

    grouped: dict[
        str,
        list[dict],
    ] = {}

    for record in records:

        licence_code = str(
            record.get(
                "licence_code"
            )
            or ""
        ).strip()

        if not licence_code:
            continue

        grouped.setdefault(
            licence_code,
            [],
        ).append(
            record
        )

    changes: list[dict] = []

    for (
        licence_code,
        events,
    ) in grouped.items():

        if len(
            events
        ) < 2:
            continue

        ordered = sorted(
            events,
            key=licensing_event_date,
        )

        for (
            previous,
            current,
        ) in zip(
            ordered,
            ordered[1:],
        ):

            previous_decision = str(
                previous.get(
                    "decision"
                )
                or ""
            ).strip()

            current_decision = str(
                current.get(
                    "decision"
                )
                or ""
            ).strip()

            if (
                not previous_decision
                or not current_decision
            ):
                continue

            if (
                previous_decision.casefold()
                == current_decision.casefold()
            ):
                continue

            change_record = dict(
                current
            )

            change_record[
                "decision_change"
            ] = True

            change_record[
                "previous_decision"
            ] = previous_decision

            change_record[
                "latest_decision"
            ] = current_decision

            change_record[
                "previous_event_date"
            ] = licensing_event_date(
                previous
            )

            change_record[
                "latest_event_date"
            ] = licensing_event_date(
                current
            )

            change_record[
                "previous_source_id"
            ] = previous.get(
                "source_id"
            )

            change_record[
                "previous_source_url"
            ] = previous.get(
                "source_url"
            )

            change_record[
                "previous_title"
            ] = previous.get(
                "title"
            )

            change_record[
                "latest_source_id"
            ] = current.get(
                "source_id"
            )

            change_record[
                "latest_source_url"
            ] = current.get(
                "source_url"
            )

            change_record[
                "latest_title"
            ] = current.get(
                "title"
            )

            changes.append(
                change_record
            )

    changes.sort(
        key=lambda record: (
            record.get(
                "latest_event_date"
            )
            or "",
            record.get(
                "licence_code"
            )
            or "",
        ),
        reverse=True,
    )


    transition_counts: dict[
        str,
        int,
    ] = {}

    for record in changes:

        previous_decision = str(
            record.get(
                "previous_decision"
            )
            or ""
        ).strip()

        latest_decision = str(
            record.get(
                "latest_decision"
            )
            or ""
        ).strip()

        transition = (
            f"{previous_decision} -> "
            f"{latest_decision}"
        )

        transition_counts[
            transition
        ] = (
            transition_counts.get(
                transition,
                0,
            )
            + 1
        )

    total = len(
        changes
    )

    for record in changes:

        record[
            "decision_change_total"
        ] = total

        record[
            "decision_change_transition_counts"
        ] = dict(
            transition_counts
        )

    return changes


def latest_licensing_records(
    records: list[dict],
) -> list[dict]:
    """
    Return the latest known event for each licence code.

    Historical records remain available in the original
    record collection and are used when history is
    explicitly requested.
    """

    ordered = sorted(
        records,
        key=licensing_event_date,
        reverse=True,
    )

    latest: list[dict] = []

    seen_codes: set[str] = set()

    for record in ordered:

        licence_code = str(
            record.get(
                "licence_code"
            )
            or ""
        ).strip()

        if not licence_code:

            latest.append(
                record
            )

            continue

        if licence_code in seen_codes:
            continue

        seen_codes.add(
            licence_code
        )

        latest.append(
            record
        )

    return latest
# ---------------------------------------------------------
# Structured search
# ---------------------------------------------------------

def search_licensing_records(
    query: str,
    records: list[dict],
    top_k: int = DEFAULT_TOP_K,
    licence_code: str | None = None,
    licence_type: str | None = None,
    decision: str | None = None,
    province: str | None = None,
    district: str | None = None,
    commodity: str | None = None,
    applicant: str | None = None,
) -> tuple[
    list[dict],
    dict,
]:
    """
    Search structured licensing records.

    Normal searches use the latest known event for each
    licence code.

    Explicit history queries retain all committee events.

    Query conditions are converted into hard filters
    before BM25 ranking.

    Explicit CLI filters override inferred filters.
    """

    if top_k <= 0:
        raise ValueError(
            "top_k must be greater than zero."
        )

    change_mode = (
        wants_licensing_decision_changes(
            query
        )
    )

    history_mode = (
        wants_licensing_history(
            query
        )
        or change_mode
    )

    if change_mode:

        searchable_records = (
            licensing_decision_change_records(
                records
            )
        )

    elif history_mode:

        searchable_records = sorted(
            records,
            key=licensing_event_date,
            reverse=True,
        )

    else:

        searchable_records = (
            latest_licensing_records(
                records
            )
        )

    inferred_code = (
        infer_licence_code(
            query
        )
    )

    inferred_types = (
        infer_licence_types(
            query
        )
    )

    inferred_decision = (
        infer_decision(
            query
        )
    )

    (
        inferred_province,
        inferred_district,
    ) = infer_location(
        query=query,
        records=searchable_records,
    )

    inferred_commodity = (
        infer_commodity(
            query
        )
    )

    if licence_type is not None:

        selected_types = {
            licence_type.upper()
        }

    else:

        selected_types = (
            inferred_types
        )

    filters = {
        "licence_code": (
            licence_code
            or inferred_code
        ),
        "licence_types": (
            selected_types
        ),
        "decision": (
            decision
            or inferred_decision
        ),
        "province": (
            province
            or inferred_province
        ),
        "district": (
            district
            or inferred_district
        ),
        "commodity": (
            commodity
            or inferred_commodity
        ),
        "applicant": (
            applicant
        ),
        "history": (
            history_mode
        ),
        "decision_changes": (
            change_mode
),
    }

    filter_arguments = {
        key: value
        for key, value in filters.items()
        if key
        not in {
            "history",
            "decision_changes",
        }
    }

    filtered = filter_records(
        records=searchable_records,
        **filter_arguments,
    )

    if not filtered:

        return (
            [],
            filters,
        )
    if change_mode:

        chunks = (
            records_to_search_chunks(
                filtered
            )
        )

        return (
            [
                {
                    "score": 1.0,
                    "chunk": chunk,
                }
                for chunk in chunks[
                    :top_k
                ]
            ],
            filters,
        )

    # Exact-code lookup.
    #
    # Normal mode returns only the latest event.
    # History mode returns all matching committee events.
    if filters[
        "licence_code"
    ]:

        filtered = sorted(
            filtered,
            key=licensing_event_date,
            reverse=True,
        )

        if history_mode:

            selected_records = (
                filtered[
                    :top_k
                ]
            )

        else:

            selected_records = (
                filtered[
                    :1
                ]
            )

        chunks = (
            records_to_search_chunks(
                selected_records
            )
        )

        return (
            [
                {
                    "score": 1.0,
                    "chunk": chunk,
                }
                for chunk in chunks
            ],
            filters,
        )

    chunks = (
        records_to_search_chunks(
            filtered
        )
    )

    index = BM25Index(
        chunks
    )

    results = index.search(
        query=query,
        top_k=min(
            top_k,
            len(
                chunks
            ),
        ),
    )

    # If all useful query terms were consumed by hard
    # filters, return filtered records directly.
    if not results:

        results = [
            {
                "score": 0.0,
                "chunk": chunk,
            }
            for chunk in chunks[
                :top_k
            ]
        ]

    return (
        results,
        filters,
    )

# ---------------------------------------------------------
# Display
# ---------------------------------------------------------

def format_licence_types(
    licence_types: set[str],
) -> str:
    """
    Format one or multiple licence types for display.
    """

    return ", ".join(
        sorted(
            licence_types
        )
    )


def display_filters(
    filters: dict,
) -> None:
    """
    Display filters inferred or explicitly supplied.
    """

    print()
    print(
        "Structured filters:"
    )

    active_count = 0

    for key, value in (
        filters.items()
    ):

        if value is None:
            continue

        active_count += 1

        if key == "licence_types":

            label = (
                "Licence Type"
            )

            formatted_value = (
                format_licence_types(
                    value
                )
            )

        else:

            label = (
                key.replace(
                    "_",
                    " ",
                )
                .title()
            )

            formatted_value = (
                value
            )

        print(
            f"  {label}: "
            f"{formatted_value}"
        )

    if active_count == 0:

        print(
            "  None"
        )


def display_results(
    query: str,
    results: list[dict],
    filters: dict,
) -> None:
    """
    Display structured licensing search results.
    """

    print()
    print("=" * 72)

    print(
        "MINELENS ZAMBIA "
        "LICENSING SEARCH"
    )

    print("=" * 72)

    print()
    print(
        f'Query: "{query}"'
    )

    display_filters(
        filters
    )

    print()

    if not results:

        print(
            "No licensing records matched "
            "the structured filters."
        )

        return

    print(
        f"Matched results shown: "
        f"{len(results)}"
    )

    for rank, result in enumerate(
        results,
        start=1,
    ):

        record = result[
            "chunk"
        ]

        print()
        print("-" * 72)

        print(
            f"RESULT {rank}"
        )

        print(
            f"Score:       "
            f"{result['score']:.4f}"
        )

        print(
            f"Licence:     "
            f"{record.get('licence_code')}"
        )

        print(
            f"Type:        "
            f"{record.get('licence_type')}"
        )

        print(
            f"Applicant:   "
            f"{record.get('applicant')}"
        )

        print(
            f"Decision:    "
            f"{record.get('decision')}"
        )

        province = record.get(
            "province"
        )

        districts = record.get(
            "districts",
            [],
        )

        if province:

            print(
                f"Province:    "
                f"{province}"
            )

        if districts:

            print(
                f"District:    "
                f"{', '.join(districts)}"
            )

        commodities = (
            record.get(
                "commodities_text"
            )
        )

        if commodities:

            print(
                f"Commodities: "
                f"{commodities}"
            )

        area = record.get(
            "area_text"
        )

        if area:

            print(
                f"Area:        "
                f"{area}"
            )

        deadline = record.get(
            "deadline"
        )

        if deadline:

            print(
                f"Deadline:    "
                f"{deadline}"
            )

        print()

        print(
            make_snippet(
                text=record[
                    "text"
                ],
                query=query,
                max_chars=500,
            )
        )

        source_url = (
            record.get(
                "source_url"
            )
        )

        if source_url:

            print()
            print(
                f"Source: "
                f"{source_url}"
            )

    print()
    print("-" * 72)


# ---------------------------------------------------------
# CLI
# ---------------------------------------------------------

def main() -> None:

    parser = argparse.ArgumentParser(
        description=(
            "Search structured Zambia mining "
            "licensing committee records."
        )
    )

    parser.add_argument(
        "query",
        nargs="+",
        help=(
            "Natural-language licensing query"
        ),
    )

    parser.add_argument(
        "--top-k",
        type=int,
        default=DEFAULT_TOP_K,
        help=(
            "Maximum number of results "
            f"(default: {DEFAULT_TOP_K})"
        ),
    )

    parser.add_argument(
        "--licence-type",
        choices=[
            "LML",
            "LEL",
            "SML",
            "SEL",
            "AMR",
            "MPL",
        ],
        help=(
            "Explicit licence type filter"
        ),
    )

    parser.add_argument(
        "--decision",
        choices=[
            "Approved",
            "Rejected",
            "Deferred",
        ],
        help=(
            "Explicit committee decision filter"
        ),
    )

    parser.add_argument(
        "--province",
        help=(
            "Explicit province filter"
        ),
    )

    parser.add_argument(
        "--district",
        help=(
            "Explicit district filter"
        ),
    )

    parser.add_argument(
        "--commodity",
        help=(
            "Commodity code such as Cu, "
            "Au, Co or Li"
        ),
    )

    parser.add_argument(
        "--applicant",
        help=(
            "Applicant/company name filter"
        ),
    )

    args = parser.parse_args()

    query = " ".join(
        args.query
    )

    records = (
        load_licensing_records()
    )

    print(
        f"Loaded "
        f"{len(records):,} "
        "licensing records."
    )

    results, filters = (
        search_licensing_records(
            query=query,
            records=records,
            top_k=args.top_k,
            licence_type=(
                args.licence_type
            ),
            decision=(
                args.decision
            ),
            province=(
                args.province
            ),
            district=(
                args.district
            ),
            commodity=(
                args.commodity
            ),
            applicant=(
                args.applicant
            ),
        )
    )

    display_results(
        query=query,
        results=results,
        filters=filters,
    )


if __name__ == "__main__":
    main()