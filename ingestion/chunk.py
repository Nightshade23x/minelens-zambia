from __future__ import annotations

import argparse
import json
import re

from datetime import datetime, timezone
from pathlib import Path


# ---------------------------------------------------------
# Project paths
# ---------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]

PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"


# ---------------------------------------------------------
# Default chunking configuration
# ---------------------------------------------------------

DEFAULT_TARGET_CHARS = 1200
DEFAULT_MAX_CHARS = 1600
DEFAULT_OVERLAP_CHARS = 200


# ---------------------------------------------------------
# Input loading
# ---------------------------------------------------------

def load_pages(input_path: Path) -> list[dict]:
    """
    Load page records from the JSONL file produced by parse_pdf.py.
    """

    if not input_path.exists():
        raise FileNotFoundError(
            f"Parsed page file not found: {input_path}"
        )

    pages: list[dict] = []

    with input_path.open(
        "r",
        encoding="utf-8",
    ) as file:

        for line_number, line in enumerate(file, start=1):

            line = line.strip()

            if not line:
                continue

            try:
                record = json.loads(line)

            except json.JSONDecodeError as error:
                raise ValueError(
                    f"Invalid JSON on line {line_number}"
                ) from error

            pages.append(record)

    if not pages:
        raise ValueError(
            f"No page records found in {input_path}"
        )

    return pages


# ---------------------------------------------------------
# Text splitting
# ---------------------------------------------------------

def split_long_text(
    text: str,
    max_chars: int,
) -> list[str]:
    """
    Split an unusually long paragraph/block without cutting
    through words where possible.
    """

    text = text.strip()

    if len(text) <= max_chars:
        return [text]

    pieces: list[str] = []

    remaining = text

    while len(remaining) > max_chars:

        split_position = remaining.rfind(
            " ",
            0,
            max_chars + 1,
        )

        # If no convenient space is found, perform a hard split.
        if split_position <= 0:
            split_position = max_chars

        piece = remaining[:split_position].strip()

        if piece:
            pieces.append(piece)

        remaining = remaining[split_position:].strip()

    if remaining:
        pieces.append(remaining)

    return pieces


def page_to_segments(
    page_record: dict,
    max_chars: int,
) -> list[dict]:
    """
    Convert one page into smaller text segments.

    Blank lines are treated as natural paragraph/block boundaries.
    """

    page_number = page_record["page"]

    text = page_record.get(
        "text",
        "",
    ).strip()

    if not text:
        return []

    blocks = re.split(
        r"\n\s*\n",
        text,
    )

    segments: list[dict] = []

    for block in blocks:

        block = block.strip()

        if not block:
            continue

        # Within a block, collapse line breaks into spaces.
        # This makes normal prose easier to search while retaining
        # blank-line boundaries between larger logical sections.
        block = re.sub(
            r"\s*\n\s*",
            " ",
            block,
        )

        block = re.sub(
            r"[ \t]+",
            " ",
            block,
        )

        for piece in split_long_text(
            block,
            max_chars=max_chars,
        ):
            segments.append(
                {
                    "page": page_number,
                    "text": piece,
                }
            )

    return segments


# ---------------------------------------------------------
# Chunk helpers
# ---------------------------------------------------------

def chunk_text_length(
    segments: list[dict],
) -> int:
    """
    Calculate the approximate character count of a chunk.
    """

    if not segments:
        return 0

    return sum(
        len(segment["text"])
        for segment in segments
    ) + (len(segments) - 1) * 2


def segments_to_text(
    segments: list[dict],
) -> str:
    """
    Join chunk segments into final searchable text.
    """

    return "\n\n".join(
        segment["text"]
        for segment in segments
    ).strip()


def get_overlap_segments(
    segments: list[dict],
    overlap_chars: int,
) -> list[dict]:
    """
    Preserve approximately the requested number of characters
    from the end of the previous chunk.

    Unlike keeping entire segments, this prevents a large
    paragraph from creating excessive overlap between chunks.
    """

    if overlap_chars <= 0:
        return []

    overlap_reversed: list[dict] = []

    remaining_chars = overlap_chars

    for segment in reversed(segments):

        if remaining_chars <= 0:
            break

        text = segment["text"].strip()

        if not text:
            continue

        # Entire segment fits inside remaining overlap budget.
        if len(text) <= remaining_chars:

            overlap_reversed.append(
                {
                    "page": segment["page"],
                    "text": text,
                }
            )

            remaining_chars -= len(text)

        else:
            # Only keep the tail required to reach the
            # approximate overlap target.
            tail = text[-remaining_chars:]

            # Avoid starting halfway through a word.
            first_space = tail.find(" ")

            if first_space != -1:
                tail = tail[first_space + 1:]

            tail = tail.strip()

            if tail:
                overlap_reversed.append(
                    {
                        "page": segment["page"],
                        "text": tail,
                    }
                )

            remaining_chars = 0

    overlap_reversed.reverse()

    return overlap_reversed

