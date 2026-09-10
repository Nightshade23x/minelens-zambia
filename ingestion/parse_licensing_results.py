from __future__ import annotations

import argparse
import json
import re

from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup

from ingestion.parse_html import (
    clean_text,
    download_html,
    find_main_content,
)


# ---------------------------------------------------------
# Project paths
# ---------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]

PROCESSED_DATA_DIR = (
    PROJECT_ROOT
    / "data"
    / "processed"
)


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

LICENCE_CODE_PATTERN = re.compile(
    r"\b(\d{3,6})\s*-\s*HQ\s*-\s*([A-Z0-9]{2,6})\b",
    re.IGNORECASE,
)


LICENCE_TYPES = {
    "LML": "Large-Scale Mining Licence",
    "SML": "Small-Scale Mining Licence",
    "AMR": "Artisanal Mining Right",
    "LEL": "Large-Scale Exploration Licence",
    "SEL": "Small-Scale Exploration Licence",
    "MPL": "Mineral Processing Licence",
}


KNOWN_DECISIONS = {
    "approved": "Approved",
    "deferred": "Deferred",
    "rejected": "Rejected",
}


# ---------------------------------------------------------
# General helpers
# ---------------------------------------------------------

def normalize_licence_code(
    text: str,
) -> str | None:
    """
    Find and normalize a Zambia mining licence code.

    Example:

        42553-HQ- LML

    becomes:

        42553-HQ-LML
    """

    match = LICENCE_CODE_PATTERN.search(
        text
    )

    if match is None:
        return None

    number = match.group(
        1
    )

    suffix = match.group(
        2
    ).upper()

    return (
        f"{number}-HQ-{suffix}"
    )


def licence_suffix(
    licence_code: str,
) -> str:
    """
    Return the final component of a licence code.
    """

    return (
        licence_code
        .split("-")[-1]
        .upper()
    )


def licence_type_name(
    licence_code: str,
) -> str:
    """
    Convert a licence-code suffix into a readable
    licence type where known.
    """

    suffix = licence_suffix(
        licence_code
    )

    return LICENCE_TYPES.get(
        suffix,
        f"{suffix} Licence/Application",
    )


def normalize_decision(
    text: str,
) -> str:
    """
    Normalize common committee decisions.
    """

    cleaned = clean_text(
        text
    )

    lowered = cleaned.lower()

    for keyword, normalized in (
        KNOWN_DECISIONS.items()
    ):

        if keyword in lowered:
            return normalized

    return cleaned


def parse_area_hectares(
    text: str,
) -> float | None:
    """
    Extract an area measured in hectares.
    """

    cleaned = clean_text(
        text
    )

    match = re.search(
        r"([\d,]+(?:\.\d+)?)\s*ha\b",
        cleaned,
        flags=re.IGNORECASE,
    )

    if match is None:
        return None

    number = (
        match.group(1)
        .replace(
            ",",
            "",
        )
    )

    try:
        return float(
            number
        )

    except ValueError:
        return None


def normalize_location(
    text: str,
) -> tuple[
    str,
    str | None,
    list[str],
]:
    """
    Normalize a map-reference/location field.

    Returns:
        full_location
        province
        districts
    """

    location = clean_text(
        text
    )

    replacements = {
        "NorthWestern": (
            "North Western"
        ),
        "Northwestern": (
            "North Western"
        ),
        "North-Western": (
            "North Western"
        ),
    }

    for old, new in (
        replacements.items()
    ):

        location = location.replace(
            old,
            new,
        )

    parts = [
        part.strip()
        for part in location.split(
            ","
        )
        if part.strip()
    ]

    if not parts:
        return (
            location,
            None,
            [],
        )

    province = parts[
        0
    ]

    districts = parts[
        1:
    ]

    return (
        location,
        province,
        districts,
    )


def parse_deadline(
    text: str,
) -> tuple[
    str,
    str | None,
]:
    """
    Return both the original deadline text and an
    ISO-formatted date where it can be parsed.
    """

    original = clean_text(
        text
    )

    normalized = re.sub(
        r"(\d{1,2})(st|nd|rd|th)",
        r"\1",
        original,
        flags=re.IGNORECASE,
    )

    normalized = re.sub(
        r"([A-Za-z])(\d{4})",
        r"\1 \2",
        normalized,
    )

    normalized = " ".join(
        normalized.split()
    )

    formats = [
        "%d %B %Y",
        "%d %b %Y",
    ]

    for date_format in formats:

        try:

            parsed = datetime.strptime(
                normalized,
                date_format,
            )

            return (
                original,
                parsed.date().isoformat(),
            )

        except ValueError:
            continue

    return (
        original,
        None,
    )


