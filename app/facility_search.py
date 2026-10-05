from __future__ import annotations

import argparse
import json
import re

from pathlib import Path


# =========================================================
# PATHS
# =========================================================

PROJECT_ROOT = Path(
    __file__
).resolve().parents[1]


PROCESSED_DATA_DIR = (
    PROJECT_ROOT
    / "data"
    / "processed"
)


DEFAULT_FACILITIES_FILE = (
    PROCESSED_DATA_DIR
    / "usgs_2024_zambia_facilities.jsonl"
)


# =========================================================
# CONFIGURATION
# =========================================================

DEFAULT_TOP_K = 10


GENERIC_FACILITY_WORDS = {
    "mine",
    "mines",
    "plant",
    "refinery",
    "smelter",
    "facility",
    "facilities",
    "operation",
    "operations",
}


STATUS_ACTIVE_TERMS = (
    "active",
    "currently active",
    "operational",
    "currently operational",
)


STATUS_INACTIVE_TERMS = (
    "inactive",
    "closed",
    "not operating",
)


FEATURE_TERMS = {
    "mine": "mine",
    "mines": "mine",
    "refinery": "refinery",
    "refineries": "refinery",
    "smelter": "smelter",
    "smelters": "smelter",
    "processing plant": "processing_plant",
    "processing plants": "processing_plant",
}


COMMODITY_ALIASES = {
    "cement": "Cement",
    "cobalt": "Cobalt",
    "copper": "Copper",
    "fluorspar": "Fluorspar",
    "gemstone": "Gemstones",
    "gemstones": "Gemstones",
    "gold": "Gold",
    "lime": "Lime",
    "manganese": "Manganese",
    "nickel": "Nickel",
    "steel": "Raw steel",
    "raw steel": "Raw steel",
    "stone": "Stone, size and shape unspecified",
    "sulfur": "Sulfur",
    "sulphur": "Sulfur",
}


# =========================================================
# LOADING
# =========================================================

def load_facilities(
    path: Path = DEFAULT_FACILITIES_FILE,
) -> list[dict]:
    """
    Load grouped USGS Zambia facility profiles.
    """

    if not path.exists():

        raise FileNotFoundError(
            "Structured USGS Zambia facilities file "
            f"not found:\n{path}\n\n"
            "Run:\n"
            "python -m ingestion.ingest_usgs_zambia"
        )


    facilities: list[
        dict
    ] = []


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


            facilities.append(
                record
            )


    if not facilities:

        raise ValueError(
            "USGS facilities file contains "
            "no records."
        )


    return facilities


# =========================================================
# NORMALIZATION
# =========================================================

def normalize_text(
    value: str | None,
) -> str:

    return " ".join(
        str(
            value
            or ""
        )
        .casefold()
        .split()
    )


def text_tokens(
    value: str | None,
) -> set[str]:
    """
    Alphanumeric search tokens.
    """

    return set(
        re.findall(
            r"[a-z0-9]+",
            normalize_text(
                value
            ),
        )
    )


def contains_phrase(
    text: str,
    phrase: str,
) -> bool:

    return (
        normalize_text(
            phrase
        )
        in normalize_text(
            text
        )
    )


# =========================================================
# QUERY INFERENCE
# =========================================================

def infer_commodity(
    query: str,
) -> str | None:

    normalized = normalize_text(
        query
    )


    aliases = sorted(
        COMMODITY_ALIASES.items(),
        key=lambda item:
            len(item[0]),
        reverse=True,
    )


    for alias, commodity in aliases:

        pattern = (
            r"\b"
            + re.escape(
                alias
            )
            + r"\b"
        )


        if re.search(
            pattern,
            normalized,
        ):

            return commodity


    return None


def infer_province(
    query: str,
    facilities: list[dict],
) -> str | None:

    normalized = normalize_text(
        query
    )


    provinces = sorted(
        {
            facility.get(
                "province"
            )
            for facility in facilities
            if facility.get(
                "province"
            )
        },
        key=len,
        reverse=True,
    )


    for province in provinces:

        if (
            normalize_text(
                province
            )
            in normalized
        ):

            return province


    return None


