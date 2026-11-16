"""Fail-closed document-section support for the deterministic Form I answer."""

from __future__ import annotations

import re

from app.large_scale_requirements import (
    COMPANY_NOTE,
    INTRO,
    REQUIREMENTS,
    company_rule_source,
    verified_large_scale_source,
)


def validate_large_scale_mining_requirements_support(
    question: str,
    evidence: list[dict],
    answer_result: dict,
) -> dict:
    unchecked = {"checked": False, "supported": None, "issues": []}
    if answer_result.get("generation_method") != "deterministic-mining-requirements":
        return unchecked
    if not re.search(r"large[-\s]*scale", question, re.I) or not re.search(r"mining\s+licen[cs]e", question, re.I):
        return unchecked
    source = verified_large_scale_source(evidence)
    if source is None:
        return unchecked
    sid = str(source["source_id"])
    company = company_rule_source(evidence)
    company_id = str(company["source_id"]) if company else None
    issues = []
    text = str(answer_result.get("answer") or "")
    citations = [str(value) for value in (answer_result.get("citations") or [])]

    # Require every appendix and its exact corresponding supporting passage.
    # Comparison of the whole answer also rejects added unsupported claims.
    expected_lines = [f"- {description}. [{sid}]" for _, description, _ in REQUIREMENTS]
    expected = INTRO + "\n\n" + "\n".join(expected_lines)
    expected_citations = [sid]
    if company_id:
        expected += "\n\n" + COMPANY_NOTE + f" [{company_id}]"
        if company_id not in expected_citations:
            expected_citations.append(company_id)
    if text != expected:
        issues.append("requirements_text_or_item_citation_mismatch")
    if citations != expected_citations:
        issues.append("requirements_source_citation_mismatch")
    return {"checked": True, "supported": not issues, "issues": issues}