def safe_slug(
    text: str,
) -> str:
    """
    Convert text into a safe deterministic identifier.
    """

    slug = re.sub(
        r"[^a-z0-9]+",
        "_",
        text.lower(),
    )

    return slug.strip(
        "_"
    )


# ---------------------------------------------------------
# Table helpers
# ---------------------------------------------------------

def row_cells(
    row,
) -> list[str]:
    """
    Extract only the direct cells belonging to one row.

    recursive=False is important because government
    webpages sometimes contain nested table structures.
    """

    cells = row.find_all(
        [
            "th",
            "td",
        ],
        recursive=False,
    )

    return [
        clean_text(
            cell.get_text(
                " ",
                strip=True,
            )
        )
        for cell in cells
    ]


def looks_like_section_title(
    text: str,
) -> bool:
    """
    Determine whether a table row looks like a licence
    category heading.
    """

    lowered = text.lower()

    category_words = (
        "licence application",
        "license application",
        "mining right",
        "exploration licence",
        "exploration license",
        "mineral processing",
        "non-mining",
    )

    return any(
        word in lowered
        for word in category_words
    )


# ---------------------------------------------------------
# Record extraction
# ---------------------------------------------------------

def extract_licensing_records(
    html: str,
) -> list[dict]:
    """
    Extract structured licensing committee records.

    One table row containing a licence code becomes one
    structured record.
    """

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    main_content = find_main_content(
        soup
    )

    records: list[dict] = []

    seen_records: set[
        tuple
    ] = set()

    current_section: (
        str
        | None
    ) = None

    for table in (
        main_content.find_all(
            "table"
        )
    ):

        for row in table.find_all(
            "tr"
        ):

            cells = row_cells(
                row
            )

            cells = [
                cell
                for cell in cells
                if cell
            ]

            if not cells:
                continue

            joined = " | ".join(
                cells
            )

            # ---------------------------------------------
            # Section/category headings
            # ---------------------------------------------

            if (
                normalize_licence_code(
                    joined
                )
                is None
            ):

                if looks_like_section_title(
                    joined
                ):

                    current_section = (
                        clean_text(
                            joined
                        )
                    )

                continue

            # ---------------------------------------------
            # Find the cell containing the licence code
            # ---------------------------------------------

            code_index = None
            licence_code = None

            for index, cell in enumerate(
                cells
            ):

                candidate = (
                    normalize_licence_code(
                        cell
                    )
                )

                if candidate:

                    code_index = index
                    licence_code = (
                        candidate
                    )

                    break

            if (
                code_index is None
                or licence_code is None
            ):
                continue

            # Expected table layout:
            #
            # S/N
            # CODE
            # PARTIES
            # COMMODITIES
            # AREA
            # MAP REFERENCE
            # DECISION
            # TIMEFRAME

            remaining = cells[
                code_index + 1:
            ]

            if len(
                remaining
            ) < 6:

                print(
                    "[WARNING] Skipping "
                    f"incomplete row for "
                    f"{licence_code}: "
                    f"{len(remaining)} "
                    "fields after code."
                )

                continue

            applicant = remaining[
                0
            ]

            commodities_text = (
                remaining[
                    1
                ]
            )

            area_text = remaining[
                2
            ]

            location_text = (
                remaining[
                    3
                ]
            )

            decision_text = (
                remaining[
                    4
                ]
            )

            deadline_text = (
                remaining[
                    5
                ]
            )

            # ---------------------------------------------
            # Sequence number
            # ---------------------------------------------

            sequence_number = None

            if code_index > 0:

                sequence_match = re.search(
                    r"\d+",
                    cells[
                        code_index - 1
                    ],
                )

                if sequence_match:

                    sequence_number = int(
                        sequence_match.group()
                    )

            # ---------------------------------------------
            # Commodities
            # ---------------------------------------------

            commodities = [
                clean_text(
                    commodity
                )
                for commodity
                in commodities_text.split(
                    ","
                )
                if clean_text(
                    commodity
                )
            ]

            # ---------------------------------------------
            # Area
            # ---------------------------------------------

            area_hectares = (
                parse_area_hectares(
                    area_text
                )
            )

            # ---------------------------------------------
            # Location
            # ---------------------------------------------

            (
                location,
                province,
                districts,
            ) = normalize_location(
                location_text
            )

            # ---------------------------------------------
            # Decision
            # ---------------------------------------------

            decision = normalize_decision(
                decision_text
            )

            # ---------------------------------------------
            # Deadline
            # ---------------------------------------------

            (
                deadline,
                deadline_iso,
            ) = parse_deadline(
                deadline_text
            )

            # ---------------------------------------------
            # Licence type
            # ---------------------------------------------

            suffix = licence_suffix(
                licence_code
            )

            licence_type = (
                licence_type_name(
                    licence_code
                )
            )

            # ---------------------------------------------
            # Deduplication
            # ---------------------------------------------

            identity = (
                licence_code,
                applicant.lower(),
                decision.lower(),
                area_hectares,
            )

            if identity in seen_records:
                continue

            seen_records.add(
                identity
            )

            record = {
                "sequence_number": (
                    sequence_number
                ),
                "licence_code": (
                    licence_code
                ),
                "licence_type_code": (
                    suffix
                ),
                "licence_type": (
                    licence_type
                ),
                "section": (
                    current_section
                ),
                "applicant": applicant,
                "commodities": (
                    commodities
                ),
                "commodities_text": (
                    commodities_text
                ),
                "area_hectares": (
                    area_hectares
                ),
                "area_text": (
                    area_text
                ),
                "location": location,
                "province": province,
                "districts": (
                    districts
                ),
                "decision": decision,
                "deadline": deadline,
                "deadline_iso": (
                    deadline_iso
                ),
            }

            records.append(
                record
            )

    if not records:
        raise ValueError(
            "No licensing records could be "
            "extracted from the webpage."
        )

    return records


