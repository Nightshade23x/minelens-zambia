from app import router

from app.mining_statistics import (
    answer_statistics_result,
)


def sample_statistics_records() -> list[dict]:

    common = {
        "dataset_id":
            "world_mining_data_2026",

        "dataset_title":
            "World Mining Data 2026",

        "agency":
            "Austrian Federal Ministry of Finance",

        "record_type":
            "mineral_production",

        "commodity":
            "Copper",

        "country":
            "Zambia",

        "unit":
            "metr. t",

        "data_quality":
            "reported",

        "source_url":
            "https://example.com/wmd",
    }


    return [
        {
            **common,
            "year": 2020,
            "production": 882061.0,
            "rank_2024": None,
            "world_share_percent": None,
        },
        {
            **common,
            "year": 2021,
            "production": 830357.0,
            "rank_2024": None,
            "world_share_percent": None,
        },
        {
            **common,
            "year": 2022,
            "production": 795141.0,
            "rank_2024": None,
            "world_share_percent": None,
        },
        {
            **common,
            "year": 2023,
            "production": 732583.0,
            "rank_2024": None,
            "world_share_percent": None,
        },
        {
            **common,
            "year": 2024,
            "production": 822824.0,
            "rank_2024": 8,
            "world_share_percent": (
                3.591370051562242
            ),
        },
    ]


def test_statistics_query_routes_to_structured_engine(
    monkeypatch,
) -> None:

    records = (
        sample_statistics_records()
    )

    monkeypatch.setattr(
        router,
        "load_mining_statistics",
        lambda: records,
    )


    result = router.route_query(
        "How much copper did "
        "Zambia produce in 2024?"
    )


    assert (
        result["route"]
        == router.ROUTE_MINING_STATISTICS
    )


def test_statistics_answer_is_deterministic() -> None:

    result = {
        "route":
            "mining_statistics",

        "statistics_intent":
            "production",

        "commodity":
            "Copper",

        "countries":
            ["Zambia"],

        "years":
            [2024],

        "results":
            [
                sample_statistics_records()[
                    -1
                ]
            ],
    }


    answer = (
        answer_statistics_result(
            result
        )
    )


    assert (
        "822,824 metric tonnes"
        in answer["answer"]
    )

    assert (
        answer[
            "generation_method"
        ]
        == "structured-statistics"
    )

    assert (
        answer["model"]
        is None
    )


def test_statistics_trend_answer() -> None:

    result = {
        "route":
            "mining_statistics",

        "statistics_intent":
            "trend",

        "commodity":
            "Copper",

        "countries":
            ["Zambia"],

        "years":
            [2020, 2024],

        "results":
            sample_statistics_records(),
    }


    answer = (
        answer_statistics_result(
            result
        )
    )


    assert (
        "882,061"
        in answer["answer"]
    )

    assert (
        "822,824"
        in answer["answer"]
    )

    assert (
        "59,237"
        in answer["answer"]
    )

    assert (
        "6.72%"
        in answer["answer"]
    )


def test_requirement_query_prefers_requirement_sources() -> None:

    chunks = [
        {
            "source_id":
                "mining_rights_requirements",
        },
        {
            "source_id":
                "application_for_mining_right",
        },
        {
            "source_id":
                (
                    "national_mineral_resources_"
                    "development_policy_2022"
                ),
        },
    ]


    selected = (
        router.preferred_document_source_ids(
            query=(
                "What are the requirements "
                "for a large-scale mining licence?"
            ),
            chunks=chunks,
        )
    )


    assert selected == {
        "mining_rights_requirements",
        "application_for_mining_right",
    }


def test_policy_requirement_query_is_not_forced() -> None:

    chunks = [
        {
            "source_id":
                "mining_rights_requirements",
        },
    ]


    selected = (
        router.preferred_document_source_ids(
            query=(
                "What are Zambia's local "
                "content requirements?"
            ),
            chunks=chunks,
        )
    )


    assert selected == set()