# ---------------------------------------------------------
# Chunk creation
# ---------------------------------------------------------

def build_chunks(
    pages: list[dict],
    target_chars: int,
    max_chars: int,
    overlap_chars: int,
) -> list[dict]:
    """
    Build page-aware overlapping chunks from parsed PDF pages.
    """

    if target_chars <= 0:
        raise ValueError(
            "target_chars must be greater than zero."
        )

    if max_chars < target_chars:
        raise ValueError(
            "max_chars must be greater than or equal to target_chars."
        )

    if overlap_chars < 0:
        raise ValueError(
            "overlap_chars cannot be negative."
        )

    if overlap_chars >= target_chars:
        raise ValueError(
            "overlap_chars must be smaller than target_chars."
        )

    all_segments: list[dict] = []

    for page in pages:

        all_segments.extend(
            page_to_segments(
                page_record=page,
                max_chars=max_chars,
            )
        )

    chunks: list[dict] = []

    current_segments: list[dict] = []

    def save_current_chunk() -> None:
        """
        Save the current chunk if it contains useful content.
        """

        if not current_segments:
            return

        chunks.append(
            create_chunk_record(
                segments=current_segments,
                chunk_number=len(chunks) + 1,
                document=pages[0].get("document"),
                source_url=pages[0].get("source_url"),
                document_sha256=pages[0].get(
                    "document_sha256"
                ),
            )
        )

    for segment in all_segments:

        # -------------------------------------------------
        # Start a new chunk
        # -------------------------------------------------

        if not current_segments:

            current_segments = [segment]

        else:

            proposed_segments = (
                current_segments
                + [segment]
            )

            proposed_size = chunk_text_length(
                proposed_segments
            )

            # ---------------------------------------------
            # New segment would exceed maximum size
            # ---------------------------------------------

            if proposed_size > max_chars:

                current_size = chunk_text_length(
                    current_segments
                )

                # If current content is more than merely
                # overlap, save it as a real chunk.
                if current_size > overlap_chars:

                    save_current_chunk()

                    overlap = get_overlap_segments(
                        current_segments,
                        overlap_chars=overlap_chars,
                    )

                    # Keep overlap only when it still allows
                    # the incoming segment to fit.
                    if (
                        chunk_text_length(
                            overlap + [segment]
                        )
                        <= max_chars
                    ):
                        current_segments = (
                            overlap + [segment]
                        )

                    else:
                        current_segments = [segment]

                else:
                    # Current content contains only overlap.
                    # Drop it rather than creating an
                    # overlap-only chunk.
                    current_segments = [segment]

            else:

                current_segments.append(
                    segment
                )

        # -------------------------------------------------
        # Preferred chunk size reached
        # -------------------------------------------------

        if (
            chunk_text_length(current_segments)
            >= target_chars
        ):

            save_current_chunk()

            current_segments = get_overlap_segments(
                current_segments,
                overlap_chars=overlap_chars,
            )

    # -----------------------------------------------------
    # Remaining content
    # -----------------------------------------------------

    if current_segments:

        final_text = segments_to_text(
            current_segments
        )

        # Prevent an overlap-only duplicate at EOF.
        if (
            not chunks
            or final_text != chunks[-1]["text"]
        ):

            # Do not write a tiny final record that consists
            # only of overlap already stored in the previous
            # chunk.
            if (
                not chunks
                or len(final_text) > overlap_chars
            ):

                save_current_chunk()

    return chunks

def create_chunk_record(
    segments: list[dict],
    chunk_number: int,
    document: str | None,
    source_url: str | None,
    document_sha256: str | None,
) -> dict:
    """
    Turn a group of segments into the final JSON chunk record.
    """

    pages = [
        segment["page"]
        for segment in segments
    ]

    text = segments_to_text(
        segments
    )

    return {
        "chunk_id": f"chunk_{chunk_number:05d}",
        "chunk_number": chunk_number,
        "document": document,
        "page_start": min(pages),
        "page_end": max(pages),
        "text": text,
        "character_count": len(text),
        "source_url": source_url,
        "document_sha256": document_sha256,
    }


# ---------------------------------------------------------
# File generation
# ---------------------------------------------------------

