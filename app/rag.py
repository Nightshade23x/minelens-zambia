from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request

from typing import Any

from app.evidence import (
    evidence_sources,
    evidence_to_context,
)
from app.context_expansion import (
    is_list_query,
)

# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

DEFAULT_OLLAMA_URL = (
    "http://127.0.0.1:11434"
)

DEFAULT_TIMEOUT_SECONDS = 120

OLLAMA_MODEL_ENV = (
    "MINELENS_OLLAMA_MODEL"
)

OLLAMA_URL_ENV = (
    "MINELENS_OLLAMA_URL"
)


PREFERRED_MODELS = (
    "qwen3:4b-instruct-2507-q4_K_M",
    "qwen3:4b",
    "llama3.2:3b",
    "qwen2.5:7b",
    "llama3.1:8b",
    "mistral:7b",
)


SYSTEM_PROMPT = """
You are MineLens Zambia, a mining intelligence assistant.

Answer ONLY from the evidence supplied to you.

Rules:

1. Do not invent facts or use outside knowledge.
2. If the evidence is insufficient, say so clearly.
3. Cite factual claims using [S1], [S2], etc.
4. Never cite a source label that was not supplied.
5. Prefer short, direct answers.
6. Preserve exact licence codes, company names, decisions,
   locations, areas, dates, quantities and monetary values.
7. Do not reinterpret field meanings. For example, a field
   called "deadline" or "stipulated timeframe" must not be
   described as a compliance deadline unless the evidence
   explicitly says that.
8. Tables may contain both FEE UNITS and AMOUNT (K).
   Never confuse fee units with the monetary amount.
9. Do not expand the symbol "K" into a currency name unless
   the evidence itself gives that currency name.
10. Do not combine application fees with area charges unless
    the question asks for both.
11. Do not add a Sources section. MineLens adds sources
    separately.
12. If the question asks for a list, categories, types,
    requirements, objectives, minerals, companies or other
    multiple items, include all clearly relevant items that
    are explicitly present in the supplied evidence. Do not
    stop after the first item.
13. When the evidence explicitly lists actions, capabilities,
    skills, expertise, requirements, objectives, challenges,
    or responsibilities relevant to the question, treat those
    listed items as the answer. Do not claim the information is
    unspecified merely because the source describes the items
    as actions or capabilities rather than using exactly the
    same wording as the question.
""".strip()


# ---------------------------------------------------------
# General helpers
# ---------------------------------------------------------

def clean_text(
    value: Any,
) -> str:
    """
    Convert a value into clean single-spaced text.
    """

    if value is None:
        return ""

    return " ".join(
        str(value).split()
    )


def normalized_query(
    value: str,
) -> str:
    """
    Lower-case query normalization.
    """

    text = value.lower()

    text = re.sub(
        r"[‐-–—]",
        "-",
        text,
    )

    return " ".join(
        text.split()
    )


# ---------------------------------------------------------
# Ollama helpers
# ---------------------------------------------------------

def get_ollama_base_url() -> str:
    """
    Return configured Ollama base URL.
    """

    return (
        os.environ.get(
            OLLAMA_URL_ENV,
            DEFAULT_OLLAMA_URL,
        )
        .strip()
        .rstrip("/")
    )


