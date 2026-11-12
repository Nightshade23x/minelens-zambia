"""Verify mining licence application fees against retrieved schedules."""

import re

from app.answer_reliability import audit_answer_reliability


SECTION_RE = re.compile(
    r"\((?P<number>[1-6])\)\s+"
    r"(?P<title>(?:(?:Transfer|Alteration) of )?"
    r"(?:Exploration|Mining)\s+Licen[cs]e)\b",
    re.I,
)

SCALE_RE = re.compile(
    r"\([a-z]\)\s*(Artisanal|Small[- ]scale|Large[- ]scale)\b",
    re.I,
)

NUMBER_RE = re.compile(
    r"\d[\d,]*(?:\.\d{2})?"
)

KWACHA_RE = re.compile(
    r"(?<![A-Za-z0-9])K\s*([0-9][0-9,]*)"
    r"(?:\.[0-9]{2})?\b",
    re.I,
)


def fee_category_from_question(question: str):
    """Identify unambiguous mining-right application fee questions."""

    query = question.casefold()

    if "application" not in query:
        return None

    if not re.search(r"\blicen[cs]e\b", query):
        return None

    if re.search(
        r"\b(?:transfer|renewal|alteration|"
        r"area charges?|per hectare)\b",
        query,
    ):
        return None

    scales = re.findall(
        r"\b(large|small)[-\s]*scale\b",
        query,
    )

    if "artisanal" in query:
        scales.append("artisanal")

    if len(scales) != 1:
        return None

    categories = [
        category
        for category in ("exploration", "mining")
        if re.search(r"\b" + category + r"\b", query)
    ]

    if len(categories) != 1:
        return None

    return categories[0], scales[0]


def extract_application_fee_rows(evidence: list[dict]):
    """Read the application-fee rows, not transfers or area charges."""

    rows = []

    for item in evidence:
        if not isinstance(item, dict):
            continue

        text = str(item.get("text") or "")
        source_id = str(item.get("source_id") or "")

        if not re.fullmatch(r"S[1-9][0-9]*", source_id):
            continue

        if not re.search(r"PRESCRIBED FEES", text, re.I):
            continue

        if not re.search(
            r"TYPE OF MINING RIGHT OR APPLICATION",
            text,
            re.I,
        ):
            continue

        headings = list(SECTION_RE.finditer(text))

        for index, heading in enumerate(headings):
            section_number = heading.group("number")

            if section_number not in ("1", "2"):
                continue

            category = (
                "exploration"
                if section_number == "1"
                else "mining"
            )

            next_start = (
                headings[index + 1].start()
                if index + 1 < len(headings)
                else len(text)
            )

            section = text[heading.end():next_start]

            labels = list(SCALE_RE.finditer(section))

            expected_scales = (
                ["small", "large"]
                if category == "exploration"
                else ["artisanal", "small", "large"]
            )

            scales = [
                re.sub(
                    r"[-\s]+",
                    "",
                    match.group(1).casefold(),
                ).replace("scale", "")
                for match in labels
            ]

            if scales != expected_scales:
                continue

            numeric_part = section[labels[-1].end():]
            numbers = NUMBER_RE.findall(numeric_part)

            count = len(scales)

            # The official layout has fee-unit columns followed
            # by kwacha amounts in the same category order.
            if len(numbers) != 2 * count:
                continue

            units = numbers[:count]
            amounts = numbers[count:]

            if not all("." not in value for value in units):
                continue

            if not all(
                re.fullmatch(r"[\d,]+\.\d{2}", value)
                for value in amounts
            ):
                continue

            for scale, value in zip(scales, amounts):
                rows.append({
                    "category": category,
                    "scale": scale,
                    "amount_kwacha": int(
                        float(value.replace(",", ""))
                    ),
                    "source_id": source_id,
                    "document": item.get("document"),
                    "pages": item.get("pages"),
                })

    return rows


def validate_fee_support(
    question: str,
    evidence: list[dict],
    answer_result: dict,
) -> dict:
    """Independently validate an application fee answer."""

    unchecked = {
        "checked": False,
        "supported": None,
        "issues": [],
    }

    category = fee_category_from_question(question)

    if category is None:
        return unchecked

    rows = [
        row
        for row in extract_application_fee_rows(evidence)
        if (row["category"], row["scale"]) == category
    ]

    if not rows:
        return unchecked

    amounts = {row["amount_kwacha"] for row in rows}

    if len(amounts) != 1:
        return {
            "checked": True,
            "supported": False,
            "issues": ["conflicting_fee_schedule_values"],
        }

    expected_amount = next(iter(amounts))

    answer = str(answer_result.get("answer") or "")

    answer_amounts = {
        int(value.replace(",", ""))
        for value in KWACHA_RE.findall(answer)
    }

    cited_ids = {
        str(value)
        for value in answer_result.get("citations", [])
    }

    supporting_ids = {
        row["source_id"] for row in rows
    }

    normalized_answer = re.sub(
        r"[-\s]+", " ", answer.casefold()
    )

    category_text = (
        category[1] + " scale " + category[0]
        if category[1] != "artisanal"
        else "artisanal " + category[0]
    )

    issues = []

    if answer_amounts != {expected_amount}:
        issues.append("fee_amount_mismatch")

    if category_text not in normalized_answer:
        issues.append("fee_category_mismatch")

    if "application fee" not in normalized_answer:
        issues.append("fee_type_mismatch")

    if not cited_ids or not cited_ids.issubset(supporting_ids):
        issues.append("fee_citation_mismatch")

    return {
        "checked": True,
        "supported": not issues,
        "issues": issues,
        "expected_amount_kwacha": expected_amount,
        "supporting_source_ids": sorted(supporting_ids),
    }
