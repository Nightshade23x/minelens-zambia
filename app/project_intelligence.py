"""Read-only mining project/facility explorer backed by existing MineLens records.

USGS facilities and source-verified project comparison records are deliberately
SEPARATE catalog entries. This avoids automatically equating a facility, mine,
smelter, and capital investment project based on name similarity.
"""
from __future__ import annotations

from dataclasses import asdict
import csv
from io import StringIO
from typing import Any

from app.facility_search import distinct_capacity_records, load_facilities
from app.mining_map_data import load_admin_centroids, map_facilities, names, text_value
from app.project_comparison_data import load_comparison

USGS_SOURCE_URL = "https://doi.org/10.5066/P1KEQASH"
USGS_SOURCE_TITLE = "U.S. Geological Survey — Zambia Minerals Yearbook 2024 facilities"


def _str(value: object, default: str = "Not reported") -> str:
    result = text_value(value)
    return result or default


def _unique_strings(value: object) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in names(value):
        key = item.casefold()
        if key not in seen:
            seen.add(key)
            output.append(item)
    return output


def _owners(value: object) -> list[str]:
    output = []
    if not isinstance(value, list):
        return output
    for item in value:
        if not isinstance(item, dict):
            continue
        name = _str(item.get("name"), "")
        if not name:
            continue
        share = item.get("share_percent")
        if share is None or str(share).strip() == "":
            output.append(name)
        else:
            output.append(f"{name} ({share}%)")
    return output


def _http_links(value: object) -> list[str]:
    return [url for url in _unique_strings(value) if url.startswith(("https://", "http://"))]


def build_catalog(
    facilities: list[dict],
    centroids: list[dict],
    project_evidence: dict[str, dict] | None = None,
) -> list[dict[str, Any]]:
    """Build a typed, source-backed catalog. No network calls or guessed coordinates."""
    mapped = map_facilities(facilities, centroids)
    catalog: list[dict[str, Any]] = []
    for index, (raw, geo) in enumerate(zip(facilities, mapped)):
        fid = _str(raw.get("usgs_facility_id"), f"row-{index}")
        status = _unique_strings(raw.get("facility_statuses"))
        catalog.append({
            "id": f"USGS:{fid}:{index}",
            "kind": "USGS facility",
            "name": _str(raw.get("facility_name"), "Unnamed facility"),
            "record_id": fid,
            "operator": _unique_strings(raw.get("major_operating_companies")),
            "owners": _owners(raw.get("equity_owners")),
            "commodities": _unique_strings(raw.get("commodities")),
            "feature_types": _unique_strings(raw.get("feature_types")),
            "status": status,
            "province": _str(geo.get("province"), ""),
            "district": _str(geo.get("district"), ""),
            "location_description": _str(geo.get("location_description"), ""),
            "coordinate_basis": _str(geo.get("coordinate_basis"), "not mapped"),
            "map_lat": geo.get("lat"),
            "map_lon": geo.get("lon"),
            "publication_year": raw.get("publication_year") or 2024,
            "capacity_records": distinct_capacity_records(raw),
            "claims": [],
            "source_title": USGS_SOURCE_TITLE,
            "source_url": USGS_SOURCE_URL,
            "supporting_urls": _http_links(raw.get("sources")),
            "source_scope": (
                "USGS source-reported facility information. Operators, ownership, "
                "status and capacity are historical/source-reported, NOT verified live facts."
            ),
        })

    for project_name, project in (project_evidence or {}).items():
        # load_comparison already verifies every claim against cited source text.
        claims = [asdict(c) if not isinstance(c, dict) else dict(c)
                  for c in project.get("claims", [])]
        catalog.append({
            "id": f"PROJECT:{project_name}",
            "kind": "Verified project evidence",
            "name": project_name,
            "record_id": "",
            "operator": [str(project["developer"])] if project.get("developer") else [],
            "owners": [],
            "commodities": [str(project["commodity"])] if project.get("commodity") else [],
            "feature_types": [],
            "status": [],
            "province": "",  # Not asserted by the comparison source.
            "district": "",
            "location_description": "",
            "coordinate_basis": "not mapped",
            "map_lat": None,
            "map_lon": None,
            "publication_year": "2024 / 2026",
            "capacity_records": [],
            "claims": claims,
            "source_title": "MineLens verified project comparison evidence",
            "source_url": "",
            "supporting_urls": _http_links([c.get("source_url") for c in claims]),
            "source_scope": (
                "Project-level claims verified against local evidence snapshots. "
                "CapEx is reported/estimated, capacity can be a target or potential, "
                "and 2024 production is historical. Not verified live status."
            ),
        })

    catalog.sort(key=lambda p: (p["name"].casefold(), p["kind"], p["id"]))
    return catalog