# ---------------------------------------------------------
# Search text
# ---------------------------------------------------------

def build_search_text(
    record: dict,
) -> str:
    """
    Convert one structured licence record into clean
    natural-language text for MineLens retrieval.
    """

    parts = [
        (
            f"Licence code: "
            f"{record['licence_code']}."
        ),
        (
            f"Licence type: "
            f"{record['licence_type']}."
        ),
        (
            f"Applicant: "
            f"{record['applicant']}."
        ),
    ]

    commodities = record.get(
        "commodities_text"
    )

    if commodities:

        parts.append(
            f"Commodities: "
            f"{commodities}."
        )

    area_hectares = record.get(
        "area_hectares"
    )

    if area_hectares is not None:

        parts.append(
            f"Area: "
            f"{area_hectares:,.4f} "
            f"hectares."
        )

    elif record.get(
        "area_text"
    ):

        parts.append(
            f"Area: "
            f"{record['area_text']}."
        )

    province = record.get(
        "province"
    )

    districts = record.get(
        "districts",
        [],
    )

    if province:

        parts.append(
            f"Province: "
            f"{province}."
        )

    if districts:

        parts.append(
            "District or districts: "
            + ", ".join(
                districts
            )
            + "."
        )

    elif record.get(
        "location"
    ):

        parts.append(
            f"Location: "
            f"{record['location']}."
        )

    decision = record.get(
        "decision"
    )

    if decision:

        parts.append(
            f"Committee decision: "
            f"{decision}."
        )

    deadline = record.get(
        "deadline"
    )

    if deadline:

        parts.append(
            f"Stipulated timeframe: "
            f"{deadline}."
        )

    return " ".join(
        parts
    )


# ---------------------------------------------------------
# Parser
# ---------------------------------------------------------

