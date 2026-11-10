"""Validate the structural integrity of MineLens citations."""

import re
from collections import Counter


CITATION_PATTERN = re.compile(r"^S[1-9][0-9]*$")


def validate_citation_integrity(answer_result: dict) -> dict:
    """Check citation references against returned source metadata."""

    answer = str(answer_result.get("answer") or "")
    citations = [
        str(value)
        for value in (answer_result.get("citations") or [])
    ]

    sources = answer_result.get("sources") or []

    source_ids = [
        str(source.get("source_id") or "")
        for source in sources
        if isinstance(source, dict)
    ]

    inline_ids = []

    for contents in re.findall(r"\[([^\[\]]+)\]", answer):
        inline_ids.extend(
            re.findall(r"\bS\d+\b", contents)
        )

    issues = []

    for label, values in (
        ("declared citation", citations),
        ("inline citation", inline_ids),
        ("source ID", source_ids),
    ):
        invalid = sorted({
            value for value in values
            if not CITATION_PATTERN.fullmatch(value)
        })

        if invalid:
            issues.append(
                f"Invalid {label}: {invalid}"
            )

    if len(citations) != len(set(citations)):
        issues.append("Duplicate declared citations.")

    if len(source_ids) != len(set(source_ids)):
        issues.append("Duplicate source IDs.")

    inline_set = set(inline_ids)
    citation_set = set(citations)
    source_set = set(source_ids)

    missing_declarations = inline_set - citation_set
    unused_declarations = citation_set - inline_set
    missing_sources = citation_set - source_set

    if missing_declarations:
        issues.append(
            "Inline references missing from citation list: "
            + str(sorted(missing_declarations))
        )

    if unused_declarations:
        issues.append(
            "Declared citations missing from answer: "
            + str(sorted(unused_declarations))
        )

    if missing_sources:
        issues.append(
            "Citations without source metadata: "
            + str(sorted(missing_sources))
        )

    if any(not isinstance(source, dict) for source in sources):
        issues.append("Invalid source metadata entry.")

    return {
        "valid": not issues,
        "issues": issues,
        "inline_citations": sorted(inline_set),
        "declared_citations": sorted(citation_set),
        "source_ids": sorted(source_set),
    }
