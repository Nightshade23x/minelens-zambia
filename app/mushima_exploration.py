"""Structured Phase 4 Mushima North drilling search and answers.

This dataset is separate from Shuka Kabwe. The figures are company-reported
exploration observations, not resources or confirmed true widths.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "processed"
INTERVALS_PATH = DATA_DIR / "mushima_north_phase4_20261109_intersections.jsonl"
HOLES_PATH = DATA_DIR / "mushima_north_phase4_20261109_holes.jsonl"
SUMMARY_PATH = DATA_DIR / "mushima_north_phase4_20261109_summary.json"
ID_RE = re.compile(r"\b26TMNRC\s*[- ]?\s*(\d{3})\b", re.I)
PROJECT_RE = re.compile(r"\bmushima(?:\s+north)?\b", re.I)
SOURCE_ID = "tertiary_minerals_mushima_north_phase4_20261109"
SOURCE_TITLE = "Mushima North - Final Phase 4 Drilling Results (9 November 2026)"
SOURCE_DOCUMENT = "20261109-tm-adm-news-mushima-north-phase-4-results-and-drilling-start.pdf"
SOURCE_URL = (
    "https://www.tertiaryminerals.com/downloads/"
    "20261109-tm-adm-news-mushima-north-phase-4-results-and-drilling-start.pdf"
)


def is_mushima_query(query: str) -> bool:
    """Recognize known project or its RC-hole identifiers."""
    return bool(PROJECT_RE.search(query) or ID_RE.search(query))


def _load_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        raise FileNotFoundError(
            f"Mushima North data missing: {path}. "
            "Run python -m ingestion.ingest_tertiary_mushima_north first."
        )
    with path.open(encoding="utf-8-sig") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _materialize(record: dict) -> dict:
    """Adapt source schema to the existing exploration evidence normalizer."""
    row = dict(record)
    row["document"] = row.get("source_document") or SOURCE_DOCUMENT
    row["source_title"] = SOURCE_TITLE
    row["published_date"] = row.get("announcement_date", "2026-11-09")
    row["agency"] = row.get("reporting_company", "Tertiary Minerals plc")
    row["source_authority"] = "company_disclosure"
    row["document_type"] = "exploration_results"
    row["source_type"] = "company_announcement"
    row["canonical_source_id"] = SOURCE_ID
    row["status"] = "reportable_intersection" if "interval_m" in row else "drill_hole_summary"
    if "interval_m" in row:
        row["width_m"] = row["interval_m"]
        row["zinc_pct"] = row["zn_pct"]
        row["lead_pct"] = None  # No lead assay was reported here.
        row["search_text"] = (
            f"Mushima North phase 4 drilling {row['hole_id']} "
            f"{row['zone']} {row['from_m']}-{row['to_m']} m "
            f"{row['interval_m']} m {row['ag_gpt']} g/t Ag "
            f"{row['cu_pct']}% Cu {row['zn_pct']}% Zn"
        )
    else:
        row["search_text"] = (
            f"Mushima North phase 4 drill hole {row['hole_id']} "
            f"{row.get('zone', '')} individual peak assays"
        )
    return row


def _metal(query: str) -> tuple[str, str, str]:
    normalized = query.casefold()
    if re.search(r"\b(?:silver|ag)\b", normalized):
        return "ag_gpt", "silver", "g/t Ag"
    if re.search(r"\b(?:copper|cu)\b", normalized):
        return "cu_pct", "copper", "% Cu"
    if re.search(r"\b(?:zinc|zn)\b", normalized):
        return "zn_pct", "zinc", "% Zn"
    return "ag_gpt", "silver", "g/t Ag"


def _intent(query: str) -> str:
    normalized = query.casefold()
    if "individual" in normalized or "peak assay" in normalized:
        return "highest_individual_assay" if re.search(r"\b(?:highest|maximum|peak|best)\b", normalized) else "individual_assays"
    if re.search(r"\b(?:highest|maximum|best|strongest)\b", normalized):
        return "highest_intersection"
    if re.search(r"\b(?:list|which|how many|all)\b", normalized) and re.search(r"\b(?:holes|drill holes)\b", normalized):
        return "holes"
    return "intersections"


def query_mushima(query: str, top_k: int = 5) -> dict:
    if top_k <= 0:
        raise ValueError("top_k must be positive")
    if not is_mushima_query(query):
        raise ValueError("Not a Mushima North query")
    # The published release covers only Phase 4 RC drilling.
    if re.search(r"\bphase\s*5\b", query, re.I) and re.search(r"\b(?:results|assays?|grades?|intervals?)\b", query, re.I):
        return {"intent": "not_yet_reported", "hole_ids": [], "target": "A1", "results": [],
                "intersection_record_count": 18, "maximum_assay_record_count": 0,
                "source_url": SOURCE_URL}
    holes = _load_jsonl(HOLES_PATH)
    intervals = _load_jsonl(INTERVALS_PATH)
    ids = list(dict.fromkeys("26TMNRC-" + match for match in ID_RE.findall(query)))
    filtered_holes = [row for row in holes if not ids or row["hole_id"] in ids]
    filtered_intervals = [row for row in intervals if not ids or row["hole_id"] in ids]
    zone_match = re.search(r"\b(?:discovery|western)\s+zone\b", query, re.I)
    if zone_match:
        zone = zone_match.group(0).casefold()
        filtered_intervals = [r for r in filtered_intervals if r["zone"].casefold() == zone]
        filtered_holes = [r for r in filtered_holes if r["zone"].casefold() == zone]
    intent = _intent(query)
    field, _, _ = _metal(query)
    if intent in ("highest_individual_assay", "individual_assays"):
        rows = [r for r in filtered_holes if field in r.get("reported_peak_individual_assays", {})]
        rows.sort(key=lambda r: float(r["reported_peak_individual_assays"][field]), reverse=True)
    elif intent == "holes":
        rows = sorted(filtered_holes, key=lambda r: r["hole_id"])
    elif intent == "highest_intersection":
        rows = sorted(filtered_intervals, key=lambda r: (-float(r[field]), r["hole_id"], r["from_m"]))
    else:
        rows = sorted(filtered_intervals, key=lambda r: (r["hole_id"], r["from_m"], r["to_m"]))
    return {
        "intent": intent, "hole_ids": ids, "target": "A1", "results": [_materialize(r) for r in rows[:top_k]],
        "intersection_record_count": len(intervals),
        "maximum_assay_record_count": sum(bool(h.get("reported_peak_individual_assays")) for h in holes),
        "source_url": SOURCE_URL,
    }


def _num(value: object) -> str:
    return str(value) if isinstance(value, int) else f"{float(value):g}"


def _source() -> dict:
    return {
        "source_id": "S1", "canonical_source_id": SOURCE_ID,
        "title": SOURCE_TITLE, "document": SOURCE_DOCUMENT, "pages": "3",
        "source_url": SOURCE_URL, "published_date": "2026-11-09",
        "agency": "Tertiary Minerals plc", "source_authority": "company_disclosure",
        "document_type": "exploration_results",
    }


def answer_mushima(question: str, evidence: list[dict]) -> dict:
    """Deterministic answer; only reads normalized evidence for this project."""
    rows = [item.get("record", {}) for item in evidence]
    rows = [r for r in rows if r.get("project") == "Mushima North"]
    if not rows:
        answer = (
            "No matching Mushima North Phase 4 drilling results were found "
            "in the ingested announcement. Phase 5 assay results are not "
            "included in this dataset."
        )
        return {"answer": answer, "model": None, "generation_method": "structured-exploration",
                "citations": [], "sources": []}
    intent = _intent(question)
    field, metal, unit = _metal(question)
    if intent == "highest_intersection":
        row = max(rows, key=lambda r: float(r.get(field) or -1))
        answer = (
            f"The highest reported {metal} interval grade in the retrieved "
            f"Mushima North Phase 4 results is {_num(row[field])} {unit} in "
            f"{row['hole_id']}, over {_num(row['interval_m'])} m from "
            f"{_num(row['from_m'])} to {_num(row['to_m'])} m "
            f"({row['zone']}). [S1] This is an interval grade, not a "
            "peak individual assay."
        )
    elif intent in ("highest_individual_assay", "individual_assays"):
        rows = [r for r in rows if field in r.get("reported_peak_individual_assays", {})]
        if not rows:
            return {"answer": f"No reported peak individual {metal} assay was found in the selected Mushima North records.",
                    "model": None, "generation_method": "structured-exploration", "citations": [], "sources": []}
        lines = [
            f"- {r['hole_id']}: {_num(r['reported_peak_individual_assays'][field])} {unit} [S1]"
            for r in rows
        ]
        answer = (
            f"Reported peak individual {metal} assays at Mushima North:\n"
            + "\n".join(lines) + "\nThese are individual peak assays, not interval-average grades."
        )
    elif intent == "holes":
        answer = (
            "Mushima North Phase 4 drill holes in the selected results:\n"
            + "\n".join(f"- {r['hole_id']}: {r['zone']} [S1]" for r in rows)
        )
    else:
        answer = (
            "Mushima North Phase 4 reported intervals:\n"
            + "\n".join(
                f"- {r['hole_id']}: {_num(r['interval_m'])} m "
                f"from {_num(r['from_m'])} to {_num(r['to_m'])} m; "
                f"{_num(r['ag_gpt'])} g/t Ag, {_num(r['cu_pct'])}% Cu, "
                f"{_num(r['zn_pct'])}% Zn"
                + (" (reported including interval)" if r.get("explicitly_marked_including") else "")
                + " [S1]"
                for r in rows
            )
        )
    answer += (
        "\n\nSource: Tertiary Minerals plc, 9 November 2026, Table 1. "
        "These company-reported exploration intervals have unconfirmed true widths; "
        "they are not mineral resources or reserves. Equivalent grades are illustrative."
    )
    return {"answer": answer, "model": None, "generation_method": "structured-exploration",
            "citations": ["S1"], "sources": [_source()]}
