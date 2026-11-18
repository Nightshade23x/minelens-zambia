"""Geographic adapters for MineLens's district-level mining intelligence map.

USGS facility records do NOT generally contain surveyed point coordinates. We
match unambiguous district names from their descriptions to administrative
CENTROIDS; uncertain facilities are left off the map, not geocoded by guess.
"""

from __future__ import annotations

import csv
import math
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Callable


ROOT = Path(__file__).resolve().parents[1]
ADMIN_CSV = ROOT / "frontend" / "data" / "zambia_admin_divisions.csv"


def canonical_name(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    text = text.replace("\u2013", "-").replace("\u2014", "-")
    text = re.sub(r"\bprovince\b", "", text, flags=re.IGNORECASE)
    return re.sub(r"[^a-z0-9]", "", text.casefold())


def text_value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple, set)):
        return ", ".join(str(item) for item in value if item is not None)
    return str(value).strip()


def names(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(x).strip() for x in value if str(x).strip()]
    value = str(value).strip()
    return [value] if value else []


def load_admin_centroids(path: Path = ADMIN_CSV) -> list[dict]:
    """Load REAL admin centroid coordinates already used by Location Explorer."""
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(line for line in file if not line.startswith("#"))
        required = {"level", "name.en", "parent.name.en", "geo.lat", "geo.lon"}
        if not required.issubset(set(reader.fieldnames or [])):
            raise ValueError("Admin geography CSV is missing expected columns")
        results: list[dict] = []
        seen = set()
        for row in reader:
            try:
                if float(row.get("level") or 0) != 2:
                    continue
                lat = float(row["geo.lat"])
                lon = float(row["geo.lon"])
            except (TypeError, ValueError):
                continue
            district = (row.get("name.en") or "").strip()
            province = (row.get("parent.name.en") or "").strip()
            if not district or not province or not (-18.5 < lat < -8.0 and 21 < lon < 35):
                continue
            key = (canonical_name(province), canonical_name(district))
            if key in seen:
                continue
            seen.add(key)
            results.append({
                "province": province,
                "district": district,
                "lat": lat,
                "lon": lon,
                "coordinate_basis": "district_centroid",
            })
    return results


def _district_candidates(description: str, province: str, centroids: list[dict]) -> list[dict]:
    description = unicodedata.normalize("NFKC", description).casefold()
    region = canonical_name(province)
    out = []
    for item in centroids:
        if region and canonical_name(item["province"]) != region:
            continue
        district = item["district"].casefold()
        # Word boundaries: do not mistake 'Kitwe' for part of a longer word.
        if re.search(r"(?<!\w)" + re.escape(district) + r"(?!\w)", description):
            out.append(item)
    return out


def map_facilities(facilities: list[dict], centroids: list[dict]) -> list[dict]:
    """Enrich each USGS record; map only ONE unambiguous district match."""
    result = []
    for index, record in enumerate(facilities):
        province = text_value(record.get("province"))
        description = text_value(record.get("location_description"))
        candidates = _district_candidates(description, province, centroids)
        mapped = candidates[0] if len(candidates) == 1 else None
        company = names(record.get("major_operating_companies"))
        commodities = names(record.get("commodities"))
        row = {
            "facility_id": text_value(record.get("usgs_facility_id")) or f"row-{index}",
            "facility_name": text_value(record.get("facility_name")) or "Unnamed facility",
            "province": province,
            "district": mapped["district"] if mapped else "",
            "location_description": description,
            "commodities": commodities,
            "feature_types": names(record.get("feature_types")),
            "reported_statuses": names(record.get("facility_statuses")),
            "operators": company,
            "source_url": next((str(s) for s in names(record.get("sources")) if str(s).startswith("http")), ""),
            "publication_year": record.get("publication_year"),
            "lat": mapped["lat"] if mapped else None,
            "lon": mapped["lon"] if mapped else None,
            "coordinate_basis": "district centroid, not facility position" if mapped else "not mapped",
            "mapping_note": "" if mapped else (
                "Ambiguous district references" if len(candidates) > 1
                else "No unambiguous district match"
            ),
        }
        result.append(row)
    return result


def map_licence_records(
    records: list[dict],
    centroids: list[dict],
    district_extractor: Callable[[dict], list[str]],
) -> list[dict]:
    """One mention per district; multi-district licences are not unique sites."""
    lookup = {
        (canonical_name(c["province"]), canonical_name(c["district"])): c
        for c in centroids
    }
    result: list[dict] = []
    for index, record in enumerate(records):
        province = text_value(record.get("province"))
        districts = district_extractor(record) or []
        if isinstance(districts, str):
            districts = [districts]
        unique = set()
        for district in districts:
            name = canonical_name(district)
            if not name or name in unique:
                continue
            unique.add(name)
            item = lookup.get((canonical_name(province), name))
            if item is None:
                continue
            result.append({
                "record_index": index,
                "licence_code": text_value(record.get("licence_code")),
                "applicant": text_value(record.get("applicant")),
                "licence_type": text_value(record.get("licence_type")),
                "decision": text_value(record.get("decision")),
                "commodities": names(record.get("commodities")),
                "province": item["province"],
                "district": item["district"],
                "lat": item["lat"],
                "lon": item["lon"],
                "coordinate_basis": "district centroid, not licensed-area boundary",
                "source_url": text_value(record.get("source_url")),
            })
    return result


def matches_filters(
    rows: list[dict],
    *,
    province: str = "All provinces",
    commodity: str = "All commodities",
    search: str = "",
    status: str = "All statuses",
    status_key: str = "reported_statuses",
) -> list[dict]:
    needle = search.casefold().strip()
    out = []
    for row in rows:
        if province != "All provinces" and canonical_name(row.get("province")) != canonical_name(province):
            continue
        if commodity != "All commodities" and canonical_name(commodity) not in {
            canonical_name(x) for x in names(row.get("commodities"))
        }:
            continue
        if status != "All statuses" and canonical_name(status) not in {
            canonical_name(x) for x in names(row.get(status_key))
        }:
            continue
        searchable = " ".join(text_value(row.get(k)) for k in (
            "facility_name", "facility_id", "location_description", "operators",
            "applicant", "licence_code", "district", "province", "commodities",
        )).casefold()
        if needle and needle not in searchable:
            continue
        out.append(row)
    return out


def district_summary(facilities: list[dict], licences: list[dict]) -> list[dict]:
    """Aggregate COUNT of records by district, not exact facility/map positions."""
    grouped: dict[tuple[str, str], dict] = {}
    for kind, rows in (("facilities", facilities), ("licence_mentions", licences)):
        for row in rows:
            if row.get("lat") is None or row.get("lon") is None:
                continue
            key = (canonical_name(row["province"]), canonical_name(row["district"]))
            if key not in grouped:
                grouped[key] = {
                    "province": row["province"],
                    "district": row["district"],
                    "lat": row["lat"], "lon": row["lon"],
                    "facilities": 0, "licence_mentions": 0,
                }
            grouped[key][kind] += 1
    return sorted(grouped.values(), key=lambda x: (-x["facilities"], -x["licence_mentions"], x["district"]))


def distinct_values(rows: list[dict], field: str) -> list[str]:
    return sorted({str(x) for row in rows for x in names(row.get(field)) if str(x).strip()}, key=str.casefold)


def circle_radius(count: int, base: float = 11000) -> float:
    """Meters for pydeck ScatterplotLayer, capped to avoid hiding the map."""
    if not isinstance(count, int) or count < 0:
        raise ValueError("count must be a nonnegative integer")
    return min(75000.0, base * math.sqrt(max(count, 1)))
