from __future__ import annotations

import re

from app.context_expansion import (
    expand_document_results,
)
from app.embeddings import (
    SemanticIndex,
    load_embedding_cache,
    save_embedding_cache,
)
from app.hybrid import (
    DEFAULT_CANDIDATE_K,
    hybrid_search,
)
from app.licensing_search import (
    infer_decision,
    infer_licence_code,
    load_licensing_records,
    search_licensing_records,
)
from app.mining_statistics import (
    has_statistics_intent,
    load_mining_statistics,
    query_mining_statistics,
)
from app.search import (
    BM25Index,
    load_chunks,
)
from app.facility_search import (
    load_facilities,
    search_facilities as search_facility_records,
)

# ---------------------------------------------------------
# Routes
# ---------------------------------------------------------

ROUTE_DOCUMENTS = "documents"
ROUTE_LICENSING = "licensing"
ROUTE_MINING_STATISTICS = "mining_statistics"
ROUTE_FACILITIES = "facilities"

VALID_ROUTES = {
    ROUTE_DOCUMENTS,
    ROUTE_LICENSING,
    ROUTE_MINING_STATISTICS,
    ROUTE_FACILITIES,
}


# ---------------------------------------------------------
# Router configuration
# ---------------------------------------------------------

DOCUMENT_INTENT_PHRASES = (
    "fee",
    "fees",
    "application fee",
    "area charge",
    "area charges",
    "charge",
    "charges",
    "cost",
    "costs",
    "price",
    "how much",
    "requirement",
    "requirements",
    "required",
    "documents required",
    "information required",
    "what information",
    "application form",
    "application process",
    "how to apply",
    "who can apply",
    "eligible",
    "eligibility",
    "procedure",
    "process",
    "legislation",
    "law",
    "regulation",
    "regulations",
    "policy",
    "strategy",
    "statistics",
    "statistical",
    "production",
    "exports",
    "employment",
    "workforce",
    "gdp",
    "accident",
    "accidents",
    "beneficiation",
    "value addition",
    "critical minerals",
    "exploration targets",
    "investment policy",
)

STRUCTURED_ENTITY_PHRASES = (
    "applicant",
    "applicants",
    "company",
    "companies",
    "committee decision",
    "licence code",
    "license code",
    "decision",
    "decisions",
    "granted",
)

LISTING_WORDS = (
    "which",
    "who",
    "list",
    "show",
    "find",
)

LOCATION_PREPOSITIONS = (
    "in",
    "from",
    "within",
    "around",
    "near",
)
FACILITY_ENTITY_TERMS = (
    "mine",
    "mines",
    "plant",
    "plants",
    "refinery",
    "refineries",
    "smelter",
    "smelters",
    "facility",
    "facilities",
    "quarry",
    "quarries",
)

FACILITY_ATTRIBUTE_TERMS = (
    "who operates",
    "who operate",
    "operated by",
    "operator",
    "operating company",
    "who owns",
    "owner",
    "owners",
    "ownership",
    "equity",
    "shareholder",
    "shareholders",
    "capacity",
    "production capacity",
    "annual capacity",
    "where is",
    "where are",
    "located",
    "location",
    "active",
    "inactive",
    "operational",
)

FACILITY_GENERIC_NAME_TERMS = {
    "mine",
    "mines",
    "plant",
    "plants",
    "refinery",
    "refineries",
    "smelter",
    "smelters",
    "facility",
    "facilities",
    "quarry",
    "quarries",
}

MINING_RIGHT_REQUIREMENT_TERMS = (
    "requirement",
    "requirements",
    "required",
    "documents required",
    "information required",
    "what information",
    "need to provide",
    "must provide",
    "how to apply",
    "application process",
)

MINING_RIGHT_CONTEXT_TERMS = (
    "mining licence",
    "mining license",
    "mining licences",
    "mining licenses",
    "mining right",
    "mining rights",
    "exploration licence",
    "exploration license",
    "large-scale mining",
    "large scale mining",
    "small-scale mining",
    "small scale mining",
    "artisanal mining",
)

MINING_RIGHT_REQUIREMENT_SOURCE_IDS = {
    "mining_rights_requirements",
    "application_for_mining_right",
}