def request_json(
    url: str,
    method: str = "GET",
    payload: dict | None = None,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict:
    """
    Send a JSON request using Python's standard library.
    """

    data = None

    headers = {
        "Content-Type": (
            "application/json"
        ),
    }

    if payload is not None:

        data = json.dumps(
            payload
        ).encode(
            "utf-8"
        )

    request = urllib.request.Request(
        url=url,
        data=data,
        headers=headers,
        method=method,
    )

    try:

        with urllib.request.urlopen(
            request,
            timeout=timeout,
        ) as response:

            raw = response.read()

    except urllib.error.HTTPError as error:

        raise RuntimeError(
            "Ollama returned HTTP error "
            f"{error.code}."
        ) from error

    except urllib.error.URLError as error:

        raise RuntimeError(
            "Could not connect to Ollama. "
            "Make sure Ollama is running."
        ) from error

    except TimeoutError as error:

        raise RuntimeError(
            "Ollama request timed out."
        ) from error

    try:

        parsed = json.loads(
            raw.decode(
                "utf-8"
            )
        )

    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as error:

        raise RuntimeError(
            "Ollama returned invalid JSON."
        ) from error

    if not isinstance(
        parsed,
        dict,
    ):

        raise RuntimeError(
            "Ollama returned an unexpected "
            "response format."
        )

    return parsed


def get_installed_models(
    base_url: str | None = None,
) -> list[str]:
    """
    Ask Ollama which models are installed locally.
    """

    if base_url is None:

        base_url = (
            get_ollama_base_url()
        )

    response = request_json(
        url=(
            f"{base_url}/api/tags"
        ),
        method="GET",
    )

    models = response.get(
        "models",
        [],
    )

    installed: list[str] = []

    for model in models:

        if not isinstance(
            model,
            dict,
        ):
            continue

        name = model.get(
            "name"
        )

        if name:

            installed.append(
                str(
                    name
                )
            )

    return installed


def select_ollama_model(
    installed_models: list[str],
    requested_model: str | None = None,
) -> str:
    """
    Choose which installed Ollama model MineLens uses.
    """

    environment_model = (
        os.environ.get(
            OLLAMA_MODEL_ENV
        )
    )

    selected = (
        requested_model
        or environment_model
    )

    if selected:

        selected = (
            selected.strip()
        )

        if (
            selected
            not in installed_models
        ):

            raise RuntimeError(
                "Requested Ollama model "
                f"'{selected}' is not installed. "
                "Installed models: "
                + (
                    ", ".join(
                        installed_models
                    )
                    if installed_models
                    else "none"
                )
            )

        return selected

    if not installed_models:

        raise RuntimeError(
            "Ollama is running, but no "
            "local models are installed."
        )

    for preferred in (
        PREFERRED_MODELS
    ):

        if (
            preferred
            in installed_models
        ):

            return preferred

    return installed_models[
        0
    ]


# ---------------------------------------------------------
# Prompt building
# ---------------------------------------------------------

def build_user_prompt(
    question: str,
    evidence: list[dict],
    correction: str | None = None,
) -> str:
    """
    Build the grounded prompt supplied to Ollama.
    """

    if not question.strip():

        raise ValueError(
            "Question must not be empty."
        )

    if not evidence:

        return (
            "Question:\n"
            f"{question.strip()}\n\n"
            "Evidence:\n"
            "No evidence was retrieved.\n\n"
            "State that the available evidence "
            "is insufficient."
        )

    context = evidence_to_context(
        evidence
    )

    prompt = (
        "Question:\n"
        f"{question.strip()}\n\n"
        "Evidence:\n"
        f"{context}\n\n"
    )

    if correction:

        prompt += (
            "IMPORTANT: A previous answer failed "
            "MineLens grounding validation.\n"
            f"Validation problem: {correction}\n\n"
            "Rewrite the answer conservatively. "
            "Do not repeat the unsupported claim.\n\n"
        )

    prompt += (
        "Write the final answer now. "
        "Use [S1], [S2], etc. immediately "
        "after the claims they support."
    )

    return prompt


# ---------------------------------------------------------
# Citation validation
# ---------------------------------------------------------

CITATION_PATTERN = re.compile(
    r"\[S(\d+)\]",
    flags=re.IGNORECASE,
)


def extract_citations(
    answer: str,
) -> list[str]:
    """
    Return unique source citations in order.
    """

    citations: list[str] = []

    seen: set[str] = set()

    for match in (
        CITATION_PATTERN.finditer(
            answer
        )
    ):

        citation = (
            "S"
            + match.group(
                1
            )
        )

        if citation in seen:
            continue

        seen.add(
            citation
        )

        citations.append(
            citation
        )

    return citations


def validate_citations(
    answer: str,
    evidence: list[dict],
) -> list[str]:
    """
    Ensure the answer only uses real evidence IDs.
    """

    citations = extract_citations(
        answer
    )

    valid_ids = {
        str(
            item.get(
                "source_id"
            )
        )
        for item in evidence
    }

    invalid = [
        citation
        for citation in citations
        if citation
        not in valid_ids
    ]

    if invalid:

        raise RuntimeError(
            "The generated answer used "
            "invalid citation(s): "
            + ", ".join(
                invalid
            )
        )

    return citations


# ---------------------------------------------------------
# Grounding validation
# ---------------------------------------------------------

INSUFFICIENT_PHRASES = (
    "insufficient",
    "not enough information",
    "does not provide enough",
    "cannot determine",
    "unable to determine",
)


CURRENCY_WORDS = (
    "kwacha",
    "kiswahili",
    "shilling",
    "dollar",
    "euro",
    "pound",
    "rand",
)


NUMBER_PATTERN = re.compile(
    r"(?<![A-Za-z])"
    r"\d[\d,]*(?:\.\d+)?"
    r"%?"
)

def repair_single_source_list_citation(
    question: str,
    answer: str,
    evidence: list[dict],
) -> str:
    """
    Repair a missing citation for a list-style question
    only when exactly one evidence source was supplied.

    The answer content is not changed. MineLens only
    appends the sole available source label.
    """

    if not is_list_query(
        question
    ):

        return answer

    if len(
        evidence
    ) != 1:

        return answer

    if extract_citations(
        answer
    ):

        return answer

    source_id = clean_text(
        evidence[
            0
        ].get(
            "source_id"
        )
    )

    if not source_id:

        return answer

    cleaned_answer = (
        answer.rstrip()
    )

    if cleaned_answer.endswith(
        "."
    ):

        return (
            f"{cleaned_answer} "
            f"[{source_id}]"
        )

    return (
        f"{cleaned_answer}. "
        f"[{source_id}]"
    )
def answer_says_insufficient(
    answer: str,
) -> bool:
    """
    Detect an explicit insufficiency response.
    """

    lowered = answer.lower()

    return any(
        phrase in lowered
        for phrase in (
            INSUFFICIENT_PHRASES
        )
    )


def normalize_number(
    value: str,
) -> str:
    """
    Normalize numbers for evidence comparison.
    """

    cleaned = (
        value
        .replace(",", "")
        .replace("%", "")
        .strip()
    )

    try:

        number = float(
            cleaned
        )

    except ValueError:

        return cleaned

    if number.is_integer():

        return str(
            int(
                number
            )
        )

    return (
        f"{number:.10f}"
        .rstrip("0")
        .rstrip(".")
    )


def extract_numbers(
    text: str,
) -> set[str]:
    """
    Extract normalized numeric values.
    """

    without_citations = (
        CITATION_PATTERN.sub(
            "",
            text,
        )
    )

    return {
        normalize_number(
            match.group(
                0
            )
        )
        for match in (
            NUMBER_PATTERN.finditer(
                without_citations
            )
        )
    }


def validate_numeric_grounding(
    answer: str,
    evidence: list[dict],
) -> None:
    """
    Reject numeric claims that do not appear anywhere in
    the supplied evidence.

    This does not prove that every number was interpreted
    correctly, but it blocks fabricated numeric values.
    """

    answer_numbers = (
        extract_numbers(
            answer
        )
    )

    if not answer_numbers:

        return

    evidence_text = (
        evidence_to_context(
            evidence
        )
    )

    evidence_numbers = (
        extract_numbers(
            evidence_text
        )
    )

    unsupported = sorted(
        answer_numbers
        - evidence_numbers
    )

    if unsupported:

        raise RuntimeError(
            "Answer contains unsupported "
            "numeric value(s): "
            + ", ".join(
                unsupported
            )
        )


def validate_currency_language(
    answer: str,
    evidence: list[dict],
) -> None:
    """
    Stop the model from expanding currency symbols using
    outside knowledge.
    """

    answer_lower = (
        answer.lower()
    )

    evidence_lower = (
        evidence_to_context(
            evidence
        ).lower()
    )

    unsupported: list[str] = []

    for word in (
        CURRENCY_WORDS
    ):

        if (
            word in answer_lower
            and word not in evidence_lower
        ):

            unsupported.append(
                word
            )

    if unsupported:

        raise RuntimeError(
            "Answer introduced unsupported "
            "currency terminology: "
            + ", ".join(
                unsupported
            )
        )


def validate_answer_grounding(
    question: str,
    answer: str,
    evidence: list[dict],
) -> list[str]:
    """
    Run lightweight deterministic checks over a generated
    document answer.
    """

    citations = validate_citations(
        answer=answer,
        evidence=evidence,
    )

    if (
        evidence
        and not citations
        and not answer_says_insufficient(
            answer
        )
    ):

        raise RuntimeError(
            "Generated factual answer contains "
            "no evidence citation."
        )

    validate_numeric_grounding(
        answer=answer,
        evidence=evidence,
    )

    validate_currency_language(
        answer=answer,
        evidence=evidence,
    )

    return citations


# ---------------------------------------------------------
# Source selection
# ---------------------------------------------------------

def filter_sources_by_citations(
    evidence: list[dict],
    citations: list[str],
) -> list[dict]:
    """
    Display only sources actually cited in the answer.
    """

    all_sources = (
        evidence_sources(
            evidence
        )
    )

    if not citations:

        return []

    wanted = set(
        citations
    )

    return [
        source
        for source in all_sources
        if source.get(
            "source_id"
        )
        in wanted
    ]


# ---------------------------------------------------------
# Deterministic licensing answers
# ---------------------------------------------------------

def format_location(
    record: dict,
) -> str:
    """
    Create a readable location from structured fields.
    """

    districts = record.get(
        "districts",
        [],
    )

    if isinstance(
        districts,
        list,
    ):

        district_text = ", ".join(
            clean_text(
                district
            )
            for district in districts
            if clean_text(
                district
            )
        )

    else:

        district_text = clean_text(
            districts
        )

    province = clean_text(
        record.get(
            "province"
        )
    )

    if (
        district_text
        and province
    ):

        return (
            f"{district_text}, "
            f"{province} Province"
        )

    return (
        district_text
        or province
    )


def licensing_record_summary(
    evidence_item: dict,
) -> str:
    """
    Format one licensing record without using an LLM.
    """

    source_id = clean_text(
        evidence_item.get(
            "source_id"
        )
    )

    record = evidence_item.get(
        "record",
        {},
    )

    licence_code = clean_text(
        record.get(
            "licence_code"
        )
    )

    licence_type = clean_text(
        record.get(
            "licence_type"
        )
    )

    applicant = clean_text(
        record.get(
            "applicant"
        )
    )

    decision = clean_text(
        record.get(
            "decision"
        )
    )

    location = format_location(
        record
    )

    area_text = clean_text(
        record.get(
            "area_text"
        )
    )

    if not area_text:

        area_hectares = (
            record.get(
                "area_hectares"
            )
        )

        if area_hectares is not None:

            area_text = (
                f"{area_hectares} ha"
            )

    deadline = clean_text(
        record.get(
            "deadline"
        )
    )

    commodities = record.get(
        "commodities",
        [],
    )

    if isinstance(
        commodities,
        list,
    ):

        commodity_text = ", ".join(
            clean_text(
                commodity
            )
            for commodity in commodities
            if clean_text(
                commodity
            )
        )

    else:

        commodity_text = clean_text(
            commodities
        )

    sentences: list[str] = []

    first_sentence = ""

    if licence_code:

        first_sentence += (
            f"Licence {licence_code}"
        )

    else:

        first_sentence += (
            "The licence record"
        )

    if licence_type:

        first_sentence += (
            f" is a {licence_type} "
            "application"
        )

    if applicant:

        first_sentence += (
            f" by {applicant}"
        )

    first_sentence += "."

    sentences.append(
        first_sentence
    )
    if decision:

        sentences.append(
            f"The committee decision is {decision}."
        )
        

    if location:

        sentences.append(
            f"Location: {location}."
        )

    if area_text:

        sentences.append(
            f"Area: {area_text}."
        )

    if commodity_text:

        sentences.append(
            "Commodities: "
            f"{commodity_text}."
        )

    if deadline:

        sentences.append(
            "Stipulated timeframe: "
            f"{deadline}."
        )

    summary = " ".join(
        sentences
    )

    if source_id:

        summary += (
            f" [{source_id}]"
        )

    return summary


def generate_licensing_answer(
    evidence: list[dict],
) -> dict:
    """
    Generate licensing answers directly from structured
    records. No LLM is used.
    """

    if not evidence:

        return {
            "answer": (
                "No matching licensing "
                "evidence was retrieved."
            ),
            "model": None,
            "generation_method": (
                "deterministic-licensing"
            ),
            "citations": [],
            "sources": [],
        }

    summaries = [
        licensing_record_summary(
            item
        )
        for item in evidence
    ]

    if len(
        summaries
    ) == 1:

        answer = summaries[
            0
        ]

    else:

        lines = [
            (
                "The retrieved evidence contains "
                "the following matching "
                "licensing records:"
            )
        ]

        for summary in summaries:

            lines.append(
                f"- {summary}"
            )

        answer = "\n".join(
            lines
        )

    citations = [
        clean_text(
            item.get(
                "source_id"
            )
        )
        for item in evidence
        if clean_text(
            item.get(
                "source_id"
            )
        )
    ]

    return {
        "answer": answer,
        "model": None,
        "generation_method": (
            "deterministic-licensing"
        ),
        "citations": citations,
        "sources": (
            filter_sources_by_citations(
                evidence=evidence,
                citations=citations,
            )
        ),
    }


# ---------------------------------------------------------
# Deterministic application-fee extraction
# ---------------------------------------------------------

def fee_query_type(
    question: str,
) -> tuple[str, str] | None:
    """
    Infer a simple licence category and scale from a fee
    question.

    Returns:
        ("mining", "large")
        ("exploration", "small")
        ("processing", "all")
        etc.
    """

    query = normalized_query(
        question
    )

    fee_intent = (
        "fee" in query
        or "cost" in query
        or "how much" in query
        or "price" in query
    )

    if not fee_intent:

        return None

    # Do not confuse annual area charges or other
    # transactions with application fees.

    blocked_terms = (
        "area charge",
        "area charges",
        "transfer",
        "renewal",
        "renew ",
        "alteration",
        "alter ",
        "replacement",
    )

    if any(
        term in query
        for term in blocked_terms
    ):

        return None

    if (
        "mineral processing"
        in query
    ):

        return (
            "processing",
            "all",
        )

    if "exploration" in query:

        category = (
            "exploration"
        )

    elif "mining" in query:

        category = (
            "mining"
        )

    else:

        return None

    if re.search(
        r"\blarge[\s-]*scale\b",
        query,
    ):

        scale = "large"

    elif re.search(
        r"\bsmall[\s-]*scale\b",
        query,
    ):

        scale = "small"

    elif (
        "artisanal"
        in query
    ):

        scale = (
            "artisanal"
        )

    else:

        return None

    return (
        category,
        scale,
    )


def format_kwacha_amount(
    raw_amount: str,
) -> str:
    """
    Preserve the source's K notation while removing a
    redundant .00 suffix.
    """

    amount = clean_text(
        raw_amount
    )

    if amount.endswith(
        ".00"
    ):

        amount = amount[
            :-3
        ]

    return (
        f"K{amount}"
    )


def infer_application_fee(
    question: str,
    evidence: list[dict],
) -> dict | None:
    """
    Extract application fees deterministically from the
    flattened prescribed-fees table.

    This prevents an LLM from confusing FEE UNITS with
    AMOUNT (K).
    """

    query_type = fee_query_type(
        question
    )

    if query_type is None:

        return None

    category, scale = (
        query_type
    )

    exploration_pattern = re.compile(
        r"Exploration\s+Licen[cs]e"
        r"\s+\(a\)\s*Small[- ]scale"
        r"\s+\(b\)\s*Large[- ]scale"
        r"\s+([\d,]+)"
        r"\s+([\d,]+)"
        r"\s+([\d,]+(?:\.\d+)?)"
        r"\s+([\d,]+(?:\.\d+)?)",
        flags=re.IGNORECASE,
    )

    mining_pattern = re.compile(
        r"Mining\s+Licen[cs]e"
        r"\s+\(a\)\s*Artisanal"
        r"\s+\(b\)\s*Small[- ]scale"
        r"\s+\(c\)\s*Large[- ]scale"
        r"\s+([\d,]+)"
        r"\s+([\d,]+)"
        r"\s+([\d,]+)"
        r"\s+([\d,]+(?:\.\d+)?)"
        r"\s+([\d,]+(?:\.\d+)?)"
        r"\s+([\d,]+(?:\.\d+)?)",
        flags=re.IGNORECASE,
    )

    processing_pattern = re.compile(
        r"Mineral\s+Processing\s+"
        r"Licen[cs]e"
        r"\s+([\d,]+)"
        r"\s+([\d,]+(?:\.\d+)?)",
        flags=re.IGNORECASE,
    )

    for item in evidence:

        if (
            item.get(
                "evidence_type"
            )
            != "document"
        ):

            continue

        text = clean_text(
            item.get(
                "text"
            )
        )

        source_id = clean_text(
            item.get(
                "source_id"
            )
        )

        raw_amount: str | None = None

        if category == "exploration":

            match = (
                exploration_pattern.search(
                    text
                )
            )

            if not match:

                continue

            if scale == "small":

                raw_amount = (
                    match.group(
                        3
                    )
                )

            elif scale == "large":

                raw_amount = (
                    match.group(
                        4
                    )
                )

        elif category == "mining":

            match = (
                mining_pattern.search(
                    text
                )
            )

            if not match:

                continue

            amount_groups = {
                "artisanal": 4,
                "small": 5,
                "large": 6,
            }

            group_number = (
                amount_groups.get(
                    scale
                )
            )

            if group_number:

                raw_amount = (
                    match.group(
                        group_number
                    )
                )

        elif category == "processing":

            match = (
                processing_pattern.search(
                    text
                )
            )

            if not match:

                continue

            raw_amount = (
                match.group(
                    2
                )
            )

        if raw_amount:

            return {
                "category": (
                    category
                ),
                "scale": scale,
                "amount": (
                    format_kwacha_amount(
                        raw_amount
                    )
                ),
                "source_id": (
                    source_id
                ),
            }

    return None


def fee_type_label(
    category: str,
    scale: str,
) -> str:
    """
    Human-readable licence label.
    """

    if category == "processing":

        return (
            "mineral processing licence"
        )

    scale_labels = {
        "large": "large-scale",
        "small": "small-scale",
        "artisanal": "artisanal",
    }

    scale_label = (
        scale_labels.get(
            scale,
            scale,
        )
    )

    return (
        f"{scale_label} "
        f"{category} licence"
    )


def generate_fee_answer(
    question: str,
    evidence: list[dict],
) -> dict | None:
    """
    Return a deterministic fee answer when the prescribed
    fee table can be interpreted safely.
    """

    fee = infer_application_fee(
        question=question,
        evidence=evidence,
    )

    if fee is None:

        return None

    label = fee_type_label(
        category=fee[
            "category"
        ],
        scale=fee[
            "scale"
        ],
    )

    source_id = fee[
        "source_id"
    ]

    answer = (
        "The prescribed application fee for "
        f"a {label} is "
        f"{fee['amount']}. "
        f"[{source_id}]"
    )

    citations = [
        source_id
    ]

    return {
        "answer": answer,
        "model": None,
        "generation_method": (
            "deterministic-fee"
        ),
        "citations": citations,
        "sources": (
            filter_sources_by_citations(
                evidence=evidence,
                citations=citations,
            )
        ),
    }


# ---------------------------------------------------------
# Ollama generation
# ---------------------------------------------------------
# ---------------------------------------------------------
# Deterministic critical-minerals answers
# ---------------------------------------------------------

CRITICAL_MINERAL_NAMES = (
    "Lithium",
    "Tin",
    "Graphite",
    "Coltan (Columbite-Tantalum)",
    "Rare Earth Elements (REEs)",
    "Manganese",
    "Nickel",
)


def is_critical_minerals_list_query(
    question: str,
) -> bool:
    """
    Detect questions asking for Zambia's critical-mineral
    list rather than an explanation of critical minerals.
    """

    query = normalized_query(
        question
    )

    if (
        "critical mineral"
        not in query
    ):

        return False

    list_phrases = (
        "what are",
        "which",
        "list",
        "name",
        "identify",
    )

    return any(
        phrase in query
        for phrase in list_phrases
    )


def evidence_contains_phrase(
    evidence_item: dict,
    phrase: str,
) -> bool:
    """
    Case-insensitive phrase check against one evidence item.
    """

    text = clean_text(
        evidence_item.get(
            "text"
        )
    ).lower()

    return (
        phrase.lower()
        in text
    )


def extract_critical_minerals(
    evidence: list[dict],
) -> tuple[
    list[str],
    str | None,
]:
    """
    Extract supported critical-mineral names from retrieved
    evidence.

    Only canonical names that are explicitly present in the
    evidence are returned.
    """

    for item in evidence:

        if (
            item.get(
                "evidence_type"
            )
            != "document"
        ):

            continue

        text = clean_text(
            item.get(
                "text"
            )
        )

        text_lower = (
            text.lower()
        )

        # Make sure this really is the relevant occurrence
        # section rather than any random mention of critical
        # minerals.
        section_markers = (
            "occurrence of critical minerals",
            "notable the critical minerals",
            "notable critical minerals",
        )

        if not any(
            marker in text_lower
            for marker in section_markers
        ):

            continue

        minerals: list[str] = []

        checks = (
            (
                "Lithium",
                (
                    "lithium",
                ),
            ),
            (
                "Tin",
                (
                    "tin occurrences",
                    "tin tin occurrences",
                ),
            ),
            (
                "Graphite",
                (
                    "graphite occurrences",
                    "graphite graphite occurrences",
                ),
            ),
            (
                "Coltan (Columbite-Tantalum)",
                (
                    "coltan (columbite-tantalum)",
                    "coltan",
                ),
            ),
            (
                "Rare Earth Elements (REEs)",
                (
                    "rare earth elements (rees)",
                    "rare earth elements",
                ),
            ),
            (
                "Manganese",
                (
                    "manganese",
                ),
            ),
            (
                "Nickel",
                (
                    "nickel",
                ),
            ),
        )

        for canonical_name, phrases in checks:

            if any(
                phrase in text_lower
                for phrase in phrases
            ):

                minerals.append(
                    canonical_name
                )

        if minerals:

            source_id = clean_text(
                item.get(
                    "source_id"
                )
            )

            return (
                minerals,
                source_id,
            )

    return (
        [],
        None,
    )


def format_natural_list(
    items: list[str],
) -> str:
    """
    Format a list using commas and a final 'and'.
    """

    if not items:

        return ""

    if len(
        items
    ) == 1:

        return items[
            0
        ]

    if len(
        items
    ) == 2:

        return (
            f"{items[0]} and "
            f"{items[1]}"
        )

    return (
        ", ".join(
            items[
                :-1
            ]
        )
        + ", and "
        + items[
            -1
        ]
    )


def generate_critical_minerals_answer(
    question: str,
    evidence: list[dict],
) -> dict | None:
    """
    Generate Zambia's notable critical-minerals list
    directly from the official retrieved evidence.
    """

    if not is_critical_minerals_list_query(
        question
    ):

        return None

    minerals, source_id = (
        extract_critical_minerals(
            evidence
        )
    )

    if (
        not minerals
        or not source_id
    ):

        return None

    mineral_text = (
        format_natural_list(
            minerals
        )
    )

    answer = (
        "According to Zambia's National Critical "
        "Minerals Strategy, the notable critical "
        "minerals identified in the retrieved "
        f"section are {mineral_text}. "
        f"[{source_id}]"
    )

    citations = [
        source_id
    ]

    return {
        "answer": answer,
        "model": None,
        "generation_method": (
            "deterministic-critical-minerals"
        ),
        "citations": citations,
        "sources": (
            filter_sources_by_citations(
                evidence=evidence,
                citations=citations,
            )
        ),
    }
def call_ollama_generate(
    *,
    base_url: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    timeout: int,
) -> str:
    """
    Make one non-streaming Ollama generation request.
    """

    response = request_json(
        url=(
            f"{base_url}/api/generate"
        ),
        method="POST",
        payload={
            "model": model,
            "system": system_prompt,
            "prompt": user_prompt,
            "stream": False,
            "options": {
                "temperature": 0.0,
            },
        },
        timeout=timeout,
    )

    answer = str(
        response.get(
            "response",
            "",
        )
    ).strip()

    if not answer:

        raise RuntimeError(
            "Ollama returned an empty answer."
        )

    return answer


def generate_ollama_answer(
    question: str,
    evidence: list[dict],
    model: str | None = None,
    base_url: str | None = None,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict:
    """
    Generate and validate a grounded document answer.

    One correction attempt is allowed if deterministic
    grounding checks reject the first answer.
    """

    if base_url is None:

        base_url = (
            get_ollama_base_url()
        )

    installed_models = (
        get_installed_models(
            base_url=base_url
        )
    )

    selected_model = (
        select_ollama_model(
            installed_models=(
                installed_models
            ),
            requested_model=model,
        )
    )

    first_prompt = build_user_prompt(
        question=question,
        evidence=evidence,
    )

    first_answer = (
        call_ollama_generate(
            base_url=base_url,
            model=selected_model,
            system_prompt=(
                SYSTEM_PROMPT
            ),
            user_prompt=(
                first_prompt
            ),
            timeout=timeout,
        )
    )
    first_answer = (
        repair_single_source_list_citation(
            question=question,
            answer=first_answer,
            evidence=evidence,
        )
    )
    try:

        citations = (
            validate_answer_grounding(
                question=question,
                answer=first_answer,
                evidence=evidence,
            )
        )

        final_answer = (
            first_answer
        )

    except RuntimeError as error:

        correction_prompt = (
            build_user_prompt(
                question=question,
                evidence=evidence,
                correction=str(
                    error
                ),
            )
        )

        second_answer = (
            call_ollama_generate(
                base_url=base_url,
                model=selected_model,
                system_prompt=(
                    SYSTEM_PROMPT
                ),
                user_prompt=(
                    correction_prompt
                ),
                timeout=timeout,
            )
        )
        second_answer = (
            repair_single_source_list_citation(
                question=question,
                answer=second_answer,
                evidence=evidence,
            )
        )
        citations = (
            validate_answer_grounding(
                question=question,
                answer=second_answer,
                evidence=evidence,
            )
        )

        final_answer = (
            second_answer
        )

    return {
        "answer": final_answer,
        "model": selected_model,
        "generation_method": (
            "ollama"
        ),
        "citations": citations,
        "sources": (
            filter_sources_by_citations(
                evidence=evidence,
                citations=citations,
            )
        ),
    }


# ---------------------------------------------------------
# Source display
# ---------------------------------------------------------

def format_source(
    source: dict,
) -> str:
    """
    Convert source metadata to readable output.
    """

    source_id = source.get(
        "source_id"
    )

    title = source.get(
        "title"
    )

    pages = source.get(
        "pages"
    )

    source_url = source.get(
        "source_url"
    )

    line = (
        f"[{source_id}] "
        f"{title}"
    )

    if pages:

        line += (
            f", pp. {pages}"
        )

    if source_url:

        line += (
            f"\n    {source_url}"
        )

    return line


def display_answer(
    rag_result: dict,
) -> None:
    """
    Display final MineLens answer and cited sources.
    """

    print()
    print(
        "=" * 72
    )

    print(
        "MINELENS ANSWER"
    )

    print(
        "=" * 72
    )

    print()
    print(
        rag_result[
            "answer"
        ]
    )

    sources = rag_result.get(
        "sources",
        [],
    )

    if sources:

        print()
        print(
            "Sources:"
        )

        for source in sources:

            print()

            print(
                format_source(
                    source
                )
            )

    generation_method = (
        rag_result.get(
            "generation_method"
        )
    )

    model = rag_result.get(
        "model"
    )

    print()

    if model:

        print(
            "Model: "
            f"{model}"
        )

    elif generation_method:

        print(
            "Generator: "
            f"{generation_method}"
        )


# ---------------------------------------------------------
# Unified answer interface
# ---------------------------------------------------------

def answer_from_evidence(
    question: str,
    evidence: list[dict],
    model: str | None = None,
) -> dict:
    """
    Public MineLens answer-generation interface.

    High-confidence structured cases are answered
    deterministically. Ollama is only used when needed.
    """

    if not question.strip():

        raise ValueError(
            "Question must not be empty."
        )

    if not evidence:

        return {
            "answer": (
                "The available evidence is "
                "insufficient to answer this "
                "question."
            ),
            "model": None,
            "generation_method": (
                "no-evidence"
            ),
            "citations": [],
            "sources": [],
        }

    evidence_types = {
        item.get(
            "evidence_type"
        )
        for item in evidence
    }

    if evidence_types == {
        "licensing_record"
    }:

        return generate_licensing_answer(
            evidence
        )

    fee_answer = generate_fee_answer(
        question=question,
        evidence=evidence,
    )

    if fee_answer is not None:

        return fee_answer
    critical_minerals_answer = (
        generate_critical_minerals_answer(
            question=question,
            evidence=evidence,
        )
    )

    if (
        critical_minerals_answer
        is not None
    ):

        return (
            critical_minerals_answer
        )
    if is_list_query(
        question
    ):

        evidence = evidence[
            :1
    ]
    return generate_ollama_answer(
        question=question,
        evidence=evidence,
        model=model,
    )