from __future__ import annotations

import json
import re

from pathlib import Path


PROJECT_ROOT = Path(
    __file__
).resolve().parents[1]

INTERSECTIONS_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "shuka_kabwe_2026_drill_intersections.jsonl"
)

MAX_ASSAYS_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "shuka_kabwe_2026_hole_max_assays.jsonl"
)


def normalize_query(
    query: str,
) -> str:
    return " ".join(
        query.casefold().split()
    )


def load_jsonl(
    path: Path,
) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(
            f"Structured exploration file not found: {path}"
        )

    records: list[dict] = []

    with path.open(
        "r",
        encoding="utf-8",
    ) as file:

        for line in file:

            if not line.strip():
                continue

            records.append(
                json.loads(
                    line
                )
            )

    return records


def load_exploration_intersections() -> list[dict]:
    return load_jsonl(
        INTERSECTIONS_PATH
    )


def load_exploration_max_assays() -> list[dict]:
    return load_jsonl(
        MAX_ASSAYS_PATH
    )


def infer_hole_ids(
    query: str,
) -> list[str]:
    """
    Extract one or more KBDD drill-hole IDs.
    """

    matches = re.findall(
        r"\bKBDD\s*[- ]?\s*(0[6-9]|1[01])\b",
        query,
        flags=re.IGNORECASE,
    )

    holes: list[str] = []

    for suffix in matches:

        hole_id = (
            "KBDD"
            + suffix
        ).upper()

        if hole_id not in holes:
            holes.append(
                hole_id
            )

    return holes


def infer_target(
    query: str,
) -> str | None:
    normalized = normalize_query(
        query
    )

    if "sperm whale" in normalized:
        return "Sperm Whale"

    if "swimming pool" in normalized:
        return "Swimming Pool"

    return None


def infer_zinc_threshold(
    query: str,
) -> float | None:
    """
    Detect phrases such as:
        above 10% zinc
        over 15% Zn
        at least 20 percent zinc
    """

    patterns = (
        r"(?:above|over|greater than|more than|at least)"
        r"\s+(\d+(?:\.\d+)?)\s*%\s*(?:zn|zinc)",

        r"(?:above|over|greater than|more than|at least)"
        r"\s+(\d+(?:\.\d+)?)\s*percent\s*(?:zn|zinc)",
    )

    normalized = normalize_query(
        query
    )

    for pattern in patterns:

        match = re.search(
            pattern,
            normalized,
        )

        if match:
            return float(
                match.group(
                    1
                )
            )

    return None



def infer_zinc_threshold_operator(
    query: str,
) -> str | None:
    """
    Determine whether a zinc threshold is strict.

    Examples:
        above 10% Zn      -> gt
        over 10% zinc     -> gt
        greater than 10%  -> gt
        more than 10%     -> gt
        at least 10% Zn   -> gte
        10% Zn or more    -> gte
    """

    normalized = normalize_query(
        query
    )

    zinc_value = (
        r"\d+(?:\.\d+)?"
        r"\s*(?:%|percent)"
        r"\s*(?:zn|zinc)"
    )

    if re.search(
        (
            r"(?:above|over|greater than|more than)"
            r"\s+"
            + zinc_value
        ),
        normalized,
    ):
        return "gt"

    if re.search(
        (
            r"at least\s+"
            + zinc_value
        ),
        normalized,
    ):
        return "gte"

    if re.search(
        (
            zinc_value
            + r"\s+or more"
        ),
        normalized,
    ):
        return "gte"

    return None

def infer_width_threshold(
    query: str,
) -> float | None:
    """
    Detect phrases such as:
        wider than 10 metres
        over 20 m wide
        interval greater than 5 m
    """

    normalized = normalize_query(
        query
    )

    patterns = (
        r"(?:wider than|greater than|more than|over)"
        r"\s+(\d+(?:\.\d+)?)\s*(?:m|metres|meters)",

        r"intervals?\s+(?:above|over|greater than|more than)"
        r"\s+(\d+(?:\.\d+)?)\s*(?:m|metres|meters)",
    )

    for pattern in patterns:

        match = re.search(
            pattern,
            normalized,
        )

        if match:
            return float(
                match.group(
                    1
                )
            )

    return None


