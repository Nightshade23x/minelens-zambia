"""Compare documented Mingomba capital expenditure estimates."""

import re
from decimal import Decimal


MINGOMBA_RE = re.compile(r"\bmingomba\b", re.I)

MONEY_RE = re.compile(
    '(?P<operator>>=|<=|>|<|~)?[ ]*[$][ ]*(?P<amount>[0-9]+(?:[.][0-9]+)?)[ ]*(?P<unit>billions?|bn|b|millions?|mn|m)\\b',
    re.IGNORECASE,
)

CITATION_RE = re.compile(r"\[(S[1-9]\d*)\]")


def extract_mingomba_capex(evidence: list[dict]) -> list[dict]:
    """Extract source-attributed estimates, without merging qualifiers."""

    estimates = []
    seen = set()

    for item in evidence:
        source_id = str(item.get("source_id") or "")
        text = str(item.get("text") or "")

        if not re.fullmatch(r"S[1-9]\d*", source_id):
            continue

        for occurrence in MINGOMBA_RE.finditer(text):
            segment = text[
                occurrence.end():occurrence.end() + 220
            ]

            # Stop at the following projects in the Compact's table.
            segment = re.split(
                r"\b(?:Enterprise\s+Nickel|"
                r"Luongo\s+Manganese|Mopani\s+Copper|"
                r"Lumwana\s+Copper|Konkola\s+Copper)\b",
                segment,
                maxsplit=1,
                flags=re.I,
            )[0]

            for match in MONEY_RE.finditer(segment):
                prefix = segment[
                    max(0, match.start() - 140):
                    match.start()
                ]

                # Prevent unrelated monetary values being attributed
                # to Mingomba simply because they are nearby.
                if not re.search(
                    r"\b(?:capex|capital expenditure|"
                    r"production potential)\b",
                    prefix,
                    re.I,
                ):
                    continue

                scale = (
                    1_000_000_000
                    if match.group("unit").lower().startswith("b")
                    else 1_000_000
                )

                amount_usd = int(
                    Decimal(match.group("amount")) * scale
                )

                operator = {
                    "?": ">=",
                    "?": "<=",
                    "?": "~",
                }.get(
                    match.group("operator") or "reported",
                    match.group("operator") or "reported",
                )

                key = (
                    source_id,
                    amount_usd,
                    operator,
                    str(item.get("pages")),
                )

                if key in seen:
                    break

                seen.add(key)

                estimates.append({
                    "source_id": source_id,
                    "document": str(
                        item.get("document") or ""
                    ),
                    "pages": str(item.get("pages") or ""),
                    "canonical_source_id": str(
                        item.get("canonical_source_id") or ""
                    ),
                    "amount_usd": amount_usd,
                    "operator": operator,
                    "quoted_amount": match.group(0).strip(),
                    "expected": bool(
                        re.search(r"\bexpected\b", prefix, re.I)
                    ),
                })

                break

    return sorted(
        estimates,
        key=lambda row: (
            int(row["source_id"][1:]),
            row["amount_usd"],
        ),
    )


def analyze_mingomba_capex(evidence: list[dict]) -> dict:
    """Classify different source formulations without declaring conflict."""

    estimates = extract_mingomba_capex(evidence)

    amounts = {row["amount_usd"] for row in estimates}
    formulations = {
        (row["amount_usd"], row["operator"])
        for row in estimates
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

    documents = {
        row["canonical_source_id"] or row["document"]
        for row in estimates
    }

    return {
        "status": status,
        "estimates": estimates,
        "distinct_documents": len(documents),
        "requires_comparison": status in (
            "qualifier_difference",
            "different_values",
        ),
    }


def audit_mingomba_answer(
    evidence: list[dict],
    answer: str,
) -> dict:
    """Flag relevant estimate citations omitted by an answer."""

    analysis = analyze_mingomba_capex(evidence)

    source_ids = {
        row["source_id"]
        for row in analysis["estimates"]
    }

    cited = set(CITATION_RE.findall(answer))

    missing = sorted(source_ids - cited)

    requires_comparison = analysis["requires_comparison"]

    return {
        "status": analysis["status"],
        "requires_comparison": requires_comparison,
        "complete_comparison": (
            not missing if requires_comparison else None
        ),
        "missing_source_ids": (
            missing if requires_comparison else []
        ),
    }


def draft_mingomba_comparison(
    evidence: list[dict],
) -> str | None:
    """Create a source-grounded comparison for distinct estimates."""

    analysis = analyze_mingomba_capex(evidence)

    if not analysis["requires_comparison"]:
        return None

    parts = []

    for row in analysis["estimates"]:
        description = row["quoted_amount"]

        if row["expected"]:
            description = "an expected " + description

        page_label = (
            f" (page {row['pages']})"
            if row["pages"]
            else ""
        )

        parts.append(
            f"{description} [{row['source_id']}]{page_label}"
        )

    if len(analysis["estimates"]) == 2:
        detail = " and ".join(parts)
    else:
        detail = "; ".join(parts)

    answer = (
        "The available Mingomba project evidence gives "
        "different capital expenditure estimates: "
        + detail + "."
    )

    if analysis["distinct_documents"] == 1:
        answer += (
            " These are different passages within the same "
            "document, not independent confirmations."
        )

    answer += (
        " The retrieved evidence does not establish which "
        "estimate is newer or a confirmed final cost."
    )

    return answer
