"""Read-only summary of ingested Muntanga North 20 Nov 2026 intercepts.

Usage: python -m scripts.inspect_muntanga_north [MNDTH2421]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / 'data' / 'processed'


def load_records(path: Path) -> list[dict]:
    if not path.exists():
        raise SystemExit('Missing ' + str(path) + '. Run: python -m ingestion.ingest_atomic_eagle_muntanga')
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('hole_id', nargs='?', help='Optional hole ID, e.g. MNDTH2421')
    args = parser.parse_args()
    holes = load_records(DIRECTORY / 'muntanga_north_20261120_holes.jsonl')
    intervals = load_records(DIRECTORY / 'muntanga_north_20261120_intercepts.jsonl')
    print('Muntanga North | 20 Nov 2026 | radiometric eU3O8, NOT lab assays')
    print('Appendix hole records:', len(holes), '| intervals:', len(intervals))
    if args.hole_id:
        hole_id = args.hole_id.strip().upper()
        matches = [h for h in holes if h['hole_id'] == hole_id]
        if not matches:
            raise SystemExit('Hole not found in this release: ' + hole_id)
        h = matches[0]
        print('Hole:', hole_id, '| Status:', h['intercept_reporting_status'])
        print('WGS84 UTM 35S easting/northing:', h['easting_m'], h['northing_m'])
        subset = [r for r in intervals if r['hole_id'] == hole_id]
    else:
        subset = sorted(intervals, key=lambda r: (-r['eu3o8_ppm'], r['hole_id']))[:12]
        print('Top reported interval grades (ppm eU3O8):')
    for r in subset:
        print(f"{r['hole_id']}: {r['from_m']:.2f}-{r['to_m']:.2f} m "
              f"({r['interval_m']:.2f} m) @ {r['eu3o8_ppm']:g} ppm eU3O8 "
              f"[source p.{r['source_page']}]")
    if not subset:
        print('No significant interval in Appendix 2 at the release cutoff.')

if __name__ == '__main__':
    main()
