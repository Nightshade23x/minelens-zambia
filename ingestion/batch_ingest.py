from __future__ import annotations

import argparse
import json

from pathlib import Path

from ingestion.chunk import chunk_document
from ingestion.download import download_document
from ingestion.parse_html import parse_html
from ingestion.parse_pdf import parse_pdf


# ---------------------------------------------------------
# Paths
# ---------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_SOURCE_FILE = (
    PROJECT_ROOT
    / "config"
    / "sources.json"
)

RAW_DATA_DIR = (
    PROJECT_ROOT
    / "data"
    / "raw"
)


# ---------------------------------------------------------
# Source registry
# ---------------------------------------------------------

def load_sources(
    source_file: Path = DEFAULT_SOURCE_FILE,
) -> list[dict]:
    """
    Load and validate MineLens sources from the
    JSON source registry.
    """

    if not source_file.exists():
        raise FileNotFoundError(
            f"Source registry not found: "
            f"{source_file}"
        )

    with source_file.open(
        "r",
        encoding="utf-8",
    ) as file:

        sources = json.load(
            file
        )

    if not isinstance(
        sources,
        list,
    ):
        raise ValueError(
            "sources.json must contain "
            "a JSON list."
        )

    required_fields = {
        "id",
        "title",
        "agency",
        "document_type",
        "source_type",
        "url",
        "filename",
    }

    supported_source_types = {
        "pdf",
        "html",
    }

    seen_ids: set[str] = set()

    for source in sources:

        if not isinstance(
            source,
            dict,
        ):
            raise ValueError(
                "Every source in sources.json "
                "must be a JSON object."
            )

        missing = (
            required_fields
            - source.keys()
        )

        if missing:
            raise ValueError(
                f"Source "
                f"{source.get('id')} "
                f"is missing fields: "
                f"{sorted(missing)}"
            )

        source_id = source[
            "id"
        ]

        if source_id in seen_ids:
            raise ValueError(
                f"Duplicate source ID: "
                f"{source_id}"
            )

        seen_ids.add(
            source_id
        )

        source_type = source[
            "source_type"
        ].lower()

        if (
            source_type
            not in supported_source_types
        ):
            raise ValueError(
                f"Unsupported source_type "
                f"'{source_type}' "
                f"for source "
                f"'{source_id}'."
            )

        # Normalize the value once so the rest of
        # the pipeline does not need to handle
        # PDF/pdf/Html/etc.

        source[
            "source_type"
        ] = source_type

        filename = source[
            "filename"
        ].lower()

        if (
            source_type == "pdf"
            and not filename.endswith(
                ".pdf"
            )
        ):
            raise ValueError(
                f"PDF source "
                f"'{source_id}' "
                f"must use a .pdf filename."
            )

        if (
            source_type == "html"
            and not filename.endswith(
                (
                    ".html",
                    ".htm",
                )
            )
        ):
            raise ValueError(
                f"HTML source "
                f"'{source_id}' "
                f"must use a .html "
                f"or .htm filename."
            )

    return sources


# ---------------------------------------------------------
# Utilities
# ---------------------------------------------------------

def count_jsonl_records(
    path: Path,
) -> int:
    """
    Count non-empty records in a JSONL file.
    """

    if not path.exists():
        return 0

    count = 0

    with path.open(
        "r",
        encoding="utf-8",
    ) as file:

        for line in file:

            if line.strip():
                count += 1

    return count


# ---------------------------------------------------------
# Metadata enrichment
# ---------------------------------------------------------

