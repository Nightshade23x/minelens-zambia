from __future__ import annotations

import argparse
import json
import math

from pathlib import Path
from typing import Any

import pandas as pd


# =========================================================
# PATHS
# =========================================================

PROJECT_ROOT = Path(
    __file__
).resolve().parents[1]


RAW_DATA_DIR = (
    PROJECT_ROOT
    / "data"
    / "raw"
)


PROCESSED_DATA_DIR = (
    PROJECT_ROOT
    / "data"
    / "processed"
)


DEFAULT_PRODUCTION_FILE = (
    RAW_DATA_DIR
    / (
        "world_mining_data_2026_"
        "chapter_6_4_country_production.xlsx"
    )
)


DEFAULT_SHARE_FILE = (
    RAW_DATA_DIR
    / (
        "world_mining_data_2026_"
        "chapter_6_5_world_share.xlsx"
    )
)


DEFAULT_OUTPUT_FILE = (
    PROCESSED_DATA_DIR
    / "world_mining_data_2026.statistics.jsonl"
)


DEFAULT_SUMMARY_FILE = (
    PROCESSED_DATA_DIR
    / "world_mining_data_2026.statistics_summary.json"
)


# =========================================================
# SOURCE METADATA
# =========================================================

DATASET_ID = (
    "world_mining_data_2026"
)


DATASET_TITLE = (
    "World Mining Data 2026"
)


AGENCY = (
    "Austrian Federal Ministry of Finance"
)


SOURCE_URL = (
    "https://www.bmf.gv.at/en/topics/mining/"
    "mineral-resources-policy/wmd.html"
)


PRODUCTION_SOURCE = (
    "World Mining Data 2026 - Chapter 6.4"
)


SHARE_SOURCE = (
    "World Mining Data 2026 - Chapter 6.5"
)


# =========================================================
# BASIC HELPERS
# =========================================================

def clean_text(
    value: Any,
) -> str:
    """
    Convert spreadsheet values to clean text.
    """

    if value is None:
        return ""

    try:

        if pd.isna(
            value
        ):
            return ""

    except TypeError:
        pass

    return " ".join(
        str(
            value
        ).split()
    )


def safe_float(
    value: Any,
) -> float | None:
    """
    Convert spreadsheet numeric values safely.
    """

    if value is None:
        return None

    try:

        if pd.isna(
            value
        ):
            return None

    except TypeError:
        pass

    if isinstance(
        value,
        (int, float),
    ):

        number = float(
            value
        )

        if math.isfinite(
            number
        ):
            return number

        return None

    text = clean_text(
        value
    )

    if not text:
        return None

    text = (
        text
        .replace(
            ",",
            "",
        )
        .replace(
            "%",
            "",
        )
    )

    try:

        number = float(
            text
        )

    except ValueError:

        return None

    if not math.isfinite(
        number
    ):
        return None

    return number


def safe_int(
    value: Any,
) -> int | None:
    """
    Convert rank-like spreadsheet values to integers.

    Handles values such as:
        8
        8.0
        "(10)"
        "( 10)"
    """

    if value is None:
        return None

    numeric_value = safe_float(
        value
    )

    if numeric_value is not None:

        return int(
            numeric_value
        )

    text = clean_text(
        value
    )

    if not text:
        return None

    digits = "".join(
        character
        for character in text
        if character.isdigit()
    )

    if not digits:
        return None

    return int(
        digits
    )


def normalize_commodity(
    sheet_name: str,
) -> str:
    """
    Normalize commodity sheet names while preserving the
    official World Mining Data terminology.
    """

    return clean_text(
        sheet_name
    )


def normalize_data_quality(
    value: Any,
) -> str | None:
    """
    Expand World Mining Data source-quality codes.
    """

    code = (
        clean_text(
            value
        )
        .casefold()
    )

    labels = {
        "r": "reported",
        "e": "estimated",
        "p": "provisional",
    }

    return labels.get(
        code
    )


def country_key(
    country: str,
) -> str:

    return (
        clean_text(
            country
        )
        .casefold()
    )


def commodity_key(
    commodity: str,
) -> str:

    return (
        clean_text(
            commodity
        )
        .casefold()
    )


# =========================================================
# CHAPTER 6.4
# =========================================================

