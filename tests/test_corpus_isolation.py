from __future__ import annotations

import json

from pathlib import Path

from app.search import load_chunks


def write_jsonl(
    path: Path,
    records: list[dict],
) -> None:
    """
    Write test records to a JSONL file.
    """

    with path.open(
        "w",
        encoding="utf-8",
    ) as file:

        for record in records:

            file.write(
                json.dumps(
                    record
                )
            )

            file.write(
                "\n"
            )


def test_load_chunks_excludes_structured_by_default(
    tmp_path: Path,
) -> None:
    """
    General document search must not load individual
    structured licensing applications by default.
    """

    chunk_file = (
        tmp_path
        / "sample.chunks.jsonl"
    )

    write_jsonl(
        chunk_file,
        [
            {
                "chunk_id": "document_chunk",
                "text": (
                    "Zambia copper production "
                    "statistics."
                ),
                "source_status": "current",
            },
            {
                "chunk_id": "licence_chunk",
                "text": (
                    "Licence 42553-HQ-LML "
                    "was approved."
                ),
                "source_status": "current",
                "record_type": (
                    "licensing_application"
                ),
            },
        ],
    )

    chunks = load_chunks(
        data_directory=tmp_path
    )

    assert len(
        chunks
    ) == 1

    assert (
        chunks[0][
            "chunk_id"
        ]
        == "document_chunk"
    )


def test_load_chunks_can_include_structured(
    tmp_path: Path,
) -> None:
    """
    Structured records can still be loaded deliberately
    for diagnostics or combined-corpus experiments.
    """

    chunk_file = (
        tmp_path
        / "sample.chunks.jsonl"
    )

    write_jsonl(
        chunk_file,
        [
            {
                "chunk_id": "document_chunk",
                "text": (
                    "Zambia copper production "
                    "statistics."
                ),
                "source_status": "current",
            },
            {
                "chunk_id": "licence_chunk",
                "text": (
                    "Licence 42553-HQ-LML "
                    "was approved."
                ),
                "source_status": "current",
                "record_type": (
                    "licensing_application"
                ),
            },
        ],
    )

    chunks = load_chunks(
        data_directory=tmp_path,
        include_structured=True,
    )

    chunk_ids = {
        chunk[
            "chunk_id"
        ]
        for chunk in chunks
    }

    assert len(
        chunks
    ) == 2

    assert chunk_ids == {
        "document_chunk",
        "licence_chunk",
    }