"""Source-scoped, read-only data access for the 20 Nov 2026 Muntanga release.

Uranium grades are radiometric equivalent uranium (ppm eU3O8), NOT lab
assays. 'No significant intercept' is never converted to a zero grade.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Iterable

STEM = "muntanga_north_20261120"
SOURCE_ID = "atomic_eagle_muntanga_north_drilling_20261120"


@dataclass(frozen=True)
class MuntangaReport:
    summary: dict
    holes: tuple[dict, ...]
    intervals: tuple[dict, ...]


def _load_jsonl(path: Path) -> tuple[dict, ...]:
    records = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        obj = json.loads(line)
        if not isinstance(obj, dict):
            raise ValueError(f"Expected JSON object: {path.name}:{number}")
        records.append(obj)
    return tuple(records)


def load_muntanga_report(root: Path | None = None) -> MuntangaReport:
    root = Path(root) if root is not None else Path(__file__).resolve().parents[1]
    folder = root / "data" / "processed"
    summary = json.loads((folder / f"{STEM}_summary.json").read_text(encoding="utf-8"))
    holes = _load_jsonl(folder / f"{STEM}_holes.jsonl")
    intervals = _load_jsonl(folder / f"{STEM}_intercepts.jsonl")
    if summary.get("project") != "Muntanga North" or summary.get("source_id") != SOURCE_ID:
        raise ValueError("Unexpected Muntanga source summary")
    if len(holes) != summary.get("holes_in_appendix") or len(intervals) != summary.get("reported_intervals"):
        raise ValueError("Muntanga dataset counts differ from the verified release summary")
    if summary.get("reported_date") != "2026-11-20":
        raise ValueError("Dataset is not the 20 Nov 2026 release")
    hole_ids = [h.get("hole_id") for h in holes]
    if len(hole_ids) != len(set(hole_ids)) or any(not h for h in hole_ids):
        raise ValueError("Duplicate or empty Muntanga collar identifier")
    ids = set(hole_ids)
    for hole in holes:
        if hole.get("project") != "Muntanga North" or hole.get("source_id") != SOURCE_ID:
            raise ValueError("Hole source mismatch")
        if hole.get("utm_zone") != "35S" or hole.get("coordinate_datum") != "WGS84":
            raise ValueError("Unexpected collar coordinate reference system")
        if hole.get("intercept_reporting_status") not in {
            "reported_radiometric_intercept", "no_significant_intercept"
        }:
            raise ValueError("Unexpected uranium collar reporting status")
    for row in intervals:
        if row.get("project") != "Muntanga North" or row.get("source_id") != SOURCE_ID:
            raise ValueError("Intercept source mismatch")
        if row.get("hole_id") not in ids:
            raise ValueError("Intercept references missing collar")
        if row.get("grade_basis") != "downhole_gamma_equivalent_uranium":
            raise ValueError("Non-radiometric grade encountered")
        if row.get("is_laboratory_assay") is not False or row.get("is_mineral_resource") is not False:
            raise ValueError("Uranium assay/resource claims cannot be displayed as radiometric intervals")
        if row.get("grade_unit") != "ppm eU3O8" or row.get("eu3o8_ppm") is None:
            raise ValueError("Missing equivalent-uranium measurement or unit")
        if abs((float(row["to_m"]) - float(row["from_m"])) - float(row["interval_m"])) > 0.025:
            raise ValueError("Uranium interval length differs from depth bounds")
    with_intercept = {r["hole_id"] for r in intervals}
    for hole in holes:
        has_reported = hole["intercept_reporting_status"] == "reported_radiometric_intercept"
        if has_reported != (hole["hole_id"] in with_intercept):
            raise ValueError("Collar and intercept reporting statuses disagree")
    return MuntangaReport(summary, holes, intervals)


def visible_records(report: MuntangaReport, hole_ids: set[str] | None = None,
                    target_ids: set[int | None] | None = None,
                    include_no_significant: bool = True) -> tuple[list[dict], list[dict]]:
    """Filter collars and associated intervals without changing source metadata."""
    holes = [
        h for h in report.holes
        if (hole_ids is None or h["hole_id"] in hole_ids)
        and (target_ids is None or h.get("target_id") in target_ids)
        and (include_no_significant or h["intercept_reporting_status"] == "reported_radiometric_intercept")
    ]
    selected = {h["hole_id"] for h in holes}
    intervals = [r for r in report.intervals if r["hole_id"] in selected]
    return holes, intervals


def best_by_hole(intervals: Iterable[dict]) -> list[dict]:
    best: dict[str, dict] = {}
    for row in intervals:
        hole = row["hole_id"]
        if hole not in best or float(row["eu3o8_ppm"]) > float(best[hole]["eu3o8_ppm"]):
            best[hole] = row
    return sorted(best.values(), key=lambda r: (-float(r["eu3o8_ppm"]), r["hole_id"]))


def collar_map_rows(holes: Iterable[dict], intervals: Iterable[dict]) -> list[dict]:
    """Convert verified WGS84 / UTM 35 SOUTH collars to WGS84 lon/lat.

    EPSG:32735 is the southern-hemisphere UTM 35 CRS. This conversion maps
    drill-hole collars, not subsurface intervals or licence boundaries.
    """
    try:
        from pyproj import Transformer
    except ImportError as exc:
        raise RuntimeError("Install pyproj: python -m pip install -r requirements-exploration-map.txt") from exc
    converter = Transformer.from_crs("EPSG:32735", "EPSG:4326", always_xy=True)
    top = {r["hole_id"]: r for r in best_by_hole(intervals)}
    mapped = []
    for hole in holes:
        east, north = float(hole["easting_m"]), float(hole["northing_m"])
        lon, lat = converter.transform(east, north)
        # Zambia bounds provide a sanity check against wrong CRS/hemisphere.
        if not (-19.0 < lat < -8.0 and 21.0 < lon < 34.0):
            raise ValueError(f"Collar coordinate outside Zambia after conversion: {hole['hole_id']}")
        best = top.get(hole["hole_id"])
        mapped.append({
            "hole_id": hole["hole_id"],
            "latitude": lat,
            "longitude": lon,
            "easting_m": east,
            "northing_m": north,
            "target": str(hole.get("target_id")) if hole.get("target_id") is not None else "Not identified in Table 1",
            "reporting_status": hole["intercept_reporting_status"],
            "best_reported_ppm": float(best["eu3o8_ppm"]) if best else None,
            "best_grade_label": f"{best['eu3o8_ppm']:g} ppm eU3O8" if best else "No significant intercept reported",
            "source_page": hole.get("source_page"),
            "color": [70, 165, 244, 205] if best else [158, 166, 181, 145],
        })
    return mapped