def load_production_records(
    path: Path,
) -> list[dict]:
    """
    Read Chapter 6.4.

    Each commodity is one worksheet.

    Output is normalized into one record per:

        commodity + country + year
    """

    if not path.exists():

        raise FileNotFoundError(
            "World Mining Data production workbook "
            f"not found:\n{path}"
        )

    workbook = pd.ExcelFile(
        path
    )

    records: list[dict] = []


    for sheet_name in (
        workbook.sheet_names
    ):

        commodity = (
            normalize_commodity(
                sheet_name
            )
        )

        dataframe = pd.read_excel(
            path,
            sheet_name=sheet_name,
            header=1,
        )

        if dataframe.shape[1] < 8:

            raise ValueError(
                f"Unexpected Chapter 6.4 layout "
                f"in sheet '{sheet_name}'. "
                f"Expected at least 8 columns, "
                f"found {dataframe.shape[1]}."
            )


        # Use column position rather than relying on
        # Excel header typing such as 2020 vs 2020.0.
        dataframe = dataframe.iloc[
            :,
            :8,
        ].copy()


        dataframe.columns = [
            "country",
            "unit",
            "2020",
            "2021",
            "2022",
            "2023",
            "2024",
            "data_source_code",
        ]


        for _, row in (
            dataframe.iterrows()
        ):

            country = clean_text(
                row[
                    "country"
                ]
            )

            if not country:
                continue

            if (
                country.casefold()
                == "total"
            ):
                continue


            unit = clean_text(
                row[
                    "unit"
                ]
            )

            quality_code = (
                clean_text(
                    row[
                        "data_source_code"
                    ]
                )
                .casefold()
            )

            quality_label = (
                normalize_data_quality(
                    quality_code
                )
            )


            for year in range(
                2020,
                2025,
            ):

                production = (
                    safe_float(
                        row[
                            str(
                                year
                            )
                        ]
                    )
                )

                if production is None:
                    continue


                record = {
                    "dataset_id":
                        DATASET_ID,

                    "dataset_title":
                        DATASET_TITLE,

                    "agency":
                        AGENCY,

                    "record_type":
                        "mineral_production",

                    "commodity":
                        commodity,

                    "country":
                        country,

                    "unit":
                        unit,

                    "year":
                        year,

                    "production":
                        production,

                    "data_quality_code":
                        (
                            quality_code
                            or None
                        ),

                    "data_quality":
                        quality_label,

                    "rank_2024":
                        None,

                    "rank_2023":
                        None,

                    "world_share_percent":
                        None,

                    "cumulative_world_share_percent":
                        None,

                    "share_hhi":
                        None,

                    "source_url":
                        SOURCE_URL,

                    "production_source":
                        PRODUCTION_SOURCE,

                    "world_share_source":
                        None,

                    "production_workbook":
                        path.name,
                }


                records.append(
                    record
                )


    return records


# =========================================================
# CHAPTER 6.5
# =========================================================

def load_world_share_records(
    path: Path,
) -> dict[
    tuple[str, str],
    dict,
]:
    """
    Read Chapter 6.5.

    Returns one 2024 share/rank record per:

        commodity + country
    """

    if not path.exists():

        raise FileNotFoundError(
            "World Mining Data world-share workbook "
            f"not found:\n{path}"
        )


    workbook = pd.ExcelFile(
        path
    )

    records: dict[
        tuple[str, str],
        dict,
    ] = {}


    for sheet_name in (
        workbook.sheet_names
    ):

        commodity = (
            normalize_commodity(
                sheet_name
            )
        )


        dataframe = pd.read_excel(
            path,
            sheet_name=sheet_name,
            header=1,
        )


        if dataframe.shape[1] < 8:

            raise ValueError(
                f"Unexpected Chapter 6.5 layout "
                f"in sheet '{sheet_name}'. "
                f"Expected at least 8 columns, "
                f"found {dataframe.shape[1]}."
            )


        dataframe = dataframe.iloc[
            :,
            :8,
        ].copy()


        dataframe.columns = [
            "rank_2024",
            "rank_2023",
            "country",
            "unit",
            "production_2024",
            "world_share_percent",
            "cumulative_world_share_percent",
            "share_hhi",
        ]


        for _, row in (
            dataframe.iterrows()
        ):

            country = clean_text(
                row[
                    "country"
                ]
            )


            if not country:
                continue


            if (
                country.casefold()
                == "total"
            ):
                continue


            key = (
                commodity_key(
                    commodity
                ),
                country_key(
                    country
                ),
            )


            records[
                key
            ] = {
                "commodity":
                    commodity,

                "country":
                    country,

                "unit":
                    clean_text(
                        row[
                            "unit"
                        ]
                    ),

                "production_2024":
                    safe_float(
                        row[
                            "production_2024"
                        ]
                    ),

                "rank_2024":
                    safe_int(
                        row[
                            "rank_2024"
                        ]
                    ),

                "rank_2023":
                    safe_int(
                        row[
                            "rank_2023"
                        ]
                    ),

                "world_share_percent":
                    safe_float(
                        row[
                            "world_share_percent"
                        ]
                    ),

                "cumulative_world_share_percent":
                    safe_float(
                        row[
                            "cumulative_world_share_percent"
                        ]
                    ),

                "share_hhi":
                    safe_float(
                        row[
                            "share_hhi"
                        ]
                    ),

                "world_share_source":
                    SHARE_SOURCE,

                "world_share_workbook":
                    path.name,
            }


    return records


