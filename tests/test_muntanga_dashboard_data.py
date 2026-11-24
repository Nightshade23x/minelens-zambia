"""Tests for source-scoped multi-project exploration dashboard data."""
from pathlib import Path
import json

import pytest
from app.muntanga_dashboard_data import (
    SOURCE_ID, best_by_hole, collar_map_rows, load_muntanga_report, visible_records,
)


def make_report(tmp_path: Path):
    folder = tmp_path / 'data' / 'processed'
    folder.mkdir(parents=True)
    holes = []
    intervals = []
    for i in range(84):
        hole_id = f'MNDTH{i+2000}'
        significant = i < 18
        holes.append({
            'hole_id': hole_id, 'project': 'Muntanga North', 'source_id': SOURCE_ID,
            'intercept_reporting_status': 'reported_radiometric_intercept' if significant else 'no_significant_intercept',
            'target_id': 5 if i < 7 else (6 if i < 14 else None),
            'utm_zone': '35S', 'coordinate_datum': 'WGS84',
            'easting_m': 682462 + i, 'northing_m': 8209207 + i,
            'source_page': 8, 'hole_depth_m': 100,
        })
        if significant:
            for j in range(2 if i < 11 else 1):
                grade = 380 if (i,j) == (0,0) else 100+i+j
                intervals.append({
                    'hole_id': hole_id, 'project': 'Muntanga North', 'source_id': SOURCE_ID,
                    'grade_basis': 'downhole_gamma_equivalent_uranium',
                    'grade_unit': 'ppm eU3O8', 'is_laboratory_assay': False,
                    'is_mineral_resource': False, 'eu3o8_ppm': grade,
                    'from_m': 10+j*3, 'to_m': 11+j*3, 'interval_m': 1,
                    'source_page': 12,
                })
    assert len(intervals) == 29
    summary = {'project': 'Muntanga North', 'source_id': SOURCE_ID,
               'reported_date': '2026-11-20', 'holes_in_appendix': 84,
               'reported_intervals': 29, 'source_url': 'https://example.org/source.pdf'}
    for name, rows in [('holes',holes), ('intercepts',intervals)]:
        (folder / f'muntanga_north_20261120_{name}.jsonl').write_text(
            ''.join(json.dumps(r)+'\n' for r in rows), encoding='utf-8')
    (folder / 'muntanga_north_20261120_summary.json').write_text(json.dumps(summary), encoding='utf-8')
    return folder


def test_load_verified_release_counts(tmp_path):
    make_report(tmp_path)
    report = load_muntanga_report(tmp_path)
    assert len(report.holes) == 84 and len(report.intervals) == 29


def test_highest_is_radiometric_not_assay(tmp_path):
    make_report(tmp_path)
    report = load_muntanga_report(tmp_path)
    top = best_by_hole(report.intervals)[0]
    assert (top['hole_id'], top['eu3o8_ppm']) == ('MNDTH2000', 380)
    assert top['is_laboratory_assay'] is False


def test_no_significant_is_missing_not_zero(tmp_path):
    make_report(tmp_path)
    report = load_muntanga_report(tmp_path)
    holes, intervals = visible_records(report)
    rows = collar_map_rows(holes, intervals)
    missing = next(r for r in rows if r['hole_id'] == 'MNDTH2020')
    assert missing['best_reported_ppm'] is None
    assert 'No significant' in missing['best_grade_label']


def test_filter_by_target(tmp_path):
    make_report(tmp_path)
    report = load_muntanga_report(tmp_path)
    holes, intervals = visible_records(report, target_ids={5}, include_no_significant=False)
    assert len(holes) == 7
    assert {h['target_id'] for h in holes} == {5}
    assert len(intervals) == 14


def test_explicit_hole_selection(tmp_path):
    make_report(tmp_path)
    report = load_muntanga_report(tmp_path)
    holes, intervals = visible_records(report, hole_ids={'MNDTH2001'})
    assert len(holes) == 1 and len(intervals) == 2


def test_bad_source_rejected(tmp_path):
    folder = make_report(tmp_path)
    file = folder / 'muntanga_north_20261120_intercepts.jsonl'
    rows = [json.loads(s) for s in file.read_text(encoding='utf-8').splitlines()]
    rows[0]['is_laboratory_assay'] = True
    file.write_text('\n'.join(map(json.dumps, rows))+'\n', encoding='utf-8')
    with pytest.raises(ValueError, match='assay/resource'):
        load_muntanga_report(tmp_path)


def test_wrong_crs_rejected(tmp_path):
    folder = make_report(tmp_path)
    path = folder / 'muntanga_north_20261120_holes.jsonl'
    lines = path.read_text(encoding='utf-8').splitlines()
    first = json.loads(lines[0]); first['utm_zone'] = '35N'; lines[0] = json.dumps(first)
    path.write_text('\n'.join(lines)+'\n', encoding='utf-8')
    with pytest.raises(ValueError, match='coordinate reference'):
        load_muntanga_report(tmp_path)


def test_real_utm_south_conversion(tmp_path):
    make_report(tmp_path)
    report = load_muntanga_report(tmp_path)
    row = collar_map_rows(report.holes[:1], report.intervals[:2])[0]
    assert -18 < row['latitude'] < -15
    assert 27 < row['longitude'] < 30


def test_unique_ids(tmp_path):
    folder = make_report(tmp_path)
    path = folder / 'muntanga_north_20261120_holes.jsonl'
    rows = [json.loads(x) for x in path.read_text().splitlines()]
    rows[1]['hole_id'] = rows[0]['hole_id']
    path.write_text('\n'.join(map(json.dumps, rows))+'\n', encoding='utf-8')
    with pytest.raises(ValueError, match='Duplicate'):
        load_muntanga_report(tmp_path)


def test_real_dataset_if_present():
    source = Path('data/processed/muntanga_north_20261120_summary.json')
    if not source.exists():
        pytest.skip('Full local MineLens dataset is not mounted in this environment')
    report = load_muntanga_report()
    assert len(report.holes) == 84 and len(report.intervals) == 29
    assert best_by_hole(report.intervals)[0]['hole_id'] == 'MNDTH2421'
