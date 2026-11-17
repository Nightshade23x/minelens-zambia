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


# MINELENS_LML_SUPPORT_V2
def validate_large_scale_mining_requirements_support(
    question: str,
    evidence: list[dict],
    answer_result: dict,
) -> dict:
    """Check the exact Form I list plus any correctly scoped LML additions."""
    from app.large_scale_requirements import build_large_scale_mining_requirements_answer
    from app.lml_source_scope import _get_passage, supplement_lml_answer

    unchecked = {"checked": False, "supported": None, "issues": []}
    if answer_result.get("generation_method") != "deterministic-mining-requirements":
        return unchecked
    if not re.search(r"large[-\s]*scale", question, re.I):
        return unchecked
    if not re.search(r"mining\s+licen[cs]e", question, re.I):
        return unchecked

    expected = build_large_scale_mining_requirements_answer(question, evidence)
    if expected is None:
        return unchecked

    beginning = _get_passage(evidence, "lml_beginning")
    continuation = _get_passage(evidence, "lml_continuation")
    if (beginning is None) != (continuation is None):
        # Partial ministry sections cannot verify the full checklist.
        return unchecked
    if beginning is not None:
        expected = supplement_lml_answer(question, evidence, expected)

    issues = []
    if str(answer_result.get("answer") or "") != expected["answer"]:
        issues.append("requirements_text_or_item_citation_mismatch")
    if list(answer_result.get("citations") or []) != expected["citations"]:
        issues.append("requirements_source_citation_mismatch")
    return {"checked": True, "supported": not issues, "issues": issues}
