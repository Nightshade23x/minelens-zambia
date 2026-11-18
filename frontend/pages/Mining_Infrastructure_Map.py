"""MineLens mining infrastructure and licensing activity by district.

All markers are administrative district CENTROIDS. They are not verified mine
coordinates, licence polygon locations, or exact exploration sites.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
import pydeck as pdk
import streamlit as st

from app.facility_search import load_facilities
from app.licensing_search import load_licensing_records
from app.mining_map_data import (
    distinct_values,
    district_summary,
    load_admin_centroids,
    map_facilities,
    map_licence_records,
    matches_filters,
    circle_radius,
)
from frontend.styles.theme import apply_theme
from frontend.utils.licensing_geo import normalized_districts


st.set_page_config(
    page_title="Mining Map | MineLens Zambia",
    page_icon="🗺️",
    layout="wide",
    initial_sidebar_state="expanded",
)
apply_theme()


@st.cache_data(show_spinner=False)
def map_records():
    admin = load_admin_centroids()
    facilities = map_facilities(load_facilities(), admin)
    raw_licences = load_licensing_records()
    licences = map_licence_records(raw_licences, admin, normalized_districts)
    return facilities, licences, len(raw_licences)


@st.cache_data(show_spinner=False)
def boundary_geojson(path: str):
    target = ROOT / "frontend" / "data" / path
    if not target.exists():
        return None
    return json.loads(target.read_text(encoding="utf-8"))


st.title("Zambia Mining Infrastructure Map")
st.caption("USGS Minerals Yearbook 2024 facilities + MineLens mining-licensing records")
st.markdown(
    "Explore mining and processing facilities alongside district-level licensing "
    "activity. Markers show **district centres**, not exact facility coordinates "
    "or mining-right boundaries."
)

try:
    all_facilities, all_licences, raw_licence_count = map_records()
except (FileNotFoundError, ValueError, KeyError) as exc:
    st.error(f"Required local MineLens data is unavailable: {exc}")
    st.stop()

with st.sidebar:
    st.header("Map filters")
    show_facilities = st.checkbox("Show USGS facilities", value=True)
    show_licences = st.checkbox("Show licensing activity", value=True)

    province_choices = sorted(
        set(distinct_values(all_facilities, "province"))
        | set(distinct_values(all_licences, "province")),
        key=str.casefold,
    )
    province = st.selectbox("Province", ["All provinces", *province_choices])
    commodity_choices = sorted(
        set(distinct_values(all_facilities, "commodities"))
        | set(distinct_values(all_licences, "commodities")),
        key=str.casefold,
    )
    commodity = st.selectbox("Commodity", ["All commodities", *commodity_choices])
    search = st.text_input("Find facility, operator, applicant or licence", "")
    facility_status = st.selectbox(
        "USGS reported facility status",
        ["All statuses", *distinct_values(all_facilities, "reported_statuses")],
    )
    decision = st.selectbox(
        "Licensing decision",
        ["All statuses", *distinct_values(all_licences, "decision")],
    )
    st.caption(
        "Facility statuses reflect source reporting, not verified live operation. "
        "Licensing decisions do not by themselves confirm an active issued licence."
    )

facilities = matches_filters(
    all_facilities,
    province=province,
    commodity=commodity,
    search=search,
    status=facility_status,
)
licences = matches_filters(
    all_licences,
    province=province,
    commodity=commodity,
    search=search,
    status=decision,
    status_key="decision",
)

visible_facilities = facilities if show_facilities else []
visible_licences = licences if show_licences else []
summary = district_summary(visible_facilities, visible_licences)

mapped_facilities = sum(row["lat"] is not None for row in facilities)
known_facility_count = len(all_facilities)
# Multi-district licensing records may be represented at multiple district centres.
unique_licensing_rows = len({r["record_index"] for r in licences})

m1, m2, m3, m4 = st.columns(4)
m1.metric("USGS facilities", f"{len(facilities):,} / {known_facility_count:,}")
m2.metric("Facilities with district match", f"{mapped_facilities:,}")
m3.metric("Districts on map", f"{len(summary):,}")
m4.metric("Licensing records in filter", f"{unique_licensing_rows:,}")

if len(facilities) > mapped_facilities:
    st.caption(
        f"{len(facilities) - mapped_facilities:,} matching facility record(s) lack "
        "an unambiguous district match; they remain in the table but are not pinned."
    )

if not summary:
    st.info("No mappable district records match the current filters.")
else:
    for row in summary:
        row["facility_radius"] = circle_radius(row["facilities"], base=10000)
        row["licence_radius"] = circle_radius(row["licence_mentions"], base=13000)
        row["display_place"] = f"{row['district']}, {row['province']}"

    layers = []
    province_geo = boundary_geojson("zambia_provinces.geojson")
    country_geo = boundary_geojson("zambia_country.geojson")

    if province_geo is not None:
        layers.append(pdk.Layer(
            "GeoJsonLayer", data=province_geo, filled=True, stroked=True,
            get_fill_color=[45, 65, 90, 22],
            get_line_color=[105, 160, 210, 165],
            line_width_min_pixels=1, pickable=False,
        ))
    if country_geo is not None:
        layers.append(pdk.Layer(
            "GeoJsonLayer", data=country_geo, filled=False, stroked=True,
            get_line_color=[245, 245, 245, 220],
            line_width_min_pixels=2.5, pickable=False,
        ))

    if show_licences:
        licence_points = [r for r in summary if r["licence_mentions"]]
        layers.append(pdk.Layer(
            "ScatterplotLayer", data=licence_points,
            radius_units="meters", radius_min_pixels=3, radius_max_pixels=9,
            get_position=["lon", "lat"], get_radius="licence_radius",
            filled=False, stroked=True, get_line_color=[245, 95, 95, 215],
            line_width_min_pixels=1.5, line_width_max_pixels=2, pickable=True,
        ))
    if show_facilities:
        facility_points = [r for r in summary if r["facilities"]]
        layers.append(pdk.Layer(
            "ScatterplotLayer", data=facility_points,
            radius_units="meters", radius_min_pixels=3, radius_max_pixels=7,
            get_position=["lon", "lat"], get_radius="facility_radius",
            filled=True, stroked=True, get_fill_color=[105, 195, 250, 195],
            get_line_color=[255, 255, 255, 230], line_width_min_pixels=1,
            pickable=True,
        ))

    deck = pdk.Deck(
        layers=layers,
        initial_view_state=pdk.ViewState(latitude=-13.3, longitude=27.8, zoom=5.25, pitch=0),
        tooltip={
            "html": "<b>{display_place}</b><br/>USGS facility records: {facilities}"
                    "<br/>Licence district mentions: {licence_mentions}"
                    "<br/><small>District centre; not an exact site</small>",
            "style": {"backgroundColor": "#171b23", "color": "white"},
        },
        map_style=None,
    )
    st.pydeck_chart(deck, use_container_width=True)
    st.caption(
        "Blue filled markers = mapped USGS facility records; red outlines = "
        "licence-record district mentions. Circle sizes are screen-limited count symbols, not geographic coverage. "
        "Positions are district centroids, NOT site coordinates."
    )

st.subheader("Inspect a district")
if summary:
    options = sorted(summary, key=lambda r: (r["province"], r["district"]))
    labels = [f"{r['district']} ({r['province']})" for r in options]
    selected_index = st.selectbox(
        "District", range(len(options)), format_func=lambda i: labels[i]
    )
    selected = options[selected_index]
    subset_facilities = [
        r for r in visible_facilities
        if (r["province"], r["district"]) == (selected["province"], selected["district"])
    ]
    subset_licences = [
        r for r in visible_licences
        if (r["province"], r["district"]) == (selected["province"], selected["district"])
    ]
    st.write(
        f"**{selected['district']}, {selected['province']}** — "
        f"{len(subset_facilities)} facility record(s), "
        f"{len(subset_licences)} licence district mention(s)."
    )
else:
    subset_facilities, subset_licences = [], []

facility_columns = [
    "facility_id", "facility_name", "province", "district",
    "location_description", "commodities", "feature_types",
    "reported_statuses", "operators", "source_url", "coordinate_basis",
]
licence_columns = [
    "licence_code", "applicant", "licence_type", "decision", "commodities",
    "province", "district", "source_url", "coordinate_basis",
]

f_tab, l_tab, unmapped_tab, source_tab = st.tabs([
    "Facilities", "Licensing records", "Unmapped facilities", "Sources & accuracy",
])
with f_tab:
    data = pd.DataFrame(subset_facilities, columns=facility_columns)
    st.dataframe(data, use_container_width=True, hide_index=True)
    st.download_button(
        "Export district facilities (CSV)",
        data=data.to_csv(index=False).encode("utf-8"),
        file_name="minelens_district_facilities.csv", mime="text/csv",
    )
with l_tab:
    data = pd.DataFrame(subset_licences, columns=licence_columns)
    st.dataframe(data, use_container_width=True, hide_index=True)
    st.download_button(
        "Export district licensing records (CSV)",
        data=data.to_csv(index=False).encode("utf-8"),
        file_name="minelens_district_licensing.csv", mime="text/csv",
    )
    st.caption(
        "A licence can appear in more than one district. Counts represent "
        "district mentions, not the number of unique licensed mine sites."
    )
with unmapped_tab:
    unknown = [r for r in facilities if r["lat"] is None]
    st.dataframe(
        pd.DataFrame(unknown, columns=facility_columns + ["mapping_note"]),
        use_container_width=True, hide_index=True,
    )
    st.caption("Unmapped records are not automatically placed at provincial centres.")
with source_tab:
    st.markdown(
        "**Facilities:** USGS Minerals Yearbook 2024 - Zambia, using the "
        "existing `data/processed/usgs_2024_zambia_facilities.jsonl` loader. "
        "Reported operating status and owners reflect that dataset.\n\n"
        "**Licensing:** existing MineLens licensing record loader. "
        "Committee decisions must not be interpreted as verified active licences.\n\n"
        "**Map geography:** administrative district centroids and provincial "
        "boundaries already bundled with MineLens. Centre coordinates are "
        "approximations and do not establish exact facility locations, "
        "mining-right polygons, or resource estimates.\n\n"
        f"The underlying licensing loader contains {raw_licence_count:,} "
        "records before geographic matching."
    )
