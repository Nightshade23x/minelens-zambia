"""Read-only model for the Mushima North Phase 4 exploration dashboard.

Only the 9 November 2026 Tertiary Minerals release is represented. Intervals
are downhole intervals, not true widths. Nested 'including' intervals must not
be aggregated as independent mineralised lengths or converted into resources.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path


DATA_STEM = "mushima_north_phase4_20261109"
METALS = {
    "Silver (Ag)": ("ag_gpt", "g/t Ag"),
    "Copper (Cu)": ("cu_pct", "% Cu"),
    "Zinc (Zn)": ("zn_pct", "% Zn"),
}


@dataclass(frozen=True)
class Phase4Report:
    summary: dict
    holes: tuple[dict, ...]
    intervals: tuple[dict, ...]


def _load_jsonl(path: Path) -> tuple[dict, ...]:
    records = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        record = json.loads(line)
        if not isinstance(record, dict):
            raise ValueError(f"Non-object record at {path}:{line_number}")
        records.append(record)
    return tuple(records)


def load_phase4_report(project_root: Path | None = None) -> Phase4Report:
    if project_root is None:
        project_root = Path(__file__).resolve().parents[1]
    directory = Path(project_root) / "data" / "processed"
    summary = json.loads((directory / f"{DATA_STEM}_summary.json").read_text(encoding="utf-8"))
    holes = _load_jsonl(directory / f"{DATA_STEM}_holes.jsonl")
    intervals = _load_jsonl(directory / f"{DATA_STEM}_intersections.jsonl")

    if summary.get("project") != "Mushima North":
        raise ValueError("Unexpected project in Mushima North summary")
    if not summary.get("source_url"):
        raise ValueError("Source URL missing from report summary")
    ids = {hole.get("hole_id") for hole in holes}
    if len(ids) != len(holes) or None in ids:
        raise ValueError("Missing or duplicate drill-hole IDs")
    source_id = summary.get("source_id")
    for record in (*holes, *intervals):
        if record.get("project") != "Mushima North" or record.get("source_id") != source_id:
            raise ValueError("Record source does not match the release")
        if record.get("hole_id") not in ids:
            raise ValueError("An interval references a missing drill hole")
    for interval in intervals:
        if interval.get("record_type") != "exploration_drill_intersection":
            raise ValueError("Unexpected intersection record type")
        if float(interval["to_m"]) - float(interval["from_m"]) != float(interval["interval_m"]):
            raise ValueError("Interval length does not match from/to depths")
    return Phase4Report(summary=summary, holes=holes, intervals=intervals)


def filter_intervals(
    intervals: tuple[dict, ...] | list[dict],
    zones: set[str],
    hole_ids: set[str],
    include_nested: bool = True,
) -> list[dict]:
    return [
        row for row in intervals
        if row.get("zone") in zones
        and row.get("hole_id") in hole_ids
        and (include_nested or not row.get("explicitly_marked_including", False))
    ]


def highest_interval(intervals: tuple[dict, ...] | list[dict], metal_key: str) -> dict | None:
    if metal_key not in {value[0] for value in METALS.values()}:
        raise ValueError("Unrecognized metal field")
    eligible = [row for row in intervals if row.get(metal_key) is not None]
    return max(eligible, key=lambda row: float(row[metal_key]), default=None)


def peak_individual_assays(holes: tuple[dict, ...] | list[dict], metal_key: str | None = None) -> list[dict]:
    """Return reported individual assays; never treat them as interval grades."""
    if metal_key is not None and metal_key not in {value[0] for value in METALS.values()}:
        raise ValueError("Unrecognized metal field")
    result = []
    for hole in holes:
        for metal, grade in (hole.get("reported_peak_individual_assays") or {}).items():
            if metal in {value[0] for value in METALS.values()} and grade is not None:
                if metal_key is None or metal_key == metal:
                    result.append({
                        "hole_id": hole["hole_id"],
                        "zone": hole.get("zone", ""),
                        "metal_key": metal,
                        "grade": float(grade),
                        "source_url": hole.get("source_url", ""),
                    })
    return sorted(result, key=lambda row: (-row["grade"], row["hole_id"]))


def hole_comparison(
    report: Phase4Report, metal_key: str, *, intervals: list[dict] | tuple[dict, ...] | None = None
) -> list[dict]:
    """Max reported interval grades by hole, never a whole-hole average."""
    if metal_key not in {value[0] for value in METALS.values()}:
        raise ValueError("Unrecognized metal field")
    results = []
    source_intervals = report.intervals if intervals is None else intervals
    for hole in report.holes:
        matching = [
            row for row in source_intervals
            if row["hole_id"] == hole["hole_id"]
            and row.get(metal_key) is not None
        ]
        best = highest_interval(matching, metal_key)
        results.append({
            "hole_id": hole["hole_id"],
            "zone": hole.get("zone", ""),
            "end_of_hole_m": hole.get("end_of_hole_m"),
            "reported_intervals": len(matching),
            "max_interval_grade": best[metal_key] if best else None,
            "best_interval_from_m": best["from_m"] if best else None,
            "best_interval_to_m": best["to_m"] if best else None,
        })
    return results
