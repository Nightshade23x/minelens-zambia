from __future__ import annotations

import argparse
import json
import math
import re

from collections import Counter, defaultdict
from pathlib import Path


# ---------------------------------------------------------
# Project paths
# ---------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]

PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"


# ---------------------------------------------------------
# Search configuration
# ---------------------------------------------------------

DEFAULT_TOP_K = 5

BM25_K1 = 1.5
BM25_B = 0.75


# ---------------------------------------------------------
# Basic English stopwords
# ---------------------------------------------------------

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "been",
    "being",
    "by",
    "for",
    "from",
    "had",
    "has",
    "have",
    "he",
    "her",
    "hers",
    "him",
    "his",
    "i",
    "in",
    "into",
    "is",
    "it",
    "its",
    "of",
    "on",
    "or",
    "our",
    "ours",
    "she",
    "that",
    "the",
    "their",
    "theirs",
    "them",
    "they",
    "this",
    "those",
    "to",
    "was",
    "we",
    "were",
    "what",
    "when",
    "where",
    "which",
    "who",
    "will",
    "with",
    "you",
    "your",
}


# ---------------------------------------------------------
# Text processing
# ---------------------------------------------------------

def tokenize(text: str) -> list[str]:
    """
    Convert text into normalized searchable tokens.

    Example:

        "Copper production increased by 12.5%."

    becomes approximately:

        ["copper", "production", "increased", "12", "5"]
    """

    text = text.lower()

    tokens = re.findall(
        r"[a-z0-9]+",
        text,
    )

    return [
        token
        for token in tokens
        if token not in STOPWORDS
        and len(token) > 1
    ]


# ---------------------------------------------------------
# Chunk loading
# ---------------------------------------------------------

def load_chunks(
    data_directory: Path = PROCESSED_DATA_DIR,
    include_superseded: bool = False,
) -> list[dict]:
    """
    Load all searchable *.chunks.jsonl files from
    data/processed/.

    Superseded sources are excluded by default so
    normal MineLens searches prefer current information.

    Set include_superseded=True when historical material
    should also be searchable.
    """

    if not data_directory.exists():
        raise FileNotFoundError(
            f"Processed data directory not found: "
            f"{data_directory}"
        )

    chunk_files = sorted(
        data_directory.glob(
            "*.chunks.jsonl"
        )
    )

    if not chunk_files:
        raise FileNotFoundError(
            "No .chunks.jsonl files were found in "
            f"{data_directory}"
        )

    chunks: list[dict] = []

    for chunk_file in chunk_files:

        with chunk_file.open(
            "r",
            encoding="utf-8",
        ) as file:

            for line_number, line in enumerate(
                file,
                start=1,
            ):

                line = line.strip()

                if not line:
                    continue

                try:
                    chunk = json.loads(
                        line
                    )

                except json.JSONDecodeError as error:
                    raise ValueError(
                        f"Invalid JSON in "
                        f"{chunk_file.name} "
                        f"on line {line_number}"
                    ) from error

                if not chunk.get(
                    "text"
                ):
                    continue

                source_status = (
                    chunk.get(
                        "source_status",
                        ""
                    )
                    .strip()
                    .lower()
                )

                if (
                    not include_superseded
                    and source_status
                    == "superseded"
                ):
                    continue

                chunk[
                    "_chunk_file"
                ] = chunk_file.name

                chunks.append(
                    chunk
                )

    if not chunks:
        raise ValueError(
            "Chunk files were found, but no searchable "
            "text records were loaded."
        )

    return chunks


# ---------------------------------------------------------
# BM25 index
# ---------------------------------------------------------

class BM25Index:
    """
    Small BM25 search engine for MineLens.

    BM25 ranks documents based on:

    - how often query terms occur
    - how rare those terms are across the collection
    - document/chunk length

    This gives us a strong lexical-search baseline before
    adding semantic embeddings.
    """

    def __init__(
        self,
        chunks: list[dict],
        k1: float = BM25_K1,
        b: float = BM25_B,
    ) -> None:

        self.chunks = chunks
        self.k1 = k1
        self.b = b

        self.document_tokens: list[list[str]] = []

        self.term_frequencies: list[Counter[str]] = []

        self.document_frequencies: dict[str, int] = defaultdict(int)

        self.document_lengths: list[int] = []

        self.average_document_length = 0.0

        self.idf: dict[str, float] = {}

        self._build_index()

    def _build_index(self) -> None:
        """
        Build all statistics required for BM25 scoring.
        """

        for chunk in self.chunks:

            tokens = tokenize(
                chunk["text"]
            )

            self.document_tokens.append(
                tokens
            )

            frequencies = Counter(
                tokens
            )

            self.term_frequencies.append(
                frequencies
            )

            document_length = len(
                tokens
            )

            self.document_lengths.append(
                document_length
            )

            for term in frequencies:
                self.document_frequencies[
                    term
                ] += 1

        total_documents = len(
            self.chunks
        )

        total_length = sum(
            self.document_lengths
        )

        self.average_document_length = (
            total_length / total_documents
            if total_documents
            else 0.0
        )

        for term, frequency in (
            self.document_frequencies.items()
        ):

            # Standard BM25 inverse document frequency.
            self.idf[term] = math.log(
                1
                + (
                    total_documents
                    - frequency
                    + 0.5
                )
                / (
                    frequency
                    + 0.5
                )
            )

    def score_document(
        self,
        document_index: int,
        query_tokens: list[str],
    ) -> float:
        """
        Calculate BM25 score for one chunk.
        """

        score = 0.0

        frequencies = self.term_frequencies[
            document_index
        ]

        document_length = self.document_lengths[
            document_index
        ]

        query_frequency = Counter(
            query_tokens
        )

        for term, query_count in query_frequency.items():

            if term not in frequencies:
                continue

            term_frequency = frequencies[
                term
            ]

            inverse_document_frequency = (
                self.idf.get(
                    term,
                    0.0,
                )
            )

            denominator = (
                term_frequency
                + self.k1
                * (
                    1
                    - self.b
                    + self.b
                    * (
                        document_length
                        / self.average_document_length
                    )
                )
            )

            term_score = (
                inverse_document_frequency
                * (
                    term_frequency
                    * (
                        self.k1
                        + 1
                    )
                )
                / denominator
            )

            # Slightly reward repeated query terms.
            score += (
                term_score
                * query_count
            )

        return score

    def search(
        self,
        query: str,
        top_k: int = DEFAULT_TOP_K,
    ) -> list[dict]:
        """
        Search the MineLens chunk collection.
        """

        query_tokens = tokenize(
            query
        )

        if not query_tokens:
            return []

        results: list[dict] = []

        normalized_query = " ".join(
            query.lower().split()
        )

        for index, chunk in enumerate(
            self.chunks
        ):

            score = self.score_document(
                document_index=index,
                query_tokens=query_tokens,
            )

            if score <= 0:
                continue

            text_normalized = " ".join(
                chunk["text"]
                .lower()
                .split()
            )

            # Exact phrase matches are especially useful
            # for mining queries such as:
            #
            #     copper production
            #     mining licence
            #
            # so give them a modest ranking bonus.
            if (
                normalized_query
                and normalized_query
                in text_normalized
            ):
                score *= 1.25

            results.append(
                {
                    "score": score,
                    "chunk": chunk,
                }
            )

        results.sort(
            key=lambda result: result["score"],
            reverse=True,
        )

        return results[
            :top_k
        ]


