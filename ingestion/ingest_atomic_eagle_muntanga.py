"""Ingest Atomic Eagle 20 Nov 2026 Muntanga North drilling disclosure.

Reads the company's original ASX PDF, not news summaries. This job is
independent from the Kabwe and Mushima search pipelines.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
SOURCE_URL = (
    'https://newswire.iguana2.com/2fee0049d633f441/announcements/'
    'aeu.asx/6A1356079/AEU_New_Uranium_Mineralised_Zones_Defined_at_Muntanga_North.pdf'
)
SOURCE_ID = 'atomic_eagle_muntanga_north_drilling_20261120'
SOURCE_TITLE = 'New Uranium Mineralised Zones Defined at Muntanga North'
PUBLISHED = '2026-11-20'
RAW_PDF = ROOT / 'data/raw/atomic_eagle_muntanga_north_20261120.pdf'
OUT_DIR = ROOT / 'data/processed'
HOLE_RE = r'MNDTH\d{4}'
NUM_RE = r'-?\d+(?:\.\d+)?'
COLLAR = re.compile(
    rf'^({HOLE_RE})\s+(\d{{6}})\s+(\d{{7}})\s+({NUM_RE})\s+({NUM_RE})\s+({NUM_RE})\s+({NUM_RE})$'
)
INTERVAL = re.compile(
    rf'^({HOLE_RE})\s+({NUM_RE})\s+({NUM_RE})\s+({NUM_RE})\s+({NUM_RE})$'
)
NO_INTERCEPT = re.compile(rf'^({HOLE_RE})\s+No\s+Significant\s+Intercept$', re.I)
HIGHLIGHT = re.compile(
    rf'^([56])\s+({HOLE_RE})\s+({NUM_RE})\s+({NUM_RE})\s+({NUM_RE})\s+({NUM_RE})$'
)


def source_fields(page: int) -> dict:
    return {
        'project': 'Muntanga North',
        'parent_project': 'Muntanga Uranium Project',
        'operator': 'Atomic Eagle Limited',
        'reported_date': PUBLISHED,
        'source_id': SOURCE_ID,
        'canonical_source_id': SOURCE_ID,
        'source_title': SOURCE_TITLE,
        'source_url': SOURCE_URL,
        'source_page': page,
        'source_type': 'company_asx_announcement',
    }


def fetch_pdf(dest: Path, force: bool = False) -> Path:
    if dest.exists() and not force:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = Request(SOURCE_URL, headers={'User-Agent': 'Mozilla/5.0 MineLens/0.1'})
    try:
        with urlopen(req, timeout=40) as response:
            blob = response.read()
    except Exception as exc:
        raise RuntimeError(
            'PDF download failed. Open SOURCE_URL in your browser, save the '
            '22-page PDF, then run with --pdf "C:\\path\\to\\announcement.pdf".'
        ) from exc
    if not blob.startswith(b'%PDF-') or len(blob) < 100_000:
        raise ValueError('Download is not the expected PDF; refusing to ingest.')
    dest.write_bytes(blob)
    return dest


def word_rows(page) -> list[str]:
    """Reassemble PDF table rows by vertical alignment, not text-block order."""
    words = page.get_text('words')
    words = sorted(words, key=lambda w: ((w[1] + w[3]) / 2, w[0]))
    groups: list[dict] = []
    for word in words:
        y = (word[1] + word[3]) / 2
        if not groups or abs(y - groups[-1]['mean']) > 3.0:
            groups.append({'mean': y, 'words': [word]})
        else:
            g = groups[-1]
            g['words'].append(word)
            g['mean'] = sum((w[1] + w[3]) / 2 for w in g['words']) / len(g['words'])
    lines = [
        ' '.join(str(w[4]).strip() for w in sorted(g['words'], key=lambda w: w[0])).strip()
        for g in groups
    ]
    return [line for line in lines if line]


def candidate_rows(page, pattern: re.Pattern) -> list[str]:
    """Choose between aligned words and PyMuPDF sorted text if either parses better."""
    aligned = word_rows(page)
    sorted_text = [s.strip() for s in page.get_text('text', sort=True).splitlines()]
    # Sorted extraction can be column-major, so only use it if demonstrably better.
    a = [s for s in aligned if pattern.match(s)]
    b = [s for s in sorted_text if pattern.match(s)]
    return a if len(a) >= len(b) else b


def parse_collar(line: str, page: int) -> dict | None:
    m = COLLAR.fullmatch(' '.join(line.split()))
    if not m:
        return None
    hole, east, north, elevation, dip, azimuth, depth = m.groups()
    return {
        **source_fields(page),
        'record_type': 'uranium_drill_hole',
        'hole_id': hole,
        'utm_zone': '35S',
        'coordinate_datum': 'WGS84',
        'easting_m': int(east),
        'northing_m': int(north),
        'rl_m_asl': float(elevation),
        'dip_deg': float(dip),
        'azimuth_deg': float(azimuth),
        'hole_depth_m': float(depth),
        'target_id': None,  # Only assigned when the release explicitly says.
        'intercept_reporting_status': 'unverified',
    }


def parse_intercept(line: str, page: int) -> dict | None:
    normalized = ' '.join(line.split())
    m = INTERVAL.fullmatch(normalized)
    if not m:
        return None
    hole, from_m, to_m, length_m, grade = m.groups()
    return {
        **source_fields(page),
        'record_type': 'uranium_radiometric_intercept',
        'hole_id': hole,
        'from_m': float(from_m),
        'to_m': float(to_m),
        'interval_m': float(length_m),
        'eu3o8_ppm': float(grade),
        'grade_basis': 'downhole_gamma_equivalent_uranium',
        'grade_unit': 'ppm eU3O8',
        'is_laboratory_assay': False,
        'is_mineral_resource': False,
        'target_id': None,
        'highlighted_in_table_1': False,
        'cutoff_eu3o8_ppm': 100,
        'minimum_interval_m': 1.0,
        'maximum_internal_dilution_m': 0.5,
    }


def parse_highlight(line: str, page: int) -> dict | None:
    m = HIGHLIGHT.fullmatch(' '.join(line.split()))
    if not m:
        return None
    target, hole, from_m, to_m, length_m, grade = m.groups()
    return {
        'target_id': int(target), 'hole_id': hole,
        'from_m': float(from_m), 'to_m': float(to_m),
        'interval_m': float(length_m), 'eu3o8_ppm': float(grade),
        'source_page': page,
    }


def fingerprint(row: dict) -> tuple:
    return (row['hole_id'], round(row['from_m'], 2), round(row['to_m'], 2),
            round(row['interval_m'], 2), round(row['eu3o8_ppm'], 2))


def validate(holes: list[dict], intervals: list[dict], highlights: list[dict], no_sig: set[str]) -> None:
    """Strict, release-specific guardrails: never silently publish partial parsing."""
    hole_ids = {h['hole_id'] for h in holes}
    if len(holes) != 84 or len(hole_ids) != 84:
        raise ValueError(f'Expected 84 unique Appendix 1 holes; got {len(holes)} rows / {len(hole_ids)} unique.')
    if len(intervals) != 29:
        raise ValueError(f'Expected 29 Appendix 2 interval rows; got {len(intervals)}.')
    if len(highlights) != 14:
        raise ValueError(f'Expected 14 Table 1 significant entries; got {len(highlights)}.')
    if len(no_sig) != 66:
        raise ValueError(f'Expected 66 no-significant-intercept holes; got {len(no_sig)}.')
    with_intercepts = {r['hole_id'] for r in intervals}
    if len(with_intercepts) != 18:
        raise ValueError(f'Expected 18 unique holes with reported intercepts; got {len(with_intercepts)}.')
    if no_sig & with_intercepts:
        raise ValueError('A hole was marked both significant and not significant.')
    if hole_ids != (no_sig | with_intercepts):
        raise ValueError('Appendix 1 collars do not match Appendix 2 rows; refusing partial data.')
    if any(fingerprint(r) not in {fingerprint(x) for x in intervals} for r in highlights):
        raise ValueError('Some Table 1 highlights are missing from Appendix 2.')
    if any(abs((r['to_m'] - r['from_m']) - r['interval_m']) > 0.081 or r['from_m'] < 0
           or r['to_m'] <= r['from_m'] or r['eu3o8_ppm'] < 100 for r in intervals):
        raise ValueError('Implausible uranium intercept geometry or grade.')
    anchor = {fingerprint(r) for r in intervals}
    for h, a, b, n, grade in [
        ('MNDTH2421', 38.79, 43.97, 5.18, 380),
        ('MNDTH2454', 36.75, 47.65, 10.90, 250),
        ('MNDTH2424', 21.86, 26.84, 4.98, 261),
        ('MNDTH2453', 45.35, 49.60, 4.25, 273),
    ]:
        if (h, a, b, n, grade) not in anchor:
            raise ValueError(f'Expected company-reported interval absent: {h}.')


def extract_pdf(pdf_file: Path) -> tuple[list[dict], list[dict], dict]:
    try:
        import fitz  # PyMuPDF
    except ImportError as exc:
        raise SystemExit('Install PDF parser: python -m pip install pymupdf') from exc
    blob = pdf_file.read_bytes()
    if not blob.startswith(b'%PDF-'):
        raise ValueError('Not a PDF file.')
    sha = hashlib.sha256(blob).hexdigest()
    doc = fitz.open(stream=blob, filetype='pdf')
    if len(doc) != 22:
        raise ValueError(f'Expected 22 announcement pages; found {len(doc)}.')
    if 'New Uranium Mineralised Zones' not in doc[0].get_text():
        raise ValueError('Wrong PDF title. Expected Muntanga North 20 Nov 2026 announcement.')
    holes: list[dict] = []
    intervals: list[dict] = []
    highlights: list[dict] = []
    no_sig: set[str] = set()
    for i in range(7, 10):
        for line in candidate_rows(doc[i], COLLAR):
            row = parse_collar(line, i+1)
            if row: holes.append(row)
    for i in range(10, 13):
        rows = word_rows(doc[i])
        sorted_rows = [s.strip() for s in doc[i].get_text('text', sort=True).splitlines()]
        for raw in (rows if sum(bool(INTERVAL.match(r) or NO_INTERCEPT.match(r)) for r in rows)
                    >= sum(bool(INTERVAL.match(r) or NO_INTERCEPT.match(r)) for r in sorted_rows)
                    else sorted_rows):
            normalized = ' '.join(raw.split())
            match = NO_INTERCEPT.fullmatch(normalized)
            if match:
                no_sig.add(match.group(1))
                continue
            row = parse_intercept(normalized, i+1)
            if row: intervals.append(row)
    for line in candidate_rows(doc[3], HIGHLIGHT):
        row = parse_highlight(line, 4)
        if row: highlights.append(row)
    validate(holes, intervals, highlights, no_sig)
    target_map = {r['hole_id']: r['target_id'] for r in highlights}
    highlight_keys = {fingerprint(r) for r in highlights}
    for row in intervals:
        if fingerprint(row) in highlight_keys:
            row['highlighted_in_table_1'] = True
            row['target_id'] = target_map[row['hole_id']]
        row['source_sha256'] = sha
    for row in holes:
        row['intercept_reporting_status'] = (
            'no_significant_intercept' if row['hole_id'] in no_sig else 'reported_radiometric_intercept'
        )
        row['target_id'] = target_map.get(row['hole_id'])
        row['source_sha256'] = sha
    summary = {
        'project': 'Muntanga North',
        'parent_project': 'Muntanga Uranium Project',
        'operator': 'Atomic Eagle Limited',
        'source_id': SOURCE_ID,
        'source_url': SOURCE_URL,
        'source_title': SOURCE_TITLE,
        'reported_date': PUBLISHED,
        'source_sha256': sha,
        'pdf_page_count': len(doc),
        'scope': 'Appendix 1 drill collars and Appendix 2 intersections in 20 November announcement',
        'holes_in_appendix': len(holes),
        'holes_with_reported_intercepts': len({r['hole_id'] for r in intervals}),
        'holes_without_significant_intercept': len(no_sig),
        'reported_intervals': len(intervals),
        'table_1_highlights': len(highlights),
        '2026_program_muntanga_north_and_namakande_holes': 216,
        '2026_program_muntanga_north_and_namakande_metres': 21829,
        'holes_since_2026_09_16': 84,
        'metres_since_2026_09_16': 8367,
        'target_5_zone_approx_m': {'length': 1500, 'width': 200},
        'target_6_zone_approx_m': {'length': 800, 'width': 200, 'average_thickness': 3},
        'grade_basis': 'radiometric eU3O8 inferred from downhole gamma, not laboratory assay',
        'cutoff_eu3o8_ppm': 100,
        'minimum_interval_m': 1,
        'maximum_internal_dilution_m': 0.5,
        'resource_note': 'These new exploration intercepts do not constitute a mineral resource or reserve.',
        'true_width_note': 'Lenses dip approximately 15-25 degrees; the announcement assumes intercepts are close to true width, not independently proven true widths.',
        'target_note': 'Target IDs only assigned to holes explicitly listed in Table 1; others left null.',
        'historical_duplicate_policy': 'This is the 20 Nov 2026 release only; do not merge with 16 Sep values without keys/date.',
    }
    return holes, intervals, summary


def write_outputs(holes: list[dict], intervals: list[dict], summary: dict, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    files = [
        (out_dir / 'muntanga_north_20261120_holes.jsonl', holes),
        (out_dir / 'muntanga_north_20261120_intercepts.jsonl', intervals),
    ]
    for dest, records in files:
        data = ''.join(json.dumps(row, ensure_ascii=False, sort_keys=True) + '\n' for row in records)
        temp = dest.with_suffix(dest.suffix + '.tmp')
        temp.write_text(data, encoding='utf-8')
        temp.replace(dest)
    dest = out_dir / 'muntanga_north_20261120_summary.json'
    tmp = dest.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True)+'\n', encoding='utf-8')
    tmp.replace(dest)
    return [p for p, _ in files] + [dest]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pdf', type=Path, help='Use a manually downloaded PDF instead of auto-download')
    parser.add_argument('--refetch', action='store_true', help='Re-download original announcement')
    parser.add_argument('--dry-run', action='store_true', help='Parse/validate only, do not write processed files')
    parser.add_argument('--out-dir', type=Path, default=OUT_DIR)
    args = parser.parse_args()
    pdf_file = args.pdf if args.pdf else fetch_pdf(RAW_PDF, force=args.refetch)
    print('PDF:', pdf_file)
    holes, intercepts, summary = extract_pdf(pdf_file)
    print('Release verified:', summary['reported_date'], '22 pages')
    print('Appendix holes:', len(holes), '| Radiometric intercepts:', len(intercepts))
    print('Holes with intercepts:', summary['holes_with_reported_intercepts'])
    print('Holes without significant intercept:', summary['holes_without_significant_intercept'])
    print('Table 1 highlights:', summary['table_1_highlights'])
    print('Source SHA256:', summary['source_sha256'])
    if args.dry_run:
        print('DRY RUN: No processed files written.')
        return
    for path in write_outputs(holes, intercepts, summary, args.out_dir):
        print('CREATED:', path)

if __name__ == '__main__':
    main()
