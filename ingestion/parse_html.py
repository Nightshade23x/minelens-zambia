from __future__ import annotations

import argparse
import hashlib
import json
import re

from datetime import datetime, timezone
from pathlib import Path

import truststore

truststore.inject_into_ssl()

import requests

from bs4 import BeautifulSoup
from bs4.element import Tag


# ---------------------------------------------------------
# Project paths
# ---------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]

RAW_DATA_DIR = (
    PROJECT_ROOT
    / "data"
    / "raw"
)

PROCESSED_DATA_DIR = (
    PROJECT_ROOT
    / "data"
    / "processed"
)


# ---------------------------------------------------------
# Text cleaning
# ---------------------------------------------------------

def clean_text(
    text: str,
) -> str:
    """
    Apply light text cleaning while preserving the
    source wording.
    """

    text = text.replace(
        "\u00ad",
        "",
    )

    text = text.replace(
        "\xa0",
        " ",
    )

    # Common mojibake produced by some older
    # WordPress/government pages.
    replacements = {
        "â€™": "’",
        "â€˜": "‘",
        "â€œ": "“",
        "â€\x9d": "”",
        "â€“": "–",
        "â€”": "—",
        "Â©": "©",
        "Â": "",
    }

    for bad, good in replacements.items():
        text = text.replace(
            bad,
            good,
        )

    text = re.sub(
        r"[ \t]+",
        " ",
        text,
    )

    text = re.sub(
        r"\n{3,}",
        "\n\n",
        text,
    )

    return text.strip()

# ---------------------------------------------------------
# Hashing
# ---------------------------------------------------------

def sha256_bytes(
    content: bytes,
) -> str:
    """
    Calculate SHA-256 for downloaded HTML.
    """

    return hashlib.sha256(
        content
    ).hexdigest()


# ---------------------------------------------------------
# Main-content detection
# ---------------------------------------------------------

def find_main_content(
    soup: BeautifulSoup,
) -> Tag:
    """
    Find the most likely element containing the useful
    page content.

    WordPress sites commonly use entry-content, article,
    or main containers.
    """

    selectors = [
        ".entry-content",
        ".post-content",
        ".page-content",
        "article",
        "main",
        "body",
    ]

    for selector in selectors:

        element = soup.select_one(
            selector
        )

        if element is not None:
            return element

    raise ValueError(
        "Could not find readable HTML content."
    )


# ---------------------------------------------------------
# HTML extraction
# ---------------------------------------------------------

def extract_html_text(
    html: str,
) -> str:
    """
    Extract useful structured text from an HTML page.

    Standard headings, Elementor accordion titles,
    paragraphs, list items and table rows are preserved.

    Duplicate content is removed within each section,
    but repeated requirements across different licence
    sections are intentionally preserved.
    """

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    main_content = find_main_content(
        soup
    )

    # Remove obvious non-content elements.

    for element in main_content.select(
        (
            "script, style, noscript, "
            "nav, header, footer, form, "
            "svg, iframe"
        )
    ):

        element.decompose()

    stop_headings = {
        "contact information",
        "external links",
        "confidential reporting",
        "frequently asked question",
    }

    heading_tags = {
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
    }

    elements = main_content.select(
        (
            "h1, h2, h3, h4, h5, h6, "
            "div.elementor-tab-title, "
            "p, li, tr"
        )
    )

    blocks: list[str] = []

    # Duplicate tracking is section-local.
    #
    # When a new heading or accordion title begins,
    # this set is reset so legitimate repeated
    # requirements in another licence section are kept.

    seen_in_section: set[str] = set()

    for element in elements:

        is_accordion_title = (
            element.name == "div"
            and "elementor-tab-title"
            in element.get(
                "class",
                [],
            )
        )

        is_heading = (
            element.name
            in heading_tags
            or is_accordion_title
        )

        # ---------------------------------------------
        # Avoid parent/child duplicate blocks
        # ---------------------------------------------

        if element.name in {
            "p",
            "li",
        }:

            nested_block = element.find(
                [
                    "p",
                    "li",
                    "tr",
                ]
            )

            if nested_block is not None:
                continue

        # ---------------------------------------------
        # Tables
        # ---------------------------------------------

        if element.name == "tr":

            cells = element.find_all(
                [
                    "th",
                    "td",
                ]
            )

            parts = [
                clean_text(
                    cell.get_text(
                        " ",
                        strip=True,
                    )
                )
                for cell in cells
            ]

            parts = [
                part
                for part in parts
                if part
            ]

            text = " | ".join(
                parts
            )

        else:

            text = clean_text(
                element.get_text(
                    " ",
                    strip=True,
                )
            )

        if not text:
            continue

        # ---------------------------------------------
        # Stop before website boilerplate
        # ---------------------------------------------

        if (
            is_heading
            and text.lower()
            in stop_headings
        ):

            break

        # ---------------------------------------------
        # New section
        # ---------------------------------------------

        if is_heading:

            seen_in_section.clear()

            blocks.append(
                text
            )

            continue

        # ---------------------------------------------
        # Remove duplicates only within this section
        # ---------------------------------------------

        normalized = (
            text.lower()
            .strip()
        )

        if normalized in seen_in_section:
            continue

        seen_in_section.add(
            normalized
        )

        blocks.append(
            text
        )

    if not blocks:

        fallback = clean_text(
            main_content.get_text(
                "\n",
                strip=True,
            )
        )

        if fallback:
            blocks.append(
                fallback
            )

    return "\n\n".join(
        blocks
    )

