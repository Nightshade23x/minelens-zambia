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


DEFAULT_STATISTICS_FILE = (
    PROCESSED_DATA_DIR
    / "world_mining_data_2026.statistics.jsonl"
)


# =========================================================
# COMMODITY ALIASES
# =========================================================

COMMODITY_ALIASES = {
    "cobalt": "Cobalt",
    "co": "Cobalt",

    "copper": "Copper",
    "cu": "Copper",

    "gold": "Gold",
    "au": "Gold",

    "manganese": "Manganese",
    "mn": "Manganese",

    "nickel": "Nickel",
    "ni": "Nickel",

    "beryllium":
        "Beryllium (conc.)",

    "beryllium concentrate":
        "Beryllium (conc.)",

    "sulfur":
        "Sulfur (elementar & industrial)",

    "sulphur":
        "Sulfur (elementar & industrial)",

    "steam coal":
        "Steam Coal",

    "coal":
        "Steam Coal",
}


# =========================================================
# LOADING
# =========================================================

def load_mining_statistics(
    path: Path = DEFAULT_STATISTICS_FILE,
) -> list[dict]:
    """
    Load structured World Mining Data records.
    """

    if not path.exists():

        raise FileNotFoundError(
            "Structured mining statistics file "
            f"not found:\n{path}\n\n"
            "Run:\n"
            "python -m ingestion.ingest_wmd_statistics"
        )


    records: list[
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


            records.append(
                record
            )


    if not records:

        raise ValueError(
            "Mining statistics file "
            "contains no records."
        )


    return records


# =========================================================
# NORMALIZATION
# =========================================================

def normalize_text(
    value: str,
) -> str:

    return " ".join(
        value.casefold().split()
    )


def normalize_commodity(
    value: str,
) -> str:

    normalized = normalize_text(
        value
    )


    if normalized in (
        COMMODITY_ALIASES
    ):

        return (
            COMMODITY_ALIASES[
                normalized
            ]
        )


    return value.strip()


# =========================================================
# FILTERING
# =========================================================

def find_statistics(
    records: list[dict],
    country: str | None = None,
    commodity: str | None = None,
    year: int | None = None,
) -> list[dict]:
    """
    Filter structured statistics.
    """

    country_normalized = (
        normalize_text(
            country
        )
        if country
        else None
    )


    commodity_normalized = (
        normalize_text(
            normalize_commodity(
                commodity
            )
        )
        if commodity
        else None
    )


    matches: list[
        dict
    ] = []


    for record in records:

        if country_normalized:

            if (
                normalize_text(
                    record[
                        "country"
                    ]
                )
                != country_normalized
            ):

                continue


        if commodity_normalized:

            if (
                normalize_text(
                    record[
                        "commodity"
                    ]
                )
                != commodity_normalized
            ):

                continue


        if year is not None:

            if (
                record[
                    "year"
                ]
                != year
            ):

                continue


        matches.append(
            record
        )


    return matches


# =========================================================
# COMMON QUERIES
# =========================================================

def production_record(
    records: list[dict],
    country: str,
    commodity: str,
    year: int,
) -> dict | None:
    """
    Return one country/commodity/year record.
    """

    matches = find_statistics(
        records=records,
        country=country,
        commodity=commodity,
        year=year,
    )


    if not matches:
        return None


    return matches[0]


def production_series(
    records: list[dict],
    country: str,
    commodity: str,
) -> list[dict]:
    """
    Return a chronological production series.
    """

    matches = find_statistics(
        records=records,
        country=country,
        commodity=commodity,
    )


    return sorted(
        matches,
        key=lambda record:
            record[
                "year"
            ],
    )


def country_commodities(
    records: list[dict],
    country: str,
    year: int = 2024,
) -> list[dict]:
    """
    Return all commodities recorded for a country/year.
    """

    matches = find_statistics(
        records=records,
        country=country,
        year=year,
    )


    return sorted(
        matches,
        key=lambda record:
            record[
                "commodity"
            ].casefold(),
    )


def commodity_ranking(
    records: list[dict],
    commodity: str,
    year: int = 2024,
) -> list[dict]:
    """
    Return countries ranked by production.

    For 2024, official WMD rank values are used when
    available. Other years are ranked deterministically
    from production values.
    """

    matches = find_statistics(
        records=records,
        commodity=commodity,
        year=year,
    )


    if year == 2024:

        ranked = [
            record
            for record in matches
            if record.get(
                "rank_2024"
            )
            is not None
        ]


        if ranked:

            return sorted(
                ranked,
                key=lambda record:
                    record[
                        "rank_2024"
                    ],
            )


    return sorted(
        matches,
        key=lambda record:
            record[
                "production"
            ],
        reverse=True,
    )


# =========================================================
# FORMATTING
# =========================================================

def format_number(
    value: float | int | None,
) -> str:

    if value is None:
        return "—"


    numeric = float(
        value
    )


    if numeric.is_integer():

        return f"{int(numeric):,}"


    return f"{numeric:,.2f}"


def format_production(
    record: dict,
) -> str:

    return (
        f"{format_number(record.get('production'))} "
        f"{record.get('unit') or ''}"
    ).strip()

# =========================================================
# NATURAL-LANGUAGE QUERY INFERENCE
# =========================================================

import re


COUNTRY_ALIASES = {
    "zambia": "Zambia",

    "drc": "Congo, D.R.",
    "dr congo": "Congo, D.R.",
    "congo dr": "Congo, D.R.",
    "congo d r": "Congo, D.R.",
    "democratic republic of congo": (
        "Congo, D.R."
    ),
}


STATISTICS_INTENT_TERMS = (
    "production",
    "produced",
    "produce",
    "output",
    "world share",
    "global share",
    "share of world",
    "world production",
    "global production",
    "world rank",
    "global rank",
    "rank globally",
    "ranked globally",
    "ranking",
    "production trend",
)


TREND_TERMS = (
    "trend",
    "change",
    "changed",
    "increase",
    "increased",
    "decrease",
    "decreased",
    "grew",
    "growth",
    "fell",
    "declined",
    "over time",
    "since",
)


SHARE_TERMS = (
    "world share",
    "global share",
    "share of world",
    "share of global",
)


RANK_TERMS = (
    "world rank",
    "global rank",
    "rank globally",
    "ranked globally",
    "ranking",
    "what rank",
    "where did",
)


def infer_statistics_years(
    query: str,
) -> list[int]:
    """
    Extract supported WMD years from a natural-language
    question.
    """

    years = {
        int(match)
        for match in re.findall(
            r"\b20(?:20|21|22|23|24)\b",
            query,
        )
    }

    return sorted(
        years
    )


def infer_statistics_commodity(
    query: str,
    records: list[dict],
) -> str | None:
    """
    Infer one WMD commodity from the user's query.
    """

    normalized_query = (
        normalize_text(
            query
        )
    )


    # Prefer known aliases first.
    alias_matches = sorted(
        COMMODITY_ALIASES.items(),
        key=lambda item:
            len(item[0]),
        reverse=True,
    )


    for alias, commodity in (
        alias_matches
    ):

        pattern = (
            r"\b"
            + re.escape(
                normalize_text(
                    alias
                )
            )
            + r"\b"
        )

        if re.search(
            pattern,
            normalized_query,
        ):

            return commodity


    # Fall back to official WMD commodity names.
    commodities = sorted(
        {
            record[
                "commodity"
            ]
            for record in records
        },
        key=len,
        reverse=True,
    )


    for commodity in commodities:

        candidate = (
            normalize_text(
                commodity
            )
        )

        if candidate in normalized_query:

            return commodity


    return None


def infer_statistics_countries(
    query: str,
    records: list[dict],
) -> list[str]:
    """
    Infer countries mentioned in a statistics query.

    Supports both official WMD country names and a small
    alias layer for common alternatives such as DRC.
    """

    normalized_query = (
        normalize_text(
            query
        )
    )


    matches: list[str] = []


    # Common aliases first.
    alias_items = sorted(
        COUNTRY_ALIASES.items(),
        key=lambda item:
            len(item[0]),
        reverse=True,
    )


    for alias, country in (
        alias_items
    ):

        pattern = (
            r"\b"
            + re.escape(
                normalize_text(
                    alias
                )
            )
            + r"\b"
        )

        if re.search(
            pattern,
            normalized_query,
        ):

            if country not in matches:

                matches.append(
                    country
                )


    # Official country names from the dataset.
    countries = sorted(
        {
            record[
                "country"
            ]
            for record in records
        },
        key=len,
        reverse=True,
    )


    for country in countries:

        normalized_country = (
            normalize_text(
                country
            )
        )

        if not normalized_country:
            continue


        pattern = (
            r"\b"
            + re.escape(
                normalized_country
            )
            + r"\b"
        )


        if re.search(
            pattern,
            normalized_query,
        ):

            if country not in matches:

                matches.append(
                    country
                )


    return matches


def infer_statistics_intent(
    query: str,
) -> str:
    """
    Infer the kind of structured statistics answer needed.
    """

    normalized = (
        normalize_text(
            query
        )
    )


    if any(
        term in normalized
        for term in SHARE_TERMS
    ):

        return "world_share"


    if any(
        term in normalized
        for term in RANK_TERMS
    ):

        return "world_rank"


    if any(
        term in normalized
        for term in TREND_TERMS
    ):

        return "trend"


    return "production"


def has_statistics_intent(
    query: str,
    records: list[dict] | None = None,
) -> bool:
    """
    Decide whether a question is suitable for the structured
    World Mining Data engine.

    A statistics term alone is not enough: the query must
    also identify a commodity.
    """

    normalized = (
        normalize_text(
            query
        )
    )


    if not any(
        term in normalized
        for term in STATISTICS_INTENT_TERMS
    ):

        return False


    if records is None:

        records = (
            load_mining_statistics()
        )


    commodity = (
        infer_statistics_commodity(
            query=query,
            records=records,
        )
    )


    return (
        commodity
        is not None
    )


# =========================================================
# STRUCTURED QUERY
# =========================================================

def query_mining_statistics(
    query: str,
    records: list[dict] | None = None,
) -> dict:
    """
    Interpret and execute a natural-language mining
    statistics query.
    """

    if records is None:

        records = (
            load_mining_statistics()
        )


    commodity = (
        infer_statistics_commodity(
            query=query,
            records=records,
        )
    )


    countries = (
        infer_statistics_countries(
            query=query,
            records=records,
        )
    )


    years = (
        infer_statistics_years(
            query
        )
    )


    intent = (
        infer_statistics_intent(
            query
        )
    )


    if commodity is None:

        return {
            "intent":
                intent,

            "commodity":
                None,

            "countries":
                countries,

            "years":
                years,

            "results":
                [],

            "error":
                "No supported commodity was detected.",
        }


    # -----------------------------------------------------
    # Trend query
    # -----------------------------------------------------

    if intent == "trend":

        country = (
            countries[0]
            if countries
            else "Zambia"
        )


        series = (
            production_series(
                records=records,
                country=country,
                commodity=commodity,
            )
        )


        if years:

            first_year = min(
                years
            )

            last_year = max(
                years
            )


            series = [
                record
                for record in series
                if (
                    first_year
                    <= record[
                        "year"
                    ]
                    <= last_year
                )
            ]


        return {
            "intent":
                intent,

            "commodity":
                commodity,

            "countries":
                [
                    country
                ],

            "years":
                years,

            "results":
                series,

            "error":
                None,
        }


    # -----------------------------------------------------
    # Global ranking query
    # -----------------------------------------------------

    if (
        intent == "world_rank"
        and not countries
    ):

        year = (
            years[0]
            if years
            else 2024
        )


        ranking = (
            commodity_ranking(
                records=records,
                commodity=commodity,
                year=year,
            )
        )


        return {
            "intent":
                intent,

            "commodity":
                commodity,

            "countries":
                [],

            "years":
                [
                    year
                ],

            "results":
                ranking,

            "error":
                None,
        }


    # -----------------------------------------------------
    # Country production/share/rank query
    # -----------------------------------------------------

    if not countries:

        countries = [
            "Zambia"
        ]


    year = (
        years[0]
        if years
        else 2024
    )


    results: list[
        dict
    ] = []


    for country in countries:

        record = production_record(
            records=records,
            country=country,
            commodity=commodity,
            year=year,
        )


        if record is not None:

            results.append(
                record
            )


    return {
        "intent":
            intent,

        "commodity":
            commodity,

        "countries":
            countries,

        "years":
            [
                year
            ],

        "results":
            results,

        "error":
            None,
    }
# =========================================================
# DETERMINISTIC ANSWERS
# =========================================================

def human_unit(
    unit: str | None,
) -> str:
    """
    Convert WMD unit labels into readable display units.
    """

    mapping = {
        "metr. t": "metric tonnes",
        "kg": "kg",
        "mio m3": "million m³",
    }

    normalized = (
        str(unit or "")
        .strip()
        .casefold()
    )

    return mapping.get(
        normalized,
        str(unit or "").strip(),
    )


def ordinal(
    value: int | None,
) -> str:
    """
    Convert an integer into an ordinal label.
    """

    if value is None:
        return "—"

    if 10 <= value % 100 <= 20:
        suffix = "th"

    else:
        suffix = {
            1: "st",
            2: "nd",
            3: "rd",
        }.get(
            value % 10,
            "th",
        )

    return (
        f"{value}{suffix}"
    )


def statistics_source(
    records: list[dict],
) -> dict | None:
    """
    Build one source object for structured WMD answers.
    """

    if not records:
        return None

    record = records[0]

    return {
        "source_id": "S1",
        "title": record.get(
            "dataset_title",
            "World Mining Data 2026",
        ),
        "agency": record.get(
            "agency",
        ),
        "source_url": record.get(
            "source_url",
        ),
    }


def answer_statistics_result(
    search_result: dict,
) -> dict:
    """
    Build a deterministic answer from a structured
    mining-statistics search result.

    No language model is required.
    """

    records = search_result.get(
        "results",
        [],
    )

    intent = search_result.get(
        "statistics_intent",
        "production",
    )

    commodity = search_result.get(
        "commodity",
    )


    if not records:

        return {
            "answer": (
                "No matching structured "
                "World Mining Data statistics "
                "were found for this query."
            ),
            "model": None,
            "generation_method": (
                "structured-statistics"
            ),
            "citations": [],
            "sources": [],
        }


    source = statistics_source(
        records
    )

    sources = (
        [source]
        if source
        else []
    )


    # -----------------------------------------------------
    # TREND
    # -----------------------------------------------------

    if intent == "trend":

        ordered = sorted(
            records,
            key=lambda record:
                record["year"],
        )

        first = ordered[0]
        last = ordered[-1]

        first_value = float(
            first["production"]
        )

        last_value = float(
            last["production"]
        )

        absolute_change = (
            last_value
            - first_value
        )

        if first_value:

            percentage_change = (
                absolute_change
                / first_value
                * 100
            )

        else:

            percentage_change = None


        if absolute_change > 0:
            direction = "increased"

        elif absolute_change < 0:
            direction = "decreased"

        else:
            direction = "was unchanged"


        change_value = abs(
            absolute_change
        )

        unit = human_unit(
            last.get(
                "unit"
            )
        )


        if percentage_change is None:

            change_text = (
                f"{format_number(change_value)} "
                f"{unit}"
            )

        else:

            change_text = (
                f"{format_number(change_value)} "
                f"{unit} "
                f"({abs(percentage_change):.2f}%)"
            )


        answer = (
            f"{last['country']}'s "
            f"{commodity.lower()} production "
            f"{direction} from "
            f"**{format_number(first_value)} "
            f"{unit} in {first['year']}** to "
            f"**{format_number(last_value)} "
            f"{unit} in {last['year']}**. "
        )


        if absolute_change != 0:

            answer += (
                f"The overall change was "
                f"**{change_text}**. [S1]"
            )

        else:

            answer += (
                "There was no overall change. "
                "[S1]"
            )


        return {
            "answer": answer,
            "model": None,
            "generation_method": (
                "structured-statistics"
            ),
            "citations": [
                "S1"
            ],
            "sources": sources,
        }


    # -----------------------------------------------------
    # GLOBAL RANKING LIST
    # -----------------------------------------------------

    if (
        intent == "world_rank"
        and not search_result.get(
            "countries"
        )
    ):

        year = records[0][
            "year"
        ]

        lines = [
            (
                f"World Mining Data 2026 "
                f"ranks the following countries "
                f"for {commodity.lower()} "
                f"production in {year}:"
            )
        ]


        for record in records:

            rank = (
                record.get(
                    "rank_2024"
                )
            )

            lines.append(
                (
                    f"{ordinal(rank)} — "
                    f"{record['country']}: "
                    f"{format_number(record['production'])} "
                    f"{human_unit(record.get('unit'))}"
                )
            )


        lines.append(
            "[S1]"
        )


        return {
            "answer": "\n\n".join(
                lines
            ),
            "model": None,
            "generation_method": (
                "structured-statistics"
            ),
            "citations": [
                "S1"
            ],
            "sources": sources,
        }


    # -----------------------------------------------------
    # SINGLE / MULTI-COUNTRY RECORD ANSWERS
    # -----------------------------------------------------

    if len(records) == 1:

        record = records[0]

        country = record[
            "country"
        ]

        year = record[
            "year"
        ]

        production = (
            format_number(
                record[
                    "production"
                ]
            )
        )

        unit = human_unit(
            record.get(
                "unit"
            )
        )

        share = record.get(
            "world_share_percent"
        )

        rank = record.get(
            "rank_2024"
        )


        if intent == "world_share":

            if share is None:

                answer = (
                    f"World-production share data "
                    f"is not available for "
                    f"{country}'s "
                    f"{commodity.lower()} production "
                    f"in {year}. [S1]"
                )

            else:

                answer = (
                    f"{country} accounted for "
                    f"**{share:.2f}% of world "
                    f"{commodity.lower()} production "
                    f"in {year}**, producing "
                    f"{production} {unit}. [S1]"
                )


        elif intent == "world_rank":

            if rank is None:

                answer = (
                    f"A World Mining Data ranking is "
                    f"not available for {country}'s "
                    f"{commodity.lower()} production "
                    f"in {year}. [S1]"
                )

            else:

                answer = (
                    f"{country} ranked "
                    f"**{ordinal(rank)} globally** "
                    f"for {commodity.lower()} production "
                    f"in {year}, producing "
                    f"{production} {unit}"
                )

                if share is not None:

                    answer += (
                        f" and accounting for "
                        f"{share:.2f}% of world "
                        "production"
                    )

                answer += ". [S1]"


        else:

            answer = (
                f"{country} produced "
                f"**{production} {unit} of "
                f"{commodity.lower()} in {year}**. "
                "[S1]"
            )


        return {
            "answer": answer,
            "model": None,
            "generation_method": (
                "structured-statistics"
            ),
            "citations": [
                "S1"
            ],
            "sources": sources,
        }


    # -----------------------------------------------------
    # COUNTRY COMPARISON
    # -----------------------------------------------------

    lines = []

    for record in records:

        lines.append(
            (
                f"**{record['country']}** — "
                f"{format_number(record['production'])} "
                f"{human_unit(record.get('unit'))}"
            )
        )


    return {
        "answer": (
            "\n\n".join(
                lines
            )
            + "\n\n[S1]"
        ),
        "model": None,
        "generation_method": (
            "structured-statistics"
        ),
        "citations": [
            "S1"
        ],
        "sources": sources,
    }
# =========================================================
# CLI
# =========================================================

def main() -> None:

    parser = argparse.ArgumentParser(
        description=(
            "Query MineLens structured "
            "World Mining Data statistics."
        )
    )


    parser.add_argument(
        "--country",
        required=True,
    )


    parser.add_argument(
        "--commodity",
        required=True,
    )


    parser.add_argument(
        "--year",
        type=int,
        default=2024,
    )


    args = parser.parse_args()


    records = (
        load_mining_statistics()
    )


    record = production_record(
        records=records,
        country=args.country,
        commodity=args.commodity,
        year=args.year,
    )


    if record is None:

        print(
            "No matching structured "
            "statistics found."
        )

        return


    print(
        f"{record['country']} "
        f"{record['commodity']} "
        f"{record['year']}"
    )

    print(
        "Production:",
        format_production(
            record
        ),
    )


    if record.get(
        "rank_2024"
    ) is not None:

        print(
            "World rank:",
            record[
                "rank_2024"
            ],
        )


    if record.get(
        "world_share_percent"
    ) is not None:

        print(
            "World share:",
            (
                f"{record['world_share_percent']:.4f}%"
            ),
        )


    print(
        "Data quality:",
        record.get(
            "data_quality"
        )
        or "unspecified",
    )

    print(
        "Source:",
        record[
            "dataset_title"
        ],
    )


if __name__ == "__main__":
    main()