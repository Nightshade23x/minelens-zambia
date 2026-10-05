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
    / "2024MYBv3_Production_table.csv"
)


DEFAULT_FACILITIES_FILE = (
    RAW_DATA_DIR
    / "2024MYBv3_Facilities_table.csv"
)


DEFAULT_PRODUCTION_OUTPUT = (
    PROCESSED_DATA_DIR
    / "usgs_2024_zambia_production.jsonl"
)


DEFAULT_FACILITY_PRODUCTS_OUTPUT = (
    PROCESSED_DATA_DIR
    / "usgs_2024_zambia_facility_products.jsonl"
)


DEFAULT_FACILITIES_OUTPUT = (
    PROCESSED_DATA_DIR
    / "usgs_2024_zambia_facilities.jsonl"
)


DEFAULT_SUMMARY_OUTPUT = (
    PROCESSED_DATA_DIR
    / "usgs_2024_zambia_summary.json"
)


# =========================================================
# SOURCE METADATA
# =========================================================

DATASET_ID = (
    "usgs_zambia_minerals_yearbook_2024"
)


DATASET_TITLE = (
    "USGS Minerals Yearbook 2024 - Zambia"
)


AGENCY = (
    "U.S. Geological Survey"
)


COUNTRY = (
    "Zambia"
)


# =========================================================
# BASIC HELPERS
# =========================================================

def clean_text(
    value: Any,
) -> str:
    """
    Convert an arbitrary value into clean one-line text.
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


def optional_text(
    value: Any,
) -> str | None:
    """
    Return normalized text or None.
    """

    text = clean_text(
        value
    )

    return (
        text
        if text
        else None
    )


def safe_number(
    value: Any,
) -> float | None:
    """
    Convert a numeric field safely.

    USGS uses -999 as a missing / unavailable sentinel
    in several facilities fields. That value must never
    be treated as a real negative capacity or ownership
    share.
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


    try:

        number = float(
            value
        )

    except (
        TypeError,
        ValueError,
    ):

        text = clean_text(
            value
        ).replace(
            ",",
            "",
        )

        if not text:
            return None

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


    if math.isclose(
        number,
        -999.0,
        rel_tol=0.0,
        abs_tol=1e-9,
    ):

        return None


    return number


def safe_int(
    value: Any,
) -> int | None:

    number = safe_number(
        value
    )

    if number is None:
        return None

    return int(
        number
    )


def split_shared_capacity(
    value: Any,
) -> list[str]:
    """
    Convert comma-separated USGS shared-capacity IDs
    into a normalized list.
    """

    text = clean_text(
        value
    )

    if not text:
        return []

    return [
        item.strip()
        for item in text.split(
            ","
        )
        if item.strip()
    ]


def unique_nonempty(
    values: list[Any],
) -> list[str]:

    result: list[str] = []

    seen: set[str] = set()


    for value in values:

        text = clean_text(
            value
        )

        if not text:

            continue


        key = text.casefold()

        if key in seen:

            continue


        seen.add(
            key
        )

        result.append(
            text
        )


    return result


# =========================================================
# EXACT ZAMBIA FILTER
# =========================================================

