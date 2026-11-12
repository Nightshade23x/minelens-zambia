"""Conservative factual-support checks for project estimates."""

import re
from decimal import Decimal

from app.estimate_consistency import MONEY_RE
from app.project_estimates import (
    analyze_project_estimates,
    project_from_question,
)


def _money_values(text: str) -> list[tuple[int, str]]:
    values = []

    for match in MONEY_RE.finditer(text):
        unit = match.group("unit").casefold()

        multiplier = (
            1_000_000_000
            if unit.startswith("b")
            else 1_000_000
        )

        amount = int(
            Decimal(match.group("amount")) * multiplier
        )

        operator = match.group("operator") or "reported"
        values.append((amount, operator))

    return values


def validate_project_estimate_support(
    question: str,
    evidence: list[dict],
    answer_result: dict,
) -> dict:
    """Verify a consistent project estimate against cited evidence."""

    unchecked = {
        "checked": False,
        "supported": None,
        "issues": [],
    }

    project = project_from_question(question)

    if not project:
        return unchecked

    analysis = analyze_project_estimates(project, evidence)
    estimates = analysis["estimates"]

    if analysis["status"] not in (
        "consistent",
        "qualifier_difference",
    ):
        return unchecked

    if len(estimates) < 2:
        return unchecked

    amounts = {item["amount_usd"] for item in estimates}
    operators = {item["operator"] for item in estimates}

    if len(amounts) != 1:
        return unchecked

    if not operators.issubset({"reported", "~"}):
        return unchecked

    expected_amount = next(iter(amounts))

    supporting_ids = {
        item["source_id"] for item in estimates
    }

    cited_ids = {
        str(source_id)
        for source_id in answer_result.get("citations", [])
    }

    answer = str(answer_result.get("answer") or "")
    issues = []

    if not re.search(
        r"(?<!\w)" + re.escape(project) + r"(?!\w)",
        answer,
        re.I,
    ):
        issues.append("project_missing_from_answer")

    answer_values = _money_values(answer)

    if (
        not answer_values
        or any(
            amount != expected_amount
            or operator not in ("reported", "~")
            for amount, operator in answer_values
        )
    ):
        issues.append("project_estimate_amount_mismatch")

    if (
        len(cited_ids) < 2
        or not cited_ids.issubset(supporting_ids)
    ):
        issues.append("project_estimate_citation_mismatch")

    if "~" in operators and not re.search(
        r"\b(?:approximately|about|roughly|around)\b",
        answer,
        re.I,
    ):
        issues.append("approximate_estimate_not_qualified")

    return {
        "checked": True,
        "supported": not issues,
        "issues": issues,
    }
