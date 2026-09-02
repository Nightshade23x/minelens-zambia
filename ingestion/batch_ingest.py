from __future__ import annotations

import argparse
import json

from pathlib import Path

from ingestion.chunk import chunk_document
from ingestion.download import download_document
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


# ---------------------------------------------------------
# Source registry
# ---------------------------------------------------------

def load_sources(
    source_file: Path = DEFAULT_SOURCE_FILE,
) -> list[dict]:
    """
    Load MineLens document sources from the JSON registry.
    """

    if not source_file.exists():
        raise FileNotFoundError(
            f"Source registry not found: {source_file}"
        )

    with source_file.open(
        "r",
        encoding="utf-8",
    ) as file:

        sources = json.load(file)

    if not isinstance(sources, list):
        raise ValueError(
            "sources.json must contain a JSON list."
        )

    required_fields = {
        "id",
        "title",
        "agency",
        "document_type",
        "url",
        "filename",
    }

    for source in sources:

        missing = (
            required_fields
            - source.keys()
        )

        if missing:
            raise ValueError(
                f"Source {source.get('id')} "
                f"is missing fields: "
                f"{sorted(missing)}"
            )

    return sources


# ---------------------------------------------------------
# Metadata enrichment
# ---------------------------------------------------------

def enrich_metadata(
    pdf_path: Path,
    source: dict,
) -> None:
    """
    Add MineLens-specific source information to the
    metadata created by download.py.
    """

    metadata_path = pdf_path.with_suffix(
        pdf_path.suffix
        + ".metadata.json"
    )

    if not metadata_path.exists():
        return

    with metadata_path.open(
        "r",
        encoding="utf-8",
    ) as file:

        metadata = json.load(file)

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
# One source
# ---------------------------------------------------------

def ingest_source(
    source: dict,
    overwrite: bool = False,
) -> dict:
    """
    Run one source through the complete MineLens
    PDF ingestion pipeline.
    """

    source_id = source[
        "id"
    ]

    print()
    print("=" * 72)

    print(
        f"INGESTING: {source_id}"
    )

    print("=" * 72)

    print(
        f"Title: {source['title']}"
    )

    print(
        f"Type:  {source['document_type']}"
    )

    print()

    # -----------------------------------------------------
    # Download
    # -----------------------------------------------------

    pdf_path = download_document(
        url=source["url"],
        filename=source["filename"],
        overwrite=overwrite,
    )

    enrich_metadata(
        pdf_path=pdf_path,
        source=source,
    )

    # -----------------------------------------------------
    # Parse PDF
    # -----------------------------------------------------

    pages_path = parse_pdf(
        pdf_path=pdf_path,
        overwrite=overwrite,
    )

    # -----------------------------------------------------
    # Chunk
    # -----------------------------------------------------

    chunks_path = chunk_document(
        input_path=pages_path,
        overwrite=overwrite,
    )
    chunk_count = count_jsonl_records(
        chunks_path
    )

    if chunk_count == 0:

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
            "pdf": str(pdf_path),
            "pages": str(pages_path),
            "chunks": str(chunks_path),
            "chunk_count": 0,
        }
    return {
        "id": source_id,
        "status": "success",
        "pdf": str(pdf_path),
        "pages": str(pages_path),
        "chunks": str(chunks_path),
        "chunk_count": chunk_count,
    }    


# ---------------------------------------------------------
# Batch ingestion
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
            and source["id"]
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
        if result["status"] == "success"
    ]

    needs_ocr = [
        result
        for result in results
        if result["status"] == "needs_ocr"
    ]

    failed = [
        result
        for result in results
        if result["status"] == "failed"
    ]

    print()

    print(
        f"Successful: {len(successful)}"
    )

    print(
        f"Needs OCR:  {len(needs_ocr)}"
    )

    print(
        f"Failed:     {len(failed)}"
    )

    if successful:

        print()
        print(
            "Successfully ingested:"
        )

        for result in successful:

            print(
                f"  [OK] "
                f"{result['id']}"
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
            "official mining documents."
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
            "existing documents."
        ),
    )

    args = parser.parse_args()

    sources = load_sources()

    selected_sources = (
        set(args.source)
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
            "No matching enabled sources found."
        )

        return

    display_summary(
        results
    )


if __name__ == "__main__":
    main()