def filter_zambia(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:
    """
    Keep only records whose country/locality field is
    exactly Zambia.

    Do not search every column for the word Zambia:
    foreign facilities may mention Zambia in location
    notes.
    """

    country_column = (
        "Country (Short Form) or Locality"
    )


    if country_column not in dataframe.columns:

        raise ValueError(
            "Required USGS country column not found: "
            f"{country_column}"
        )


    country_values = (
        dataframe[
            country_column
        ]
        .astype(str)
        .str.strip()
        .str.casefold()
    )


    return (
        dataframe[
            country_values
            == COUNTRY.casefold()
        ]
        .copy()
    )


# =========================================================
# PRODUCTION
# =========================================================

def build_production_records(
    path: Path,
) -> list[dict]:
    """
    Normalize Zambia USGS production records.

    The source is intentionally kept at product-stream
    granularity. Copper mine concentrate production,
    solvent-extraction output, refinery output, etc. are
    distinct records and must not be silently combined.
    """

    if not path.exists():

        raise FileNotFoundError(
            "USGS production CSV not found:\n"
            f"{path}"
        )


    dataframe = pd.read_csv(
        path,
        low_memory=False,
    )


    dataframe = filter_zambia(
        dataframe
    )


    records: list[
        dict
    ] = []


    for _, row in (
        dataframe.iterrows()
    ):

        record = {
            "dataset_id":
                DATASET_ID,

            "dataset_title":
                DATASET_TITLE,

            "agency":
                AGENCY,

            "record_type":
                "country_production",

            "object_id":
                safe_int(
                    row.get(
                        "ObjectID"
                    )
                ),

            "publication_year":
                safe_int(
                    row.get(
                        "Publication Year"
                    )
                ),

            "publication_name":
                optional_text(
                    row.get(
                        "Publication Short Name and Volume"
                    )
                ),

            "country":
                optional_text(
                    row.get(
                        "Country (Short Form) or Locality"
                    )
                ),

            "commodity_group":
                optional_text(
                    row.get(
                        "Level 1 (Commodity Group)"
                    )
                ),

            "commodity":
                optional_text(
                    row.get(
                        "Level 2 (Commodity)"
                    )
                ),

            "type":
                optional_text(
                    row.get(
                        "Level 3 (Type)"
                    )
                ),

            "phase":
                optional_text(
                    row.get(
                        "Level 4 (Phase)"
                    )
                ),

            "form":
                optional_text(
                    row.get(
                        "Level 5 (Form)"
                    )
                ),

            "descriptor":
                optional_text(
                    row.get(
                        "Descriptor"
                    )
                ),

            "commodity_unit":
                optional_text(
                    row.get(
                        "Commodity Unit"
                    )
                ),

            "commodity_unit_classification":
                optional_text(
                    row.get(
                        "Commodity Unit Classification"
                    )
                ),

            "year":
                safe_int(
                    row.get(
                        "Time Period"
                    )
                ),

            "timeframe":
                optional_text(
                    row.get(
                        "Timeframe"
                    )
                ),

            "data_type":
                optional_text(
                    row.get(
                        "Data Type"
                    )
                ),

            "value":
                safe_number(
                    row.get(
                        "Value"
                    )
                ),

            "unit":
                optional_text(
                    row.get(
                        "Unit"
                    )
                ),

            "value_notes":
                optional_text(
                    row.get(
                        "Value Notes"
                    )
                ),

            "other_notes":
                optional_text(
                    row.get(
                        "Other Notes"
                    )
                ),

            "source_1":
                optional_text(
                    row.get(
                        "Source 1"
                    )
                ),

            "source_2":
                optional_text(
                    row.get(
                        "Source 2"
                    )
                ),

            "currentness_date":
                optional_text(
                    row.get(
                        "Currentness Date"
                    )
                ),
        }


        records.append(
            record
        )


    return records


# =========================================================
# FACILITY PRODUCTS
# =========================================================

def extract_equity_owners(
    row: pd.Series,
) -> list[dict]:
    """
    Extract up to eight USGS equity-owner fields.
    """

    owners: list[
        dict
    ] = []


    for index in range(
        1,
        9,
    ):

        owner = optional_text(
            row.get(
                f"Equity Owner {index}"
            )
        )

        share = safe_number(
            row.get(
                f"Share of Equity Owner {index}"
            )
        )


        if not owner:

            continue


        owners.append(
            {
                "name":
                    owner,

                "share_percent":
                    share,
            }
        )


    return owners


def build_facility_product_records(
    path: Path,
) -> list[dict]:
    """
    Normalize one record per USGS facility-product row.
    """

    if not path.exists():

        raise FileNotFoundError(
            "USGS facilities CSV not found:\n"
            f"{path}"
        )


    dataframe = pd.read_csv(
        path,
        low_memory=False,
    )


    dataframe = filter_zambia(
        dataframe
    )


    records: list[
        dict
    ] = []


    for _, row in (
        dataframe.iterrows()
    ):

        capacity = safe_number(
            row.get(
                "Annual Production Capacity"
            )
        )


        record = {
            "dataset_id":
                DATASET_ID,

            "dataset_title":
                DATASET_TITLE,

            "agency":
                AGENCY,

            "record_type":
                "facility_product",

            "global_entry":
                optional_text(
                    row.get(
                        "Global Entry"
                    )
                ),

            "usgs_facility_id":
                optional_text(
                    row.get(
                        "USGS Facility ID"
                    )
                ),

            "publication_year":
                safe_int(
                    row.get(
                        "Publication Year"
                    )
                ),

            "currentness_date":
                optional_text(
                    row.get(
                        "Currentness Date"
                    )
                ),

            "country":
                optional_text(
                    row.get(
                        "Country (Short Form) or Locality"
                    )
                ),

            "facility_name":
                optional_text(
                    row.get(
                        "Facility Name"
                    )
                ),

            "feature_type":
                optional_text(
                    row.get(
                        "Feature Type"
                    )
                ),

            "commodity_group":
                optional_text(
                    row.get(
                        "Level 1 (Commodity Group)"
                    )
                ),

            "commodity":
                optional_text(
                    row.get(
                        "Level 2 (Commodity)"
                    )
                ),

            "type":
                optional_text(
                    row.get(
                        "Level 3 (Type)"
                    )
                ),

            "phase":
                optional_text(
                    row.get(
                        "Level 4 (Phase)"
                    )
                ),

            "form":
                optional_text(
                    row.get(
                        "Level 5 (Form)"
                    )
                ),

            "descriptor":
                optional_text(
                    row.get(
                        "Descriptor"
                    )
                ),

            "commodity_unit":
                optional_text(
                    row.get(
                        "Commodity Unit"
                    )
                ),

            "commodity_unit_classification":
                optional_text(
                    row.get(
                        "Commodity Unit Classification"
                    )
                ),

            "commodity_footnote":
                optional_text(
                    row.get(
                        "Commodity Footnote"
                    )
                ),

            "multiple_commodities":
                optional_text(
                    row.get(
                        "Multiple Commodities"
                    )
                ),

            "multiple_products":
                optional_text(
                    row.get(
                        "Multiple Products"
                    )
                ),

            "annual_production_capacity":
                capacity,

            "capacity_unit":
                (
                    optional_text(
                        row.get(
                            "Capacity Unit"
                        )
                    )
                    if capacity is not None
                    else None
                ),

            "capacity_code":
                optional_text(
                    row.get(
                        "Capacity Code"
                    )
                ),

            "shared_capacity_entries":
                split_shared_capacity(
                    row.get(
                        "Shared Capacity"
                    )
                ),

            "capacity_notes":
                optional_text(
                    row.get(
                        "Capacity Notes"
                    )
                ),

            "facility_status":
                optional_text(
                    row.get(
                        "Facility Status"
                    )
                ),

            "location_description":
                optional_text(
                    row.get(
                        "Location Description"
                    )
                ),

            "location_notes":
                optional_text(
                    row.get(
                        "Location Notes"
                    )
                ),

            "location_footnote":
                optional_text(
                    row.get(
                        "Location Footnote"
                    )
                ),

            "admin_division_type":
                optional_text(
                    row.get(
                        "First-Level Administrative Division Type"
                    )
                ),

            "province":
                optional_text(
                    row.get(
                        "First-Level Administrative Division Name"
                    )
                ),

            "major_operating_company":
                optional_text(
                    row.get(
                        "Major Operating Company"
                    )
                ),

            "equity_owners":
                extract_equity_owners(
                    row
                ),

            "company_footnote":
                optional_text(
                    row.get(
                        "Company Footnote"
                    )
                ),

            "source_1":
                optional_text(
                    row.get(
                        "Data Source 1"
                    )
                ),

            "source_2":
                optional_text(
                    row.get(
                        "Data Source 2"
                    )
                ),
        }


        records.append(
            record
        )


    return records


# =========================================================
# GROUPED FACILITIES
# =========================================================

def group_facilities(
    product_records: list[dict],
) -> list[dict]:
    """
    Collapse product rows into one physical facility profile.

    Product-level capacities remain inside `products`.
    Capacities are NEVER summed because the USGS table may
    explicitly share capacity across several product rows.
    """

    grouped: dict[
        str,
        list[dict],
    ] = {}


    for record in product_records:

        facility_id = (
            record.get(
                "usgs_facility_id"
            )
            or record.get(
                "global_entry"
            )
        )


        if not facility_id:

            continue


        grouped.setdefault(
            facility_id,
            [],
        ).append(
            record
        )


    facilities: list[
        dict
    ] = []


    for facility_id, rows in (
        grouped.items()
    ):

        first = rows[0]


        product_profiles: list[
            dict
        ] = []


        for row in rows:

            product_profiles.append(
                {
                    "global_entry":
                        row.get(
                            "global_entry"
                        ),

                    "commodity_group":
                        row.get(
                            "commodity_group"
                        ),

                    "commodity":
                        row.get(
                            "commodity"
                        ),

                    "type":
                        row.get(
                            "type"
                        ),

                    "phase":
                        row.get(
                            "phase"
                        ),

                    "form":
                        row.get(
                            "form"
                        ),

                    "descriptor":
                        row.get(
                            "descriptor"
                        ),

                    "commodity_unit":
                        row.get(
                            "commodity_unit"
                        ),

                    "commodity_unit_classification":
                        row.get(
                            "commodity_unit_classification"
                        ),

                    "annual_production_capacity":
                        row.get(
                            "annual_production_capacity"
                        ),

                    "capacity_unit":
                        row.get(
                            "capacity_unit"
                        ),

                    "capacity_code":
                        row.get(
                            "capacity_code"
                        ),

                    "shared_capacity_entries":
                        row.get(
                            "shared_capacity_entries",
                            [],
                        ),

                    "capacity_notes":
                        row.get(
                            "capacity_notes"
                        ),
                }
            )


        owners: list[
            dict
        ] = []

        owner_names: set[
            str
        ] = set()


        for row in rows:

            for owner in row.get(
                "equity_owners",
                [],
            ):

                name = clean_text(
                    owner.get(
                        "name"
                    )
                )

                if not name:

                    continue


                key = name.casefold()

                if key in owner_names:

                    continue


                owner_names.add(
                    key
                )

                owners.append(
                    owner
                )


        facility = {
            "dataset_id":
                DATASET_ID,

            "dataset_title":
                DATASET_TITLE,

            "agency":
                AGENCY,

            "record_type":
                "facility",

            "usgs_facility_id":
                facility_id,

            "facility_name":
                first.get(
                    "facility_name"
                ),

            "country":
                COUNTRY,

            "feature_types":
                unique_nonempty(
                    [
                        row.get(
                            "feature_type"
                        )
                        for row in rows
                    ]
                ),

            "facility_statuses":
                unique_nonempty(
                    [
                        row.get(
                            "facility_status"
                        )
                        for row in rows
                    ]
                ),

            "location_description":
                first.get(
                    "location_description"
                ),

            "location_notes":
                first.get(
                    "location_notes"
                ),

            "admin_division_type":
                first.get(
                    "admin_division_type"
                ),

            "province":
                first.get(
                    "province"
                ),

            "major_operating_companies":
                unique_nonempty(
                    [
                        row.get(
                            "major_operating_company"
                        )
                        for row in rows
                    ]
                ),

            "equity_owners":
                owners,

            "commodities":
                unique_nonempty(
                    [
                        row.get(
                            "commodity"
                        )
                        for row in rows
                    ]
                ),

            "commodity_groups":
                unique_nonempty(
                    [
                        row.get(
                            "commodity_group"
                        )
                        for row in rows
                    ]
                ),

            "product_count":
                len(
                    rows
                ),

            "products":
                product_profiles,

            "sources":
                unique_nonempty(
                    [
                        value
                        for row in rows
                        for value in [
                            row.get(
                                "source_1"
                            ),
                            row.get(
                                "source_2"
                            ),
                        ]
                    ]
                ),

            "publication_year":
                first.get(
                    "publication_year"
                ),

            "currentness_date":
                first.get(
                    "currentness_date"
                ),
        }


        facilities.append(
            facility
        )


    return sorted(
        facilities,
        key=lambda record: (
            clean_text(
                record.get(
                    "facility_name"
                )
            ).casefold(),
            clean_text(
                record.get(
                    "usgs_facility_id"
                )
            ).casefold(),
        ),
    )


# =========================================================
# OUTPUT
# =========================================================

def write_jsonl(
    records: list[dict],
    path: Path,
) -> None:

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )


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


