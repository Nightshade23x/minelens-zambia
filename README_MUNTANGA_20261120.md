# Atomic Eagle Muntanga North — 20 November 2026 ingestion

Source: [Original Atomic Eagle ASX announcement (22-page PDF)](https://newswire.iguana2.com/2fee0049d633f441/announcements/aeu.asx/6A1356079/AEU_New_Uranium_Mineralised_Zones_Defined_at_Muntanga_North.pdf).

The script downloads the original PDF (or uses `--pdf`), extracts **84 Appendix 1 drill-hole collars**, **29 radiometric intercepts from Appendix 2**, and the **14 headline Table 1 intervals**. It verifies every hole and interval before writing. The 216 holes / 21,829 m figure is the *2026 Muntanga North + Namakande programme total*, not the number of newly disclosed collar rows.

## Setup (PowerShell, from project root)

```powershell
python -m pip install -r requirements-muntanga.txt
python -m pytest -q tests/test_atomic_eagle_muntanga_ingestion.py
python -m ingestion.ingest_atomic_eagle_muntanga --dry-run
python -m ingestion.ingest_atomic_eagle_muntanga
```

If download fails, open the PDF URL above in your browser, download it, then:

```powershell
python -m ingestion.ingest_atomic_eagle_muntanga --pdf "$env:USERPROFILE\Downloads\AEU_New_Uranium_Mineralised_Zones_Defined_at_Muntanga_North.pdf"
```

## Outputs

- `data/raw/atomic_eagle_muntanga_north_20261120.pdf` (if auto-downloaded; keep source provenance)
- `data/processed/muntanga_north_20261120_holes.jsonl`
- `data/processed/muntanga_north_20261120_intercepts.jsonl`
- `data/processed/muntanga_north_20261120_summary.json`

**Measurement rules:** `eu3o8_ppm` is *equivalent uranium* calculated from downhole gamma data, **not** a laboratory U₃O₈ assay, a reserve or a new mineral resource estimate. “No Significant Intercept” means no interval met the stated reporting threshold; do not store it as grade zero. Table 1 assigns explicit target 5/6 labels only to those intervals. The remaining target IDs stay unknown instead of being inferred from coordinates. Previous September results are not merged.

**Site coordinates:** Appendix 1 uses WGS84 UTM Zone 35S (easting/northing), not latitude/longitude. Do not plot these raw coordinates as GPS degrees.

**Safe integration:** This import creates structured datasets. It does **not** modify MineLens's global router, RAG answers, or the existing drilling dashboards; add search/UI support only after the 84/29/14 validation passes.

Optional quick inspection after ingestion:

```powershell
python -m scripts.inspect_muntanga_north
python -m scripts.inspect_muntanga_north MNDTH2421
```