def enrich_metadata(
    document_path: Path,
    source: dict,
) -> None:
    """
    Add MineLens-specific registry information to the
    metadata associated with a downloaded source.
    """

    metadata_path = (
        document_path.with_suffix(
            document_path.suffix
            + ".metadata.json"
        )
    )

    if not metadata_path.exists():
        return

    with metadata_path.open(
        "r",
        encoding="utf-8",
    ) as file:

        metadata = json.load(
            file
        )

    metadata.update(
        {
            "source_id": source[
                "id"
            ],
            "title": source[
                "title"
            ],
            "agency": source[
                "agency"
            ],
            "document_type": source[
                "document_type"
            ],
            "source_type": source[
                "source_type"
            ],
        }
    )

    with metadata_path.open(
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            metadata,
            file,
            indent=4,
        )


# ---------------------------------------------------------
# PDF ingestion
# ---------------------------------------------------------

def ingest_pdf_source(
    source: dict,
    overwrite: bool = False,
) -> tuple[Path, Path]:
    """
    Download and parse one PDF source.

    Returns:
        raw_path
        pages_path
    """

    raw_path = download_document(
        url=source[
            "url"
        ],
        filename=source[
            "filename"
        ],
        overwrite=overwrite,
    )

    enrich_metadata(
        document_path=raw_path,
        source=source,
    )

    pages_path = parse_pdf(
        pdf_path=raw_path,
        overwrite=overwrite,
    )

    return (
        raw_path,
        pages_path,
    )


# ---------------------------------------------------------
# HTML ingestion
# ---------------------------------------------------------

def ingest_html_source(
    source: dict,
    overwrite: bool = False,
) -> tuple[Path, Path]:
    """
    Download and parse one HTML source.

    parse_html() handles both downloading and parsing
    the webpage.
    """

    pages_path = parse_html(
        url=source[
            "url"
        ],
        filename=source[
            "filename"
        ],
        overwrite=overwrite,
    )

    raw_path = (
        RAW_DATA_DIR
        / source[
            "filename"
        ]
    )

    enrich_metadata(
        document_path=raw_path,
        source=source,
    )

    return (
        raw_path,
        pages_path,
    )


# ---------------------------------------------------------
# One source
# ---------------------------------------------------------

def ingest_source(
    source: dict,
    overwrite: bool = False,
) -> dict:
    """
    Run one source through the complete MineLens
    ingestion pipeline.

    Supported source types:
        PDF
        HTML
    """

    source_id = source[
        "id"
    ]

    source_type = source[
        "source_type"
    ]

    print()
    print("=" * 72)

    print(
        f"INGESTING: "
        f"{source_id}"
    )

    print("=" * 72)

    print(
        f"Title:       "
        f"{source['title']}"
    )

    print(
        f"Document:    "
        f"{source['document_type']}"
    )

    print(
        f"Source type: "
        f"{source_type}"
    )

    print()

    # -----------------------------------------------------
    # Source-specific ingestion
    # -----------------------------------------------------

    if source_type == "pdf":

        raw_path, pages_path = (
            ingest_pdf_source(
                source=source,
                overwrite=overwrite,
            )
        )

    elif source_type == "html":

        raw_path, pages_path = (
            ingest_html_source(
                source=source,
                overwrite=overwrite,
            )
        )

    else:

        # load_sources() should prevent this path,
        # but retaining the guard makes ingest_source()
        # safe when called directly.

        raise ValueError(
            f"Unsupported source type: "
            f"{source_type}"
        )

    # -----------------------------------------------------
    # Chunk
    # -----------------------------------------------------

    chunks_path = chunk_document(
        input_path=pages_path,
        overwrite=overwrite,
    )

    chunk_count = (
        count_jsonl_records(
            chunks_path
        )
    )

    # -----------------------------------------------------
    # Empty document handling
    # -----------------------------------------------------

    if chunk_count == 0:

        if source_type == "pdf":

            print()
            print(
                "[WARNING] No searchable text "
                "was extracted from this document."
            )

            print(
                "The PDF may be scanned and "
                "require OCR."
            )

            return {
                "id": source_id,
                "status": "needs_ocr",
                "source_type": source_type,
                "raw": str(
                    raw_path
                ),
                "pages": str(
                    pages_path
                ),
                "chunks": str(
                    chunks_path
                ),
                "chunk_count": 0,
            }

        raise ValueError(
            "HTML source produced zero "
            "searchable chunks."
        )

    # -----------------------------------------------------
    # Success
    # -----------------------------------------------------

    return {
        "id": source_id,
        "status": "success",
        "source_type": source_type,
        "raw": str(
            raw_path
        ),
        "pages": str(
            pages_path
        ),
        "chunks": str(
            chunks_path
        ),
        "chunk_count": chunk_count,
    }


