from __future__ import annotations

import json
import re

from pathlib import Path

from bs4 import BeautifulSoup


# ---------------------------------------------------------
# Paths
# ---------------------------------------------------------

PROJECT_ROOT = Path(
    __file__
).resolve().parents[1]

RAW_PATH = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / (
        "shuka_kabwe_drilling_"
        "kbdd06_11_als_october_2026.html"
    )
)

PROCESSED_DIR = (
    PROJECT_ROOT
    / "data"
    / "processed"
)

INTERSECTIONS_PATH = (
    PROCESSED_DIR
    / "shuka_kabwe_2026_drill_intersections.jsonl"
)

MAX_ASSAYS_PATH = (
    PROCESSED_DIR
    / "shuka_kabwe_2026_hole_max_assays.jsonl"
)

SUMMARY_PATH = (
    PROCESSED_DIR
    / "shuka_kabwe_2026_exploration_summary.json"
)


# ---------------------------------------------------------
# Source metadata
# ---------------------------------------------------------

SOURCE_ID = (
    "shuka_kabwe_drilling_"
    "kbdd06_11_als_october_2026"
)

SOURCE_URL = (
    "https://www.shukaminerals.com/post/"
    "kabwe-drilling-kbdd06-11-drilling-results-"
    "from-als-laboratories"
)

SOURCE_TITLE = (
    "Kabwe Drilling KBDD06-11 - "
    "Drilling Results from ALS Laboratories"
)

PUBLISHED_DATE = "2026-10-16"

PROJECT_NAME = "Kabwe Zinc Mine"

PROJECT_ALIAS = "Kabwe Project"

PROJECT_AREA = "Speaks / Mine Club"

COMPANY = "Shuka Minerals Plc"

LABORATORY = "ALS Laboratories"

ASSAY_METHOD = (
    "ICP Sodium Peroxide Infusion "
    "(ME-ICP 81)"
)


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def clean_text(
    value: object,
) -> str:
    """
    Normalize whitespace without otherwise altering
    source wording.
    """

    if value is None:
        return ""

    return " ".join(
        str(
            value
        ).split()
    )


def parse_float(
    value: str,
) -> float | None:
    """
    Convert one numeric table value to float.
    Hyphens and blanks represent missing values.
    """

    cleaned = clean_text(
        value
    )

    if (
        not cleaned
        or cleaned
        in {
            "-",
            "–",
            "—",
        }
    ):
        return None

    cleaned = cleaned.replace(
        ",",
        "",
    )

    try:
        return float(
            cleaned
        )

    except ValueError:
        return None


def parse_cutoff_percent(
    value: str,
) -> float | None:
    """
    Extract numeric zinc cut-off percentage.
    """

    cleaned = clean_text(
        value
    )

    match = re.search(
        r"(\d+(?:\.\d+)?)\s*%",
        cleaned,
    )

    if not match:
        return None

    return float(
        match.group(
            1
        )
    )


def target_for_hole(
    hole_id: str,
) -> str:
    """
    Map drill holes to the exploration targets
    identified in the announcement.
    """

    if hole_id in {
        "KBDD06",
        "KBDD07",
        "KBDD08",
    }:
        return "Swimming Pool"

    if hole_id in {
        "KBDD09",
        "KBDD10",
        "KBDD11",
    }:
        return "Sperm Whale"

    return ""


def valid_hole_id(
    value: str,
) -> bool:
    """
    Accept only the six holes covered by this release.
    """

    return bool(
        re.fullmatch(
            r"KBDD(?:0[6-9]|1[01])",
            clean_text(
                value
            ),
        )
    )


def write_jsonl(
    path: Path,
    records: list[dict],
) -> None:
    """
    Write records as UTF-8 JSON Lines.
    """

    with path.open(
        "w",
        encoding="utf-8",
    ) as file:

        for record in records:

            file.write(
                json.dumps(
                    record,
                    ensure_ascii=False,
                )
            )

            file.write(
                "\n"
            )


# ---------------------------------------------------------
# Drill intersection extraction
# ---------------------------------------------------------

