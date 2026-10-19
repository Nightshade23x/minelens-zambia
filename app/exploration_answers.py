from __future__ import annotations

from app.exploration_search import (
    infer_exploration_intent,
)


GENERATION_METHOD = (
    "structured-exploration"
)


def clean_text(
    value: object,
) -> str:
    if value is None:
        return ""

    return " ".join(
        str(
            value
        ).split()
    )


def format_number(
    value: object,
) -> str:
    """
    Display numeric values without unnecessary
    trailing zeroes.
    """

    if value is None:
        return ""

    try:
        number = float(
            value
        )

    except (
        TypeError,
        ValueError,
    ):
        return clean_text(
            value
        )

    if number.is_integer():
        return str(
            int(
                number
            )
        )

    return (
        f"{number:.4f}"
        .rstrip("0")
        .rstrip(".")
    )


def exploration_source(
    evidence: list[dict],
) -> dict:
    """
    Build one canonical source entry.

    All current structured Kabwe drilling records come
    from the same Shuka Minerals announcement.
    """

    if not evidence:
        return {}

    first = evidence[
        0
    ]

    return {
        "source_id": "S1",
        "title": (
            clean_text(
                first.get(
                    "document"
                )
            )
            or (
                "Kabwe Drilling KBDD06-11 - "
                "Drilling Results from "
                "ALS Laboratories"
            )
        ),
        "document": clean_text(
            first.get(
                "document"
            )
        ),
        "source_url": clean_text(
            first.get(
                "source_url"
            )
        ),
        "published_date": clean_text(
            first.get(
                "published_date"
            )
        ),
        "agency": (
            "Shuka Minerals Plc"
        ),
    }


def base_answer(
    text: str,
    evidence: list[dict],
) -> dict:
    source = exploration_source(
        evidence
    )

    sources = (
        [
            source
        ]
        if source.get(
            "source_url"
        )
        else []
    )

    citations = (
        ["S1"]
        if sources
        else []
    )

    if evidence:

        caveat = (
            "Note: These are company-reported laboratory "
            "drilling results from Shuka Minerals Plc, "
            "not a government dataset. Drill intersections "
            "and assays are exploration results and are "
            "not mineral resource or reserve estimates."
        )

        text = (
            text.rstrip()
            + "\n\n"
            + caveat
        )

    return {
        "answer": text,
        "model": None,
        "generation_method": (
            GENERATION_METHOD
        ),
        "citations": citations,
        "sources": sources,
    }