def infer_status(
    query: str,
) -> str | None:

    normalized = normalize_text(
        query
    )


    if any(
        term
        in normalized
        for term
        in STATUS_INACTIVE_TERMS
    ):

        return "Inactive"


    if any(
        term
        in normalized
        for term
        in STATUS_ACTIVE_TERMS
    ):

        return "Assumed active"


    return None


def infer_feature_filter(
    query: str,
) -> str | None:

    normalized = normalize_text(
        query
    )


    for phrase, feature in sorted(
        FEATURE_TERMS.items(),
        key=lambda item:
            len(item[0]),
        reverse=True,
    ):

        if contains_phrase(
            normalized,
            phrase,
        ):

            return feature


    return None


# =========================================================
# FACILITY HELPERS
# =========================================================
def facility_status_summary(
    facility: dict,
) -> str | None:
    """
    Return one facility-level status.

    Product rows can occasionally disagree. In that case,
    preserve the ambiguity instead of treating the facility
    as both active and inactive.
    """

    statuses = {
        normalize_text(
            status
        )
        for status in facility.get(
            "facility_statuses",
            [],
        )
        if normalize_text(
            status
        )
    }


    if not statuses:

        return None


    if statuses == {
        "assumed active"
    }:

        return "Assumed active"


    if statuses == {
        "inactive"
    }:

        return "Inactive"


    return "Mixed"

def facility_is_active(
    facility: dict,
) -> bool:

    return (
        facility_status_summary(
            facility
        )
        == "Assumed active"
    )


def matches_feature(
    facility: dict,
    feature: str | None,
) -> bool:

    if feature is None:
        return True


    name = normalize_text(
        facility.get(
            "facility_name"
        )
    )


    feature_types = [
        normalize_text(
            value
        )
        for value in facility.get(
            "feature_types",
            [],
        )
    ]


    products = facility.get(
        "products",
        [],
    )


    product_types = [
        normalize_text(
            product.get(
                "type"
            )
        )
        for product in products
    ]


    if feature == "mine":

        return (
            "mine" in name
            or any(
                "mines and quarries"
                in value
                for value in feature_types
            )
            and any(
                value == "mine"
                for value in product_types
            )
        )


    if feature == "refinery":

        return (
            "refinery" in name
            or any(
                value == "refinery"
                for value in product_types
            )
        )


    if feature == "smelter":

        return (
            "smelter" in name
            or any(
                value == "smelter"
                for value in product_types
            )
        )


    if feature == "processing_plant":

        return any(
            "mineral processing plant"
            in value
            for value in feature_types
        )


    return True


def matching_products(
    facility: dict,
    commodity: str | None = None,
) -> list[dict]:
    """
    Return product rows relevant to a commodity filter.
    """

    products = facility.get(
        "products",
        [],
    )


    if commodity is None:

        return list(
            products
        )


    target = normalize_text(
        commodity
    )


    return [
        product
        for product in products
        if (
            normalize_text(
                product.get(
                    "commodity"
                )
            )
            == target
        )
    ]


# =========================================================
# CAPACITY DEDUPLICATION
# =========================================================

