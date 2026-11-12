"""Project-independent extraction of mining capital estimates."""

import re
from decimal import Decimal

from app.estimate_consistency import MONEY_RE


COST_QUERY_RE = re.compile(
    r"\b(?:capex|capital expenditure|cost|costs|"
    r"investment|construction budget)\b",
    re.I,
)

NEXT_PROJECT_RE = re.compile(
    r"\b[A-Z][A-Za-z-]*"
    r"(?:\s+[A-Z][A-Za-z-]*){0,2}\s+"
    r"(?:Copper|Nickel|Gold|Zinc|Cobalt|Manganese)\s+"
    r"[A-Z][A-Za-z-]*(?:\s+[A-Z][A-Za-z-]*)+"
)

GENERIC_NAMES = {
    "project", "mine", "investment", "cost",
    "capital", "expenditure", "expansion",
}


def project_from_question(question: str) -> str | None:
    if not COST_QUERY_RE.search(question):
        return None

    patterns = [
        (
            r"\b(?:for|of)\s+(?:the\s+)?"
            r"(?P<name>[A-Za-z][A-Za-z-]{2,})"
            r"(?:\s+(?:project|mine|expansion))?\s*[?.!]*$"
        ),
        (
            r"\b(?:the\s+)?"
            r"(?P<name>[A-Za-z][A-Za-z-]{2,})"
            r"\s+(?:mine|project)\b"
        ),
    ]

    for pattern in patterns:
        match = re.search(pattern, question, re.I)

        if match:
            name = match.group("name")

            if name.casefold() not in GENERIC_NAMES:
                return name

    return None


def extract_project_estimates(
    project: str,
    evidence: list[dict],
) -> list[dict]:
    """Extract the first nearby cost estimate for each project mention."""

    project_pattern = re.compile(
        r"(?<!\w)" + re.escape(project) + r"(?!\w)",
        re.I,
    )

    estimates = []
    seen = set()

    for item in evidence:
        if not isinstance(item, dict):
            continue

        text = str(item.get("text") or "")
        source_id = str(item.get("source_id") or "")

        if not re.fullmatch(r"S[1-9][0-9]*", source_id):
            continue

        for mention in project_pattern.finditer(text):
            segment = text[mention.end():mention.end() + 180]

            # Normalize approximation symbols without changing amounts.
            for character in (
                "\u223c", "\u2248", "\u2243", "\u223d"
            ):
                segment = segment.replace(character, "~")

            money = MONEY_RE.search(segment)

            if money is None:
                continue

            prefix = segment[:money.start()]

            # A table row without a figure must not borrow
            # the following project's capital estimate.
            if re.search(r"\bTBD\b", prefix, re.I):
                continue

            next_project = NEXT_PROJECT_RE.search(prefix)

            # Prose may mention another mine before its investment
            # figure, e.g. "Mopani Copper Mines plc secured $1.1B".
            # Do not assign that amount to the preceding project.
            other_mine_pattern = re.compile(
                r"\b(?P<name>[A-Z][A-Za-z-]*)\s+"
                r"(?:Copper|Nickel|Gold|Zinc|Cobalt|"
                r"Manganese)\s+Mines?\b"
            )

            other_mine = other_mine_pattern.search(prefix)

            if next_project is not None:
                continue

            if (
                other_mine is not None
                and other_mine.group("name").casefold()
                != project.casefold()
            ):
                continue

            scale = (
                1_000_000_000
                if money.group("unit").casefold().startswith("b")
                else 1_000_000
            )

            value = int(
                Decimal(money.group("amount")) * scale
            )

            operator = money.group("operator") or "reported"

            if operator == "reported" and re.search(
                r"\b(?:approximately|roughly|about)\b",
                prefix[-75:],
                re.I,
            ):
                operator = "~"

            if re.search(r"\bexpected\b", prefix[-75:], re.I):
                qualifier = "expected"
            elif re.search(
                r"\b(?:estimated|estimate)\b",
                prefix[-75:],
                re.I,
            ):
                qualifier = "estimated"
            elif operator == "~":
                qualifier = "approximate"
            else:
                qualifier = "unspecified"

            key = (
                source_id,
                str(item.get("pages") or ""),
                value,
                operator,
            )

            if key in seen:
                continue

            seen.add(key)

            estimates.append({
                "project": project,
                "source_id": source_id,
                "document": str(item.get("document") or ""),
                "canonical_source_id": str(
                    item.get("canonical_source_id") or ""
                ),
                "pages": str(item.get("pages") or ""),
                "amount_usd": value,
                "operator": operator,
                "qualifier": qualifier,
                "quoted_amount": money.group(0).strip(),
            })


    # BACKWARD PROJECT ESTIMATES
    # Match explicit constructions such as:
    # "$2 billion expansion project at the Lumwana Mine".
    backward_context = re.compile(
        r"\s+(?:(?:expansion|development|construction|investment)"
        r"\s+(?:project|plan|budget)|investment)"
        r"\s+(?:at|for|of|in)\s+(?:the\s+)?$",
        re.I,
    )

    for item in evidence:
        if not isinstance(item, dict):
            continue

        text = str(item.get("text") or "")
        source_id = str(item.get("source_id") or "")

        if not re.fullmatch(r"S[1-9][0-9]*", source_id):
            continue

        for mention in project_pattern.finditer(text):
            following = text[
                mention.end():mention.end() + 16
            ]

            # Require an explicit project or mine reference.
            if not re.match(
                r"\s+(?:mine|project)\b",
                following,
                re.I,
            ):
                continue

            left = text[
                max(0, mention.start() - 150):
                mention.start()
            ]

            for money in MONEY_RE.finditer(left):
                between = left[money.end():]

                if not backward_context.fullmatch(between):
                    continue

                scale = (
                    1_000_000_000
                    if money.group("unit").casefold().startswith("b")
                    else 1_000_000
                )

                value = int(
                    Decimal(money.group("amount")) * scale
                )

                operator = money.group("operator") or "reported"

                pages = str(item.get("pages") or "")

                key = (
                    source_id,
                    pages,
                    value,
                    operator,
                )

                if key in seen:
                    continue

                seen.add(key)

                estimates.append({
                    "project": project,
                    "source_id": source_id,
                    "document": str(item.get("document") or ""),
                    "canonical_source_id": str(
                        item.get("canonical_source_id") or ""
                    ),
                    "pages": pages,
                    "amount_usd": value,
                    "operator": operator,
                    "qualifier": (
                        "approximate"
                        if operator == "~"
                        else "unspecified"
                    ),
                    "quoted_amount": money.group(0).strip(),
                })

    return sorted(
        estimates,
        key=lambda row: (
            int(row["source_id"][1:]),
            row["amount_usd"],
        ),
    )


def analyze_project_estimates(
    project: str,
    evidence: list[dict],
) -> dict:
    estimates = extract_project_estimates(project, evidence)

    formulations = {
        (item["amount_usd"], item["operator"])
        for item in estimates
    }

    amounts = {
        item["amount_usd"]
        for item in estimates
    }

    documents = {
        item["canonical_source_id"]
        or item["document"]
        or item["source_id"]
        for item in estimates
    }

    if not estimates:
        status = "no_estimates"
    elif len(estimates) == 1:
        status = "single_estimate"
    elif len(formulations) == 1:
        status = "consistent"
    elif len(amounts) == 1:
        status = "qualifier_difference"
    else:
        status = "different_values"

    return {
        "project": project,
        "status": status,
        "estimates": estimates,
        "distinct_documents": len(documents),
    }
