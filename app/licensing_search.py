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


LICENCE_TYPE_PHRASES = {
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
    path: Path = DEFAULT_LICENSING_FILE,
) -> list[dict]:
    """
    Load structured licensing committee records.
    """

    if not path.exists():
        raise FileNotFoundError(
            "Structured licensing file "
            f"not found:\n{path}"
        )

    records: list[dict] = []

    with path.open(
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
                    f"{line_number} of {path}"
                ) from error

            records.append(
                record
            )

    if not records:
        raise ValueError(
            "Licensing file contains "
            "no records."
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

def infer_licence_type(
    query: str,
) -> str | None:
    """
    Infer a licence type from natural-language query text.
    """

    normalized = normalize_text(
        query
    )

    # Check longer phrases first to avoid ambiguous
    # matches such as "mining" by itself.

    candidates: list[
        tuple[int, str]
    ] = []

    for code, phrases in (
        LICENCE_TYPE_PHRASES.items()
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
        reverse=True
    )

    return candidates[
        0
    ][1]


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
    Infer province and district from location names
    already present in the structured dataset.

    Returns:
        province
        district
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

    province_candidates = sorted(
        provinces,
        key=len,
        reverse=True,
    )

    for province in (
        province_candidates
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

    district_candidates = sorted(
        districts,
        key=len,
        reverse=True,
    )

    for district in (
        district_candidates
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

    target = commodity.upper()

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
    licence_type: str | None = None,
    decision: str | None = None,
    province: str | None = None,
    district: str | None = None,
    commodity: str | None = None,
    applicant: str | None = None,
) -> bool:
    """
    Return True if a licensing record satisfies all
    supplied structured filters.
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

    if licence_type is not None:

        if (
            str(
                record.get(
                    "licence_type_code",
                    "",
                )
            ).upper()
            != licence_type.upper()
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
    licence_type: str | None = None,
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
            licence_type=licence_type,
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
    Build readable search text from one structured
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
    Search licensing records.

    Natural-language query terms are first converted into
    structured filters. Explicit CLI filters override
    inferred values.

    BM25 is then used only to rank records that survive
    those filters.
    """

    if top_k <= 0:
        raise ValueError(
            "top_k must be greater than zero."
        )

    inferred_code = (
        infer_licence_code(
            query
        )
    )

    inferred_type = (
        infer_licence_type(
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
        records=records,
    )

    inferred_commodity = (
        infer_commodity(
            query
        )
    )

    filters = {
        "licence_code": (
            licence_code
            or inferred_code
        ),
        "licence_type": (
            licence_type
            or inferred_type
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
    }

    filtered = filter_records(
        records=records,
        **filters,
    )

    if not filtered:
        return (
            [],
            filters,
        )

    chunks = (
        records_to_search_chunks(
            filtered
        )
    )

    # Exact licence-code lookups should not need ranking.

    if filters[
        "licence_code"
    ]:

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

    # BM25 may return nothing if the query consisted
    # almost entirely of terms already consumed by
    # structured filtering. In that case return the
    # filtered records directly.

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

def display_filters(
    filters: dict,
) -> None:
    """
    Show the filters MineLens inferred from the query.
    """

    active = {
        key: value
        for key, value in filters.items()
        if value is not None
    }

    print()
    print(
        "Structured filters:"
    )

    if not active:

        print(
            "  None"
        )

        return

    for key, value in (
        active.items()
    ):

        label = (
            key.replace(
                "_",
                " ",
            )
            .title()
        )

        print(
            f"  {label}: "
            f"{value}"
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