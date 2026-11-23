"""Source-scoped Muntanga North radiometric uranium retrieval and answers.

20 November 2026 Atomic Eagle ASX release. Neither laboratory assay data nor
mineral resource figures can be inferred from these exploration intervals.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "data" / "processed"
HOLES_PATH = DIR / "muntanga_north_20261120_holes.jsonl"
INTERCEPTS_PATH = DIR / "muntanga_north_20261120_intercepts.jsonl"
SUMMARY_PATH = DIR / "muntanga_north_20261120_summary.json"
SOURCE_ID = "atomic_eagle_muntanga_north_drilling_20261120"
SOURCE_TITLE = "New Uranium Mineralised Zones Defined at Muntanga North"
SOURCE_DOCUMENT = "AEU_New_Uranium_Mineralised_Zones_Defined_at_Muntanga_North.pdf"
SOURCE_URL = (
    "https://newswire.iguana2.com/2fee0049d633f441/announcements/"
    "aeu.asx/6A1356079/AEU_New_Uranium_Mineralised_Zones_Defined_at_Muntanga_North.pdf"
)
PROJECT_PATTERN = re.compile(r"\bmuntanga\s+north\b", re.I)
HOLE_PATTERN = re.compile(r"\bMNDTH\s*[- ]?\s*(\d{4})\b", re.I)
TARGET_PATTERN = re.compile(r"\btarget\s*([56])\b", re.I)


def is_muntanga_query(query: str) -> bool:
    """Avoid mistaking other Muntanga subprojects for Muntanga North."""
    return bool(PROJECT_PATTERN.search(query) or HOLE_PATTERN.search(query))


def _read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        raise FileNotFoundError(
            f"Required Muntanga North data missing: {path}. "
            "Run python -m ingestion.ingest_atomic_eagle_muntanga first."
        )
    with path.open(encoding="utf-8-sig") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def _read_summary() -> dict:
    if not SUMMARY_PATH.is_file():
        raise FileNotFoundError(f"Required Muntanga North summary missing: {SUMMARY_PATH}")
    with SUMMARY_PATH.open(encoding="utf-8-sig") as stream:
        return json.load(stream)


def _hole_ids(query: str) -> list[str]:
    return list(dict.fromkeys("MNDTH" + digits for digits in HOLE_PATTERN.findall(query.upper())))


def _targets(query: str) -> list[int]:
    return list(dict.fromkeys(int(t) for t in TARGET_PATTERN.findall(query)))


def _intent(query: str) -> str:
    q = query.casefold()
    if re.search(r"\b(?:laboratory|lab[- ]confirmed|chemical assay|chemical analysis)\b", q):
        return "laboratory_assays_not_reported"
    if re.search(r"\b(?:resource estimates?|ore reserves?|mineral reserves?)\b", q):
        return "resources_not_established"
    if re.search(r"\b(?:no significant|without significant|no reportable|without reportable|no intercepts?)\b", q):
        return "no_significant_intercepts"
    if re.search(r"\b(?:highest|maximum|best|strongest|peak|top grade)\b", q):
        return "highest_radiometric_grade"
    if re.search(r"\b(?:compare|comparison|versus|vs\.?)\b", q) or len(_targets(query)) > 1:
        return "compare_intercepts"
    if re.search(r"\b(?:list|all|how many|which)\b", q) and re.search(r"\b(?:drill holes|holes)\b", q):
        return "holes"
    if re.search(r"\b(?:coordinates?|collars?|utm|location|easting|northing)\b", q):
        return "collars"
    return "radiometric_intercepts"


def _materialize(row: dict) -> dict:
    """Expose source metadata and compatibility aliases for existing evidence adapter."""
    result = dict(row)
    result.update({
        "document": SOURCE_DOCUMENT,
        "source_title": SOURCE_TITLE,
        "published_date": row.get("reported_date", "2026-11-20"),
        "agency": "Atomic Eagle Limited",
        "source_authority": "company_disclosure",
        "document_type": "exploration_results",
        "canonical_source_id": SOURCE_ID,
        "source_url": row.get("source_url", SOURCE_URL),
        "status": row.get("intercept_reporting_status") or "reported_radiometric_intercept",
        "zinc_pct": None,
        "lead_pct": None,
        "width_m": row.get("interval_m"),
        "target": row.get("target_id"),
    })
    if row.get("record_type") == "uranium_radiometric_intercept":
        result["search_text"] = (
            f"Muntanga North {row['hole_id']} {row['interval_m']} m "
            f"from {row['from_m']} to {row['to_m']} m "
            f"{row['eu3o8_ppm']} ppm eU3O8 radiometric equivalent uranium "
            f"not laboratory assay; source page {row.get('source_page')}"
        )
    else:
        result["search_text"] = (
            f"Muntanga North drill hole {row['hole_id']} "
            f"{row.get('intercept_reporting_status')} WGS84 UTM 35S"
        )
    return result


def query_muntanga(query: str, top_k: int = 5) -> dict:
    if not is_muntanga_query(query):
        raise ValueError("Not a Muntanga North or MNDTH-hole query")
    if top_k <= 0:
        raise ValueError("top_k must be positive")
    holes = _read_jsonl(HOLES_PATH)
    intervals = _read_jsonl(INTERCEPTS_PATH)
    summary = _read_summary()
    if (len(holes), len(intervals)) != (summary.get("holes_in_appendix"), summary.get("reported_intervals")):
        raise ValueError("Muntanga North processed-file counts do not match the source summary")
    ids = _hole_ids(query)
    targets = _targets(query)
    intent = _intent(query)
    selected_holes = [r for r in holes if (not ids or r["hole_id"] in ids)]
    selected_intervals = [r for r in intervals if (not ids or r["hole_id"] in ids)]

    # Target IDs are assigned only where Table 1 explicitly names them.
    # Other holes and intercepts have null target_id and must not be inferred.
    if targets:
        selected_holes = [r for r in selected_holes if r.get("target_id") in targets]
        selected_intervals = [r for r in selected_intervals if r.get("target_id") in targets]

    if intent in ("laboratory_assays_not_reported", "resources_not_established"):
        rows = []
    elif intent == "no_significant_intercepts":
        rows = sorted(
            (r for r in selected_holes if r.get("intercept_reporting_status") == "no_significant_intercept"),
            key=lambda r: r["hole_id"],
        )
    elif intent in ("holes", "collars"):
        rows = sorted(selected_holes, key=lambda r: r["hole_id"])
    elif intent == "highest_radiometric_grade":
        rows = sorted(selected_intervals, key=lambda r: (-float(r["eu3o8_ppm"]), r["hole_id"], r["from_m"]))
    else:
        rows = sorted(selected_intervals, key=lambda r: (r["hole_id"], r["from_m"], r["to_m"]))

    return {
        "intent": intent,
        "hole_ids": ids,
        "target": targets[0] if len(targets) == 1 else None,
        "target_ids": targets,
        "results": [_materialize(row) for row in rows[:top_k]],
        "matching_record_count": len(rows),
        "intersection_record_count": len(intervals),
        "maximum_assay_record_count": 0,  # No lab peak assays reported.
        "source_url": SOURCE_URL,
        "source_id": SOURCE_ID,
    }


def _n(value: object) -> str:
    number = float(value)
    return str(int(number)) if number.is_integer() else f"{number:.10g}"


def _source(rows: list[dict], sid: str) -> dict:
    pages = sorted({str(r.get("source_page")) for r in rows if r.get("source_page") is not None}, key=int)
    return {
        "source_id": sid,
        "canonical_source_id": SOURCE_ID,
        "title": SOURCE_TITLE,
        "document": SOURCE_DOCUMENT,
        "pages": ", ".join(pages),
        "source_url": SOURCE_URL,
        "published_date": "2026-11-20",
        "agency": "Atomic Eagle Limited",
        "source_authority": "company_disclosure",
        "document_type": "exploration_results",
    }


def _empty_answer(question: str) -> str:
    intent = _intent(question)
    if intent == "laboratory_assays_not_reported":
        return (
            "The 20 November 2026 Muntanga North release reports radiometric "
            "equivalent-uranium intercepts from downhole gamma measurements; "
            "it does not establish laboratory-confirmed uranium assays."
        )
    if intent == "resources_not_established":
        return (
            "The 20 November 2026 Muntanga North drilling intercepts do not "
            "establish a new mineral resource or reserve estimate."
        )
    if _hole_ids(question):
        return (
            "No matching Muntanga North results were found for the requested "
            "drill-hole ID in the 20 November 2026 appendix. "
            "This does not establish an assay grade of zero."
        )
    return "No matching Muntanga North records were found in the 20 November 2026 release."


def answer_muntanga(question: str, evidence: list[dict]) -> dict:
    """Generate claims exclusively from normalized, project-specific evidence rows."""
    pairs = [
        (item, item.get("record")) for item in evidence
        if isinstance(item, dict) and isinstance(item.get("record"), dict)
    ]
    pairs = [(e, r) for e, r in pairs if r.get("project") == "Muntanga North" and r.get("canonical_source_id") == SOURCE_ID]
    if not pairs:
        return {
            "answer": _empty_answer(question), "model": None,
            "generation_method": "structured-exploration", "citations": [], "sources": [],
        }
    sid = str(pairs[0][0].get("source_id") or "S1")
    # The same announcement is the source for every selected record.
    rows = [row for _, row in pairs]
    intent = _intent(question)
    if intent in ("laboratory_assays_not_reported", "resources_not_established"):
        return {
            "answer": _empty_answer(question), "model": None,
            "generation_method": "structured-exploration", "citations": [], "sources": [],
        }
    if intent == "highest_radiometric_grade":
        numeric_rows = [r for r in rows if r.get("record_type") == "uranium_radiometric_intercept" and r.get("eu3o8_ppm") is not None]
        if not numeric_rows:
            return {"answer": _empty_answer(question), "model": None, "generation_method": "structured-exploration", "citations": [], "sources": []}
        best = max(numeric_rows, key=lambda r: float(r["eu3o8_ppm"]))
        body = (
            f"The highest reported radiometric interval grade in the retrieved "
            f"Muntanga North records is {_n(best['eu3o8_ppm'])} ppm eU3O8 in "
            f"{best['hole_id']} over {_n(best['interval_m'])} m "
            f"(from {_n(best['from_m'])} to {_n(best['to_m'])} m), "
            f"reported on page {best.get('source_page')}. [{sid}]"
        )
    elif intent == "no_significant_intercepts":
        matched = [r for r in rows if r.get("intercept_reporting_status") == "no_significant_intercept"]
        body = (
            "Muntanga North holes explicitly listed as 'No Significant Intercept' "
            "in the 20 November appendix (showing retrieved matches):\n"
            + "\n".join(f"- {r['hole_id']} [{sid}]" for r in matched)
            + "\nThis is a reporting classification under the release's cutoff, not a measured zero uranium grade."
        )
    elif intent in ("holes", "collars"):
        body = "Muntanga North drill collars in the retrieved records:\n" + "\n".join(
            f"- {r['hole_id']}: WGS84 UTM zone {r.get('utm_zone', '35S')}, "
            f"E {_n(r['easting_m'])} m, N {_n(r['northing_m'])} m "
            f"(hole depth {_n(r['hole_depth_m'])} m). [{sid}]"
            for r in rows
        )
        body += "\nCoordinates are supplied as UTM grid values, not latitude/longitude."
    else:
        reported = [r for r in rows if r.get("record_type") == "uranium_radiometric_intercept"]
        body = "Muntanga North radiometric equivalent-uranium intercepts in retrieved results:\n" + "\n".join(
            f"- {r['hole_id']}: {_n(r['interval_m'])} m from {_n(r['from_m'])} "
            f"to {_n(r['to_m'])} m, {_n(r['eu3o8_ppm'])} ppm eU3O8"
            + (f" (Table 1, Target {r['target_id']})" if r.get("target_id") else "")
            + f" (source p. {r.get('source_page')}). [{sid}]"
            for r in reported
        )
        if _targets(question):
            body += (
                "\nTarget labels are available only for intersections explicitly "
                "identified in Table 1; unlabelled holes are excluded, so this "
                "is not a complete comparison of all drilling at those targets."
            )
    body += (
        "\n\nSource: Atomic Eagle Limited, ASX announcement dated 20 November 2026. "
        "These eU3O8 values are downhole-gamma radiometric estimates, NOT "
        "laboratory assays or mineral resources/reserves. Intervals are reported "
        "downhole lengths, not independently demonstrated true widths."
    )
    return {
        "answer": body, "model": None,
        "generation_method": "structured-exploration",
        "citations": [sid], "sources": [_source(rows, sid)],
    }
