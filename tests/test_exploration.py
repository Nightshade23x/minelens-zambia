from app.exploration_search import (
    filter_intersections,
    query_exploration,
)
from app.router import route_query


def test_highest_intersection():
    result = query_exploration(
        (
            "which Kabwe hole has the "
            "highest zinc intersection?"
        ),
        top_k=1,
    )

    record = result[
        "results"
    ][0]

    assert (
        result["intent"]
        == "highest_intersection"
    )

    assert (
        record["hole_id"]
        == "KBDD10"
    )

    assert (
        record["zinc_pct"]
        == 36.4
    )

    assert (
        record["width_m"]
        == 1.2
    )


def test_highest_individual_assay():
    result = query_exploration(
        (
            "what is the highest "
            "individual zinc assay?"
        ),
        top_k=1,
    )

    record = result[
        "results"
    ][0]

    assert (
        record["hole_id"]
        == "KBDD11"
    )

    assert (
        record["maximum_assay_pct"]
        == 49.7
    )


def test_no_reportable_intersection():
    result = query_exploration(
        (
            "which holes had no "
            "reportable intersections?"
        )
    )

    assert [
        record["hole_id"]
        for record in result[
            "results"
        ]
    ] == [
        "KBDD07"
    ]


def test_strict_zinc_threshold():
    records = [
        {
            "hole_id": "TEST01",
            "status": "reportable_intersection",
            "zinc_pct": 10.0,
            "width_m": 1.0,
        },
        {
            "hole_id": "TEST02",
            "status": "reportable_intersection",
            "zinc_pct": 10.1,
            "width_m": 1.0,
        },
    ]

    result = filter_intersections(
        records,
        zinc_min=10.0,
        zinc_operator="gt",
    )

    assert [
        record["zinc_pct"]
        for record in result
    ] == [
        10.1
    ]


def test_at_least_zinc_threshold():
    records = [
        {
            "hole_id": "TEST01",
            "status": "reportable_intersection",
            "zinc_pct": 10.0,
            "width_m": 1.0,
        },
        {
            "hole_id": "TEST02",
            "status": "reportable_intersection",
            "zinc_pct": 10.1,
            "width_m": 1.0,
        },
    ]

    result = filter_intersections(
        records,
        zinc_min=10.0,
        zinc_operator="gte",
    )

    assert [
        record["zinc_pct"]
        for record in result
    ] == [
        10.0,
        10.1,
    ]


def test_exploration_routing():
    assert (
        route_query(
            (
                "which Kabwe hole has the "
                "highest zinc intersection?"
            )
        )[
            "route"
        ]
        == "exploration"
    )

    assert (
        route_query(
            (
                "approved exploration "
                "licences in Solwezi"
            )
        )[
            "route"
        ]
        == "licensing"
    )

    assert (
        route_query(
            (
                "what are the requirements "
                "for an exploration licence?"
            )
        )[
            "route"
        ]
        == "documents"
    )
