from __future__ import annotations

import argparse
import json

from pathlib import Path

import numpy as np
from fastembed import TextEmbedding

from app.search import load_chunks, make_snippet
import hashlib

# ---------------------------------------------------------
# Project paths
# ---------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]

PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"

EMBEDDING_CACHE_DIR = (
    PROCESSED_DATA_DIR
    / "embeddings"
)
MODEL_CACHE_DIR = (
    PROJECT_ROOT
    / ".cache"
    / "fastembed"
)
LOCAL_MODEL_DIR = (
    MODEL_CACHE_DIR
    / "fast-all-MiniLM-L6-v2"
)


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

DEFAULT_TOP_K = 5


# ---------------------------------------------------------
# Vector helpers
# ---------------------------------------------------------
def chunk_text_sha256(
    text: str,
) -> str:
    """
    Return a stable SHA-256 hash of the exact text
    used to create an embedding.
    """

    return hashlib.sha256(
        text.encode(
            "utf-8"
        )
    ).hexdigest()
def chunk_cache_identity(
    chunk: dict,
) -> dict:
    """
    Return the information that uniquely identifies
    the exact chunk text used for an embedding.

    This is used for both saving and validating the
    embedding cache.
    """

    return {
        "document": chunk.get(
            "document"
        ),
        "chunk_id": chunk.get(
            "chunk_id"
        ),
        "document_sha256": chunk.get(
            "document_sha256"
        ),
        "text_sha256": chunk_text_sha256(
            chunk.get(
                "text",
                ""
            )
        ),
    }
def normalize_vector(
    vector: np.ndarray,
) -> np.ndarray:
    """
    Convert a vector to unit length.

    Normalized vectors make cosine-similarity calculations
    simple and stable.
    """

    norm = np.linalg.norm(vector)

    if norm == 0:
        return vector

    return vector / norm


def cosine_similarity(
    vector_a: np.ndarray,
    vector_b: np.ndarray,
) -> float:
    """
    Calculate cosine similarity between two vectors.
    """

    vector_a = normalize_vector(vector_a)
    vector_b = normalize_vector(vector_b)

    return float(
        np.dot(
            vector_a,
            vector_b,
        )
    )


# ---------------------------------------------------------
# Semantic index
# ---------------------------------------------------------

class SemanticIndex:
    """
    Semantic-search index for MineLens.

    Text chunks are converted into dense embedding vectors.

    Queries are embedded using the same model and ranked
    according to cosine similarity.
    """

    def __init__(
        self,
        chunks: list[dict],
        model_name: str = DEFAULT_MODEL,
    ) -> None:

        if not chunks:
            raise ValueError(
                "Cannot build semantic index "
                "without chunks."
            )

        self.chunks = chunks
        self.model_name = model_name

        print(
            f"Loading embedding model: "
            f"{model_name}"
        )

        MODEL_CACHE_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

        if not LOCAL_MODEL_DIR.exists():
            raise FileNotFoundError(
                "Local embedding model was not found at:\n"
                f"{LOCAL_MODEL_DIR}\n\n"
                "Download and extract the model before running "
                "semantic search."
            )

        self.model = TextEmbedding(
            model_name=model_name,
            specific_model_path=str(LOCAL_MODEL_DIR),
        )

        self.embeddings: np.ndarray | None = None


    def build(self) -> None:
        """
        Generate embeddings for all MineLens chunks.
        """

        texts = [
            chunk["text"]
            for chunk in self.chunks
        ]

        print(
            f"Generating embeddings for "
            f"{len(texts)} chunks..."
        )

        vectors = list(
            self.model.embed(texts)
        )

        self.embeddings = np.array(
            [
                normalize_vector(
                    np.asarray(
                        vector,
                        dtype=np.float32,
                    )
                )
                for vector in vectors
            ],
            dtype=np.float32,
        )

        print(
            "Semantic index ready."
        )


    def embed_query(
        self,
        query: str,
    ) -> np.ndarray:
        """
        Generate an embedding for a search query.
        """

        vectors = list(
            self.model.embed(
                [query]
            )
        )

        if not vectors:
            raise ValueError(
                "Embedding model returned "
                "no query vector."
            )

        return normalize_vector(
            np.asarray(
                vectors[0],
                dtype=np.float32,
            )
        )


    def search(
        self,
        query: str,
        top_k: int = DEFAULT_TOP_K,
    ) -> list[dict]:
        """
        Search chunks using semantic similarity.
        """

        if not query.strip():
            return []

        if top_k <= 0:
            raise ValueError(
                "top_k must be greater than zero."
            )

        if self.embeddings is None:
            self.build()

        query_vector = self.embed_query(
            query
        )

        # Embeddings are normalized, so the dot product
        # is equivalent to cosine similarity.
        scores = (
            self.embeddings
            @ query_vector
        )

        ranked_indices = np.argsort(
            scores
        )[::-1]

        results: list[dict] = []

        for index in ranked_indices[
            :top_k
        ]:

            results.append(
                {
                    "score": float(
                        scores[index]
                    ),
                    "chunk": self.chunks[
                        index
                    ],
                }
            )

        return results


