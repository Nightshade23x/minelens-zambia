"""Scope Zambia LML checklist additions to the correct retrieved passages.

This is deliberately conservative; it does not use a mention of Pegging
Certificate in a small-scale section as proof of the LML requirement.
"""

from __future__ import annotations

import re
from copy import deepcopy


def is_lml_requirements_query(query: str) -> bool:
    q = re.sub(r"[-_]+", " ", str(query).casefold())
    return (
        bool(re.search(r"\blarge\s+scale\b", q))
        and bool(re.search(r"\bmining\b", q))
        and bool(re.search(r"\blicen[cs]e\b", q))
        and bool(re.search(r"\b(requirements?|documents?|need|apply|application)\b", q))
        and not bool(re.search(r"\bexploration\b", q))
        and not bool(re.search(r"\b(fee|fees|cost|price|charges?)\b", q))
    )


def _raw_text(item: dict) -> str:
    if not isinstance(item, dict):
        return ""
    for key in ("text", "content", "chunk_text", "page_content", "snippet"):
        text = item.get(key)
        if isinstance(text, str) and len(text) > 40:
            return text
    for key in ("record", "chunk", "result", "document", "data", "metadata"):
        nested = item.get(key)
        if isinstance(nested, dict):
            text = _raw_text(nested)
            if text:
                return text
    return ""


def _kind(text: str) -> str | None:
    lowered = re.sub(r"\s+", " ", text).casefold()
    if (
        "mining licence - large scale" in lowered
        and "approved environmental impact statement" in lowered
        and "appendix no. 10" in lowered
    ):
        return "form_appendices"
    if "an application for large-scale or small-scale mining shall only be made by a company" in lowered:
        return "form_company"
    if (
        "mining rights (large scale) licence (lml)" in lowered
        and "duly completed form i" in lowered
        and "feasibility study" in lowered
    ):
        return "lml_beginning"
    if (
        "pegging certificate" in lowered
        and "detailed geographical report" in lowered
        and "25 years" in lowered
        and "environmental impact statement" in lowered
        and "mineral processing licence (mpl)" in lowered
    ):
        return "lml_continuation"
    return None


PRIORITY = {
    "form_appendices": 400,
    "form_company": 350,
    "lml_beginning": 300,
    "lml_continuation": 290,
}


def source_kinds(results: list[dict]) -> list[str | None]:
    return [_kind(_raw_text(item)) for item in results]


def prioritize_lml_results(
    results: list[dict],
    top_k: int,
    normalized_evidence: list[dict] | None = None,
) -> list[dict]:
    """Rank using normalized text when it contains additional context chunks.

    The raw hybrid hits can contain only the core chunk; evidence normalization
    may append adjacent context from the same source. Classify the normalized
    text, then reorder its corresponding raw hits (never invent source rows).
    """
    if normalized_evidence is not None:
        if len(results) != len(normalized_evidence):
            raise ValueError("Raw-to-normalized evidence length mismatch")
        for i, item in enumerate(normalized_evidence, start=1):
            if item.get("source_id") != f"S{i}":
                raise ValueError("Unexpected normalized evidence ranking")
        kinds = source_kinds(normalized_evidence)
    else:
        kinds = source_kinds(results)

    order = sorted(
        range(len(results)),
        key=lambda index: (-PRIORITY.get(kinds[index], 0), index),
    )
    return [results[index] for index in order[:top_k]]


def prioritize_lml_search_result(search_result: dict, top_k: int) -> dict:
    """Return an LML-focused result with raw hit metadata left intact."""
    from app.evidence import normalize_evidence

    raw = search_result.get("results")
    if search_result.get("route") != "documents" or not isinstance(raw, list):
        raise ValueError("Unexpected search route/result schema")

    normalized = normalize_evidence(
        search_result=search_result,
        max_evidence=len(raw),
    )

    required = {
        "form_appendices", "form_company",
        "lml_beginning", "lml_continuation",
    }
    kinds = set(source_kinds(normalized))
    if not required.issubset(kinds):
        raise ValueError(
            "Needed LML evidence missing after normalization: "
            + ", ".join(sorted(required - kinds))
        )

    ranked = dict(search_result)
    ranked["results"] = prioritize_lml_results(
        raw, top_k=top_k, normalized_evidence=normalized,
    )
    final = normalize_evidence(
        search_result=ranked,
        max_evidence=top_k,
    )
    missing = required - set(source_kinds(final))
    if missing:
        raise ValueError("LML priority preflight lost: " + ", ".join(sorted(missing)))
    return ranked


def _get_passage(evidence: list[dict], kind: str) -> dict | None:
    for item in evidence:
        if not isinstance(item, dict):
            continue
        source_id = str(item.get("source_id") or "")
        if not re.fullmatch(r"S[1-9]\d*", source_id):
            continue
        doc = str(item.get("canonical_source_id") or item.get("document") or "")
        expected_doc = (
            "application_for_mining_right"
            if kind.startswith("form_")
            else "mining_rights_requirements"
        )
        if expected_doc not in doc:
            continue
        if _kind(str(item.get("text") or "")) == kind:
            return item
    return None


def supplement_lml_answer(question: str, evidence: list[dict], base: dict | None) -> dict | None:
    """Append only claims supported by the scoped LML checklist excerpts."""
    if not is_lml_requirements_query(question) or not isinstance(base, dict):
        return base
    if base.get("generation_method") != "deterministic-mining-requirements":
        return base

    first = _get_passage(evidence, "lml_beginning")
    second = _get_passage(evidence, "lml_continuation")
    if first is None or second is None:
        return base

    s1 = first["source_id"]
    s2 = second["source_id"]
    if s1 == s2:
        return base

    # Each line is anchored to an identified section, not merely a PDF mention.
    addition = (
        "\n\nThe Ministry's separate Large Scale Mining Licence (LML) "
        "checklist also specifies:\n\n"
        f"- A completed Form I with coordinates fitting the cadastral grid. [{s1}]\n"
        f"- A detailed geographical report on the area and a Pegging Certificate. [{s2}]\n"
        f"- A statement of the requested duration, which should not exceed 25 years. [{s2}]\n"
        f"- Articles of Association, Certificate of Incorporation, and Certificate of Share Capital. [{s2}]\n"
        f"- NRC or passport copies for all shareholders. [{s2}]"
    )

    updated = deepcopy(base)
    updated["answer"] = str(base.get("answer") or "").rstrip() + addition
    citations = list(base.get("citations") or [])
    for source_id in (s1, s2):
        if source_id not in citations:
            citations.append(source_id)
    updated["citations"] = citations

    # Build metadata for every cited passage from the current evidence list.
    # This preserves citation-validation compatibility (including source URL).
    sources = []
    for item in evidence:
        if item.get("source_id") in citations:
            sources.append({k: v for k, v in item.items() if k not in ("text", "record")})
    updated["sources"] = sources
    return updated
