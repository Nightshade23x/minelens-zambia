from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd
import pydeck as pdk
import streamlit as st

from frontend.utils.display import clean_text
from frontend.utils.licensing_geo import normalized_districts


# =========================================================
# PATHS
# =========================================================

ROOT_DIR = Path(__file__).resolve().parents[2]

ADMIN_DATA_PATH = (
    ROOT_DIR
    / "frontend"
    / "data"
    / "zambia_admin_divisions.csv"
)

PROVINCE_GEOJSON_PATH = (
    ROOT_DIR
    / "frontend"
    / "data"
    / "zambia_provinces.geojson"
)

COUNTRY_GEOJSON_PATH = (
    ROOT_DIR
    / "frontend"
    / "data"
    / "zambia_country.geojson"
)


# =========================================================
# ADMINISTRATIVE GEOGRAPHY
# =========================================================

@st.cache_data(
    show_spinner=False,
)
def load_district_centroids() -> pd.DataFrame:
    """
    Load Zambia district centroid coordinates.
    """

    dataframe = pd.read_csv(
        ADMIN_DATA_PATH,
        comment="#",
    )

    districts = dataframe[
        dataframe["level"].eq(2)
    ].copy()

    districts = districts[
        [
            "name.en",
            "parent.name.en",
            "geo.lat",
            "geo.lon",
        ]
    ]

    districts = districts.rename(
        columns={
            "name.en": "district",
            "parent.name.en": "province",
            "geo.lat": "lat",
            "geo.lon": "lon",
        }
    )

    districts["district"] = (
        districts["district"]
        .astype(str)
        .str.strip()
    )

    districts["province"] = (
        districts["province"]
        .astype(str)
        .str.strip()
    )

    districts["lat"] = pd.to_numeric(
        districts["lat"],
        errors="coerce",
    )

    districts["lon"] = pd.to_numeric(
        districts["lon"],
        errors="coerce",
    )

    districts = districts.dropna(
        subset=[
            "lat",
            "lon",
        ]
    )

    return districts


@st.cache_data(
    show_spinner=False,
)
def load_geojson(
    path: Path,
) -> dict:
    """
    Load a local GeoJSON file.
    """

    with path.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(
            file
        )


# =========================================================
# MARKER STYLE
# =========================================================

def marker_color(
    records: int,
    maximum: int,
) -> list[int]:
    """
    MineLens coral/red marker palette.
    """

    if maximum <= 0:
        intensity = 0.0
    else:
        intensity = records / maximum

    return [
        255,
        int(
            125 - 45 * intensity
        ),
        int(
            125 - 45 * intensity
        ),
        220,
    ]


# =========================================================
# MAP AGGREGATION
# =========================================================

def build_district_map_data(
    records: list[dict],
) -> tuple[pd.DataFrame, int, int]:
    """
    Aggregate licensing records by district.
    """

    centroid_data = (
        load_district_centroids()
    )

    known_districts = set(
        centroid_data["district"]
    )

    district_counts: dict[
        str,
        int,
    ] = {}

    mapped_records = 0
    unmapped_records = 0

    for record in records:

        districts = normalized_districts(
            record
        )

        matched_districts = [
            district
            for district in districts
            if district in known_districts
        ]

        if matched_districts:
            mapped_records += 1
        else:
            unmapped_records += 1

        for district in set(
            matched_districts
        ):

            district_counts[
                district
            ] = (
                district_counts.get(
                    district,
                    0,
                )
                + 1
            )

    if not district_counts:

        return (
            pd.DataFrame(),
            mapped_records,
            unmapped_records,
        )

    centroid_lookup = (
        centroid_data
        .set_index(
            "district"
        )
        .to_dict(
            "index"
        )
    )

    maximum_count = max(
        district_counts.values()
    )

    rows: list[dict] = []

    for district, count in (
        district_counts.items()
    ):

        geo = centroid_lookup[
            district
        ]

        radius = (
            8000
            + math.sqrt(
                count
            )
            * 3500
        )

        rows.append(
            {
                "district": district,
                "province": clean_text(
                    geo["province"]
                ),
                "records": count,
                "lat": float(
                    geo["lat"]
                ),
                "lon": float(
                    geo["lon"]
                ),
                "radius": radius,
                "fill_color": marker_color(
                    count,
                    maximum_count,
                ),
            }
        )

    map_dataframe = (
        pd.DataFrame(
            rows
        )
        .sort_values(
            "records",
            ascending=False,
        )
        .reset_index(
            drop=True
        )
    )

    return (
        map_dataframe,
        mapped_records,
        unmapped_records,
    )


# =========================================================
# VIEW STATE
# =========================================================

def map_view_state(
    map_data: pd.DataFrame,
) -> pdk.ViewState:
    """
    Automatically choose a useful map centre and zoom
    from the currently visible districts.
    """

    if map_data.empty:

        return pdk.ViewState(
            latitude=-13.4,
            longitude=27.8,
            zoom=5.0,
            pitch=0,
        )

    latitude = float(
        map_data["lat"].mean()
    )

    longitude = float(
        map_data["lon"].mean()
    )

    if len(map_data) == 1:

        zoom = 7.0

    else:

        lat_range = (
            map_data["lat"].max()
            - map_data["lat"].min()
        )

        lon_range = (
            map_data["lon"].max()
            - map_data["lon"].min()
        )

        spread = max(
            lat_range,
            lon_range,
        )

        if spread < 0.75:
            zoom = 7.0

        elif spread < 1.5:
            zoom = 6.4

        elif spread < 3:
            zoom = 5.8

        elif spread < 5:
            zoom = 5.3

        else:
            zoom = 5.0

    return pdk.ViewState(
        latitude=latitude,
        longitude=longitude,
        zoom=zoom,
        pitch=0,
        bearing=0,
    )


