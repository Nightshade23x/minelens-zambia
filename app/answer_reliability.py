"""Source-aware reliability auditing for MineLens answers."""

import re
from decimal import Decimal

from app.estimate_consistency import MONEY_RE
from app.project_estimates import (
    analyze_project_estimates,
    project_from_question,
)


INDEPENDENCE_CLAIM_RE = re.compile(
    r"\b(?:independent sources confirm|"
    r"multiple independent sources|"
    r"independently verified|"
    r"independently confirmed|"
    r"confirmed independently)\b",
    re.I,
)


def _document_key(item: dict) -> str:
    return str(
        item.get("canonical_source_id")
        or item.get("document")
        or item.get("source_url")
        or item.get("source_id")
        or ""
    )


def _money_formulations(text: str) -> set[tuple[int, str]]:
    """Return normalized monetary values and comparison operators."""

    values = set()

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

        values.add((amount, operator))

    return values


def audit_answer_reliability(
    question: str,
    evidence: list[dict],
    answer_result: dict,
) -> dict:
    """
    Audit evidence attribution and monetary-answer completeness.

    This function reports issues. It does not change answers.
    """

    answer = str(answer_result.get("answer") or "")
    cited_ids = [
        str(value)
        for value in (answer_result.get("citations") or [])
    ]

    evidence_by_id = {
        str(item.get("source_id")): item
        for item in evidence
        if isinstance(item, dict) and item.get("source_id")
    }

    warnings = []

    unknown_citations = sorted(
        set(cited_ids) - set(evidence_by_id)
    )

    if unknown_citations:
        warnings.append("citation_not_in_retrieved_evidence")

    cited_documents = {
        _document_key(evidence_by_id[source_id])
        for source_id in cited_ids
        if source_id in evidence_by_id
    }

    if (
        INDEPENDENCE_CLAIM_RE.search(answer)
        and len(cited_documents) < 2
    ):
        warnings.append("unsupported_independence_claim")

    project = project_from_question(question)

    estimate_status = "not_applicable"
    estimates = []
    missing_amounts = []
    missing_thresholds = []

    if project:
        analysis = analyze_project_estimates(
            project,
            evidence,
        )

        estimate_status = analysis["status"]
        estimates = analysis["estimates"]

        answer_formulations = _money_formulations(answer)
        answer_amounts = {
            amount for amount, _ in answer_formulations
        }

        evidence_amounts = {
            item["amount_usd"]
            for item in estimates
        }

        if len(evidence_amounts) > 1:
            missing_amounts = sorted(
                evidence_amounts - answer_amounts
            )

            if missing_amounts:
                warnings.append(
                    "answer_omits_distinct_estimate"
                )

        strict_operators = {">", ">=", "<", "<="}

        for item in estimates:
            operator = item["operator"]

            if operator not in strict_operators:
                continue

            formulation = (
                item["amount_usd"],
                operator,
            )

            if formulation not in answer_formulations:
                missing_thresholds.append(formulation)

        if missing_thresholds:
            warnings.append(
                "answer_omits_estimate_inequality"
            )

        if (
            estimate_status == "different_values"
            and re.search(
                r"\b(?:all estimates agree|"
                r"consistent across (?:all |multiple )?sources|"
                r"identical estimates)\b",
                answer,
                re.I,
            )
        ):
            warnings.append(
                "consistency_claim_with_different_figures"
            )

    warnings = list(dict.fromkeys(warnings))

    return {
        "ok": not warnings,
        "warnings": warnings,
        "project": project,
        "estimate_status": estimate_status,
        "estimate_count": len(estimates),
        "cited_source_count": len(set(cited_ids)),
        "cited_document_count": len(cited_documents),
        "unknown_citations": unknown_citations,
        "missing_amounts_usd": missing_amounts,
        "missing_thresholds": missing_thresholds,
    }