def distinct_capacity_records(
    facility: dict,
    commodity: str | None = None,
) -> list[dict]:
    """
    Return capacity records without double-counting USGS
    shared-capacity product rows.

    For example, Kansanshi's mixed, oxide and sulfide
    copper entries share the same 180,000 t capacity and
    therefore become one capacity group.
    """

    products = matching_products(
        facility=facility,
        commodity=commodity,
    )


    capacity_records: list[
        dict
    ] = []


    seen: set[
        tuple
    ] = set()


    for product in products:

        capacity = product.get(
            "annual_production_capacity"
        )


        if capacity is None:
            continue


        shared_entries = tuple(
            sorted(
                product.get(
                    "shared_capacity_entries",
                    [],
                )
            )
        )


        if len(
            shared_entries
        ) > 1:

            group_key = (
                "shared",
                shared_entries,
            )

        else:

            group_key = (
                "entry",
                product.get(
                    "global_entry"
                ),
            )


        if group_key in seen:
            continue


        seen.add(
            group_key
        )


        capacity_records.append(
            {
                "commodity":
                    product.get(
                        "commodity"
                    ),

                "type":
                    product.get(
                        "type"
                    ),

                "phase":
                    product.get(
                        "phase"
                    ),

                "form":
                    product.get(
                        "form"
                    ),

                "descriptor":
                    product.get(
                        "descriptor"
                    ),

                "capacity":
                    capacity,

                "capacity_unit":
                    product.get(
                        "capacity_unit"
                    ),

                "capacity_code":
                    product.get(
                        "capacity_code"
                    ),

                "shared_capacity_entries":
                    list(
                        shared_entries
                    ),

                "capacity_notes":
                    product.get(
                        "capacity_notes"
                    ),
            }
        )


    return capacity_records


# =========================================================
# SCORING
# =========================================================

def facility_score(
    query: str,
    facility: dict,
) -> float:
    """
    Score one grouped facility against free text.
    """

    normalized_query = (
        normalize_text(
            query
        )
    )

    query_tokens = (
        text_tokens(
            query
        )
    )


    name = normalize_text(
        facility.get(
            "facility_name"
        )
    )

    name_tokens = (
        text_tokens(
            name
        )
    )


    meaningful_name_tokens = (
        name_tokens
        - GENERIC_FACILITY_WORDS
    )


    score = 0.0


    # Exact or near-exact facility-name references.
    if name:

        if name in normalized_query:

            score += 100.0


        if (
            meaningful_name_tokens
            and meaningful_name_tokens.issubset(
                query_tokens
            )
        ):

            score += 70.0


        overlap = (
            meaningful_name_tokens
            & query_tokens
        )


        score += (
            len(
                overlap
            )
            * 15.0
        )


    # Facility ID.
    facility_id = normalize_text(
        facility.get(
            "usgs_facility_id"
        )
    )


    if (
        facility_id
        and facility_id
        in normalized_query
    ):

        score += 120.0


    # Operator.
    for operator in facility.get(
        "major_operating_companies",
        [],
    ):

        operator_normalized = (
            normalize_text(
                operator
            )
        )

        if (
            operator_normalized
            and operator_normalized
            in normalized_query
        ):

            score += 45.0


    # Equity owners.
    for owner in facility.get(
        "equity_owners",
        [],
    ):

        owner_name = normalize_text(
            owner.get(
                "name"
            )
        )

        if (
            owner_name
            and owner_name
            in normalized_query
        ):

            score += 35.0


    return score


# =========================================================
# SEARCH
# =========================================================