# ---------------------------------------------------------
# General helpers
# ---------------------------------------------------------

def normalize_query(
    query: str,
) -> str:
    """
    Normalize whitespace and casing for routing/search logic.
    """

    return " ".join(
        query.lower().split()
    )


def contains_term(
    text: str,
    term: str,
) -> bool:
    """
    Check a term using word boundaries for single words
    and substring matching for phrases.
    """

    if " " in term:
        return term in text

    return (
        re.search(
            rf"\b{re.escape(term)}\b",
            text,
        )
        is not None
    )


def contains_any(
    text: str,
    terms: tuple[str, ...],
) -> bool:
    """
    Return True if any configured term appears.
    """

    return any(
        contains_term(
            text,
            term,
        )
        for term in terms
    )


def chunk_source_id(
    chunk: dict,
) -> str:
    """
    Return a chunk's canonical MineLens source id.

    Older processed chunks do not always contain source_id,
    so known legacy filenames are mapped back to the source
    ids used by config/sources.json.
    """

    source_id = chunk.get(
        "source_id"
    )

    if source_id:
        return str(
            source_id
        ).strip()

    metadata = chunk.get(
        "metadata",
        {},
    )

    if isinstance(
        metadata,
        dict,
    ):
        source_id = metadata.get(
            "source_id"
        )

        if source_id:
            return str(
                source_id
            ).strip()

    candidate_values: list[str] = []

    for key in (
        "title",
        "document",
        "filename",
    ):
        value = chunk.get(
            key
        )

        if value:
            candidate_values.append(
                str(
                    value
                )
            )

    if isinstance(
        metadata,
        dict,
    ):
        for key in (
            "title",
            "document",
            "filename",
        ):
            value = metadata.get(
                key
            )

            if value:
                candidate_values.append(
                    str(
                        value
                    )
                )

    searchable = normalize_query(
        " ".join(
            candidate_values
        )
    ).replace(
        "-",
        "_",
    ).replace(
        " ",
        "_",
    )

    if (
        "mining_rights_requirements"
        in searchable
    ):
        return (
            "mining_rights_requirements"
        )

    if (
        "application_for_mining_right"
        in searchable
    ):
        return (
            "application_for_mining_right"
        )

    return ""


def chunk_title(
    chunk: dict,
) -> str:
    """
    Return the best available human-readable chunk title.
    """

    for key in (
        "title",
        "document",
    ):
        value = chunk.get(
            key
        )

        if value:
            return str(
                value
            ).strip()

    metadata = chunk.get(
        "metadata",
        {},
    )

    if isinstance(
        metadata,
        dict,
    ):
        for key in (
            "title",
            "document",
        ):
            value = metadata.get(
                key
            )

            if value:
                return str(
                    value
                ).strip()

    return ""


# ---------------------------------------------------------
# Licensing-context helpers
# ---------------------------------------------------------

def has_licensing_context(
    query: str,
) -> bool:
    """
    Determine whether a query talks about mining licensing
    records.

    Document intent such as fees or requirements still has
    higher routing priority.
    """

    normalized = normalize_query(
        query
    )

    if re.search(
        r"\blicen[cs](?:e|es)\b",
        normalized,
    ):
        return True

    if re.search(
        r"\b(?:mining|exploration)\s+rights?\b",
        normalized,
    ):
        return True

    if (
        "artisanal mining right"
        in normalized
    ):
        return True

    if re.search(
        (
            r"\b(?:mining|exploration|"
            r"mineral processing|artisanal)"
            r"\b.*\bapplications?\b"
        ),
        normalized,
    ):
        return True

    return False


def has_plural_licensing_context(
    query: str,
) -> bool:
    """
    Detect plural licensing language.
    """

    normalized = normalize_query(
        query
    )

    if re.search(
        r"\blicen[cs]es\b",
        normalized,
    ):
        return True

    if re.search(
        r"\b(?:mining|exploration)\s+rights\b",
        normalized,
    ):
        return True

    return False


def has_location_style_constraint(
    query: str,
) -> bool:
    """
    Detect language suggesting a geographically filtered
    licensing-record query.
    """

    normalized = normalize_query(
        query
    )

    words = set(
        re.findall(
            r"[a-z0-9]+",
            normalized,
        )
    )

    return any(
        preposition in words
        for preposition
        in LOCATION_PREPOSITIONS
    )