def build_summary(
    production_records: list[dict],
    product_records: list[dict],
    facilities: list[dict],
) -> dict:

    production_commodities = sorted(
        {
            record[
                "commodity"
            ]
            for record in production_records
            if record.get(
                "commodity"
            )
        },
        key=str.casefold,
    )


    facility_commodities = sorted(
        {
            commodity
            for facility in facilities
            for commodity in facility.get(
                "commodities",
                [],
            )
        },
        key=str.casefold,
    )


    active_products = sum(
        clean_text(
            record.get(
                "facility_status"
            )
        ).casefold()
        == "assumed active"
        for record in product_records
    )


    inactive_products = sum(
        clean_text(
            record.get(
                "facility_status"
            )
        ).casefold()
        == "inactive"
        for record in product_records
    )


    missing_capacity_products = sum(
        record.get(
            "annual_production_capacity"
        )
        is None
        for record in product_records
    )


    return {
        "dataset_id":
            DATASET_ID,

        "dataset_title":
            DATASET_TITLE,

        "country":
            COUNTRY,

        "production_record_count":
            len(
                production_records
            ),

        "production_commodity_count":
            len(
                production_commodities
            ),

        "production_commodities":
            production_commodities,

        "facility_product_record_count":
            len(
                product_records
            ),

        "facility_count":
            len(
                facilities
            ),

        "facility_commodity_count":
            len(
                facility_commodities
            ),

        "facility_commodities":
            facility_commodities,

        "assumed_active_product_records":
            active_products,

        "inactive_product_records":
            inactive_products,

        "facility_products_without_numeric_capacity":
            missing_capacity_products,
    }


