from __future__ import annotations

from app.licensing_search import (
    filter_records,
    infer_commodity,
    infer_decision,
    infer_licence_code,
    infer_licence_types,
    infer_location,
    search_licensing_records,
)

from ingestion.parse_licensing_results import (
    build_search_text,
    extract_licensing_records,
)


# ---------------------------------------------------------
# Sample structured records
# ---------------------------------------------------------

SAMPLE_RECORDS = [
    {
        "licence_code": "42553-HQ-LML",
        "licence_type_code": "LML",
        "licence_type": (
            "Large-Scale Mining Licence"
        ),
        "applicant": (
            "Nisco Industries Ltd"
        ),
        "commodities": [
            "Au",
            "Cu",
        ],
        "commodities_text": (
            "Au, Cu"
        ),
        "area_hectares": 9541.1303,
        "area_text": (
            "9,541.1303 ha"
        ),
        "location": (
            "North Western, Solwezi"
        ),
        "province": (
            "North Western"
        ),
        "districts": [
            "Solwezi",
        ],
        "decision": (
            "Approved"
        ),
        "deadline": (
            "25th September 2026"
        ),
        "deadline_iso": (
            "2026-09-25"
        ),
    },
    {
        "licence_code": "43108-HQ-LEL",
        "licence_type_code": "LEL",
        "licence_type": (
            "Large-Scale Exploration Licence"
        ),
        "applicant": (
            "Newtel Zambia Limited"
        ),
        "commodities": [
            "Au",
            "Cu",
        ],
        "commodities_text": (
            "Au, Cu"
        ),
        "area_hectares": 4153.59,
        "area_text": (
            "4,153.5900 ha"
        ),
        "location": (
            "North Western, Solwezi"
        ),
        "province": (
            "North Western"
        ),
        "districts": [
            "Solwezi",
        ],
        "decision": (
            "Rejected"
        ),
        "deadline": (
            "25th September 2026"
        ),
        "deadline_iso": (
            "2026-09-25"
        ),
    },
    {
        "licence_code": "40280-HQ-SEL",
        "licence_type_code": "SEL",
        "licence_type": (
            "Small-Scale Exploration Licence"
        ),
        "applicant": (
            "Evonse Investments Limited"
        ),
        "commodities": [
            "Au",
            "Co",
            "Ni",
        ],
        "commodities_text": (
            "Au, Co, Ni"
        ),
        "area_hectares": 972.16,
        "area_text": (
            "972.1600 ha"
        ),
        "location": (
            "Central, Mkushi"
        ),
        "province": (
            "Central"
        ),
        "districts": [
            "Mkushi",
        ],
        "decision": (
            "Rejected"
        ),
        "deadline": (
            "25th September 2026"
        ),
        "deadline_iso": (
            "2026-09-25"
        ),
    },
    {
        "licence_code": "43020-HQ-AMR",
        "licence_type_code": "AMR",
        "licence_type": (
            "Artisanal Mining Right"
        ),
        "applicant": (
            "Sample Applicant"
        ),
        "commodities": [
            "Cu",
        ],
        "commodities_text": (
            "Cu"
        ),
        "area_hectares": 6.68,
        "area_text": (
            "6.6800 ha"
        ),
        "location": (
            "North Western, Solwezi"
        ),
        "province": (
            "North Western"
        ),
        "districts": [
            "Solwezi",
        ],
        "decision": (
            "Approved"
        ),
        "deadline": (
            "25th September 2026"
        ),
        "deadline_iso": (
            "2026-09-25"
        ),
    },
]


# ---------------------------------------------------------
# Licence-type inference
# ---------------------------------------------------------

def test_infers_large_scale_mining() -> None:

    result = infer_licence_types(
        "large scale mining licences"
    )

    assert result == {
        "LML"
    }


def test_infers_small_scale_exploration() -> None:

    result = infer_licence_types(
        "small scale exploration licences"
    )

    assert result == {
        "SEL"
    }


def test_generic_exploration_infers_family() -> None:

    result = infer_licence_types(
        "which exploration licences "
        "were rejected"
    )

    assert result == {
        "LEL",
        "SEL",
    }


def test_generic_mining_infers_family() -> None:

    result = infer_licence_types(
        "approved mining licences"
    )

    assert result == {
        "LML",
        "SML",
    }


def test_infers_artisanal_type() -> None:

    result = infer_licence_types(
        "artisanal mining rights"
    )

    assert result == {
        "AMR"
    }


# ---------------------------------------------------------
# Other query inference
# ---------------------------------------------------------

def test_infers_decision() -> None:

    assert (
        infer_decision(
            "which licences were rejected"
        )
        == "Rejected"
    )


def test_infers_copper() -> None:

    assert (
        infer_commodity(
            "approved copper licences"
        )
        == "Cu"
    )


def test_infers_exact_licence_code() -> None:

    assert (
        infer_licence_code(
            "tell me about 42553-HQ-LML"
        )
        == "42553-HQ-LML"
    )


def test_infers_district() -> None:

    province, district = (
        infer_location(
            query=(
                "approved licences in Solwezi"
            ),
            records=SAMPLE_RECORDS,
        )
    )

    assert district == "Solwezi"

    assert province is None