def load_catalog() -> tuple[list[dict], list[str]]:
    """Read existing structured sources; tolerate missing optional project evidence."""
    facilities = load_facilities()  # Core required input; errors should be visible.
    warnings: list[str] = []
    try:
        centroids = load_admin_centroids()
    except (OSError, ValueError, KeyError) as exc:
        centroids = []
        warnings.append(f"District mapping unavailable ({exc}); facility entries are still listed.")
    try:
        projects = load_comparison()
    except (OSError, ValueError, KeyError) as exc:
        projects = {}
        warnings.append(f"Verified project evidence unavailable ({exc}); USGS entries are still listed.")
    return build_catalog(facilities, centroids, projects), warnings


def filter_catalog(
    catalog: list[dict],
    *,
    query: str = "",
    kind: str = "All record types",
    province: str = "All provinces",
    commodity: str = "All commodities",
) -> list[dict]:
    tokens = query.casefold().split()
    matches = []
    for row in catalog:
        if kind != "All record types" and row["kind"] != kind:
            continue
        if province != "All provinces" and row["province"].casefold() != province.casefold():
            continue
        if commodity != "All commodities" and commodity.casefold() not in {
            x.casefold() for x in row["commodities"]
        }:
            continue
        haystack = " ".join([
            row["name"], row["record_id"], row["kind"], row["province"],
            row["district"], row["location_description"],
            *row["operator"], *row["owners"], *row["commodities"],
            *row["feature_types"], *row["status"],
        ]).casefold()
        if tokens and not all(token in haystack for token in tokens):
            continue
        matches.append(row)
    return matches


def distinct_catalog_values(catalog: list[dict], key: str) -> list[str]:
    values: set[str] = set()
    for row in catalog:
        data = row.get(key) or []
        if isinstance(data, str):
            data = [data]
        values.update(str(v) for v in data if str(v).strip())
    return sorted(values, key=str.casefold)


def catalog_table_rows(rows: list[dict]) -> list[dict]:
    return [{
        "Name": row["name"],
        "Record type": row["kind"],
        "Reported operator / developer": ", ".join(row["operator"]) or "Not reported",
        "Commodity": ", ".join(row["commodities"]) or "Not reported",
        "Province": row["province"] or "Not established",
        "Reported status": ", ".join(row["status"]) or "Not established",
        "Source year": str(row["publication_year"]),
    } for row in rows]


def filtered_catalog_csv(rows: list[dict]) -> str:
    output = StringIO()
    columns = ["Name", "Record type", "Reported operator / developer", "Commodity",
               "Province", "Reported status", "Source year"]
    writer = csv.DictWriter(output, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows(catalog_table_rows(rows))
    return output.getvalue()


def profile_markdown(row: dict) -> str:
    """Export a conservative, readable profile with explicit source limitations."""
    def values(key: str) -> str:
        return ", ".join(row[key]) if row[key] else "Not established in the loaded records"

    lines = [
        f"# {row['name']}", "",
        f"- Record type: {row['kind']}",
        f"- Reported operator/developer: {values('operator')}",
        f"- Commodities: {values('commodities')}",
        f"- Source-reported facility status: {values('status')}",
        f"- Province: {row['province'] or 'Not established'}",
        f"- District: {row['district'] or 'Not established'}",
        f"- Location description: {row['location_description'] or 'Not established'}",
        "", "## Data limitations", "", row["source_scope"], "",
    ]
    if row["owners"]:
        lines.extend(["## Source-reported equity owners", "", *[f"- {x}" for x in row["owners"]], ""])
    if row["capacity_records"]:
        lines += ["## USGS source-reported annual capacities", "",
                  "Distinct capacity groups are shown without summing shared rows.", ""]
        for item in row["capacity_records"]:
            value = item.get("capacity")
            unit = item.get("capacity_unit") or "unit not specified"
            commodity = item.get("commodity") or "Commodity not specified"
            detail = item.get("form") or item.get("descriptor") or item.get("type") or ""
            lines.append(f"- {commodity}: {value} {unit}" + (f" ({detail})" if detail else ""))
        lines.append("")
    if row["claims"]:
        lines += ["## Source-verified project claims", ""]
        for c in row["claims"]:
            lines.extend([
                f"- {c.get('label') or c.get('kind')}: {c.get('value')} "
                f"[{c.get('qualifier') or 'source-reported'}]",
                f"  - Source: {c.get('source_title')} | {c.get('document')} | pages {c.get('pages')}",
                f"  - Evidence excerpt: {c.get('excerpt')}",
                f"  - Link: {c.get('source_url') or 'No source URL in snapshot'}",
            ])
        lines.append("")
    lines += ["## Sources", "", f"- {row['source_title']}"]
    if row["source_url"]:
        lines.append(f"- {row['source_url']}")
    lines.extend([f"- Supporting URL: {url}" for url in row["supporting_urls"]])
    return "\n".join(lines) + "\n"
