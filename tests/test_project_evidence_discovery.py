"""Offline candidate-only discovery tests; not dependent on any installer."""
import json
from pathlib import Path

import pytest

from app.project_evidence_discovery import (
    candidate_passages_csv, find_candidate_passages, suggested_search_term,
)


def _write(dir_path: Path, filename: str, records: list[dict]):
    with (dir_path / filename).open("w", encoding="utf-8") as out:
        for item in records:
            out.write(json.dumps(item) + "\n")


def test_search_case_insensitive_exact_words_and_sources(tmp_path):
    _write(tmp_path, "compact.chunks.jsonl", [
        {"text": "Mingomba property expects growth.", "page_number": 8,
         "source_title": "Country Compact"},
        {"chunk_text": "PREMINGOMBA is not our mine.", "page": 9},
        {"content": {"text": "Also Mingomba mine."}, "metadata": {"page_start": 25}},
        {"text": "Completely unrelated text."},
    ])
    found = find_candidate_passages("mingomba", processed_dir=tmp_path)
    assert len(found["matches"]) == 2
    assert [m["page"] for m in found["matches"]] == ["8", "25"]
    assert found["matches"][0]["document"] == "Country Compact"
    assert all("Candidate mention" in x["evidence_status"] for x in found["matches"])
    assert found["chunks_scanned"] == 4


def test_missing_and_bad_input(tmp_path):
    assert not find_candidate_passages("Kansanshi", processed_dir=tmp_path / "missing")["matches"]
    with pytest.raises(ValueError):
        find_candidate_passages(" ", processed_dir=tmp_path)
    with pytest.raises(ValueError):
        find_candidate_passages("x" * 91, processed_dir=tmp_path)
    with pytest.raises(ValueError):
        find_candidate_passages("Kansanshi", limit=999, processed_dir=tmp_path)


def test_multiword_query_and_no_inference(tmp_path):
    _write(tmp_path, "report.chunks.jsonl", [
        {"text": "Baluba Center mine annual capacity 10,000 units.", "page": 2},
        {"text": "Baluba underground operations mentioned but not confirmed same facility.", "page": 3},
    ])
    found = find_candidate_passages("Baluba Center", processed_dir=tmp_path)
    assert len(found["matches"]) == 1
    assert "10,000" in found["matches"][0]["excerpt"]
    assert "10,000" not in found["matches"][0]["evidence_status"]
    assert "page,matched_term" in candidate_passages_csv(found["matches"])


def test_bounded_results_and_suggestions(tmp_path):
    _write(tmp_path, "small.chunks.jsonl", [{"text": "Kansanshi mine.", "page": i} for i in range(8)])
    results = find_candidate_passages("Kansanshi", processed_dir=tmp_path, limit=3)
    assert len(results["matches"]) == 3
    assert any("limit" in warning.lower() for warning in results["warnings"])
    assert suggested_search_term({"name": "Baluba Center (Underground) Mine"}) == "Baluba"
    assert suggested_search_term({"name": "Mingomba"}) == "Mingomba"


def test_ignores_non_chunk_files_and_handles_malformed_rows(tmp_path):
    (tmp_path / "compact.pages.jsonl").write_text('{"text":"Mingomba"}\n', encoding="utf-8")
    (tmp_path / "compact.chunks.jsonl").write_text('bad-json\n{"text":"Mingomba"}\n', encoding="utf-8")
    results = find_candidate_passages("Mingomba", processed_dir=tmp_path)
    assert len(results["matches"]) == 1
    assert len(results["warnings"]) == 1


def test_diversifies_hits_across_multiple_documents(tmp_path):
    _write(tmp_path, "a_compact.chunks.jsonl", [
        {"text": "Mingomba reported here", "page_number": i} for i in range(12)
    ])
    _write(tmp_path, "b_yearbook.chunks.jsonl", [
        {"text": "An independent text mentions Mingomba", "page": 3}
    ])
    hits = find_candidate_passages("Mingomba", processed_dir=tmp_path, limit=3)["matches"]
    assert len(hits) == 3
    assert {r["file"] for r in hits} == {
        "a_compact.chunks.jsonl", "b_yearbook.chunks.jsonl"
    }