def named_facility_match(
    query: str,
    facilities: list[dict],
) -> bool:
    """
    Detect a named USGS facility in the query.

    Generic words such as 'mine' and 'plant' are removed
    before matching so queries like 'Kansanshi capacity'
    can still identify Kansanshi Mine.
    """

    query_tokens = set(
        re.findall(
            r"[a-z0-9]+",
            normalize_query(
                query
            ),
        )
    )

    if not query_tokens:
        return False


    for facility in facilities:

        name = normalize_query(
            str(
                facility.get(
                    "facility_name"
                )
                or ""
            )
        )

        if not name:
            continue


        name_tokens = {
            token
            for token in re.findall(
                r"[a-z0-9]+",
                name,
            )
            if token
            not in FACILITY_GENERIC_NAME_TERMS
        }


        if (
            name_tokens
            and name_tokens.issubset(
                query_tokens
            )
        ):
            return True


    return False


def has_facility_intent(
    query: str,
    facilities: list[dict],
) -> bool:
    """
    Detect clear structured mine/facility queries.

    This is deliberately conservative so general mining
    questions remain in document retrieval.
    """

    normalized = normalize_query(
        query
    )


    has_entity_term = contains_any(
        normalized,
        FACILITY_ENTITY_TERMS,
    )


    has_attribute_term = contains_any(
        normalized,
        FACILITY_ATTRIBUTE_TERMS,
    )


    has_named_facility = (
        named_facility_match(
            query=query,
            facilities=facilities,
        )
    )


    # A named facility plus a structured attribute is a
    # strong signal:
    #
    #   Who operates Sentinel Mine?
    #   Who owns Kansanshi?
    #   Kansanshi capacity
    #   Where is Lumwana located?
    if (
        has_named_facility
        and has_attribute_term
    ):
        return True


    # Explicit facility language plus a structured
    # attribute:
    #
    #   active copper mines
    #   inactive smelters
    #   refinery capacity
    if (
        has_entity_term
        and has_attribute_term
    ):
        return True


    # Listing/filtering language with an explicit facility
    # entity:
    #
    #   show copper mines
    #   list smelters
    #   which refineries
    if (
        has_entity_term
        and contains_any(
            normalized,
            LISTING_WORDS,
        )
    ):
        return True


    return False
# ---------------------------------------------------------
# Routing
# ---------------------------------------------------------