def chunk_document(
    input_path: Path,
    target_chars: int = DEFAULT_TARGET_CHARS,
    max_chars: int = DEFAULT_MAX_CHARS,
    overlap_chars: int = DEFAULT_OVERLAP_CHARS,
    overwrite: bool = False,
) -> Path:
    """
    Convert parsed pages into searchable chunks.
    """

    pages = load_pages(
        input_path
    )

    document_stem = input_path.name

    if document_stem.endswith(
        ".pages.jsonl"
    ):
        document_stem = document_stem[
            :-len(".pages.jsonl")
        ]
    else:
        document_stem = input_path.stem

    output_path = (
        PROCESSED_DATA_DIR
        / f"{document_stem}.chunks.jsonl"
    )

    summary_path = (
        PROCESSED_DATA_DIR
        / f"{document_stem}.chunking.json"
    )

    if output_path.exists() and not overwrite:

        print(
            f"Chunk file already exists: {output_path}"
        )

        print(
            "Use --overwrite to create it again."
        )

        return output_path

    print("Chunking document:")
    print(f"  {input_path}")
    print()
    print(f"Target size: {target_chars} characters")
    print(f"Maximum size: {max_chars} characters")
    print(f"Overlap:      {overlap_chars} characters")
    print()

    chunks = build_chunks(
        pages=pages,
        target_chars=target_chars,
        max_chars=max_chars,
        overlap_chars=overlap_chars,
    )

    temporary_output = output_path.with_suffix(
        output_path.suffix + ".part"
    )

    try:
        with temporary_output.open(
            "w",
            encoding="utf-8",
        ) as file:

            for chunk in chunks:

                file.write(
                    json.dumps(
                        chunk,
                        ensure_ascii=False,
                    )
                )

                file.write("\n")

        temporary_output.replace(
            output_path
        )

    except Exception:

        temporary_output.unlink(
            missing_ok=True
        )

        raise

    character_counts = [
        chunk["character_count"]
        for chunk in chunks
    ]

    summary = {
        "document": pages[0].get(
            "document"
        ),
        "source_url": pages[0].get(
            "source_url"
        ),
        "document_sha256": pages[0].get(
            "document_sha256"
        ),
        "chunked_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "page_count": len(pages),
        "chunk_count": len(chunks),
        "target_chars": target_chars,
        "max_chars": max_chars,
        "overlap_chars": overlap_chars,
        "minimum_chunk_chars": (
            min(character_counts)
            if character_counts
            else 0
        ),
        "maximum_chunk_chars": (
            max(character_counts)
            if character_counts
            else 0
        ),
        "average_chunk_chars": (
            round(
                sum(character_counts)
                / len(character_counts),
                2,
            )
            if character_counts
            else 0
        ),
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

    print("Chunking complete.")
    print()
    print(f"Chunks created: {len(chunks)}")

    if character_counts:

        print(
            f"Smallest chunk: {min(character_counts):,} characters"
        )

        print(
            f"Largest chunk:  {max(character_counts):,} characters"
        )

        print(
            "Average chunk:  "
            f"{sum(character_counts) / len(character_counts):,.0f} "
            "characters"
        )

    print()
    print(f"Output:  {output_path}")
    print(f"Summary: {summary_path}")

    return output_path


# ---------------------------------------------------------
# Command-line interface
# ---------------------------------------------------------

def main() -> None:

    parser = argparse.ArgumentParser(
        description=(
            "Create searchable MineLens chunks "
            "from parsed PDF pages."
        )
    )

    parser.add_argument(
        "input",
        help=(
            "Parsed .pages.jsonl filename "
            "inside data/processed/ or complete path"
        ),
    )

    parser.add_argument(
        "--target-chars",
        type=int,
        default=DEFAULT_TARGET_CHARS,
        help=(
            "Preferred chunk size in characters "
            f"(default: {DEFAULT_TARGET_CHARS})"
        ),
    )

    parser.add_argument(
        "--max-chars",
        type=int,
        default=DEFAULT_MAX_CHARS,
        help=(
            "Maximum chunk size in characters "
            f"(default: {DEFAULT_MAX_CHARS})"
        ),
    )

    parser.add_argument(
        "--overlap-chars",
        type=int,
        default=DEFAULT_OVERLAP_CHARS,
        help=(
            "Approximate overlap between chunks "
            f"(default: {DEFAULT_OVERLAP_CHARS})"
        ),
    )

    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace existing chunk files",
    )

    args = parser.parse_args()

    supplied_path = Path(
        args.input
    )

    if not supplied_path.is_absolute():

        supplied_path = (
            PROCESSED_DATA_DIR
            / supplied_path
        )

    chunk_document(
        input_path=supplied_path,
        target_chars=args.target_chars,
        max_chars=args.max_chars,
        overlap_chars=args.overlap_chars,
        overwrite=args.overwrite,
    )


if __name__ == "__main__":
    main()