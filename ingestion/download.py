from __future__ import annotations

import argparse
import hashlib
import json

from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlparse

import truststore

# Use the operating system's trusted certificate store.
# On Windows this allows Python to use the same trusted
# certificate infrastructure as applications such as curl.
truststore.inject_into_ssl()

import requests


# ---------------------------------------------------------
# Project paths
# ---------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]

RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"


# ---------------------------------------------------------
# Download configuration
# ---------------------------------------------------------

DEFAULT_TIMEOUT = (10, 120)

HEADERS = {
    "User-Agent": "MineLens-Zambia/0.1"
}


# ---------------------------------------------------------
# Helper functions
# ---------------------------------------------------------

def get_filename_from_url(url: str) -> str:
    """
    Extract a filename from a URL.

    Example:
        https://example.com/reports/mining.pdf

    becomes:
        mining.pdf
    """

    parsed_url = urlparse(url)

    filename = Path(unquote(parsed_url.path)).name

    if not filename:
        filename = "downloaded_document"

    return filename


def create_sha256(file_path: Path) -> str:
    """
    Calculate a SHA-256 hash for a downloaded file.

    This allows us to detect later whether a government
    document has changed.
    """

    sha256 = hashlib.sha256()

    with file_path.open("rb") as file:
        while True:
            chunk = file.read(1024 * 1024)

            if not chunk:
                break

            sha256.update(chunk)

    return sha256.hexdigest()


def verify_pdf(file_path: Path) -> None:
    """
    Check that a file claiming to be a PDF really is a PDF.

    PDF files normally begin with the bytes:

        %PDF-

    This protects us from accidentally saving an HTML error
    page as something like report.pdf.
    """

    if file_path.suffix.lower() != ".pdf":
        return

    with file_path.open("rb") as file:
        header = file.read(5)

    if header != b"%PDF-":
        file_path.unlink(missing_ok=True)

        raise ValueError(
            f"{file_path.name} does not appear to be a valid PDF."
        )


# ---------------------------------------------------------
# Main download function
# ---------------------------------------------------------

def download_document(
    url: str,
    filename: str | None = None,
    overwrite: bool = False,
) -> Path:
    """
    Download a document into data/raw/.

    A metadata JSON file is also created so that MineLens
    always knows where the document originally came from.
    """

    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)

    if filename is None:
        filename = get_filename_from_url(url)

    destination = RAW_DATA_DIR / filename

    if destination.exists() and not overwrite:
        print(f"File already exists: {destination}")
        print("Use --overwrite if you want to download it again.")

        return destination

    temporary_file = destination.with_suffix(
        destination.suffix + ".part"
    )

    print(f"Downloading:")
    print(f"  {url}")

    try:
        with requests.get(
            url,
            headers=HEADERS,
            stream=True,
            timeout=DEFAULT_TIMEOUT,
        ) as response:

            response.raise_for_status()

            with temporary_file.open("wb") as file:

                for chunk in response.iter_content(
                    chunk_size=1024 * 1024
                ):
                    if chunk:
                        file.write(chunk)

            final_url = response.url
            content_type = response.headers.get(
                "Content-Type",
                "unknown",
            )

    except Exception:
        temporary_file.unlink(missing_ok=True)
        raise

    # Validate PDFs before accepting the file.
    verify_pdf(temporary_file)

    # Rename the temporary file only after the download succeeds.
    temporary_file.replace(destination)

    # -----------------------------------------------------
    # File metadata
    # -----------------------------------------------------

    file_size = destination.stat().st_size

    sha256 = create_sha256(destination)

    metadata = {
        "filename": destination.name,
        "source_url": url,
        "final_url": final_url,
        "downloaded_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "content_type": content_type,
        "size_bytes": file_size,
        "sha256": sha256,
    }

    metadata_path = destination.with_suffix(
        destination.suffix + ".metadata.json"
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

    print()
    print("Download successful.")
    print(f"Document: {destination}")
    print(f"Metadata: {metadata_path}")
    print(f"Size: {file_size:,} bytes")
    print(f"SHA-256: {sha256}")

    return destination


# ---------------------------------------------------------
# Command-line interface
# ---------------------------------------------------------

def main() -> None:

    parser = argparse.ArgumentParser(
        description=(
            "Download documents for the "
            "MineLens Zambia dataset."
        )
    )

    parser.add_argument(
        "url",
        help="URL of the document to download",
    )

    parser.add_argument(
        "--filename",
        help="Optional filename to use",
    )

    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite the document if it already exists",
    )

    args = parser.parse_args()

    download_document(
        url=args.url,
        filename=args.filename,
        overwrite=args.overwrite,
    )


if __name__ == "__main__":
    main()