def extract_intersections(
    soup: BeautifulSoup,
) -> list[dict]:
    """
    Extract the KBDD06-KBDD11 drilling table.

    The announcement splits the drilling results over
    two HTML tables, so both are inspected.

    Nested intersections at different cut-off grades are
    deliberately preserved as separate reported records.
    """

    records: list[dict] = []

    seen: set[
        tuple
    ] = set()

    sequence = 0

    for table in soup.find_all(
        "table"
    ):

        table_text = clean_text(
            table.get_text(
                " ",
                strip=True,
            )
        )

        if not re.search(
            r"KBDD(?:0[6-9]|1[01])",
            table_text,
        ):
            continue

        for row in table.find_all(
            "tr"
        ):

            cells = [
                clean_text(
                    cell.get_text(
                        " ",
                        strip=True,
                    )
                )
                for cell in row.find_all(
                    [
                        "th",
                        "td",
                    ]
                )
            ]

            if len(
                cells
            ) < 8:
                continue

            cells = cells[
                :8
            ]

            hole_id = clean_text(
                cells[
                    0
                ]
            ).upper()

            if not valid_hole_id(
                hole_id
            ):
                continue

            (
                _,
                from_text,
                to_text,
                width_text,
                zinc_text,
                lead_text,
                cutoff_text,
                comment,
            ) = cells

            no_reportable = (
                "no significant"
                in comment.casefold()
            )

            from_m = parse_float(
                from_text
            )

            to_m = parse_float(
                to_text
            )

            width_m = parse_float(
                width_text
            )

            zinc_pct = parse_float(
                zinc_text
            )

            lead_pct = parse_float(
                lead_text
            )

            cutoff_pct = (
                parse_cutoff_percent(
                    cutoff_text
                )
            )

            if no_reportable:

                status = (
                    "no_reportable_intersection"
                )

            else:

                status = (
                    "reportable_intersection"
                )

                required_values = (
                    from_m,
                    to_m,
                    width_m,
                    zinc_pct,
                    lead_pct,
                )

                if any(
                    value is None
                    for value in required_values
                ):
                    raise ValueError(
                        "Incomplete numeric result for "
                        f"{hole_id}: {cells}"
                    )

            uniqueness_key = (
                hole_id,
                from_m,
                to_m,
                width_m,
                zinc_pct,
                lead_pct,
                cutoff_pct,
                comment,
            )

            if uniqueness_key in seen:
                continue

            seen.add(
                uniqueness_key
            )

            sequence += 1

            calculated_width_m = None

            width_matches_depths = None

            if (
                from_m is not None
                and to_m is not None
            ):

                calculated_width_m = round(
                    to_m
                    - from_m,
                    4,
                )

                if width_m is not None:

                    width_matches_depths = (
                        abs(
                            calculated_width_m
                            - width_m
                        )
                        <= 0.05
                    )

            target = target_for_hole(
                hole_id
            )

            search_parts = [
                PROJECT_NAME,
                PROJECT_ALIAS,
                PROJECT_AREA,
                target,
                hole_id,
                status.replace(
                    "_",
                    " ",
                ),
            ]

            if width_m is not None:
                search_parts.append(
                    f"{width_m:g} metre interval"
                )

            if zinc_pct is not None:
                search_parts.append(
                    f"{zinc_pct:g}% zinc"
                )

            if lead_pct is not None:
                search_parts.append(
                    f"{lead_pct:g}% lead"
                )

            if cutoff_pct is not None:
                search_parts.append(
                    f"{cutoff_pct:g}% zinc cutoff"
                )

            if comment:
                search_parts.append(
                    comment
                )

            record = {
                "record_type":
                    "drill_intersection",

                "sequence_number":
                    sequence,

                "project":
                    PROJECT_NAME,

                "project_alias":
                    PROJECT_ALIAS,

                "project_area":
                    PROJECT_AREA,

                "target":
                    target,

                "hole_id":
                    hole_id,

                "status":
                    status,

                "from_m":
                    from_m,

                "to_m":
                    to_m,

                "width_m":
                    width_m,

                "calculated_width_m":
                    calculated_width_m,

                "width_matches_depths":
                    width_matches_depths,

                "zinc_pct":
                    zinc_pct,

                "lead_pct":
                    lead_pct,

                "cutoff_zinc_pct":
                    cutoff_pct,

                "cutoff_text":
                    clean_text(
                        cutoff_text
                    ),

                "comment":
                    comment,

                "reporting_basis":
                    "laboratory assay",

                "laboratory":
                    LABORATORY,

                "assay_method":
                    ASSAY_METHOD,

                "company":
                    COMPANY,

                "published_date":
                    PUBLISHED_DATE,

                "source_id":
                    SOURCE_ID,

                "source_title":
                    SOURCE_TITLE,

                "source_url":
                    SOURCE_URL,

                "source_type":
                    "company_announcement",

                "search_text":
                    ". ".join(
                        part
                        for part in search_parts
                        if part
                    ),

                "raw_row":
                    cells,
            }

            records.append(
                record
            )

    return records


# ---------------------------------------------------------
# Maximum individual assay extraction
# ---------------------------------------------------------

