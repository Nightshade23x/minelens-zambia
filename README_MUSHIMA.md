Mushima North Phase 4 - 9 November 2026

Source: https://www.tertiaryminerals.com/downloads/20261109-tm-adm-news-mushima-north-phase-4-results-and-drilling-start.pdf

Unzip this bundle into the MineLens Zambia project root, preserving ingestion/ and tests/.

PowerShell:
  python -m ingestion.ingest_tertiary_mushima_north --fetch-pdf
  python -m pytest -q tests/test_mushima_phase4_ingestion.py
  python -m pytest -q

The ingest generates data/processed/mushima_north_phase4_20261109_intersections.jsonl
(18 Table 1 intervals), data/processed/mushima_north_phase4_20261109_holes.jsonl
(8 holes with separate peak assays), and a summary.json. It attempts to download
the full official announcement to data/raw/. If fetch fails, omit --fetch-pdf
to build the validated datasets, and download the official PDF in a browser.

This stages structured data only. No router or retrieval integration is performed.
The existing Shuka Minerals Kabwe datasets are not modified.