def route_query(
    query: str,
) -> dict:
    """
    Decide which MineLens subsystem should handle a query.
    """

    if not query.strip():
        raise ValueError(
            "Query must not be empty."
        )

    normalized = normalize_query(
        query
    )

    # Exact licence-code lookup.
    licence_code = infer_licence_code(
        query
    )

    if licence_code is not None:
        return {
            "route": ROUTE_LICENSING,
            "reason": (
                "The query contains an exact "
                f"licence code: {licence_code}."
            ),
        }

    licensing_context = (
        has_licensing_context(
            query
        )
    )

    # Structured mining statistics gets priority over the
    # general document-statistics route when the query can
    # be answered from normalized WMD records.
    try:
        statistics_records = (
            load_mining_statistics()
        )
    except FileNotFoundError:
        statistics_records = []

    if (
        statistics_records
        and has_statistics_intent(
            query=query,
            records=statistics_records,
        )
    ):
        return {
            "route": (
                ROUTE_MINING_STATISTICS
            ),
            "reason": (
                "The query asks for structured "
                "mineral production, world-share, "
                "ranking or trend statistics."
            ),
        }
    # Structured mine/facility intelligence.
    #
    # This is checked before general document intent
    # because facility questions may contain words such
    # as "production" or "capacity".
    #
    # Explicit mining-licensing language is excluded so:
    #
    #   "approved copper licences in Solwezi"
    #
    # remains a licensing query.
    try:
        facilities = (
            load_facilities()
        )
    except FileNotFoundError:
        facilities = []


    if (
        facilities
        and not licensing_context
        and has_facility_intent(
            query=query,
            facilities=facilities,
        )
    ):
        return {
            "route": ROUTE_FACILITIES,
            "reason": (
                "The query asks about a structured "
                "mine or mineral facility, such as "
                "its operator, ownership, location, "
                "status or production capacity."
            ),
        }
    # Strong documentary intent.
    if contains_any(
        normalized,
        DOCUMENT_INTENT_PHRASES,
    ):
        return {
            "route": ROUTE_DOCUMENTS,
            "reason": (
                "The query asks for documentary "
                "information such as fees, "
                "requirements, legislation, policy "
                "or mining statistics."
            ),
        }

    # Licensing committee decision.
    decision = infer_decision(
        query
    )

    if (
        licensing_context
        and decision is not None
    ):
        return {
            "route": ROUTE_LICENSING,
            "reason": (
                "The query asks about individual "
                "licensing records with decision "
                f"status '{decision}'."
            ),
        }

    # Explicit entity / committee language.
    if (
        licensing_context
        and contains_any(
            normalized,
            STRUCTURED_ENTITY_PHRASES,
        )
    ):
        return {
            "route": ROUTE_LICENSING,
            "reason": (
                "The query asks about companies, "
                "applicants, decisions or other "
                "structured licence fields."
            ),
        }

    # Listing requests.
    if (
        licensing_context
        and contains_any(
            normalized,
            LISTING_WORDS,
        )
    ):
        return {
            "route": ROUTE_LICENSING,
            "reason": (
                "The query asks to identify or list "
                "individual licensing records."
            ),
        }

    # Geographic filtering.
    if (
        has_plural_licensing_context(
            query
        )
        and has_location_style_constraint(
            query
        )
    ):
        return {
            "route": ROUTE_LICENSING,
            "reason": (
                "The query appears to request "
                "location-filtered licensing records."
            ),
        }

    return {
        "route": ROUTE_DOCUMENTS,
        "reason": (
            "No strong structured-record intent was "
            "detected, so the query will use hybrid "
            "document retrieval."
        ),
    }


# ---------------------------------------------------------
# Document source selection
# ---------------------------------------------------------

SOURCE_TITLE_STOPWORDS = {
    "a",
    "an",
    "and",
    "for",
    "of",
    "the",
    "data",
}


def title_tokens(
    value: str,
) -> set[str]:
    """
    Return normalized alphanumeric title/query tokens.
    """

    return {
        token
        for token in re.findall(
            r"[a-z0-9]+",
            normalize_query(
                value
            ),
        )
        if token
        not in SOURCE_TITLE_STOPWORDS
    }


def explicit_document_source_ids(
    query: str,
    chunks: list[dict],
) -> set[str]:
    """
    Detect whether the user explicitly names one of the
    documents in the MineLens corpus.
    """

    query_tokens = title_tokens(
        query
    )

    if not query_tokens:
        return set()

    source_titles: dict[
        str,
        str,
    ] = {}

    for chunk in chunks:
        source_id = chunk_source_id(
            chunk
        )

        title = chunk_title(
            chunk
        )

        if (
            source_id
            and title
            and source_id
            not in source_titles
        ):
            source_titles[
                source_id
            ] = title

    matches: set[
        str
    ] = set()

    for source_id, title in (
        source_titles.items()
    ):
        tokens = title_tokens(
            title
        )

        if len(tokens) < 3:
            continue

        if tokens.issubset(
            query_tokens
        ):
            matches.add(
                source_id
            )

    return matches


def preferred_document_source_ids(
    query: str,
    chunks: list[dict],
) -> set[str]:
    """
    Select authoritative application/requirements sources
    for clear mining-right requirement questions.

    Explicitly named documents are handled separately and
    retain higher priority.
    """

    normalized = normalize_query(
        query
    )

    if not contains_any(
        normalized,
        MINING_RIGHT_REQUIREMENT_TERMS,
    ):
        return set()

    if not contains_any(
        normalized,
        MINING_RIGHT_CONTEXT_TERMS,
    ):
        return set()

    available_source_ids = {
        chunk_source_id(
            chunk
        )
        for chunk in chunks
        if chunk_source_id(
            chunk
        )
    }

    return (
        MINING_RIGHT_REQUIREMENT_SOURCE_IDS
        & available_source_ids
    )