def extract_max_assays(
    soup: BeautifulSoup,
) -> list[dict]:
    """
    Extract the maximum individual Zn assay reported for
    each KBDD06-KBDD11 drill hole.
    """

    text = clean_text(
        soup.get_text(
            " ",
            strip=True,
        )
    )

    marker = (
        "maximum individual drill-core"
    )

    marker_index = (
        text.casefold().find(
            marker
        )
    )

    if marker_index == -1:

        marker = (
            "maximum individual drill core"
        )

        marker_index = (
            text.casefold().find(
                marker
            )
        )

    if marker_index == -1:
        raise ValueError(
            "Could not locate maximum individual "
            "assay section."
        )

    section = text[
        marker_index:
        marker_index + 3000
    ]

    matches = re.findall(
        (
            r"(KBDD(?:0[6-9]|1[01]))"
            r"\s*:\s*"
            r"(\d+(?:\.\d+)?)"
            r"\s*%\s*Zn"
        ),
        section,
        flags=re.IGNORECASE,
    )

    records: list[dict] = []

    seen: set[str] = set()

    for (
        hole_id,
        zinc_text,
    ) in matches:

        hole_id = (
            hole_id.upper()
        )

        if hole_id in seen:
            continue

        seen.add(
            hole_id
        )

        zinc_pct = float(
            zinc_text
        )

        target = target_for_hole(
            hole_id
        )

        records.append(
            {
                "record_type":
                    "hole_maximum_assay",

                "project":
                    PROJECT_NAME,

                "project_alias":
                    PROJECT_ALIAS,

                "project_area":
                    PROJECT_AREA,

                "target":
                    target,

                "hole_id":
                    hole_id,

                "commodity":
                    "Zinc",

                "commodity_symbol":
                    "Zn",

                "maximum_assay_pct":
                    zinc_pct,

                "reporting_basis":
                    "maximum individual drill-core "
                    "laboratory assay",

                "laboratory":
                    LABORATORY,

                "assay_method":
                    ASSAY_METHOD,

                "company":
                    COMPANY,

                "published_date":
                    PUBLISHED_DATE,

                "source_id":
                    SOURCE_ID,

                "source_title":
                    SOURCE_TITLE,

                "source_url":
                    SOURCE_URL,

                "source_type":
                    "company_announcement",

                "search_text": (
                    f"{PROJECT_NAME}. "
                    f"{target}. "
                    f"{hole_id}. "
                    f"Maximum individual zinc assay "
                    f"{zinc_pct:g}% Zn."
                ),
            }
        )

    records.sort(
        key=lambda record: (
            record[
                "hole_id"
            ]
        )
    )

    return records


# ---------------------------------------------------------
# Summary
# ---------------------------------------------------------

def build_summary(
    intersections: list[dict],
    max_assays: list[dict],
) -> dict:
    """
    Build quality-control and overview metadata.
    """

    reportable = [
        record
        for record in intersections
        if record.get(
            "status"
        )
        == "reportable_intersection"
    ]

    no_reportable = [
        record
        for record in intersections
        if record.get(
            "status"
        )
        == "no_reportable_intersection"
    ]

    holes = sorted(
        {
            record[
                "hole_id"
            ]
            for record in intersections
        }
    )

    target_counts: dict[
        str,
        int,
    ] = {}

    for record in reportable:

        target = (
            record.get(
                "target"
            )
            or "Unknown"
        )

        target_counts[
            target
        ] = (
            target_counts.get(
                target,
                0,
            )
            + 1
        )

    highest_intersection = None

    if reportable:

        highest_intersection = max(
            reportable,
            key=lambda record: (
                record.get(
                    "zinc_pct"
                )
                if record.get(
                    "zinc_pct"
                )
                is not None
                else -1
            ),
        )

    highest_max_assay = None

    if max_assays:

        highest_max_assay = max(
            max_assays,
            key=lambda record: (
                record[
                    "maximum_assay_pct"
                ]
            ),
        )

    width_mismatches = [
        {
            "hole_id":
                record[
                    "hole_id"
                ],

            "from_m":
                record[
                    "from_m"
                ],

            "to_m":
                record[
                    "to_m"
                ],

            "reported_width_m":
                record[
                    "width_m"
                ],

            "calculated_width_m":
                record[
                    "calculated_width_m"
                ],
        }
        for record in reportable
        if (
            record.get(
                "width_matches_depths"
            )
            is False
        )
    ]

    return {
        "source_id":
            SOURCE_ID,

        "source_title":
            SOURCE_TITLE,

        "source_url":
            SOURCE_URL,

        "published_date":
            PUBLISHED_DATE,

        "company":
            COMPANY,

        "project":
            PROJECT_NAME,

        "project_area":
            PROJECT_AREA,

        "laboratory":
            LABORATORY,

        "assay_method":
            ASSAY_METHOD,

        "holes":
            holes,

        "hole_count":
            len(
                holes
            ),

        "intersection_records":
            len(
                intersections
            ),

        "reportable_intersections":
            len(
                reportable
            ),

        "no_reportable_intersection_records":
            len(
                no_reportable
            ),

        "target_reportable_counts":
            target_counts,

        "maximum_assay_records":
            len(
                max_assays
            ),

        "highest_reported_intersection_zinc":
            (
                {
                    "hole_id":
                        highest_intersection[
                            "hole_id"
                        ],

                    "target":
                        highest_intersection[
                            "target"
                        ],

                    "from_m":
                        highest_intersection[
                            "from_m"
                        ],

                    "to_m":
                        highest_intersection[
                            "to_m"
                        ],

                    "width_m":
                        highest_intersection[
                            "width_m"
                        ],

                    "zinc_pct":
                        highest_intersection[
                            "zinc_pct"
                        ],

                    "lead_pct":
                        highest_intersection[
                            "lead_pct"
                        ],

                    "cutoff_zinc_pct":
                        highest_intersection[
                            "cutoff_zinc_pct"
                        ],
                }
                if highest_intersection
                else None
            ),

        "highest_individual_zinc_assay":
            (
                {
                    "hole_id":
                        highest_max_assay[
                            "hole_id"
                        ],

                    "target":
                        highest_max_assay[
                            "target"
                        ],

                    "zinc_pct":
                        highest_max_assay[
                            "maximum_assay_pct"
                        ],
                }
                if highest_max_assay
                else None
            ),

        "width_mismatches":
            width_mismatches,

        "notes": [
            (
                "Reported intersections are preserved "
                "as published, including nested intervals "
                "at different zinc cut-off grades."
            ),
            (
                "Laboratory assay results are not treated "
                "as mineral resource or reserve estimates."
            ),
        ],
    }