def answer_highest_intersection(
    evidence: list[dict],
) -> dict:
    if not evidence:
        return base_answer(
            (
                "No reported drill intersection "
                "was found."
            ),
            evidence,
        )

    record = evidence[
        0
    ].get(
        "record",
        {},
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

    zinc = format_number(
        record.get(
            "zinc_pct"
        )
    )

    lead = format_number(
        record.get(
            "lead_pct"
        )
    )

    width = format_number(
        record.get(
            "width_m"
        )
    )

    from_m = format_number(
        record.get(
            "from_m"
        )
    )

    to_m = format_number(
        record.get(
            "to_m"
        )
    )

    cutoff = format_number(
        record.get(
            "cutoff_zinc_pct"
        )
    )

    text = (
        f"{hole_id} has the highest reported "
        f"zinc intersection in the structured "
        f"Kabwe drilling results: {width} m "
        f"grading {zinc}% Zn and {lead}% Pb, "
        f"from {from_m} m to {to_m} m"
    )

    if target:
        text += (
            f" at the {target} target"
        )

    if cutoff:
        text += (
            f", reported at a {cutoff}% Zn "
            "cut-off"
        )

    text += (
        ". [S1]\n\n"
        "This is an interval grade, not an "
        "individual drill-core assay."
    )

    return base_answer(
        text,
        evidence,
    )


def answer_highest_individual_assay(
    evidence: list[dict],
) -> dict:
    if not evidence:
        return base_answer(
            (
                "No individual zinc assay "
                "was found."
            ),
            evidence,
        )

    record = evidence[
        0
    ].get(
        "record",
        {},
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

    zinc = format_number(
        record.get(
            "maximum_assay_pct"
        )
    )

    text = (
        f"The highest individual zinc assay "
        f"in the structured Kabwe results is "
        f"{zinc}% Zn in {hole_id}"
    )

    if target:
        text += (
            f" at the {target} target"
        )

    text += (
        ". [S1]\n\n"
        "This is a maximum individual "
        "drill-core assay, not the grade of "
        "a reported drill interval."
    )

    return base_answer(
        text,
        evidence,
    )


def answer_no_reportable(
    evidence: list[dict],
) -> dict:
    if not evidence:
        return base_answer(
            (
                "No drill holes with a "
                "no-reportable-intersection "
                "status were found."
            ),
            evidence,
        )

    lines = [
        (
            "The following drill hole was "
            "reported without a significant "
            "reportable intersection:"
        )
    ]

    for item in evidence:

        record = item.get(
            "record",
            {},
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

        comment = clean_text(
            record.get(
                "comment"
            )
        )

        line = (
            f"- {hole_id}"
        )

        if target:
            line += (
                f" — {target}"
            )

        if comment:
            line += (
                f": {comment}"
            )

        lines.append(
            line
        )

    lines.append(
        "\n[S1]"
    )

    return base_answer(
        "\n".join(
            lines
        ),
        evidence,
    )


def answer_intersections(
    evidence: list[dict],
) -> dict:
    if not evidence:
        return base_answer(
            (
                "No drill intersections matched "
                "the requested filters."
            ),
            evidence,
        )

    lines = [
        "Matching reported drill results:"
    ]

    for item in evidence:

        record = item.get(
            "record",
            {},
        )

        hole_id = clean_text(
            record.get(
                "hole_id"
            )
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
            lines.append(
                (
                    f"- {hole_id}: "
                    f"{clean_text(record.get('comment'))}"
                )
            )

            continue

        width = format_number(
            record.get(
                "width_m"
            )
        )

        zinc = format_number(
            record.get(
                "zinc_pct"
            )
        )

        lead = format_number(
            record.get(
                "lead_pct"
            )
        )

        from_m = format_number(
            record.get(
                "from_m"
            )
        )

        to_m = format_number(
            record.get(
                "to_m"
            )
        )

        cutoff = format_number(
            record.get(
                "cutoff_zinc_pct"
            )
        )

        line = (
            f"- {hole_id}: "
            f"{width} m at {zinc}% Zn "
            f"and {lead}% Pb, "
            f"{from_m}-{to_m} m"
        )

        if cutoff:
            line += (
                f", {cutoff}% Zn cut-off"
            )

        lines.append(
            line
        )

    lines.append(
        (
            "\nReported intervals can overlap "
            "because the company publishes nested "
            "intervals at different zinc cut-off "
            "grades. [S1]"
        )
    )

    return base_answer(
        "\n".join(
            lines
        ),
        evidence,
    )


def answer_compare_holes(
    evidence: list[dict],
) -> dict:
    if not evidence:
        return base_answer(
            (
                "No drill-hole records were "
                "available for comparison."
            ),
            evidence,
        )

    grouped: dict[
        str,
        list[dict],
    ] = {}

    for item in evidence:

        record = item.get(
            "record",
            {},
        )

        hole_id = clean_text(
            record.get(
                "hole_id"
            )
        )

        if not hole_id:
            continue

        grouped.setdefault(
            hole_id,
            [],
        ).append(
            record
        )

    lines = [
        "Drill-hole comparison:"
    ]

    for hole_id in sorted(
        grouped
    ):

        records = grouped[
            hole_id
        ]

        reportable = [
            record
            for record in records
            if record.get(
                "status"
            )
            == "reportable_intersection"
        ]

        if not reportable:

            lines.append(
                (
                    f"- {hole_id}: no significant "
                    "reportable intersection in "
                    "the available results."
                )
            )

            continue

        highest = max(
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

        widest = max(
            reportable,
            key=lambda record: (
                record.get(
                    "width_m"
                )
                if record.get(
                    "width_m"
                )
                is not None
                else -1
            ),
        )

        lines.append(
            (
                f"- {hole_id}: "
                f"{len(reportable)} reported "
                f"interval(s) shown; highest "
                f"grade {format_number(highest.get('zinc_pct'))}% "
                f"Zn over "
                f"{format_number(highest.get('width_m'))} m; "
                f"widest interval "
                f"{format_number(widest.get('width_m'))} m "
                f"at "
                f"{format_number(widest.get('zinc_pct'))}% Zn."
            )
        )

    lines.append(
        (
            "\nNested intervals at different "
            "cut-offs are preserved as separately "
            "reported results. [S1]"
        )
    )

    return base_answer(
        "\n".join(
            lines
        ),
        evidence,
    )


def answer_exploration_result(
    question: str,
    evidence: list[dict],
) -> dict:
    """
    Deterministically answer structured exploration
    queries from normalized evidence.
    """

    intent = infer_exploration_intent(
        question
    )

    if (
        intent
        == "highest_intersection"
    ):
        return answer_highest_intersection(
            evidence
        )

    if (
        intent
        == "highest_individual_assay"
    ):
        return answer_highest_individual_assay(
            evidence
        )

    if (
        intent
        == "no_reportable_intersections"
    ):
        return answer_no_reportable(
            evidence
        )

    if (
        intent
        == "compare_holes"
    ):
        return answer_compare_holes(
            evidence
        )

    return answer_intersections(
        evidence
    )
