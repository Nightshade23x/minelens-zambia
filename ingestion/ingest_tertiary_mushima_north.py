"""Source-preserving structured import: Tertiary Minerals Mushima North, 2026-11-09.

Table 1 was transcribed and checked against page 3 of the company's
9 November 2026 regulatory announcement. Only this eight-hole release
is represented; do not conflate with earlier September 2026 releases.
"""

import argparse
import json
from pathlib import Path
import urllib.request

SOURCE_URL = (
    "https://www.tertiaryminerals.com/downloads/"
    "20261109-tm-adm-news-mushima-north-phase-4-results-and-drilling-start.pdf"
)
SOURCE_ID = "tertiary_minerals_mushima_north_phase4_20261109"
RELEASE_DATE = "2026-11-09"

# hole: (zone, EOH metres, hole ends in mineralisation, optional individual assay maxima)
HOLES = {
    "26TMNRC-075": ("Western Zone", 100, False, {}),
    "26TMNRC-076": ("Western Zone", 100, False, {"cu_pct": 0.65}),
    "26TMNRC-077": ("Discovery Zone", 100, False, {"ag_gpt": 139, "cu_pct": 0.62, "zn_pct": 1.4}),
    "26TMNRC-078": ("Discovery Zone", 80, True, {"cu_pct": 1.08}),
    "26TMNRC-079": ("Discovery Zone", 85, True, {"ag_gpt": 111}),
    "26TMNRC-080": ("Discovery Zone", 85, False, {"cu_pct": 0.86}),
    "26TMNRC-081": ("Discovery Zone", 80, True, {"ag_gpt": 115}),
    "26TMNRC-082": ("Discovery Zone", 40, False, {}),
}

# Table 1: hole, from, to, Ag g/t, Cu %, Zn %, AgEq g/t, CuEq %,
# reported Ag gram-metres, explicitly labelled "Including".
# None represents a dash in the published table, NOT a zero assay.
INTERVALS = [
    ("26TMNRC-075", 23, 48, 3, 0.11, 0.05, 10, 0.17, 66, False),
    ("26TMNRC-075", 84, 88, 4, 0.21, 0.05, 17, 0.29, 15, False),
    ("26TMNRC-076", 19, 43, 2, 0.29, 0.02, 20, 0.33, 49, False),
    ("26TMNRC-076", 32, 37, 2, 0.60, 0.03, 39, 0.64, 12, True),
    ("26TMNRC-077", 6, 49, 30, 0.11, 0.35, 42, 0.70, 1290, False),
    ("26TMNRC-077", 36, 46, 57, 0.05, 0.55, 69, 1.16, 572, True),
    ("26TMNRC-077", 87, 93, 54, 0.30, 0.47, 79, 1.32, 322, False),
    ("26TMNRC-078", 10, 80, 31, 0.29, 0.25, 52, 0.87, 2144, False),
    ("26TMNRC-078", 34, 40, 84, 0.32, 0.29, 108, 1.80, 506, True),
    ("26TMNRC-079", 17, 85, 27, 0.15, 0.52, 45, 0.75, 1859, False),
    ("26TMNRC-079", 63, 80, 53, 0.13, 0.52, 70, 1.17, 905, False),
    ("26TMNRC-080", 10, 69, 14, 0.24, 0.17, 32, 0.53, 845, False),
    ("26TMNRC-080", 48, 55, 15, 0.43, 0.20, 45, 0.74, None, False),
    ("26TMNRC-081", 12, 28, 15, 0.19, 0.12, 28, 0.47, 246, False),
    ("26TMNRC-081", 33, 41, 12, 0.16, 0.19, 25, 0.42, 98, False),
    ("26TMNRC-081", 52, 80, 42, 0.26, 0.22, 61, 1.02, 1177, False),
    ("26TMNRC-081", 66, 76, 57, 0.28, 0.17, 76, 1.27, 566, False),
    ("26TMNRC-082", 30, 40, 14, 0.06, 0.04, 18, 0.31, 143, False),
]


def provenance():
    return {
        "project": "Mushima North",
        "target": "A1",
        "country": "Zambia",
        "reporting_company": "Tertiary Minerals plc",
        "announcement_date": RELEASE_DATE,
        "source_id": SOURCE_ID,
        "source_document": "20261109-tm-adm-news-mushima-north-phase-4-results-and-drilling-start.pdf",
        "source_url": SOURCE_URL,
        "source_page": 3,
        "source_table": "Table 1",
        "drilling_phase": 4,
        "drill_method": "reverse circulation",
        "evidence_status": "company-reported laboratory analytical results",
    }


