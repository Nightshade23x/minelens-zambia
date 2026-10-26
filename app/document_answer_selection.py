"""Query-focused selection of document evidence."""

from difflib import SequenceMatcher
import re


STOPWORDS = {
    "a", "an", "and", "are", "at", "by",
    "for", "from", "how", "in", "is",
    "of", "on", "the", "to", "what",
    "which", "who", "with",
}

ENTITY_EXCLUSIONS = {
    "what", "which", "where", "when",
    "who", "how", "zambia",
}

FINANCIAL_QUERY = re.compile(
    r"\b(capital|expenditure|capex|investment|cost|budget|funding)\b"
    r"|\bhow much\b",
    re.IGNORECASE,
)

MONEY_AMOUNT = re.compile(
    r"(?:US\s*)?\$\s*\d[\d,]*(?:\.\d+)?",
    re.IGNORECASE,
)


def important_tokens(value: str) -> list[str]:
    return [
        token
        for token in re.findall(
            r"[a-z0-9]+",
            value.casefold(),
        )
        if token not in STOPWORDS
    ]


def longest_phrase_match(
    query_tokens: list[str],
    text: str,
) -> int:
    tokens = important_tokens(text)

    return SequenceMatcher(
        None,
        query_tokens,
        tokens,
        autojunk=False,
    ).find_longest_match(
        0,
        len(query_tokens),
        0,
        len(tokens),
    ).size


def has_amount_near_name(
    text: str,
    name: str,
) -> bool:
    pattern = rf"\b{re.escape(name)}\b"

    for match in re.finditer(
        pattern,
        text,
        re.IGNORECASE,
    ):
        nearby = text[
            max(0, match.start() - 35):
            match.end() + 190
        ]

        if MONEY_AMOUNT.search(nearby):
            return True

    return False


def renumber_evidence(
    items: list[dict],
) -> list[dict]:
    return [
        {
            **item,
            "source_id": f"S{index}",
        }
        for index, item in enumerate(
            items,
            start=1,
        )
    ]


def select_document_answer_evidence(
    question: str,
    evidence: list[dict],
) -> list[dict]:
    """
    Reduce irrelevant document context before generation.

    Other evidence types are unchanged.
    Ambiguous selections retain all original evidence.
    """

    if len(evidence) < 3:
        return evidence

    if any(
        item.get("evidence_type") != "document"
        for item in evidence
    ):
        return evidence

    # Financial queries involving explicitly named entities.
    if FINANCIAL_QUERY.search(question):

        names = {
            name.casefold()
            for name in re.findall(
                r"\b[A-Z][a-z]{3,}\b",
                question,
            )
            if name.casefold() not in ENTITY_EXCLUSIONS
        }

        if names:
            matching = [
                item
                for item in evidence
                if any(
                    has_amount_near_name(
                        str(item.get("text", "")),
                        name,
                    )
                    for name in names
                )
            ]

            if 2 <= len(matching) < len(evidence):
                return renumber_evidence(matching)

    # Section-focused list questions.
    from app.rag import is_list_query

    if not is_list_query(question):
        return evidence

    query_tokens = important_tokens(question)

    if len(query_tokens) < 3:
        return evidence

    spans = [
        longest_phrase_match(
            query_tokens,
            str(item.get("text", "")),
        )
        for item in evidence
    ]

    best_span = max(spans, default=0)

    if best_span < 3:
        return evidence

    matching_titles = {
        item.get("title")
        for item, span in zip(evidence, spans)
        if span == best_span and item.get("title")
    }

    selected = [
        (item, span)
        for item, span in zip(evidence, spans)
        if (
            item.get("title") in matching_titles
            and span >= max(2, best_span - 2)
        )
    ]

    if not (1 < len(selected) < len(evidence)):
        return evidence

    # Put passages with the strongest phrase match first.
    selected.sort(
        key=lambda pair: -pair[1]
    )

    return renumber_evidence(
        [item for item, _ in selected]
    )