# =========================================================
# INGESTION
# =========================================================

def ingest_usgs_zambia(
    production_path: Path = DEFAULT_PRODUCTION_FILE,
    facilities_path: Path = DEFAULT_FACILITIES_FILE,
    production_output: Path = DEFAULT_PRODUCTION_OUTPUT,
    facility_products_output: Path = (
        DEFAULT_FACILITY_PRODUCTS_OUTPUT
    ),
    facilities_output: Path = DEFAULT_FACILITIES_OUTPUT,
    summary_output: Path = DEFAULT_SUMMARY_OUTPUT,
) -> None:

    print(
        "Reading USGS Zambia production data..."
    )

    production_records = (
        build_production_records(
            production_path
        )
    )


    print(
        "Production records:",
        len(
            production_records
        ),
    )


    print(
        "Reading USGS Zambia facility data..."
    )

    product_records = (
        build_facility_product_records(
            facilities_path
        )
    )


    print(
        "Facility-product records:",
        len(
            product_records
        ),
    )


    facilities = group_facilities(
        product_records
    )


    print(
        "Unique facilities:",
        len(
            facilities
        ),
    )


    write_jsonl(
        production_records,
        production_output,
    )


    write_jsonl(
        product_records,
        facility_products_output,
    )


    write_jsonl(
        facilities,
        facilities_output,
    )


    summary = build_summary(
        production_records,
        product_records,
        facilities,
    )


    summary_output.write_text(
        json.dumps(
            summary,
            indent=4,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )


    print()
    print(
        "=" * 72
    )

    print(
        "USGS ZAMBIA STRUCTURED INGESTION COMPLETE"
    )

    print(
        "=" * 72
    )

    print(
        "Production records:",
        summary[
            "production_record_count"
        ],
    )

    print(
        "Production commodities:",
        summary[
            "production_commodity_count"
        ],
    )

    print(
        "Facility-product records:",
        summary[
            "facility_product_record_count"
        ],
    )

    print(
        "Unique facilities:",
        summary[
            "facility_count"
        ],
    )

    print(
        "Facility commodities:",
        summary[
            "facility_commodity_count"
        ],
    )

    print(
        "Assumed-active product rows:",
        summary[
            "assumed_active_product_records"
        ],
    )

    print(
        "Inactive product rows:",
        summary[
            "inactive_product_records"
        ],
    )

    print(
        "Missing numeric capacities:",
        summary[
            "facility_products_without_numeric_capacity"
        ],
    )

    print()
    print(
        "Production output:",
        production_output,
    )

    print(
        "Facility products output:",
        facility_products_output,
    )

    print(
        "Grouped facilities output:",
        facilities_output,
    )

    print(
        "Summary:",
        summary_output,
    )


# =========================================================
# CLI
# =========================================================

def main() -> None:

    parser = argparse.ArgumentParser(
        description=(
            "Normalize USGS Minerals Yearbook 2024 "
            "Zambia production and facility data."
        )
    )


    parser.add_argument(
        "--production",
        type=Path,
        default=DEFAULT_PRODUCTION_FILE,
    )


    parser.add_argument(
        "--facilities",
        type=Path,
        default=DEFAULT_FACILITIES_FILE,
    )


    args = parser.parse_args()


    ingest_usgs_zambia(
        production_path=args.production,
        facilities_path=args.facilities,
    )


if __name__ == "__main__":
    main()