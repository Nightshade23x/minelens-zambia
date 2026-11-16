"""Source-scoped factual checks for critical-minerals strategy lists."""

import re
import unicodedata


STRATEGY_ID = "national_critical_minerals_strategy_2024_2028"

MINERAL_NAMES = (
    "Lithium",
    "Tin",
    "Graphite",
    "Coltan (Columbite-Tantalum)",
    "Rare Earth Elements (REEs)",
    "Manganese",
    "Nickel",
)

MINERAL_SOURCE_MARKERS = (
    "lithium occurrences are located",
    "tin occurrences are reported",
    "graphite occurrences are widespread",
    "reported occurrences of coltan",
    "known occurrences of rare earth elements",
    "occurrences of manganese mineralization",
    "two well-known nickel deposits",
)

SKILL_BULLETS = (
    "Identify and restrict areas of potential deposits for bids by viable investors",
    "Meet the technical challenges of exploration, production, processing and refining",
    "Manage the sustainability of the critical minerals industry",
)


def normalize(text):
    value = unicodedata.normalize("NFKC", str(text or ""))
    return " ".join(value.split()).casefold()


def find_strategy_source(evidence, source_id):
    for item in evidence:
        if not isinstance(item, dict):
            continue

        if str(item.get("source_id")) != source_id:
            continue

        origin = " ".join(
            str(item.get(key) or "")
            for key in ("canonical_source_id", "document")
        )

        if (
            STRATEGY_ID in origin.casefold()
            or "critical_minerals_strategy" in origin.casefold()
        ):
            return item

    return None


def validate_critical_strategy_support(
    question: str,
    evidence: list[dict],
    answer_result: dict,
) -> dict:
    """Validate two supported strategy-list answer types."""

    unchecked = {
        "checked": False,
        "supported": None,
        "issues": [],
    }

    method = answer_result.get("generation_method")

    supported_methods = (
        "deterministic-critical-minerals",
        "deterministic-critical-skills",
    )

    if method not in supported_methods:
        return unchecked

    answer = str(answer_result.get("answer") or "")

    citations = [
        str(value)
        for value in (answer_result.get("citations") or [])
    ]

    if (
        len(citations) != 1
        or not re.fullmatch(r"S[1-9]\d*", citations[0])
    ):
        return {
            "checked": True,
            "supported": False,
            "issues": ["strategy_citation_mismatch"],
        }

    source_id = citations[0]
    source = find_strategy_source(evidence, source_id)

    if source is None:
        return {
            "checked": True,
            "supported": False,
            "issues": ["strategy_citation_mismatch"],
        }

    source_text = normalize(source.get("text"))

    if not source_text or f"[{source_id}]" not in answer:
        return {
            "checked": True,
            "supported": False,
            "issues": ["strategy_evidence_or_inline_citation_missing"],
        }

    issues = []

    if method == "deterministic-critical-minerals":
        if "critical mineral" not in question.casefold():
            return unchecked

        marker = (
            "among the notable the critical "
            "minerals in zambia include:"
        )

        start = source_text.find(marker)

        if start < 0:
            return unchecked

        section = source_text[start:]

        end = section.find("2.1.3 demand for critical")

        if end >= 0:
            section = section[:end]

        if not all(
            phrase in section
            for phrase in MINERAL_SOURCE_MARKERS
        ):
            issues.append(
                "mineral_not_supported_by_scoped_section"
            )

        match = re.search(
            r"identified in the retrieved section are\s+"
            r"(.+?)\.\s*\[S[1-9]\d*\]\s*$",
            answer,
            re.I | re.S,
        )

        if not match:
            issues.append("mineral_list_unrecognized")
        else:
            found = tuple(
                part.strip()
                for part in re.split(
                    r",\s*(?:and\s+)?|\s+and\s+(?=[A-Z])",
                    match.group(1),
                )
            )

            if found != MINERAL_NAMES:
                issues.append("mineral_list_not_supported")

    else:
        if not any(
            term in question.casefold()
            for term in ("skills", "expertise")
        ):
            return unchecked

        anchor = (
            "government needs to develop "
            "the skills and expertise to:"
        )

        if anchor not in source_text:
            return unchecked

        section = source_text[
            source_text.index(anchor):
        ].split("3. strategic vision", 1)[0]

        if not all(
            normalize(phrase) in section
            for phrase in SKILL_BULLETS
        ):
            issues.append("skill_not_supported_by_source")

        actual_bullets = [
            re.sub(r"[.;,]+$", "", line.strip())
            for line in re.findall(
                r"(?m)^\s*[-*]\s+(.+?)\s*$",
                answer,
            )
        ]

        if tuple(actual_bullets) != SKILL_BULLETS:
            issues.append("skill_list_not_supported")

    return {
        "checked": True,
        "supported": not issues,
        "issues": issues,
    }
