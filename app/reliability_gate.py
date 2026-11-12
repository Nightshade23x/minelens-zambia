"""Combine MineLens answer reliability checks."""

from app.answer_reliability import audit_answer_reliability
from app.citation_validation import validate_citation_integrity
from app.factual_support import validate_factual_support
from app.project_estimate_support import validate_project_estimate_support


def assess_answer_quality(
    question: str,
    search_result: dict,
    evidence: list[dict],
    answer_result: dict,
) -> dict:
    """Classify an answer without modifying it."""

    issues = []

    if not evidence:
        if answer_result.get("citations"):
            return {
                "status": "review_required",
                "issues": ["citation_without_evidence"],
                "citation_integrity": None,
                "factual_support": None,
                "reliability_audit": None,
            }

        return {
            "status": "insufficient_evidence",
            "issues": ["no_retrieved_evidence"],
            "citation_integrity": None,
            "factual_support": None,
            "reliability_audit": None,
        }

    integrity = validate_citation_integrity(answer_result)

    support = validate_factual_support(
        question=question,
        search_result=search_result,
        answer_result=answer_result,
        evidence=evidence,
    )

    # Use specialized checks only when the existing
    # factual-support validator has not verified the claim.
    if (
        not support.get("checked", False)
        and support.get("supported") is None
    ):
        specialized = validate_project_estimate_support(
            question=question,
            evidence=evidence,
            answer_result=answer_result,
        )

        if specialized.get("checked", False):
            support = specialized

    reliability = audit_answer_reliability(
        question=question,
        evidence=evidence,
        answer_result=answer_result,
    )

    if not integrity.get("valid", False):
        issues.append("invalid_citations")

    if support.get("supported") is False:
        issues.append("unsupported_factual_claim")

    # Unchecked is not equivalent to verified.
    if (
        not support.get("checked", False)
        or support.get("supported") is None
    ):
        issues.append("factual_support_not_checked")

    issues.extend(reliability.get("warnings", []))
    issues = list(dict.fromkeys(issues))

    return {
        "status": (
            "review_required"
            if issues
            else "checks_passed"
        ),
        "issues": issues,
        "citation_integrity": integrity,
        "factual_support": support,
        "reliability_audit": reliability,
    }