def infer_exploration_intent(
    query: str,
) -> str:
    normalized = normalize_query(
        query
    )

    if (
        "highest individual" in normalized
        or "maximum individual" in normalized
        or "highest assay" in normalized
        or "maximum assay" in normalized
    ):
        return "highest_individual_assay"

    if (
        "highest zinc" in normalized
        or "highest zn" in normalized
        or "highest grade" in normalized
        or "best zinc" in normalized
        or "best zn" in normalized
    ):
        return "highest_intersection"

    if (
        "no reportable" in normalized
        or "no significant" in normalized
        or "without reportable" in normalized
        or "did not have" in normalized
    ):
        return "no_reportable_intersections"

    if (
        "compare" in normalized
        or "comparison" in normalized
        or "versus" in normalized
        or " vs " in f" {normalized} "
    ):
        return "compare_holes"

    return "intersections"


def has_exploration_intent(
    query: str,
) -> bool:
    """
    Detect strong structured exploration/drilling intent.

    Keep licensing queries separate while recognising
    drill holes, assays, grades, intervals and targets.
    """

    normalized = normalize_query(
        query
    )

    # Explicit KBDD hole identifiers are always
    # exploration-result queries.
    if infer_hole_ids(
        query
    ):
        return True

    strong_terms = (
        "drill hole",
        "drill holes",
        "drilling result",
        "drilling results",
        "drill result",
        "drill results",
        "assay",
        "assays",
        "mineralised interval",
        "mineralised intervals",
        "mineralized interval",
        "mineralized intervals",
        "zinc grade",
        "lead grade",
        "zinc intersection",
        "zinc intersections",
        "lead intersection",
        "lead intersections",
        "sperm whale",
        "swimming pool",
    )

    if any(
        term in normalized
        for term in strong_terms
    ):
        return True

    # Natural questions often say simply "hole" rather
    # than "drill hole", for example:
    #
    # "Which Kabwe hole has the highest zinc intersection?"
    if (
        "hole" in normalized
        or "holes" in normalized
    ):
        geological_terms = (
            "zinc",
            " zn ",
            "lead",
            " pb ",
            "grade",
            "assay",
            "intersection",
            "interval",
            "drilling",
            "kabwe",
        )

        padded = (
            f" {normalized} "
        )

        if any(
            term in padded
            for term in geological_terms
        ):
            return True

    # Catch geological interval/intersection questions
    # even when the user does not explicitly say "hole".
    if (
        "intersection" in normalized
        or "intersections" in normalized
        or "interval" in normalized
        or "intervals" in normalized
    ):
        context_terms = (
            "zinc",
            "lead",
            "grade",
            "kabwe",
            "drill",
            "mineral",
        )

        if any(
            term in normalized
            for term in context_terms
        ):
            return True

    return False



def filter_intersections(
    records: list[dict],
    *,
    hole_ids: list[str] | None = None,
    target: str | None = None,
    zinc_min: float | None = None,
    zinc_operator: str | None = None,
    width_min: float | None = None,
    reportable_only: bool = False,
    no_reportable_only: bool = False,
) -> list[dict]:

    results: list[dict] = []

    hole_set = set(
        hole_ids
        or []
    )

    for record in records:

        if (
            hole_set
            and record.get(
                "hole_id"
            )
            not in hole_set
        ):
            continue

        if (
            target
            and record.get(
                "target"
            )
            != target
        ):
            continue

        status = record.get(
            "status"
        )

        if (
            reportable_only
            and status
            != "reportable_intersection"
        ):
            continue

        if (
            no_reportable_only
            and status
            != "no_reportable_intersection"
        ):
            continue

        zinc_pct = record.get(
            "zinc_pct"
        )

        if zinc_min is not None:

            if zinc_pct is None:
                continue

            if (
                zinc_operator == "gt"
                and zinc_pct <= zinc_min
            ):
                continue

            if (
                zinc_operator != "gt"
                and zinc_pct < zinc_min
            ):
                continue

        width_m = record.get(
            "width_m"
        )

        if (
            width_min is not None
            and (
                width_m is None
                or width_m <= width_min
            )
        ):
            continue

        results.append(
            record
        )

    return results


