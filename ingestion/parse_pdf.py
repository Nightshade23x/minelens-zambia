from __future__ import annotations

import argparse
import json
import re

from datetime import datetime, timezone
from pathlib import Path

import pymupdf


# ---------------------------------------------------------
# Project paths
# ---------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]

RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"


# ---------------------------------------------------------
# Text cleaning
# ---------------------------------------------------------

def clean_text(text: str) -> str:
    """
    Perform light cleaning on extracted PDF text.

    We deliberately avoid aggressive cleaning at this stage
    because tables, headings and paragraph boundaries may
    become useful later for retrieval.
    """

    # Remove soft hyphen characters.
    text = text.replace("\u00ad", "")

    # Replace non-breaking spaces with normal spaces.
    text = text.replace("\u00a0", " ")

    cleaned_lines: list[str] = []

    for line in text.splitlines():

        # Collapse repeated spaces and tabs.
        line = re.sub(r"[ \t]+", " ", line)

        # Remove whitespace around the line.
        line = line.strip()

        cleaned_lines.append(line)

    # Reassemble the page.
    text = "\n".join(cleaned_lines)

    # Do not allow huge groups of empty lines.
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


# ---------------------------------------------------------
# Metadata
# ---------------------------------------------------------

def load_download_metadata(pdf_path: Path) -> dict:
    """
    Load the metadata created by download.py.

    If no metadata file exists, return an empty dictionary.
    """

    metadata_path = pdf_path.with_suffix(
        pdf_path.suffix + ".metadata.json"
    )

    if not metadata_path.exists():
        return {}

    with metadata_path.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


# ---------------------------------------------------------
# PDF parsing
# ---------------------------------------------------------

def parse_pdf(
    pdf_path: Path,
    overwrite: bool = False,
) -> Path:
    """
    Extract text from a PDF page-by-page.

    Each page is stored as one JSON object in a JSONL file.

    This preserves page numbers so MineLens can later provide
    citations such as:

        Source: Mining Statistical Bulletin
        Page: 17
    """

    if not pdf_path.exists():
        raise FileNotFoundError(
            f"PDF not found: {pdf_path}"
        )

    if pdf_path.suffix.lower() != ".pdf":
        raise ValueError(
            f"Expected a PDF file, got: {pdf_path.name}"
        )

    PROCESSED_DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path = (
        PROCESSED_DATA_DIR
        / f"{pdf_path.stem}.pages.jsonl"
    )

    summary_path = (
        PROCESSED_DATA_DIR
        / f"{pdf_path.stem}.parse.json"
    )

    if output_path.exists() and not overwrite:
        print(f"Parsed file already exists: {output_path}")
        print("Use --overwrite to parse it again.")

        return output_path

    download_metadata = load_download_metadata(pdf_path)

    print(f"Opening PDF:")
    print(f"  {pdf_path}")

    document = pymupdf.open(pdf_path)

    total_pages = len(document)

    print()
    print(f"Pages found: {total_pages}")
    print("Extracting text...")
    print()

    total_characters = 0
    pages_with_text = 0
    pages_without_text = 0

    temporary_output = output_path.with_suffix(
        output_path.suffix + ".part"
    )

    try:
        with temporary_output.open(
            "w",
            encoding="utf-8",
        ) as output_file:

            for page_index, page in enumerate(
                document,
                start=1,
            ):
                raw_text = page.get_text("text")

                cleaned_text = clean_text(raw_text)

                character_count = len(cleaned_text)

                has_text = bool(cleaned_text)

                if has_text:
                    pages_with_text += 1
                else:
                    pages_without_text += 1

                total_characters += character_count

                page_record = {
                    "document": pdf_path.name,
                    "page": page_index,
                    "text": cleaned_text,
                    "character_count": character_count,
                    "has_text": has_text,
                    "source_url": download_metadata.get(
                        "source_url"
                    ),
                    "document_sha256": download_metadata.get(
                        "sha256"
                    ),
                }

                output_file.write(
                    json.dumps(
                        page_record,
                        ensure_ascii=False,
                    )
                )

                output_file.write("\n")

                print(
                    f"Page {page_index:>3}/{total_pages} "
                    f"- {character_count:,} characters"
                )

        temporary_output.replace(output_path)

    except Exception:
        temporary_output.unlink(
            missing_ok=True
        )
        raise

    finally:
        document.close()

    # -----------------------------------------------------
    # Parse summary
    # -----------------------------------------------------

    summary = {
        "document": pdf_path.name,
        "source_url": download_metadata.get(
            "source_url"
        ),
        "document_sha256": download_metadata.get(
            "sha256"
        ),
        "parsed_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "total_pages": total_pages,
        "pages_with_text": pages_with_text,
        "pages_without_text": pages_without_text,
        "total_characters": total_characters,
        "output_file": output_path.name,
    }

    with summary_path.open(
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            summary,
            file,
            indent=4,
        )

    print()
    print("PDF parsing complete.")
    print(f"Output:  {output_path}")
    print(f"Summary: {summary_path}")
    print()
    print(f"Pages with text:    {pages_with_text}")
    print(f"Pages without text: {pages_without_text}")
    print(f"Characters:         {total_characters:,}")

    if pages_without_text > 0:
        print()
        print(
            "Note: Some pages contain no extractable text. "
            "They may be images or scanned pages."
        )

    return output_path


# ---------------------------------------------------------
# Command-line interface
# ---------------------------------------------------------

def main() -> None:

    parser = argparse.ArgumentParser(
        description=(
            "Extract page-level text from MineLens PDF documents."
        )
    )

    parser.add_argument(
        "pdf",
        help=(
            "PDF filename inside data/raw/ "
            "or a complete path to a PDF"
        ),
    )

    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace an existing parsed output",
    )

    args = parser.parse_args()

    supplied_path = Path(args.pdf)

    # If only a filename was supplied, assume it is
    # inside data/raw/.
    if not supplied_path.is_absolute():
        supplied_path = RAW_DATA_DIR / supplied_path

    parse_pdf(
        pdf_path=supplied_path,
        overwrite=args.overwrite,
    )


if __name__ == "__main__":
    main()
    