# ---------------------------------------------------------
# Download HTML
# ---------------------------------------------------------

def download_html(
    url: str,
    filename: str,
    overwrite: bool = False,
) -> tuple[Path, dict]:
    """
    Download an HTML page into data/raw and create
    source metadata.
    """

    RAW_DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    raw_path = (
        RAW_DATA_DIR
        / filename
    )

    metadata_path = raw_path.with_suffix(
        raw_path.suffix
        + ".metadata.json"
    )

    if (
        raw_path.exists()
        and not overwrite
    ):

        print(
            f"HTML file already exists: "
            f"{raw_path}"
        )

        if metadata_path.exists():

            with metadata_path.open(
                "r",
                encoding="utf-8",
            ) as file:

                metadata = json.load(
                    file
                )

        else:

            content = raw_path.read_bytes()

            metadata = {
                "filename": raw_path.name,
                "source_url": url,
                "final_url": url,
                "content_type": "text/html",
                "size_bytes": len(content),
                "sha256": sha256_bytes(
                    content
                ),
            }

        return (
            raw_path,
            metadata,
        )

    print(
        "Downloading HTML:"
    )

    print(
        f"  {url}"
    )

    response = requests.get(
        url,
        timeout=60,
        headers={
            "User-Agent": (
                "MineLens-Zambia/0.1 "
                "research-document-indexer"
            )
        },
    )

    response.raise_for_status()

    content = response.content

    content_type = (
        response.headers.get(
            "Content-Type",
            "",
        )
    )

    if (
        "html"
        not in content_type.lower()
    ):

        raise ValueError(
            "URL did not return HTML. "
            f"Content-Type: {content_type}"
        )

    raw_path.write_bytes(
        content
    )

    document_sha256 = sha256_bytes(
        content
    )

    metadata = {
        "filename": raw_path.name,
        "source_url": url,
        "final_url": str(
            response.url
        ),
        "downloaded_at": (
            datetime.now(
                timezone.utc
            ).isoformat()
        ),
        "content_type": content_type,
        "size_bytes": len(
            content
        ),
        "sha256": document_sha256,
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

    print()
    print(
        "HTML download successful."
    )

    print(
        f"Document: {raw_path}"
    )

    print(
        f"Metadata: {metadata_path}"
    )

    return (
        raw_path,
        metadata,
    )


# ---------------------------------------------------------
# Parse HTML
# ---------------------------------------------------------

def parse_html(
    url: str,
    filename: str,
    overwrite: bool = False,
) -> Path:
    """
    Download and parse a webpage into the same page-JSONL
    format used by MineLens PDF ingestion.

    HTML documents use page=1 because web pages
    have no physical page boundaries.
    """

    if not filename.lower().endswith(
        ".html"
    ):

        filename += ".html"

    raw_path, metadata = download_html(
        url=url,
        filename=filename,
        overwrite=overwrite,
    )

    PROCESSED_DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    stem = raw_path.stem

    pages_path = (
        PROCESSED_DATA_DIR
        / f"{stem}.pages.jsonl"
    )

    summary_path = (
        PROCESSED_DATA_DIR
        / f"{stem}.parse.json"
    )

    if (
        pages_path.exists()
        and not overwrite
    ):

        print(
            f"Parsed HTML already exists: "
            f"{pages_path}"
        )

        print(
            "Use --overwrite to parse it again."
        )

        return pages_path

    html = raw_path.read_text(
        encoding="utf-8",
        errors="replace",
    )

    print()
    print(
        "Extracting webpage text..."
    )

    text = extract_html_text(
        html
    )

    if not text:

        raise ValueError(
            "No useful text could be extracted "
            "from the HTML page."
        )

    record = {
        "document": raw_path.name,
        "page": 1,
        "text": text,
        "character_count": len(
            text
        ),
        "source_url": metadata.get(
            "source_url"
        ),
        "document_sha256": metadata.get(
            "sha256"
        ),
        "content_type": "html",
    }

    with pages_path.open(
        "w",
        encoding="utf-8",
    ) as file:

        file.write(
            json.dumps(
                record,
                ensure_ascii=False,
            )
        )

        file.write(
            "\n"
        )

    summary = {
        "document": raw_path.name,
        "source_url": metadata.get(
            "source_url"
        ),
        "content_type": "html",
        "sections": 1,
        "characters": len(
            text
        ),
        "document_sha256": metadata.get(
            "sha256"
        ),
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
    print(
        "HTML parsing complete."
    )

    print(
        f"Characters: {len(text):,}"
    )

    print(
        f"Output:     {pages_path}"
    )

    print(
        f"Summary:    {summary_path}"
    )

    return pages_path


# ---------------------------------------------------------
# CLI
# ---------------------------------------------------------

def main() -> None:

    parser = argparse.ArgumentParser(
        description=(
            "Download and parse an HTML webpage "
            "for MineLens."
        )
    )

    parser.add_argument(
        "url",
        help="URL of webpage to ingest",
    )

    parser.add_argument(
        "--filename",
        required=True,
        help=(
            "Local HTML filename, for example "
            "mining_rights.html"
        ),
    )

    parser.add_argument(
        "--overwrite",
        action="store_true",
        help=(
            "Redownload and reparse the webpage."
        ),
    )

    args = parser.parse_args()

    parse_html(
        url=args.url,
        filename=args.filename,
        overwrite=args.overwrite,
    )


if __name__ == "__main__":
    main()