# =========================================================
# MAP DISPLAY
# =========================================================

def display_licensing_map(
    records: list[dict],
    selected_districts: list[str] | None = None,
) -> None:
    """
    Display district-level licensing activity.

    Province and country boundary polygons are shown
    for spatial context.

    Licence circles represent district centroids,
    not precise mining-right locations.
    """

    st.subheader(
        "Licensing map"
    )

    st.caption(
        "Markers represent district centroids and show "
        "the number of matching licensing records. "
        "They are not precise licence locations."
    )

    if not records:

        st.info(
            "No records are available to map."
        )

        return

    (
        map_data,
        mapped_records,
        unmapped_records,
    ) = build_district_map_data(
        records
    )

    if map_data.empty:

        st.info(
            "None of the current records could be "
            "matched to district coordinates."
        )

        return

    # -----------------------------------------------------
    # RESPECT ACTIVE DISTRICT FILTER
    # -----------------------------------------------------

    if selected_districts:

        selected_set = set(
            selected_districts
        )

        map_data = map_data[
            map_data[
                "district"
            ].isin(
                selected_set
            )
        ].copy()

    if map_data.empty:

        st.info(
            "No mapped districts match "
            "the active district filter."
        )

        return

    # -----------------------------------------------------
    # METRICS
    # -----------------------------------------------------

    metric_1, metric_2 = (
        st.columns(
            2
        )
    )

    with metric_1:

        st.metric(
            "Mapped records",
            f"{mapped_records:,}",
        )

    with metric_2:

        st.metric(
            "Mapped districts",
            f"{len(map_data):,}",
        )

    if unmapped_records:

        st.caption(
            f"{unmapped_records:,} record(s) could not "
            f"be mapped to a district centroid."
        )

    # -----------------------------------------------------
    # LOAD BOUNDARIES
    # -----------------------------------------------------

    province_geojson = (
        load_geojson(
            PROVINCE_GEOJSON_PATH
        )
    )

    country_geojson = (
        load_geojson(
            COUNTRY_GEOJSON_PATH
        )
    )

    # -----------------------------------------------------
    # PROVINCE BOUNDARIES
    # -----------------------------------------------------

    province_layer = pdk.Layer(
        "GeoJsonLayer",
        data=province_geojson,

        filled=True,
        stroked=True,

        # Very subtle province fill
        get_fill_color=[
            60,
            75,
            95,
            22,
        ],

        # Blue-grey internal boundaries
        get_line_color=[
            105,
            160,
            210,
            210,
        ],

        line_width_min_pixels=1.5,

        pickable=False,
    )

    # -----------------------------------------------------
    # NATIONAL BORDER
    # -----------------------------------------------------

    country_layer = pdk.Layer(
        "GeoJsonLayer",
        data=country_geojson,

        filled=False,
        stroked=True,

        # Strong white Zambia outline
        get_line_color=[
            245,
            245,
            245,
            245,
        ],

        line_width_min_pixels=3,

        pickable=False,
    )

    # -----------------------------------------------------
    # LICENSING MARKERS
    # -----------------------------------------------------

    district_layer = pdk.Layer(
        "ScatterplotLayer",
        data=map_data,

        get_position=[
            "lon",
            "lat",
        ],

        get_radius="radius",

        get_fill_color=(
            "fill_color"
        ),

        get_line_color=[
            255,
            255,
            255,
            240,
        ],

        stroked=True,
        filled=True,

        line_width_min_pixels=1.5,

        radius_min_pixels=6,
        radius_max_pixels=36,

        pickable=True,
        auto_highlight=True,

        highlight_color=[
            255,
            215,
            0,
            230,
        ],
    )

    # -----------------------------------------------------
    # TOOLTIP
    # -----------------------------------------------------

    tooltip = {
        "html": (
            "<div style='font-size:14px;'>"
            "<b style='font-size:16px;'>"
            "{district}"
            "</b>"
            "<br/>"
            "{province} Province"
            "<br/><br/>"
            "<b>{records}</b> licensing records"
            "</div>"
        ),
        "style": {
            "backgroundColor": "#17191f",
            "color": "white",
            "border": (
                "1px solid #ff5252"
            ),
        },
    }

    # -----------------------------------------------------
    # DECK
    # -----------------------------------------------------

    deck = pdk.Deck(
        layers=[
            province_layer,
            country_layer,
            district_layer,
        ],
        initial_view_state=(
            map_view_state(
                map_data
            )
        ),
        tooltip=tooltip,
        map_style=None,
    )

    st.pydeck_chart(
        deck,
        use_container_width=True,
    )

    # -----------------------------------------------------
    # NOTES
    # -----------------------------------------------------

    st.caption(
        "Coral circles show district-level licensing "
        "activity. Blue-grey lines show provincial "
        "boundaries and the bright outer line shows "
        "Zambia's national border. Licence locations "
        "remain aggregated to district centroids."
    )

    st.caption(
        "District centroid coordinates: Open Admin Data "
        "Zambia. Boundary geometry: geoBoundaries."
    )

    # -----------------------------------------------------
    # MAP DATA TABLE
    # -----------------------------------------------------

    with st.expander(
        "District map data",
        expanded=False,
    ):

        display_data = (
            map_data[
                [
                    "district",
                    "province",
                    "records",
                ]
            ]
            .rename(
                columns={
                    "district":
                        "District",

                    "province":
                        "Province",

                    "records":
                        "Records",
                }
            )
        )

        st.dataframe(
            display_data,
            use_container_width=True,
            hide_index=True,
        )