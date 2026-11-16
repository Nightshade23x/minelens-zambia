"""Form-I scoped extraction for Zambia large-scale mining applications.

Historical source-specific rules: not a live legal compliance determination.
"""

from __future__ import annotations

import re
import unicodedata

FORM_ID = "application_for_mining_right"

# Each description must be justified by the corresponding appendix number in
# Form I's large-scale MINING subsection, not by other licence categories.
REQUIREMENTS = (
    (1, "A comprehensive statement of mineral deposits, including known minerals, proved, estimated or inferred resources, ore resources and mining conditions", ("comprehensive statement", "mineral deposits", "mining conditions")),
    (2, "A feasibility study for mining operations, including forecast capital investment, estimated recovery rates, and proposed treatment and disposal of ore and minerals", ("feasibility study", "capital investment", "recovery rate", "treatment and disposal")),
    (3, "An approved Environmental Impact Statement", ("approved environmental impact statement",)),
    (4, "Details of expected infrastructure requirements", ("infrastructure requirements",)),
    (5, "Proposals for employment and training of citizens of Zambia", ("employment and training of citizens of zambia",)),
    (6, "Proposals for promotion of local business development", ("promotion of local business development",)),
    (7, "A tax clearance certificate issued under the Income Tax Act, Cap. 323", ("tax clearance certificate", "income tax act")),
    (8, "A plan of the proposed mining area", ("plan of proposed mining area",)),
    (9, "For gemstone projects, a plan for cutting, polishing and faceting gemstones in Zambia", ("in the case of gemstones", "cutting", "polishing", "faceting")),
    (10, "Any further information required by the Director of Mining Cadastre", ("any further information", "director of mining cadastre")),
)

INTRO = "The retrieved Form I lists these large-scale mining application appendices:"
COMPANY_NOTE = (
    "The application form also states that a large-scale or small-scale "
    "mining application shall only be made by a company."
)


def normalize(text: object) -> str:
    return " ".join(unicodedata.normalize("NFKC", str(text or "")).split()).casefold()


def _form_sources(evidence: list[dict]):
    for item in evidence:
        if not isinstance(item, dict):
            continue
        origin = normalize(item.get("canonical_source_id") or item.get("document"))
        if FORM_ID not in origin and "application_for_mining_right" not in origin:
            continue
        if item.get("source_authority") not in (None, "government"):
            continue
        source_id = str(item.get("source_id") or "")
        if not re.fullmatch(r"S[1-9]\d*", source_id):
            continue
        yield item


def large_scale_appendices(text: str) -> dict[int, list[str]]:
    """Parse only section '(b) Mining Licence - Large Scale'.

    The PDF's extracted text repeats appendices 8 and 9 in one chunk;
    preserve duplicate candidates and require a matching entry for each.
    """
    normalized = normalize(text)
    start = re.search(r"\(b\)\s*mining\s+licen[cs]e\s*[-\u2013]?\s*large[-\s]*scale\b", normalized)
    if not start:
        return {}
    remainder = normalized[start.end():]
    end = re.search(r"\(c\)\s*mining\s+licen[cs]e\s*[-\u2013]?\s*small[-\s]*scale\b", remainder)
    if not end:
        # A truncated document must not let a neighbouring section leak in.
        return {}
    section = remainder[:end.start()]
    matches = list(re.finditer(r"appendix\s+no\.?\s*(\d{1,2})\b", section))
    parsed: dict[int, list[str]] = {}
    for index, match in enumerate(matches):
        number = int(match.group(1))
        right = matches[index + 1].start() if index + 1 < len(matches) else len(section)
        parsed.setdefault(number, []).append(section[match.end():right].strip())
    return parsed


def verified_large_scale_source(evidence: list[dict]) -> dict | None:
    for item in _form_sources(evidence):
        sections = large_scale_appendices(item.get("text") or "")
        if all(
            any(all(anchor in part for anchor in anchors) for part in sections.get(number, []))
            for number, _, anchors in REQUIREMENTS
        ):
            return item
    return None


def company_rule_source(evidence: list[dict]) -> dict | None:
    phrase = "an application for large-scale or small-scale mining shall only be made by a company"
    for item in _form_sources(evidence):
        if phrase in normalize(item.get("text")):
            return item
    return None


def build_large_scale_mining_requirements_answer(question: str, evidence: list[dict]) -> dict | None:
    """Deterministic generator restricted to Form I's large-scale appendices."""
    if not re.search(r"large[-\s]*scale", question, re.I):
        return None
    if not re.search(r"mining\s+licen[cs]e", question, re.I):
        return None
    if not re.search(r"requirements?|application|need", question, re.I):
        return None
    source = verified_large_scale_source(evidence)
    if source is None:
        return None
    source_id = str(source["source_id"])
    bullets = [f"- {description}. [{source_id}]" for _, description, _ in REQUIREMENTS]
    answer = INTRO + "\n\n" + "\n".join(bullets)
    citations = [source_id]
    company = company_rule_source(evidence)
    if company is not None:
        company_id = str(company["source_id"])
        answer += "\n\n" + COMPANY_NOTE + f" [{company_id}]"
        if company_id not in citations:
            citations.append(company_id)
    return {
        "answer": answer,
        "model": None,
        "generation_method": "deterministic-mining-requirements",
        "citations": citations,
    }