# =========================================================
# JOIN
# =========================================================

def enrich_2024_records(
    production_records: list[dict],
    share_records: dict[
        tuple[str, str],
        dict,
    ],
) -> tuple[
    list[dict],
    list[dict],
]:
    """
    Join Chapter 6.5 rank/share fields onto 2024 Chapter 6.4
    production records.

    Also check whether both workbooks agree on production.
    """

    discrepancies: list[
        dict
    ] = []


    for record in (
        production_records
    ):

        if (
            record[
                "year"
            ]
            != 2024
        ):
            continue


        key = (
            commodity_key(
                record[
                    "commodity"
                ]
            ),
            country_key(
                record[
                    "country"
                ]
            ),
        )


        share_record = (
            share_records.get(
                key
            )
        )


        if share_record is None:
            continue


        record[
            "rank_2024"
        ] = (
            share_record[
                "rank_2024"
            ]
        )

        record[
            "rank_2023"
        ] = (
            share_record[
                "rank_2023"
            ]
        )

        record[
            "world_share_percent"
        ] = (
            share_record[
                "world_share_percent"
            ]
        )

        record[
            "cumulative_world_share_percent"
        ] = (
            share_record[
                "cumulative_world_share_percent"
            ]
        )

        record[
            "share_hhi"
        ] = (
            share_record[
                "share_hhi"
            ]
        )

        record[
            "world_share_source"
        ] = (
            share_record[
                "world_share_source"
            ]
        )

        record[
            "world_share_workbook"
        ] = (
            share_record[
                "world_share_workbook"
            ]
        )


        production_64 = (
            record[
                "production"
            ]
        )

        production_65 = (
            share_record[
                "production_2024"
            ]
        )


        if (
            production_65
            is not None
            and not math.isclose(
                production_64,
                production_65,
                rel_tol=1e-9,
                abs_tol=1e-9,
            )
        ):

            discrepancies.append(
                {
                    "commodity":
                        record[
                            "commodity"
                        ],

                    "country":
                        record[
                            "country"
                        ],

                    "chapter_6_4":
                        production_64,

                    "chapter_6_5":
                        production_65,
                }
            )


    return (
        production_records,
        discrepancies,
    )


# =========================================================
# OUTPUT
# =========================================================

def write_jsonl(
    records: list[dict],
    output_path: Path,
) -> None:

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )


    ordered_records = sorted(
        records,
        key=lambda record: (
            record[
                "commodity"
            ].casefold(),
            record[
                "country"
            ].casefold(),
            record[
                "year"
            ],
        ),
    )


    with output_path.open(
        "w",
        encoding="utf-8",
    ) as file:

        for record in (
            ordered_records
        ):

            file.write(
                json.dumps(
                    record,
                    ensure_ascii=False,
                )
            )

            file.write(
                "\n"
            )


