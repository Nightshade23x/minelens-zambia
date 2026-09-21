from __future__ import annotations

from frontend.utils.display import clean_text


# Province labels currently present in the MineLens
# structured licensing dataset.
PROVINCE_NAMES = {
    "Central",
    "Copperbelt",
    "Eastern",
    "Luapula",
    "Lusaka",
    "North Western",
    "Northern",
    "Southern",
    "Western",
}
DISTRICT_ALIASES = {
    "KapiriMposhi": "Kapiri Mposhi",
    "Itezhi Tezhi": "Itezhi-Tezhi",
}

# Known formatting aliases observed in the source data.



def normalize_district_name(
    value: str,
) -> str:
    """
    Normalize a raw district value for spatial analysis.

    Examples:
        "Chama; Northern" -> "Chama"
        "Mumbwa;North Western" -> "Mumbwa"
        "KapiriMposhi" -> "Kapiri Mposhi"

    Province-only values are discarded.
    """

    value = clean_text(
        value
    )

    if not value:
        return ""

    # Some source rows combine a district and province
    # using a semicolon.
    parts = [
        clean_text(part)
        for part in value.split(";")
        if clean_text(part)
    ]

    if not parts:
        return ""

    district = parts[0]

    # A value containing only a province is not a district.
    if district in PROVINCE_NAMES:
        return ""

    district = DISTRICT_ALIASES.get(
        district,
        district,
    )

    return district


def normalized_districts(
    record: dict,
) -> list[str]:
    """
    Return unique normalized districts for one
    licensing record.
    """

    raw_value = record.get(
        "districts",
        [],
    )

    if raw_value is None:
        return []

    if not isinstance(
        raw_value,
        list,
    ):
        raw_value = [
            raw_value
        ]

    districts: list[str] = []

    for value in raw_value:

        district = normalize_district_name(
            str(value)
        )

        if (
            district
            and district not in districts
        ):
            districts.append(
                district
            )

    return districts