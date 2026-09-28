from __future__ import annotations

import re

from app.embeddings import (
    SemanticIndex,
    load_embedding_cache,
    save_embedding_cache,
)
from app.context_expansion import (
    expand_document_results,
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

from app.search import (
    BM25Index,
    load_chunks,
)


# ---------------------------------------------------------
# Routes
# ---------------------------------------------------------

ROUTE_DOCUMENTS = "documents"

ROUTE_LICENSING = "licensing"

VALID_ROUTES = {
    ROUTE_DOCUMENTS,
    ROUTE_LICENSING,
}


# ---------------------------------------------------------
# Router configuration
# ---------------------------------------------------------

# These signals strongly indicate that the user wants
# information from legislation, policy, statistics,
# application requirements, fees, or other documents.
#
# They are checked BEFORE licensing-record signals.
#
# This is important for questions such as:
#
#   "How much does an approved mining licence cost?"
#
# which contains "approved" but is still a fee/document
# question.

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


# Terms that suggest the user wants individual licensing
# records rather than general mining documents.

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


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def normalize_query(
    query: str,
) -> str:
    """
    Normalize whitespace and casing for routing.
    """

    return " ".join(
        query.lower().split()
    )


def contains_term(
    text: str,
    term: str,
) -> bool:
    """
    Check a term using word boundaries for single
    words and substring matching for phrases.
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


def has_licensing_context(
    query: str,
) -> bool:
    """
    Determine whether a query talks about mining
    licensing records.

    This deliberately does not mean that the query MUST
    route to structured licensing search. Document intent
    such as fees or requirements has higher priority.
    """

    normalized = normalize_query(
        query
    )

    # licence / license / licences / licenses

    if re.search(
        r"\blicen[cs](?:e|es)\b",
        normalized,
    ):

        return True

    # mining right / rights

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

    # Queries such as:
    #
    #   which mining applications were approved
    #   exploration applications rejected

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

    Useful for location-constrained queries such as:
        copper licences in Solwezi
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
    record query.

    The structured licensing engine later resolves the
    actual province/district against its dataset.
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


# ---------------------------------------------------------
# Routing
# ---------------------------------------------------------

def route_query(
    query: str,
) -> dict:
    """
    Decide which MineLens subsystem should handle a query.

    Returns:
        {
            "route": "documents" | "licensing",
            "reason": "...",
        }

    Routing is deterministic and intentionally
    conservative: ambiguous questions remain in document
    retrieval unless there is clear structured-record
    intent.
    """

    if not query.strip():

        raise ValueError(
            "Query must not be empty."
        )

    normalized = normalize_query(
        query
    )

    # -----------------------------------------------------
    # Exact licence-code lookup
    # -----------------------------------------------------

    licence_code = infer_licence_code(
        query
    )

    if licence_code is not None:

        return {
            "route": (
                ROUTE_LICENSING
            ),
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

    # -----------------------------------------------------
    # Strong document intent
    # -----------------------------------------------------

    if contains_any(
        normalized,
        DOCUMENT_INTENT_PHRASES,
    ):

        return {
            "route": (
                ROUTE_DOCUMENTS
            ),
            "reason": (
                "The query asks for documentary "
                "information such as fees, "
                "requirements, legislation, policy "
                "or mining statistics."
            ),
        }

    # -----------------------------------------------------
    # Licensing committee decision
    # -----------------------------------------------------

    decision = infer_decision(
        query
    )

    if (
        licensing_context
        and decision is not None
    ):

        return {
            "route": (
                ROUTE_LICENSING
            ),
            "reason": (
                "The query asks about individual "
                f"licensing records with decision "
                f"status '{decision}'."
            ),
        }

    # -----------------------------------------------------
    # Explicit entity / committee language
    # -----------------------------------------------------

    if (
        licensing_context
        and contains_any(
            normalized,
            STRUCTURED_ENTITY_PHRASES,
        )
    ):

        return {
            "route": (
                ROUTE_LICENSING
            ),
            "reason": (
                "The query asks about companies, "
                "applicants, decisions or other "
                "structured licence fields."
            ),
        }

    # -----------------------------------------------------
    # Listing requests
    # -----------------------------------------------------

    if (
        licensing_context
        and contains_any(
            normalized,
            LISTING_WORDS,
        )
    ):

        return {
            "route": (
                ROUTE_LICENSING
            ),
            "reason": (
                "The query asks to identify or list "
                "individual licensing records."
            ),
        }

    # -----------------------------------------------------
    # Geographic filtering
    # -----------------------------------------------------

    if (
        has_plural_licensing_context(
            query
        )
        and has_location_style_constraint(
            query
        )
    ):

        return {
            "route": (
                ROUTE_LICENSING
            ),
            "reason": (
                "The query appears to request "
                "location-filtered licensing records."
            ),
        }

    # -----------------------------------------------------
    # Default: documents
    # -----------------------------------------------------

    return {
        "route": (
            ROUTE_DOCUMENTS
        ),
        "reason": (
            "No strong structured-record intent was "
            "detected, so the query will use hybrid "
            "document retrieval."
        ),
    }

# =========================================================
# EXPLICIT DOCUMENT SOURCE DETECTION
# =========================================================

SOURCE_TITLE_STOPWORDS = {
    "a",
    "an",
    "and",
    "for",
    "of",
    "the",
    "data",
}


def explicit_document_source_ids(
    query: str,
    chunks: list[dict],
) -> set[str]:
    """
    Detect whether the user explicitly names one of the
    documents in the MineLens corpus.

    Example:

        "What does World Mining Data 2026 say about
        Zambia's copper production?"

    should restrict document retrieval to:

        world_mining_data_2026

    Matching uses informative title tokens rather than
    requiring the exact title word order.
    """

    query_tokens = set(
        normalize_query(
            query
        ).split()
    )

    if not query_tokens:
        return set()

    source_titles: dict[str, str] = {}

    for chunk in chunks:

        source_id = str(
            chunk.get(
                "source_id"
            )
            or ""
        ).strip()

        title = str(
            chunk.get(
                "title"
            )
            or ""
        ).strip()

        if (
            source_id
            and title
            and source_id
            not in source_titles
        ):

            source_titles[
                source_id
            ] = title

    matches: set[str] = set()

    for source_id, title in (
        source_titles.items()
    ):

        title_tokens = {
            token
            for token in normalize_query(
                title
            ).split()
            if token
            not in SOURCE_TITLE_STOPWORDS
        }

        # Avoid accidentally treating short/generic
        # document titles as explicit source references.
        if len(title_tokens) < 3:
            continue

        if title_tokens.issubset(
            query_tokens
        ):

            matches.add(
                source_id
            )

    return matches
# =========================================================
# DOCUMENT PRECISION RERANKING
# =========================================================

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
    Score a hybrid-search result for query-specific precision.

    This complements RRF by rewarding:

    - informative query-token coverage,
    - important multi-word phrase matches,
    - exact month/year matches,
    - answer-like numeric evidence,
    - sentences containing both query anchors and numbers.

    It does not replace BM25 or semantic search.
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

    title = str(
        chunk.get(
            "title"
        )
        or ""
    )

    searchable = normalize_query(
        f"{title} {raw_text}"
    )

    query_normalized = normalize_query(
        query
    )

    query_tokens = [
        token
        for token in query_normalized.split()
        if (
            token
            not in PRECISION_STOPWORDS
            and len(token) > 1
        )
    ]

    if not query_tokens:

        return 0.0

    searchable_tokens = set(
        searchable.split()
    )

    # -----------------------------------------------------
    # TOKEN COVERAGE
    # -----------------------------------------------------

    matched_tokens = sum(
        token in searchable_tokens
        for token in set(
            query_tokens
        )
    )

    coverage = (
        matched_tokens
        / len(
            set(
                query_tokens
            )
        )
    )

    score = (
        coverage
        * 2.0
    )

    # -----------------------------------------------------
    # INFORMATIVE BIGRAMS
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # DATE MATCHING
    # -----------------------------------------------------

    date_matches = [
        match.group(0).casefold()
        for match in MONTH_YEAR_PATTERN.finditer(
            query
        )
    ]

    for date_text in date_matches:

        if date_text in searchable:

            score += 2.0

    # -----------------------------------------------------
    # ANSWER-BEARING SENTENCES
    # -----------------------------------------------------

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

    reranked: list[dict] = []

    for result in results:

        result = dict(
            result
        )

        result[
            "precision_score"
        ] = document_precision_score(
            query=query,
            result=result,
        )

        reranked.append(
            result
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

    chunks = load_chunks(
        include_superseded=(
            include_superseded
        ),
    )
    all_chunks = chunks

    explicit_source_ids = (
        explicit_document_source_ids(
            query=query,
            chunks=all_chunks,
        )
    )

    if explicit_source_ids:

        chunks = [
            chunk
            for chunk in all_chunks
            if chunk.get(
                "source_id"
            )
            in explicit_source_ids
        ]

        print(
            "Explicit document source detected: "
            + ", ".join(
                sorted(
                    explicit_source_ids
                )
            )
        )
    print(
        f"Loaded {len(chunks)} "
        f"document chunks."
    )

    print(
        "Building BM25 index..."
    )

    bm25_index = BM25Index(
        chunks
    )

    cache_variant = (
        "include-superseded"
        if include_superseded
        else "current"
    )

    if explicit_source_ids:

        source_suffix = "_".join(
            sorted(
                explicit_source_ids
            )
        )

        cache_variant = (
            f"{cache_variant}"
            f"-source-{source_suffix}"
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

    # Retrieve a larger shortlist first so the precision
    # reranker can recover answer-bearing chunks that may sit
    # below the initial RRF cutoff.
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
        "route": (
            ROUTE_DOCUMENTS
        ),
        "results": results,

        # Full searchable document corpus size.
        "chunk_count": len(
            all_chunks
        ),

        # Useful for debugging / frontend transparency.
        "searched_chunk_count": len(
            chunks
        ),

        "explicit_source_ids": sorted(
            explicit_source_ids
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
        "route": (
            ROUTE_LICENSING
        ),
        "results": results,
        "filters": filters,
        "record_count": len(
            records
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
    explicitly selects "documents" or "licensing".
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
                "'documents' or 'licensing'."
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