# ---------------------------------------------------------
# Document precision reranking
# ---------------------------------------------------------

PRECISION_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "did",
    "do",
    "does",
    "for",
    "from",
    "how",
    "in",
    "is",
    "it",
    "of",
    "on",
    "say",
    "says",
    "the",
    "to",
    "was",
    "were",
    "what",
    "which",
    "with",
}

ANSWER_NUMBER_PATTERN = re.compile(
    r"""
    (?:
        (?:K|US\$|\$)\s*\d
        |
        \d+\.\d+
        |
        \d{1,3}(?:,\d{3})+
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)

MONTH_YEAR_PATTERN = re.compile(
    r"""
    \b
    (?:
        january|february|march|april|may|june|
        july|august|september|october|november|december
    )
    \s+
    (?:19|20)\d{2}
    \b
    """,
    re.IGNORECASE | re.VERBOSE,
)


def document_precision_score(
    query: str,
    result: dict,
) -> float:
    """
    Score a hybrid-search result for query-specific
    precision.
    """

    chunk = result.get(
        "chunk",
        {},
    )

    raw_text = str(
        chunk.get(
            "text"
        )
        or ""
    )

    title = chunk_title(
        chunk
    )

    searchable = normalize_query(
        f"{title} {raw_text}"
    )

    query_normalized = normalize_query(
        query
    )

    query_tokens = [
        token
        for token in re.findall(
            r"[a-z0-9]+",
            query_normalized,
        )
        if (
            token
            not in PRECISION_STOPWORDS
            and len(token) > 1
        )
    ]

    if not query_tokens:
        return 0.0

    searchable_tokens = set(
        re.findall(
            r"[a-z0-9]+",
            searchable,
        )
    )

    unique_query_tokens = set(
        query_tokens
    )

    matched_tokens = sum(
        token in searchable_tokens
        for token in unique_query_tokens
    )

    coverage = (
        matched_tokens
        / len(
            unique_query_tokens
        )
    )

    score = (
        coverage
        * 2.0
    )

    bigrams = [
        " ".join(
            query_tokens[
                index:index + 2
            ]
        )
        for index in range(
            len(query_tokens) - 1
        )
    ]

    matched_bigrams = [
        bigram
        for bigram in bigrams
        if bigram in searchable
    ]

    score += (
        len(
            matched_bigrams
        )
        * 1.5
    )

    date_matches = [
        match.group(
            0
        ).casefold()
        for match
        in MONTH_YEAR_PATTERN.finditer(
            query
        )
    ]

    for date_text in date_matches:
        if date_text in searchable:
            score += 2.0

    sentences = re.split(
        r"(?<=[.!?])\s+|\n+",
        raw_text,
    )

    for sentence in sentences:
        sentence_normalized = (
            normalize_query(
                sentence
            )
        )

        anchor_match = any(
            bigram
            in sentence_normalized
            for bigram
            in matched_bigrams
        )

        date_match = (
            not date_matches
            or any(
                date_text
                in sentence_normalized
                for date_text
                in date_matches
            )
        )

        numeric_match = bool(
            ANSWER_NUMBER_PATTERN.search(
                sentence
            )
        )

        if (
            anchor_match
            and date_match
        ):
            score += 2.0

            if numeric_match:
                score += 4.0

    return score


def rerank_document_results(
    query: str,
    results: list[dict],
    top_k: int,
) -> list[dict]:
    """
    Rerank a larger hybrid candidate set using lightweight
    query-specific precision signals.
    """

    reranked: list[
        dict
    ] = []

    for result in results:
        copied_result = dict(
            result
        )

        copied_result[
            "precision_score"
        ] = document_precision_score(
            query=query,
            result=copied_result,
        )

        reranked.append(
            copied_result
        )

    reranked.sort(
        key=lambda result: (
            result.get(
                "precision_score",
                0.0,
            ),
            result.get(
                "rrf_score",
                0.0,
            ),
        ),
        reverse=True,
    )

    return reranked[
        :top_k
    ]


# ---------------------------------------------------------
# Document search
# ---------------------------------------------------------

def search_documents(
    query: str,
    top_k: int = 5,
    candidate_k: int = DEFAULT_CANDIDATE_K,
    include_superseded: bool = False,
) -> dict:
    """
    Run normal MineLens hybrid document retrieval.
    """

    if top_k <= 0:
        raise ValueError(
            "top_k must be greater than zero."
        )

    if candidate_k <= 0:
        raise ValueError(
            "candidate_k must be greater than zero."
        )

    print(
        "Loading MineLens document chunks..."
    )

    all_chunks = load_chunks(
        include_superseded=(
            include_superseded
        ),
    )

    chunks = all_chunks

    explicit_source_ids = (
        explicit_document_source_ids(
            query=query,
            chunks=all_chunks,
        )
    )

    preferred_source_ids: set[
        str
    ] = set()

    # Explicit document naming always has highest document
    # source-selection priority.
    if explicit_source_ids:
        explicit_chunks = [
            chunk
            for chunk in all_chunks
            if (
                chunk_source_id(
                    chunk
                )
                in explicit_source_ids
            )
        ]

        if explicit_chunks:
            chunks = explicit_chunks

            print(
                "Explicit document source detected: "
                + ", ".join(
                    sorted(
                        explicit_source_ids
                    )
                )
            )

    else:
        preferred_source_ids = (
            preferred_document_source_ids(
                query=query,
                chunks=all_chunks,
            )
        )

        if preferred_source_ids:
            preferred_chunks = [
                chunk
                for chunk in all_chunks
                if (
                    chunk_source_id(
                        chunk
                    )
                    in preferred_source_ids
                )
            ]

            if preferred_chunks:
                chunks = preferred_chunks

                print(
                    "Intent-specific document "
                    "sources detected: "
                    + ", ".join(
                        sorted(
                            preferred_source_ids
                        )
                    )
                )

    if not chunks:
        raise ValueError(
            "Document source filtering produced "
            "an empty search corpus."
        )

    print(
        f"Loaded {len(chunks)} "
        "document chunks."
    )

    print(
        "Building BM25 index..."
    )

    bm25_index = BM25Index(
        chunks
    )

    base_cache_variant = (
        "include-superseded"
        if include_superseded
        else "current"
    )

    if explicit_source_ids:
        cache_variant = (
            base_cache_variant
            + "-source-"
            + "-".join(
                sorted(
                    explicit_source_ids
                )
            )
        )

    elif preferred_source_ids:
        cache_variant = (
            base_cache_variant
            + "-intent-source-"
            + "-".join(
                sorted(
                    preferred_source_ids
                )
            )
        )

    else:
        cache_variant = (
            base_cache_variant
        )

    semantic_index = SemanticIndex(
        chunks,
        cache_variant=(
            cache_variant
        ),
    )

    if not load_embedding_cache(
        semantic_index
    ):
        semantic_index.build()

        save_embedding_cache(
            semantic_index
        )

    rerank_k = max(
        top_k,
        min(
            candidate_k * 2,
            60,
        ),
    )

    results = hybrid_search(
        query=query,
        bm25_index=bm25_index,
        semantic_index=semantic_index,
        top_k=rerank_k,
        candidate_k=candidate_k,
    )

    results = rerank_document_results(
        query=query,
        results=results,
        top_k=top_k,
    )

    results = expand_document_results(
        query=query,
        results=results,
        corpus=chunks,
    )

    return {
        "route": ROUTE_DOCUMENTS,
        "results": results,
        "chunk_count": len(
            all_chunks
        ),
        "searched_chunk_count": len(
            chunks
        ),
        "explicit_source_ids": sorted(
            explicit_source_ids
        ),
        "preferred_source_ids": sorted(
            preferred_source_ids
        ),
    }


# ---------------------------------------------------------
# Licensing search
# ---------------------------------------------------------

def search_licensing(
    query: str,
    top_k: int = 5,
) -> dict:
    """
    Run structured licensing search.
    """

    if top_k <= 0:
        raise ValueError(
            "top_k must be greater than zero."
        )

    records = (
        load_licensing_records()
    )

    print(
        f"Loaded {len(records):,} "
        "licensing records."
    )

    (
        results,
        filters,
    ) = search_licensing_records(
        query=query,
        records=records,
        top_k=top_k,
    )

    return {
        "route": ROUTE_LICENSING,
        "results": results,
        "filters": filters,
        "record_count": len(
            records
        ),
    }


# ---------------------------------------------------------
# Mining statistics search
# ---------------------------------------------------------

def search_mining_statistics(
    query: str,
    top_k: int = 5,
) -> dict:
    """
    Run structured World Mining Data search.
    """

    if top_k <= 0:
        raise ValueError(
            "top_k must be greater than zero."
        )

    records = (
        load_mining_statistics()
    )

    print(
        f"Loaded {len(records):,} "
        "mining statistics records."
    )

    result = (
        query_mining_statistics(
            query=query,
            records=records,
        )
    )

    results = result.get(
        "results",
        [],
    )

    # Ranking lists can be long. Trend series must retain
    # the complete requested time period.
    if (
        result.get(
            "intent"
        )
        == "world_rank"
        and not result.get(
            "countries"
        )
    ):
        results = results[
            :top_k
        ]

    return {
        "route": (
            ROUTE_MINING_STATISTICS
        ),
        "results": results,
        "statistics_intent": (
            result.get(
                "intent"
            )
        ),
        "commodity": (
            result.get(
                "commodity"
            )
        ),
        "countries": (
            result.get(
                "countries",
                [],
            )
        ),
        "years": (
            result.get(
                "years",
                [],
            )
        ),
        "error": (
            result.get(
                "error"
            )
        ),
        "record_count": len(
            records
        ),
    }

# ---------------------------------------------------------
# Facility search
# ---------------------------------------------------------

def search_facilities(
    query: str,
    top_k: int = 5,
) -> dict:
    """
    Run structured USGS Zambia facility search.
    """

    if top_k <= 0:
        raise ValueError(
            "top_k must be greater than zero."
        )

    facilities = (
        load_facilities()
    )

    print(
        f"Loaded {len(facilities):,} "
        "USGS facility records."
    )

    result = (
        search_facility_records(
            query=query,
            facilities=facilities,
            top_k=top_k,
        )
    )

    return {
        "route":
            ROUTE_FACILITIES,

        "results":
            result.get(
                "results",
                [],
            ),

        "filters":
            result.get(
                "filters",
                {},
            ),

        "facility_count":
            result.get(
                "facility_count",
                len(
                    facilities
                ),
            ),

        "match_count":
            result.get(
                "match_count",
                0,
            ),
    }
# ---------------------------------------------------------
# Unified MineLens search
# ---------------------------------------------------------

def search_mine(
    query: str,
    top_k: int = 5,
    candidate_k: int = DEFAULT_CANDIDATE_K,
    include_superseded: bool = False,
    force_route: str | None = None,
) -> dict:
    """
    Unified MineLens entry point.

    The query is routed automatically unless force_route
    explicitly selects documents, licensing, structured
    mining statistics or facilities.
    """

    if not query.strip():
        raise ValueError(
            "Query must not be empty."
        )

    if force_route is None:
        route_info = route_query(
            query
        )

    else:
        if (
            force_route
            not in VALID_ROUTES
        ):
            raise ValueError(
                "force_route must be "
                "'documents', 'licensing', "
                "'mining_statistics' or "
                "'facilities'."
            )

        route_info = {
            "route": force_route,
            "reason": (
                "Route selected manually."
            ),
        }

    selected_route = (
        route_info[
            "route"
        ]
    )
    if (
        selected_route
        == ROUTE_LICENSING
    ):
        payload = search_licensing(
            query=query,
            top_k=top_k,
        )

    elif (
        selected_route
        == ROUTE_MINING_STATISTICS
    ):
        payload = (
            search_mining_statistics(
                query=query,
                top_k=top_k,
            )
        )

    elif (
        selected_route
        == ROUTE_FACILITIES
    ):
        payload = (
            search_facilities(
                query=query,
                top_k=top_k,
            )
        )

    else:
        payload = search_documents(
            query=query,
            top_k=top_k,
            candidate_k=candidate_k,
            include_superseded=(
                include_superseded
            ),
        )

    payload[
        "query"
    ] = query

    payload[
        "reason"
    ] = route_info[
        "reason"
    ]

    return payload
        