def build_summary(
    records: list[dict],
    share_records: dict,
    discrepancies: list[dict],
) -> dict:

    commodities = sorted(
        {
            record[
                "commodity"
            ]
            for record in records
        },
        key=str.casefold,
    )


    countries = sorted(
        {
            record[
                "country"
            ]
            for record in records
        },
        key=str.casefold,
    )


    zambia_records = [
        record
        for record in records
        if (
            record[
                "country"
            ].casefold()
            == "zambia"
        )
    ]


    zambia_commodities = sorted(
        {
            record[
                "commodity"
            ]
            for record in zambia_records
        },
        key=str.casefold,
    )


    records_with_world_share = sum(
        record.get(
            "world_share_percent"
        )
        is not None
        for record in records
    )


    return {
        "dataset_id":
            DATASET_ID,

        "dataset_title":
            DATASET_TITLE,

        "record_count":
            len(
                records
            ),

        "commodity_count":
            len(
                commodities
            ),

        "country_count":
            len(
                countries
            ),

        "world_share_rows":
            len(
                share_records
            ),

        "records_with_world_share":
            records_with_world_share,

        "zambia_record_count":
            len(
                zambia_records
            ),

        "zambia_commodity_count":
            len(
                zambia_commodities
            ),

        "zambia_commodities":
            zambia_commodities,

        "production_discrepancy_count":
            len(
                discrepancies
            ),

        "production_discrepancies":
            discrepancies,
    }


def write_summary(
    summary: dict,
    summary_path: Path,
) -> None:

    summary_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )


    summary_path.write_text(
        json.dumps(
            summary,
            indent=4,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )


# =========================================================
# INGESTION
# =========================================================

def ingest_wmd_statistics(
    production_path: Path = DEFAULT_PRODUCTION_FILE,
    share_path: Path = DEFAULT_SHARE_FILE,
    output_path: Path = DEFAULT_OUTPUT_FILE,
    summary_path: Path = DEFAULT_SUMMARY_FILE,
) -> tuple[
    Path,
    Path,
]:
    """
    Build the structured MineLens World Mining Data dataset.
    """

    print(
        "Reading World Mining Data Chapter 6.4..."
    )

    production_records = (
        load_production_records(
            production_path
        )
    )


    print(
        "Production records:",
        f"{len(production_records):,}",
    )


    print(
        "Reading World Mining Data Chapter 6.5..."
    )

    share_records = (
        load_world_share_records(
            share_path
        )
    )


    print(
        "World-share records:",
        f"{len(share_records):,}",
    )


    print(
        "Joining 2024 rank/share data..."
    )

    (
        production_records,
        discrepancies,
    ) = enrich_2024_records(
        production_records,
        share_records,
    )


    write_jsonl(
        production_records,
        output_path,
    )


    summary = build_summary(
        production_records,
        share_records,
        discrepancies,
    )


    write_summary(
        summary,
        summary_path,
    )


    print()
    print(
        "=" * 72
    )

    print(
        "WORLD MINING DATA STRUCTURED INGESTION COMPLETE"
    )

    print(
        "=" * 72
    )

    print(
        "Records:",
        f"{summary['record_count']:,}",
    )

    print(
        "Commodities:",
        summary[
            "commodity_count"
        ],
    )

    print(
        "Countries:",
        summary[
            "country_count"
        ],
    )

    print(
        "Zambia commodities:",
        summary[
            "zambia_commodity_count"
        ],
    )

    print(
        "Production discrepancies:",
        summary[
            "production_discrepancy_count"
        ],
    )

    print()
    print(
        "Output:",
        output_path,
    )

    print(
        "Summary:",
        summary_path,
    )


    return (
        output_path,
        summary_path,
    )


# =========================================================
# CLI
# =========================================================

def main() -> None:

    parser = argparse.ArgumentParser(
        description=(
            "Ingest World Mining Data 2026 Excel "
            "workbooks into normalized MineLens "
            "structured statistics."
        )
    )


    parser.add_argument(
        "--production",
        type=Path,
        default=DEFAULT_PRODUCTION_FILE,
        help=(
            "Path to World Mining Data "
            "Chapter 6.4 workbook."
        ),
    )


    parser.add_argument(
        "--share",
        type=Path,
        default=DEFAULT_SHARE_FILE,
        help=(
            "Path to World Mining Data "
            "Chapter 6.5 workbook."
        ),
    )


    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_FILE,
        help=(
            "Output structured JSONL file."
        ),
    )


    parser.add_argument(
        "--summary",
        type=Path,
        default=DEFAULT_SUMMARY_FILE,
        help=(
            "Output ingestion summary JSON."
        ),
    )


    args = parser.parse_args()


    ingest_wmd_statistics(
        production_path=args.production,
        share_path=args.share,
        output_path=args.output,
        summary_path=args.summary,
    )


if __name__ == "__main__":
    main()