# ---------------------------------------------------------
# Result formatting
# ---------------------------------------------------------

def make_snippet(
    text: str,
    query: str,
    max_chars: int = 450,
) -> str:
    """
    Produce a readable search-result snippet centered near
    the first matching query term where possible.
    """

    text = " ".join(
        text.split()
    )

    if len(text) <= max_chars:
        return text

    query_tokens = tokenize(
        query
    )

    lower_text = text.lower()

    match_positions = []

    for token in query_tokens:

        position = lower_text.find(
            token
        )

        if position != -1:
            match_positions.append(
                position
            )

    if match_positions:

        center = min(
            match_positions
        )

        start = max(
            0,
            center - max_chars // 3,
        )

    else:
        start = 0

    end = min(
        len(text),
        start + max_chars,
    )

    snippet = text[
        start:end
    ].strip()

    if start > 0:
        snippet = "... " + snippet

    if end < len(text):
        snippet += " ..."

    return snippet


def display_results(
    query: str,
    results: list[dict],
) -> None:
    """
    Print ranked search results to the terminal.
    """

    print()
    print("=" * 70)
    print("MINELENS ZAMBIA SEARCH")
    print("=" * 70)

    print()
    print(f'Query: "{query}"')
    print()

    if not results:

        print("No matching passages found.")
        return

    print(
        f"Found {len(results)} ranked result(s)."
    )

    for rank, result in enumerate(
        results,
        start=1,
    ):

        chunk = result["chunk"]

        page_start = chunk.get(
            "page_start"
        )

        page_end = chunk.get(
            "page_end"
        )

        if page_start == page_end:
            page_display = str(
                page_start
            )
        else:
            page_display = (
                f"{page_start}-{page_end}"
            )

        print()
        print("-" * 70)

        print(
            f"RESULT {rank}"
        )

        print(
            f"Score:    {result['score']:.4f}"
        )

        print(
            f"Document: {chunk.get('document')}"
        )

        print(
            f"Pages:    {page_display}"
        )

        print(
            f"Chunk:    {chunk.get('chunk_id')}"
        )

        print()

        print(
            make_snippet(
                text=chunk["text"],
                query=query,
            )
        )

        source_url = chunk.get(
            "source_url"
        )

        if source_url:

            print()
            print(
                f"Source: {source_url}"
            )

    print()
    print("-" * 70)


# ---------------------------------------------------------
# Command-line interface
# ---------------------------------------------------------

def main() -> None:

    parser = argparse.ArgumentParser(
        description=(
            "Search MineLens mining documents "
            "using BM25 lexical retrieval."
        )
    )

    parser.add_argument(
        "query",
        nargs="+",
        help="Search query",
    )

    parser.add_argument(
        "--top-k",
        type=int,
        default=DEFAULT_TOP_K,
        help=(
            "Number of results to display "
            f"(default: {DEFAULT_TOP_K})"
        ),
    )
    parser.add_argument(
        "--include-superseded",
        action="store_true",
        help=(
            "Include superseded historical sources "
            "in search results."
        ),
    )
    args = parser.parse_args()

    query = " ".join(
        args.query
    )

    if args.top_k <= 0:
        raise ValueError(
            "--top-k must be greater than zero."
        )

    print(
        "Loading MineLens index..."
    )

    chunks = load_chunks(
        include_superseded=(
            args.include_superseded
        )
    )

    index = BM25Index(
        chunks
    )

    print(
        f"Indexed {len(chunks)} chunks."
    )

    results = index.search(
        query=query,
        top_k=args.top_k,
    )

    display_results(
        query=query,
        results=results,
    )


if __name__ == "__main__":
    main()