# ---------------------------------------------------------
# Structured filtering
# ---------------------------------------------------------

def test_filters_large_scale_approved_solwezi() -> None:

    results = filter_records(
        records=SAMPLE_RECORDS,
        licence_types={
            "LML",
        },
        decision="Approved",
        district="Solwezi",
    )

    assert len(
        results
    ) == 1

    assert (
        results[0][
            "licence_code"
        ]
        == "42553-HQ-LML"
    )


def test_exploration_family_excludes_mining() -> None:

    results = filter_records(
        records=SAMPLE_RECORDS,
        licence_types={
            "LEL",
            "SEL",
        },
        decision="Rejected",
    )

    codes = {
        record[
            "licence_code"
        ]
        for record in results
    }

    assert codes == {
        "43108-HQ-LEL",
        "40280-HQ-SEL",
    }


def test_commodity_filter_uses_exact_code() -> None:

    results = filter_records(
        records=SAMPLE_RECORDS,
        commodity="Cu",
        district="Solwezi",
    )

    codes = {
        record[
            "licence_code"
        ]
        for record in results
    }

    assert codes == {
        "42553-HQ-LML",
        "43108-HQ-LEL",
        "43020-HQ-AMR",
    }


# ---------------------------------------------------------
# Natural-language structured search
# ---------------------------------------------------------

def test_search_applies_all_solwezi_filters() -> None:

    results, filters = (
        search_licensing_records(
            query=(
                "large scale mining licences "
                "approved in Solwezi"
            ),
            records=SAMPLE_RECORDS,
            top_k=10,
        )
    )

    assert filters[
        "licence_types"
    ] == {
        "LML"
    }

    assert (
        filters[
            "decision"
        ]
        == "Approved"
    )

    assert (
        filters[
            "district"
        ]
        == "Solwezi"
    )

    assert len(
        results
    ) == 1

    assert (
        results[0][
            "chunk"
        ][
            "licence_code"
        ]
        == "42553-HQ-LML"
    )


def test_search_generic_exploration_family() -> None:

    results, filters = (
        search_licensing_records(
            query=(
                "which exploration licences "
                "were rejected"
            ),
            records=SAMPLE_RECORDS,
            top_k=10,
        )
    )

    assert filters[
        "licence_types"
    ] == {
        "LEL",
        "SEL",
    }

    codes = {
        result[
            "chunk"
        ][
            "licence_code"
        ]
        for result in results
    }

    assert codes == {
        "43108-HQ-LEL",
        "40280-HQ-SEL",
    }


def test_exact_code_lookup() -> None:

    results, filters = (
        search_licensing_records(
            query=(
                "42553-HQ-LML"
            ),
            records=SAMPLE_RECORDS,
            top_k=10,
        )
    )

    assert (
        filters[
            "licence_code"
        ]
        == "42553-HQ-LML"
    )

    assert len(
        results
    ) == 1

    assert (
        results[0][
            "chunk"
        ][
            "applicant"
        ]
        == "Nisco Industries Ltd"
    )


# ---------------------------------------------------------
# Parser
# ---------------------------------------------------------

def test_parser_extracts_one_application_per_row() -> None:

    html = """
    <html>
        <body>
            <article>
                <h2>
                    LARGE-SCALE MINING LICENCE APPLICATIONS
                </h2>

                <table>
                    <tr>
                        <th>S/N</th>
                        <th>CODE</th>
                        <th>PARTIES</th>
                        <th>COMMODITIES</th>
                        <th>AREA</th>
                        <th>MAP REFERENCE</th>
                        <th>DECISION</th>
                        <th>TIMEFRAME</th>
                    </tr>

                    <tr>
                        <td>1</td>
                        <td>42553-HQ-LML</td>
                        <td>Nisco Industries Ltd</td>
                        <td>Au, Cu</td>
                        <td>9,541.1303 ha</td>
                        <td>North Western, Solwezi</td>
                        <td>Approved</td>
                        <td>25th September 2026</td>
                    </tr>
                </table>
            </article>
        </body>
    </html>
    """

    records = (
        extract_licensing_records(
            html
        )
    )

    assert len(
        records
    ) == 1

    record = records[
        0
    ]

    assert (
        record[
            "licence_code"
        ]
        == "42553-HQ-LML"
    )

    assert (
        record[
            "applicant"
        ]
        == "Nisco Industries Ltd"
    )

    assert (
        record[
            "area_hectares"
        ]
        == 9541.1303
    )

    assert (
        record[
            "province"
        ]
        == "North Western"
    )

    assert (
        record[
            "districts"
        ]
        == [
            "Solwezi",
        ]
    )

    assert (
        record[
            "decision"
        ]
        == "Approved"
    )

    assert (
        record[
            "deadline_iso"
        ]
        == "2026-09-25"
    )


def test_parser_search_text_keeps_fields_together() -> None:

    record = (
        SAMPLE_RECORDS[
            0
        ]
    )

    text = build_search_text(
        record
    )

    assert (
        "42553-HQ-LML"
        in text
    )

    assert (
        "Nisco Industries Ltd"
        in text
    )

    assert (
        "Solwezi"
        in text
    )

    assert (
        "Approved"
        in text
    )