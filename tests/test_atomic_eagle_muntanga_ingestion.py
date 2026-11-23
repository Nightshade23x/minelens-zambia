from copy import deepcopy
import json
from pathlib import Path

import pytest

from ingestion.ingest_atomic_eagle_muntanga import (
    COLLAR, HIGHLIGHT, INTERVAL, NO_INTERCEPT,
    fingerprint, parse_collar, parse_highlight, parse_intercept,
    validate, write_outputs,
)


def test_parse_known_collar_from_company_appendix():
    row = parse_collar('MNDTH2421 682462 8209207 419 -90 0 70', 9)
    assert row['hole_id'] == 'MNDTH2421'
    assert row['utm_zone'] == '35S'
    assert row['easting_m'] == 682462
    assert row['northing_m'] == 8209207
    assert row['source_page'] == 9
    assert row['dip_deg'] == -90


def test_parse_radiometric_intercept_not_assay():
    row = parse_intercept('MNDTH2421 38.79 43.97 5.18 380', 12)
    assert row['eu3o8_ppm'] == 380
    assert row['interval_m'] == 5.18
    assert row['is_laboratory_assay'] is False
    assert row['is_mineral_resource'] is False
    assert row['grade_unit'] == 'ppm eU3O8'
    assert row['reported_date'] == '2026-11-20'


def test_highlight_table_target():
    row = parse_highlight('6 MNDTH2454 36.75 47.65 10.90 250', 4)
    assert row['target_id'] == 6
    assert row['source_page'] == 4
    assert row['interval_m'] == 10.9


def test_no_significant_is_not_numeric_zero():
    assert NO_INTERCEPT.fullmatch('MNDTH2458 No Significant Intercept')
    assert parse_intercept('MNDTH2458 No Significant Intercept', 13) is None
    assert not INTERVAL.match('MNDTH2458 No Significant Intercept')


def test_other_source_format_not_accidentally_parsed():
    assert parse_collar('KBDD001 682462 8209207 419 -90 0 70', 8) is None
    assert parse_intercept('MNDTH2421 38.79 43.97', 12) is None
    assert parse_highlight('7 MNDTH2454 36.75 47.65 10.9 250', 4) is None


def test_duplicate_identity_includes_hole_and_depth():
    a = parse_intercept('MNDTH2424 21.86 26.84 4.98 261', 12)
    b = parse_intercept('MNDTH2424 27.74 30.48 2.74 179', 12)
    assert fingerprint(a) != fingerprint(b)


def test_bad_hole_count_fails_closed():
    row = parse_collar('MNDTH2421 682462 8209207 419 -90 0 70', 9)
    with pytest.raises(ValueError, match='Expected 84'):
        validate([row], [], [], set())


def test_output_file_names_and_json(tmp_path):
    row = parse_collar('MNDTH2421 682462 8209207 419 -90 0 70', 9)
    paths = write_outputs([row], [], {'release': '2026-11-20'}, tmp_path)
    assert len(paths) == 3
    assert all(p.exists() for p in paths)
    assert json.loads(paths[0].read_text().splitlines()[0])['hole_id'] == 'MNDTH2421'
    assert json.loads(paths[2].read_text())['release'] == '2026-11-20'


def test_source_isolation_from_other_releases():
    row = parse_intercept('MNDTH2453 45.35 49.60 4.25 273', 13)
    assert row['canonical_source_id'].endswith('20261120')
    assert '20260916' not in row['canonical_source_id']
    assert row['project'] == 'Muntanga North'