def parse_licensing_results(
    url: str,
    filename: str,
    overwrite: bool = False,
) -> tuple[
    Path,
    Path,
    Path,
]:
    """
    Download and parse a licensing committee webpage.

    Outputs:
        raw HTML
        structured licence JSONL
        searchable chunk JSONL

    Unlike normal HTML ingestion, one licence application
    becomes one searchable chunk.
    """

    if not filename.lower().endswith(
        (
            ".html",
            ".htm",
        )
    ):

        filename += ".html"

    raw_path, metadata = (
        download_html(
            url=url,
            filename=filename,
            overwrite=overwrite,
        )
    )

    PROCESSED_DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    stem = raw_path.stem

    records_path = (
        PROCESSED_DATA_DIR
        / f"{stem}.licences.jsonl"
    )

    chunks_path = (
        PROCESSED_DATA_DIR
        / f"{stem}.chunks.jsonl"
    )

    summary_path = (
        PROCESSED_DATA_DIR
        / f"{stem}.parse.json"
    )

    if (
        records_path.exists()
        and chunks_path.exists()
        and not overwrite
    ):

        print(
            "Structured licensing files "
            "already exist:"
        )

        print(
            f"  {records_path}"
        )

        print(
            f"  {chunks_path}"
        )

        print(
            "Use --overwrite to parse "
            "them again."
        )

        return (
            raw_path,
            records_path,
            chunks_path,
        )

    html = raw_path.read_text(
        encoding="utf-8",
        errors="replace",
    )

    print()
    print(
        "Extracting structured "
        "licensing records..."
    )

    records = (
        extract_licensing_records(
            html
        )
    )

    source_url = metadata.get(
        "source_url"
    )

    document_sha256 = metadata.get(
        "sha256"
    )

    # -----------------------------------------------------
    # Structured records
    # -----------------------------------------------------

    with records_path.open(
        "w",
        encoding="utf-8",
    ) as file:

        for record in records:

            output_record = {
                **record,
                "document": (
                    raw_path.name
                ),
                "source_url": (
                    source_url
                ),
                "document_sha256": (
                    document_sha256
                ),
                "content_type": (
                    "html_structured"
                ),
                "record_type": (
                    "licensing_application"
                ),
            }

            file.write(
                json.dumps(
                    output_record,
                    ensure_ascii=False,
                )
            )

            file.write(
                "\n"
            )

    # -----------------------------------------------------
    # Search chunks
    # -----------------------------------------------------

    chunk_ids_seen: dict[
        str,
        int,
    ] = {}

    with chunks_path.open(
        "w",
        encoding="utf-8",
    ) as file:

        for chunk_number, record in enumerate(
            records,
            start=1,
        ):

            base_chunk_id = (
                "licence_"
                + safe_slug(
                    record[
                        "licence_code"
                    ]
                )
            )

            occurrence = (
                chunk_ids_seen.get(
                    base_chunk_id,
                    0,
                )
                + 1
            )

            chunk_ids_seen[
                base_chunk_id
            ] = occurrence

            if occurrence == 1:

                chunk_id = (
                    base_chunk_id
                )

            else:

                chunk_id = (
                    f"{base_chunk_id}_"
                    f"{occurrence}"
                )

            text = build_search_text(
                record
            )

            chunk = {
                "chunk_id": chunk_id,
                "chunk_number": (
                    chunk_number
                ),
                "document": (
                    raw_path.name
                ),
                "page_start": 1,
                "page_end": 1,
                "text": text,
                "character_count": len(
                    text
                ),
                "source_url": (
                    source_url
                ),
                "document_sha256": (
                    document_sha256
                ),
                "content_type": (
                    "html_structured"
                ),
                "record_type": (
                    "licensing_application"
                ),
                **record,
            }

            file.write(
                json.dumps(
                    chunk,
                    ensure_ascii=False,
                )
            )

            file.write(
                "\n"
            )

    # -----------------------------------------------------
    # Summary
    # -----------------------------------------------------

    decision_counts: dict[
        str,
        int,
    ] = {}

    licence_type_counts: dict[
        str,
        int,
    ] = {}

    for record in records:

        decision = record.get(
            "decision"
        )

        if decision:

            decision_counts[
                decision
            ] = (
                decision_counts.get(
                    decision,
                    0,
                )
                + 1
            )

        licence_type = record.get(
            "licence_type"
        )

        if licence_type:

            licence_type_counts[
                licence_type
            ] = (
                licence_type_counts.get(
                    licence_type,
                    0,
                )
                + 1
            )

    summary = {
        "document": (
            raw_path.name
        ),
        "source_url": (
            source_url
        ),
        "content_type": (
            "html_structured"
        ),
        "parser": (
            "licensing_results"
        ),
        "records": len(
            records
        ),
        "chunks": len(
            records
        ),
        "decision_counts": (
            decision_counts
        ),
        "licence_type_counts": (
            licence_type_counts
        ),
        "document_sha256": (
            document_sha256
        ),
    }

    with summary_path.open(
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            summary,
            file,
            indent=4,
            ensure_ascii=False,
        )

    print()
    print(
        "Structured licensing "
        "parsing complete."
    )

    print(
        f"Records extracted: "
        f"{len(records):,}"
    )

    print(
        f"Search chunks:     "
        f"{len(records):,}"
    )

    print(
        f"Records: "
        f"{records_path}"
    )

    print(
        f"Chunks:  "
        f"{chunks_path}"
    )

    print(
        f"Summary: "
        f"{summary_path}"
    )

    return (
        raw_path,
        records_path,
        chunks_path,
    )


# ---------------------------------------------------------
# CLI
# ---------------------------------------------------------

def main() -> None:

    parser = argparse.ArgumentParser(
        description=(
            "Parse a Zambia licensing committee "
            "results webpage into structured records."
        )
    )

    parser.add_argument(
        "url",
        help=(
            "Licensing-results webpage URL"
        ),
    )

    parser.add_argument(
        "--filename",
        required=True,
        help=(
            "Local HTML filename"
        ),
    )

    parser.add_argument(
        "--overwrite",
        action="store_true",
        help=(
            "Redownload and reparse "
            "the webpage."
        ),
    )

    args = parser.parse_args()

    parse_licensing_results(
        url=args.url,
        filename=args.filename,
        overwrite=args.overwrite,
    )


if __name__ == "__main__":
    main()