def query_exploration(
    query: str,
    top_k: int = 10,
) -> dict:
    """
    Query structured Kabwe drilling records.
    """

    if not query.strip():
        raise ValueError(
            "Query must not be empty."
        )

    if top_k <= 0:
        raise ValueError(
            "top_k must be greater than zero."
        )

    intersections = (
        load_exploration_intersections()
    )

    max_assays = (
        load_exploration_max_assays()
    )

    intent = infer_exploration_intent(
        query
    )

    hole_ids = infer_hole_ids(
        query
    )

    target = infer_target(
        query
    )

    zinc_min = infer_zinc_threshold(
        query
    )

    zinc_operator = (
        infer_zinc_threshold_operator(
            query
        )
    )

    width_min = infer_width_threshold(
        query
    )

    results: list[dict] = []

    if (
        intent
        == "highest_individual_assay"
    ):

        candidates = [
            record
            for record in max_assays
            if (
                not hole_ids
                or record.get(
                    "hole_id"
                )
                in hole_ids
            )
            and (
                target is None
                or record.get(
                    "target"
                )
                == target
            )
        ]

        candidates.sort(
            key=lambda record: (
                record.get(
                    "maximum_assay_pct"
                )
                or -1
            ),
            reverse=True,
        )

        results = candidates[
            :top_k
        ]

    elif (
        intent
        == "highest_intersection"
    ):

        candidates = filter_intersections(
            intersections,
            hole_ids=hole_ids,
            target=target,
            reportable_only=True,
        )

        candidates.sort(
            key=lambda record: (
                record.get(
                    "zinc_pct"
                )
                or -1
            ),
            reverse=True,
        )

        results = candidates[
            :top_k
        ]

    elif (
        intent
        == "no_reportable_intersections"
    ):

        results = filter_intersections(
            intersections,
            hole_ids=hole_ids,
            target=target,
            no_reportable_only=True,
        )[
            :top_k
        ]

    elif (
        intent
        == "compare_holes"
    ):

        results = filter_intersections(
            intersections,
            hole_ids=hole_ids,
            target=target,
            reportable_only=True,
        )

        results.sort(
            key=lambda record: (
                record.get(
                    "hole_id"
                )
                or "",
                record.get(
                    "from_m"
                )
                if record.get(
                    "from_m"
                )
                is not None
                else -1,
                record.get(
                    "cutoff_zinc_pct"
                )
                if record.get(
                    "cutoff_zinc_pct"
                )
                is not None
                else -1,
            )
        )

        results = results[
            :top_k
        ]

    else:

        results = filter_intersections(
            intersections,
            hole_ids=hole_ids,
            target=target,
            zinc_min=zinc_min,
            zinc_operator=zinc_operator,
            width_min=width_min,
        )

        results.sort(
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
            reverse=True,
        )

        results = results[
            :top_k
        ]

    return {
        "intent":
            intent,

        "hole_ids":
            hole_ids,

        "target":
            target,

        "zinc_min":
            zinc_min,

        "zinc_operator":
            zinc_operator,

        "width_min":
            width_min,

        "results":
            results,

        "intersection_record_count":
            len(
                intersections
            ),

        "maximum_assay_record_count":
            len(
                max_assays
            ),

        "source_url":
            (
                intersections[
                    0
                ].get(
                    "source_url"
                )
                if intersections
                else None
            ),
    }


if __name__ == "__main__":

    import argparse

    parser = argparse.ArgumentParser(
        description=(
            "Query structured Kabwe "
            "exploration results."
        )
    )

    parser.add_argument(
        "query",
        nargs="+",
    )

    parser.add_argument(
        "--top-k",
        type=int,
        default=10,
    )

    args = parser.parse_args()

    result = query_exploration(
        query=" ".join(
            args.query
        ),
        top_k=args.top_k,
    )

    print(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False,
        )
    )