# ---------------------------------------------------------
# Main
# ---------------------------------------------------------

def main() -> None:

    if not RAW_PATH.exists():
        raise FileNotFoundError(
            f"Raw Shuka HTML not found: "
            f"{RAW_PATH}"
        )

    PROCESSED_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    html = RAW_PATH.read_text(
        encoding="utf-8",
        errors="replace",
    )

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    intersections = (
        extract_intersections(
            soup
        )
    )

    max_assays = (
        extract_max_assays(
            soup
        )
    )

    if not intersections:
        raise ValueError(
            "No drilling intersection records "
            "were extracted."
        )

    expected_holes = {
        "KBDD06",
        "KBDD07",
        "KBDD08",
        "KBDD09",
        "KBDD10",
        "KBDD11",
    }

    actual_holes = {
        record[
            "hole_id"
        ]
        for record in intersections
    }

    if actual_holes != expected_holes:
        raise ValueError(
            "Unexpected hole coverage. "
            f"Expected {sorted(expected_holes)}, "
            f"got {sorted(actual_holes)}."
        )

    assay_holes = {
        record[
            "hole_id"
        ]
        for record in max_assays
    }

    if assay_holes != expected_holes:
        raise ValueError(
            "Maximum-assay extraction did not "
            "cover all six drill holes. "
            f"Got {sorted(assay_holes)}."
        )

    summary = build_summary(
        intersections=intersections,
        max_assays=max_assays,
    )

    write_jsonl(
        INTERSECTIONS_PATH,
        intersections,
    )

    write_jsonl(
        MAX_ASSAYS_PATH,
        max_assays,
    )

    SUMMARY_PATH.write_text(
        json.dumps(
            summary,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print()
    print(
        "=" * 72
    )
    print(
        "SHUKA KABWE EXPLORATION INGESTION"
    )
    print(
        "=" * 72
    )

    print(
        "Holes:",
        summary[
            "hole_count"
        ],
    )

    print(
        "Intersection records:",
        summary[
            "intersection_records"
        ],
    )

    print(
        "Reportable intersections:",
        summary[
            "reportable_intersections"
        ],
    )

    print(
        "No-reportable records:",
        summary[
            "no_reportable_intersection_records"
        ],
    )

    print(
        "Maximum assay records:",
        summary[
            "maximum_assay_records"
        ],
    )

    print()

    print(
        "Target counts:",
        summary[
            "target_reportable_counts"
        ],
    )

    print()

    print(
        "Highest intersection Zn:",
        summary[
            "highest_reported_intersection_zinc"
        ],
    )

    print(
        "Highest individual Zn assay:",
        summary[
            "highest_individual_zinc_assay"
        ],
    )

    print()

    print(
        "Width mismatches:",
        len(
            summary[
                "width_mismatches"
            ]
        ),
    )

    print()

    print(
        "Intersections:",
        INTERSECTIONS_PATH,
    )

    print(
        "Max assays:",
        MAX_ASSAYS_PATH,
    )

    print(
        "Summary:",
        SUMMARY_PATH,
    )


if __name__ == "__main__":
    main()