# ---------------------------------------------------------
# Batch ingestion
# ---------------------------------------------------------

def ingest_sources(
    sources: list[dict],
    source_ids: set[str] | None = None,
    overwrite: bool = False,
) -> list[dict]:
    """
    Ingest all enabled sources, or a selected subset.
    """

    results: list[dict] = []

    for source in sources:

        if not source.get(
            "enabled",
            True,
        ):
            continue

        if (
            source_ids
            and source[
                "id"
            ]
            not in source_ids
        ):
            continue

        try:

            result = ingest_source(
                source=source,
                overwrite=overwrite,
            )

        except Exception as error:

            print()
            print(
                f"[FAILED] "
                f"{source['id']}"
            )

            print(
                f"{type(error).__name__}: "
                f"{error}"
            )

            result = {
                "id": source[
                    "id"
                ],
                "status": "failed",
                "source_type": source.get(
                    "source_type"
                ),
                "error": str(
                    error
                ),
            }

        results.append(
            result
        )

    return results


# ---------------------------------------------------------
# Summary
# ---------------------------------------------------------

def display_summary(
    results: list[dict],
) -> None:

    print()
    print("=" * 72)

    print(
        "MINELENS INGESTION SUMMARY"
    )

    print("=" * 72)

    successful = [
        result
        for result in results
        if result[
            "status"
        ] == "success"
    ]

    needs_ocr = [
        result
        for result in results
        if result[
            "status"
        ] == "needs_ocr"
    ]

    failed = [
        result
        for result in results
        if result[
            "status"
        ] == "failed"
    ]

    print()

    print(
        f"Successful: "
        f"{len(successful)}"
    )

    print(
        f"Needs OCR:  "
        f"{len(needs_ocr)}"
    )

    print(
        f"Failed:     "
        f"{len(failed)}"
    )

    if successful:

        print()
        print(
            "Successfully ingested:"
        )

        for result in successful:

            print(
                f"  [OK] "
                f"{result['id']} "
                f"({result['source_type']}, "
                f"{result['chunk_count']} chunks)"
            )

    if needs_ocr:

        print()
        print(
            "Needs OCR:"
        )

        for result in needs_ocr:

            print(
                f"  [OCR] "
                f"{result['id']}"
            )

    if failed:

        print()
        print(
            "Failed:"
        )

        for result in failed:

            print(
                f"  [FAIL] "
                f"{result['id']}"
            )

            print(
                f"         "
                f"{result['error']}"
            )


# ---------------------------------------------------------
# CLI
# ---------------------------------------------------------

def main() -> None:

    parser = argparse.ArgumentParser(
        description=(
            "Batch ingest MineLens "
            "official mining sources."
        )
    )

    parser.add_argument(
        "--source",
        action="append",
        help=(
            "Only ingest a specific source ID. "
            "Can be supplied multiple times."
        ),
    )

    parser.add_argument(
        "--overwrite",
        action="store_true",
        help=(
            "Redownload and regenerate "
            "existing sources."
        ),
    )

    args = parser.parse_args()

    sources = load_sources()

    selected_sources = (
        set(
            args.source
        )
        if args.source
        else None
    )

    results = ingest_sources(
        sources=sources,
        source_ids=selected_sources,
        overwrite=args.overwrite,
    )

    if not results:

        print(
            "No matching enabled "
            "sources found."
        )

        return

    display_summary(
        results
    )


if __name__ == "__main__":
    main()