def build_intersections():
    rows = []
    base = provenance()
    for n, (hole, start, end, ag, cu, zn, ageq, cueq, gram, including) in enumerate(INTERVALS, 1):
        zone, eoh, ends_in_mineralisation, _ = HOLES[hole]
        rows.append({
            **base,
            "record_id": f"{SOURCE_ID}:interval:{n:02d}",
            "record_type": "exploration_drill_intersection",
            "hole_id": hole,
            "zone": zone,
            "from_m": start,
            "to_m": end,
            "interval_m": end - start,
            "ag_gpt": ag,
            "cu_pct": cu,
            "zn_pct": zn,
            "ageq_gpt": ageq,
            "cueq_pct": cueq,
            "ag_gram_metres_reported": gram,
            "explicitly_marked_including": including,
            "hole_end_of_hole_m": eoh,
            "hole_ends_in_mineralisation": ends_in_mineralisation,
            "true_width_known": False,
            "equivalent_grades_illustrative_only": True,
            "is_mineral_resource_or_reserve": False,
            "reporting_cutoffs": "10 g/t Ag or 0.1% Cu; up to 3m consecutive internal dilution",
        })
    return rows


def build_hole_records():
    base = provenance()
    return [{
        **base,
        "record_id": f"{SOURCE_ID}:hole:{hole}",
        "record_type": "exploration_drill_hole",
        "hole_id": hole,
        "zone": zone,
        "end_of_hole_m": eoh,
        "ends_in_mineralisation": ends,
        # These are peak individual assays, NOT interval-weighted averages.
        "reported_peak_individual_assays": maxima,
        "peak_assay_values_are_intersection_grades": False,
        "is_mineral_resource_or_reserve": False,
    } for hole, (zone, eoh, ends, maxima) in HOLES.items()]


def build_summary():
    return {
        **provenance(),
        "record_type": "exploration_announcement_summary",
        "released_holes": 8,
        "released_intervals": len(INTERVALS),
        "discovery_zone_released_holes": 6,
        "western_zone_released_holes": 2,
        "phase4_total_rc_holes": 39,
        "phase4_total_drilled_metres": 3639,
        "phase4_holes_with_results_released_by_announcement": 37,
        "phase4_holes_not_submitted_for_analysis": 2,
        "phase5_diamond_drilling_started": "2026-11-08",
        "phase5_planned_holes": 4,
        "phase5_results_included": False,
        "mineral_resource_estimate_included": False,
        "exploration_target_not_resource_estimate": True,
        "note": "Downhole widths; true widths unknown. Metal-equivalent grades illustrative only; assumed 100% recovery and unverified actual recoveries.",
    }


def validate():
    rows = build_intersections()
    assert len(HOLES) == 8, "Expected exactly eight released holes"
    assert len(rows) == 18, "Expected 18 Table 1 interval rows"
    assert len({r["record_id"] for r in rows}) == len(rows)
    assert len({r["hole_id"] for r in rows}) == 8
    assert sum(1 for v in HOLES.values() if v[0] == "Western Zone") == 2
    assert sum(1 for v in HOLES.values() if v[0] == "Discovery Zone") == 6
    for r in rows:
        assert 0 <= r["from_m"] < r["to_m"] <= r["hole_end_of_hole_m"]
        assert r["interval_m"] == r["to_m"] - r["from_m"]
    assert [(r["from_m"], r["interval_m"], r["ag_gpt"]) for r in rows if r["hole_id"] == "26TMNRC-078"][0] == (10, 70, 31)
    assert max(r["cu_pct"] for r in rows if r["hole_id"] == "26TMNRC-076") == 0.60
    assert HOLES["26TMNRC-076"][3]["cu_pct"] == 0.65
    return True


def write_jsonl(path: Path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as out:
        for record in records:
            out.write(json.dumps(record, ensure_ascii=False) + "\n")


def fetch_pdf(root: Path):
    out = root / "data" / "raw" / "tertiary_mushima_north_phase4_20261109.pdf"
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists() and out.read_bytes().startswith(b"%PDF"):
        print("Original PDF already present:", out)
        return
    req = urllib.request.Request(SOURCE_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=35) as response:
        blob = response.read()
    if not blob.startswith(b"%PDF"):
        raise ValueError("Downloaded document is not a PDF")
    out.write_bytes(blob)
    print("Saved original PDF:", out)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--fetch-pdf", action="store_true", help="Download original official PDF")
    args = parser.parse_args()
    root = args.root.resolve()
    validate()
    if args.fetch_pdf:
        fetch_pdf(root)
    proc = root / "data" / "processed"
    write_jsonl(proc / "mushima_north_phase4_20261109_intersections.jsonl", build_intersections())
    write_jsonl(proc / "mushima_north_phase4_20261109_holes.jsonl", build_hole_records())
    summary_path = proc / "mushima_north_phase4_20261109_summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(build_summary(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("PASS: 8 holes, 18 intervals, summary saved to", proc)
    print("Existing Shuka Kabwe datasets were not modified.")


if __name__ == "__main__":
    main()