def search_facilities(
    query: str,
    facilities: list[dict] | None = None,
    top_k: int = DEFAULT_TOP_K,
) -> dict:
    """
    Search structured Zambia mineral facilities.
    """

    if not query.strip():

        raise ValueError(
            "Query must not be empty."
        )


    if top_k <= 0:

        raise ValueError(
            "top_k must be greater than zero."
        )


    if facilities is None:

        facilities = (
            load_facilities()
        )


    commodity = (
        infer_commodity(
            query
        )
    )

    province = (
        infer_province(
            query,
            facilities,
        )
    )

    status = (
        infer_status(
            query
        )
    )

    feature = (
        infer_feature_filter(
            query
        )
    )


    candidates: list[
        dict
    ] = []


    for facility in facilities:

        # ---------------------------------------------
        # Commodity
        # ---------------------------------------------

        if commodity is not None:

            facility_commodities = {
                normalize_text(
                    value
                )
                for value
                in facility.get(
                    "commodities",
                    [],
                )
            }


            if (
                normalize_text(
                    commodity
                )
                not in facility_commodities
            ):

                continue


        # ---------------------------------------------
        # Province
        # ---------------------------------------------

        if province is not None:

            if (
                normalize_text(
                    facility.get(
                        "province"
                    )
                )
                != normalize_text(
                    province
                )
            ):

                continue


        # ---------------------------------------------
        # Status
        # ---------------------------------------------
        if status is not None:

            facility_status = (
                facility_status_summary(
                    facility
                )
            )


            if (
                normalize_text(
                    facility_status
                )
                != normalize_text(
                    status
                )
            ):

                continue



        # ---------------------------------------------
        # Feature
        # ---------------------------------------------

        if not matches_feature(
            facility,
            feature,
        ):

            continue


        score = facility_score(
            query=query,
            facility=facility,
        )


        # Structured-filter matches still deserve a base
        # score even when no facility name is mentioned.
        if commodity is not None:
            score += 20.0

        if province is not None:
            score += 15.0

        if status is not None:
            score += 10.0

        if feature is not None:
            score += 10.0


        candidates.append(
            {
                "facility":
                    facility,

                "score":
                    score,

                "matched_products":
                    matching_products(
                        facility=facility,
                        commodity=commodity,
                    ),

                "capacity_records":
                    distinct_capacity_records(
                        facility=facility,
                        commodity=commodity,
                    ),
            }
        )


    candidates.sort(
        key=lambda result: (
            result[
                "score"
            ],
            normalize_text(
                result[
                    "facility"
                ].get(
                    "facility_name"
                )
            ),
        ),
        reverse=True,
    )


    return {
        "results":
            candidates[
                :top_k
            ],

        "filters": {
            "commodity":
                commodity,

            "province":
                province,

            "status":
                status,

            "feature":
                feature,
        },

        "facility_count":
            len(
                facilities
            ),

        "match_count":
            len(
                candidates
            ),
    }


# =========================================================
# CLI
# =========================================================

def main() -> None:

    parser = argparse.ArgumentParser(
        description=(
            "Search structured USGS Zambia "
            "mineral facilities."
        )
    )


    parser.add_argument(
        "query",
        help=(
            "Natural-language facility query."
        ),
    )


    parser.add_argument(
        "--top-k",
        type=int,
        default=DEFAULT_TOP_K,
    )


    args = parser.parse_args()


    result = search_facilities(
        query=args.query,
        top_k=args.top_k,
    )


    print(
        "Filters:",
        result[
            "filters"
        ],
    )

    print(
        "Matches:",
        result[
            "match_count"
        ],
    )

    print()


    for index, item in enumerate(
        result[
            "results"
        ],
        start=1,
    ):

        facility = item[
            "facility"
        ]


        print(
            f"{index}. "
            f"{facility.get('facility_name')}"
        )

        print(
            "   ID:",
            facility.get(
                "usgs_facility_id"
            ),
        )

        print(
            "   Province:",
            facility.get(
                "province"
            ),
        )

        status_summary = (
            facility_status_summary(
                facility
            )
        )


        print(
            "   Status:",
            status_summary
            or "Unknown",
        )

        print(
            "   Operator:",
            ", ".join(
                facility.get(
                    "major_operating_companies",
                    [],
                )
            ),
        )

        print(
            "   Commodities:",
            ", ".join(
                facility.get(
                    "commodities",
                    [],
                )
            ),
        )

        print(
            "   Score:",
            item[
                "score"
            ],
        )


        capacities = item[
            "capacity_records"
        ]


        if capacities:

            print(
                "   Capacities:"
            )

            for capacity in capacities:

                print(
                    "      -",
                    capacity.get(
                        "capacity"
                    ),
                    capacity.get(
                        "capacity_unit"
                    ),
                    "|",
                    capacity.get(
                        "form"
                    )
                    or capacity.get(
                        "descriptor"
                    )
                    or capacity.get(
                        "type"
                    ),
                )


        print()


if __name__ == "__main__":
    main()