# ---------------------------------------------------------
# Cache
# ---------------------------------------------------------

def get_cache_paths(
    model_name: str,
) -> tuple[Path, Path]:
    """
    Return paths used to store generated vectors and
    information about the chunks they correspond to.
    """

    safe_model_name = (
        model_name
        .replace("/", "_")
        .replace("\\", "_")
    )

    vector_path = (
        EMBEDDING_CACHE_DIR
        / f"{safe_model_name}.npy"
    )

    metadata_path = (
        EMBEDDING_CACHE_DIR
        / f"{safe_model_name}.json"
    )

    return (
        vector_path,
        metadata_path,
    )


def save_embedding_cache(
    index: SemanticIndex,
) -> None:
    """
    Save generated embeddings so they do not need to be
    recalculated every time MineLens starts.
    """

    if index.embeddings is None:
        raise ValueError(
            "No embeddings available to save."
        )

    EMBEDDING_CACHE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    vector_path, metadata_path = (
        get_cache_paths(
            index.model_name
        )
    )

    np.save(
        vector_path,
        index.embeddings,
    )

    metadata = {
        "model": index.model_name,
        "chunk_count": len(
            index.chunks
        ),
        "chunks": [
            chunk_cache_identity(
                chunk
            )
            for chunk in index.chunks
        ],    
    }
    with metadata_path.open(
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            metadata,
            file,
            indent=4,
        )

    print(
        f"Embedding cache saved to:"
    )

    print(
        f"  {vector_path}"
    )


def load_embedding_cache(
    index: SemanticIndex,
) -> bool:
    """
    Load embeddings from disk if the cache still matches
    the current MineLens chunk collection.
    """

    vector_path, metadata_path = (
        get_cache_paths(
            index.model_name
        )
    )

    if (
        not vector_path.exists()
        or not metadata_path.exists()
    ):
        return False

    try:

        with metadata_path.open(
            "r",
            encoding="utf-8",
        ) as file:

            metadata = json.load(
                file
            )

        cached_chunks = metadata.get(
            "chunks",
            []
        )

        current_chunks = [
            chunk_cache_identity(
                chunk
            )
            for chunk in index.chunks
        ]              

        if (
            metadata.get("model")
            != index.model_name
        ):
            return False

        if cached_chunks != current_chunks:
            return False

        embeddings = np.load(
            vector_path
        )

        if len(embeddings) != len(
            index.chunks
        ):
            return False

        index.embeddings = embeddings

        print(
            "Loaded cached embeddings."
        )

        return True

    except (
        OSError,
        ValueError,
        json.JSONDecodeError,
    ):

        return False


# ---------------------------------------------------------
# Display
# ---------------------------------------------------------

def display_results(
    query: str,
    results: list[dict],
) -> None:
    """
    Display semantic-search results in the terminal.
    """

    print()
    print("=" * 70)

    print(
        "MINELENS ZAMBIA SEMANTIC SEARCH"
    )

    print("=" * 70)

    print()
    print(
        f'Query: "{query}"'
    )

    if not results:

        print()
        print(
            "No results found."
        )

        return

    for rank, result in enumerate(
        results,
        start=1,
    ):

        chunk = result[
            "chunk"
        ]

        page_start = chunk.get(
            "page_start"
        )

        page_end = chunk.get(
            "page_end"
        )

        if page_start == page_end:

            pages = str(
                page_start
            )

        else:

            pages = (
                f"{page_start}-{page_end}"
            )

        print()
        print("-" * 70)

        print(
            f"RESULT {rank}"
        )

        print(
            f"Similarity: "
            f"{result['score']:.4f}"
        )

        print(
            f"Document:   "
            f"{chunk.get('document')}"
        )

        print(
            f"Pages:      "
            f"{pages}"
        )

        print(
            f"Chunk:      "
            f"{chunk.get('chunk_id')}"
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
                f"Source: "
                f"{source_url}"
            )

    print()
    print("-" * 70)


# ---------------------------------------------------------
# CLI
# ---------------------------------------------------------

def main() -> None:

    parser = argparse.ArgumentParser(
        description=(
            "Search MineLens using semantic "
            "vector embeddings."
        )
    )

    parser.add_argument(
        "query",
        nargs="+",
        help="Semantic search query",
    )

    parser.add_argument(
        "--top-k",
        type=int,
        default=DEFAULT_TOP_K,
        help=(
            "Number of results to return "
            f"(default: {DEFAULT_TOP_K})"
        ),
    )

    parser.add_argument(
        "--rebuild",
        action="store_true",
        help=(
            "Ignore cached embeddings "
            "and rebuild the index"
        ),
    )

    args = parser.parse_args()

    query = " ".join(
        args.query
    )

    print(
        "Loading MineLens chunks..."
    )

    chunks = load_chunks()

    print(
        f"Loaded {len(chunks)} chunks."
    )

    index = SemanticIndex(
        chunks
    )

    cache_loaded = False

    if not args.rebuild:

        cache_loaded = (
            load_embedding_cache(
                index
            )
        )

    if not cache_loaded:

        index.build()

        save_embedding_cache(
            index
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