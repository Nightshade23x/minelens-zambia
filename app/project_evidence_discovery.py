"""Conservative offline discovery of candidate project mentions in ingested chunks.

This is NOT entity resolution, corroboration or a source-verification engine.
The selected record is never merged with, or enriched from, candidate passages.
No network/Ollama/embedding calls are made. Existing chunk files remain unchanged.
"""
from __future__ import annotations

import csv
from io import StringIO
import json
from pathlib import Path
import re
from typing import Any

DEFAULT_PROCESSED = Path(__file__).resolve().parents[1] / "data" / "processed"
MAX_QUERY_CHARS = 90
MAX_FILES = 250
MAX_SCAN_BYTES = 80_000_000
MAX_RESULTS = 25
MAX_CANDIDATES_PER_FILE = 50


def suggested_search_term(record: dict) -> str:
    """Offer a visible search term, not an assertion of entity identity."""
    name = str(record.get("name") or "").strip()
    if len(name.split()) <= 2:
        return name[:MAX_QUERY_CHARS]
    # Long USGS facility names seldom appear verbatim in other sources.
    # Searching one distinctive name token is exploratory, not proof of a match.
    candidates = re.findall(r"[\w'-]+", name, flags=re.UNICODE)
    return next((word for word in candidates if len(word) >= 5), name[:MAX_QUERY_CHARS])


def _text_from_row(row: dict[str, Any]) -> str:
    for key in ("text", "chunk_text", "page_text", "content", "body", "passage"):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value
        if isinstance(value, dict):
            for inner in ("text", "content"):
                nested = value.get(inner)
                if isinstance(nested, str) and nested.strip():
                    return nested
    return ""


def _metadata(row: dict[str, Any]) -> dict[str, Any]:
    info = row.get("metadata")
    return info if isinstance(info, dict) else {}


def _page_number(row: dict[str, Any]) -> str:
    meta = _metadata(row)
    for field in ("page_number", "page_start", "page", "page_index", "page_numbers", "pages"):
        value = row.get(field)
        if value is None or value == "":
            value = meta.get(field)
        if value is None or value == "":
            continue
        if isinstance(value, list):
            return ", ".join(str(v) for v in value[:10])
        return str(value)
    return "Not recorded"


def _excerpt(text: str, location: int, end: int, width: int = 430) -> str:
    start = max(0, location - 100)
    stop = min(len(text), max(end + 160, location + width - 100))
    return ("..." if start else "") + " ".join(text[start:stop].split()) + ("..." if stop < len(text) else "")


def find_candidate_passages(
    query: str,
    *,
    processed_dir: Path | str = DEFAULT_PROCESSED,
    limit: int = 15,
) -> dict[str, Any]:
    """Find exact case-insensitive word/phrase matches across local *.chunks.jsonl.

    Search is lexical, not relevance-ranked factual extraction. All matched
    records are candidate passages; document names are provenance identifiers.
    """
    term = " ".join(str(query).strip().split())
    if not term or len(term) > MAX_QUERY_CHARS:
        raise ValueError("Search term must be 1-90 characters")
    if not 1 <= limit <= MAX_RESULTS:
        raise ValueError(f"Limit must be 1-{MAX_RESULTS}")
    folder = Path(processed_dir)
    if not folder.is_dir():
        return {"matches": [], "files_scanned": 0, "chunks_scanned": 0,
                "warnings": ["Local processed document directory is unavailable."]}
    pattern = re.compile(r"(?<!\w)" + re.escape(term).replace(r"\ ", r"\s+") + r"(?!\w)", re.IGNORECASE)
    matches: list[dict[str, Any]] = []
    warnings: list[str] = []
    chunks_scanned = files_scanned = bytes_scanned = 0
    file_paths = sorted(folder.glob("*.chunks.jsonl"))
    if len(file_paths) > MAX_FILES:
        warnings.append(f"Only the first {MAX_FILES} chunk files were scanned; corpus is larger.")
    for path in file_paths[:MAX_FILES]:
        try:
            file_size = path.stat().st_size
            if bytes_scanned + file_size > MAX_SCAN_BYTES:
                warnings.append("Corpus scan stopped at the 80 MB safety limit; results may be incomplete.")
                break
            bytes_scanned += file_size
            files_scanned += 1
            file_match_count = 0
            with path.open("r", encoding="utf-8-sig") as handle:
                for line_number, line in enumerate(handle, 1):
                    if not line.strip():
                        continue
                    chunks_scanned += 1
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        warnings.append(f"Skipped malformed JSON in {path.name}, line {line_number}.")
                        continue
                    if not isinstance(row, dict):
                        continue
                    body = _text_from_row(row)
                    if not body:
                        continue
                    hit = pattern.search(body)
                    if not hit:
                        continue
                    meta = _metadata(row)
                    title = str(row.get("source_title") or meta.get("source_title") or
                                row.get("document_title") or meta.get("document_title") or
                                path.name.removesuffix(".chunks.jsonl").replace("_", " ")).strip()
                    matches.append({
                        "document": title,
                        "file": path.name,
                        "page": _page_number(row),
                        "matched_term": term,
                        "excerpt": _excerpt(body, hit.start(), hit.end()),
                        "source_row": line_number,
                        "evidence_status": "Candidate mention only (not verified as this project)",
                    })
                    file_match_count += 1
                    if file_match_count >= MAX_CANDIDATES_PER_FILE:
                        break
        except (OSError, UnicodeError) as exc:
            warnings.append(f"Could not read {path.name}: {exc.__class__.__name__}.")
    # Round-robin across source files so a single long source cannot crowd out
    # independent documents. This still makes no verification/corroboration claim.
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in matches:
        grouped.setdefault(item["file"], []).append(item)
    diversified: list[dict[str, Any]] = []
    while grouped and len(diversified) < limit:
        for file_key in list(grouped):
            diversified.append(grouped[file_key].pop(0))
            if not grouped[file_key]:
                del grouped[file_key]
            if len(diversified) >= limit:
                break
    if len(matches) > len(diversified):
        warnings.append("Result limit reached; additional matching passages may exist.")
    return {"matches": diversified, "files_scanned": files_scanned,
            "chunks_scanned": chunks_scanned, "warnings": warnings}


def candidate_passages_csv(matches: list[dict[str, Any]]) -> str:
    fields = ["document", "file", "page", "matched_term", "excerpt", "source_row", "evidence_status"]
    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n", extrasaction="ignore")
    writer.writeheader()
    writer.writerows(matches)
    return buffer.getvalue()
