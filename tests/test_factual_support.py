import pytest

from app.factual_support import validate_factual_support


FACILITY = {
    "route": "facilities",
    "results": [{
        "facility": {
            "facility_name": "Kansanshi Mine",
            "major_operating_companies": [
                "Kansanshi Mining plc"
            ],
        }
    }],
}

STATISTICS = {
    "route": "mining_statistics",
    "results": [{
        "country": "Zambia",
        "commodity": "Copper",
        "year": 2024,
        "production": 822824.0,
    }],
}

DOCUMENTS = {
    "route": "documents",
    "results": [{"record_type": "document"}],
}

EVIDENCE = [
    {
        "source_id": "S1",
        "text": (
            "KoBold Metals' Mingomba property "
            "(with an expected CapEx of $2 billion)."
        ),
    },
    {
        "source_id": "S2",
        "text": (
            "Mingomba Copper KoBold Metals "
            "AI-driven exploration; 300ktpa "
            "production potential >$2.0B "
            "Enterprise Nickel"
        ),
    },
]


@pytest.mark.parametrize(
    "answer,expected",
    [
        (
            "Kansanshi Mine is operated by "
            "Kansanshi Mining plc. [S1]",
            True,
        ),
        (
            "Kansanshi Mine is operated by "
            "Imaginary Mining Ltd. [S1]",
            False,
        ),
    ],
)
def test_facility_operator(answer, expected):
    result = validate_factual_support(
        "Who operates Kansanshi Mine?",
        FACILITY,
        {"answer": answer},
    )

    assert result["checked"]
    assert result["supported"] is expected


@pytest.mark.parametrize(
    "answer,expected",
    [
        (
            "Zambia produced 822,824 metric "
            "tonnes of copper in 2024. [S1]",
            True,
        ),
        (
            "Zambia produced 999,999 metric "
            "tonnes of copper in 2024. [S1]",
            False,
        ),
        (
            "Zambia produced 822,824 metric "
            "tonnes of copper in 2023. [S1]",
            False,
        ),
    ],
)
def test_production_claim(answer, expected):
    result = validate_factual_support(
        "What was Zambia's copper production in 2024?",
        STATISTICS,
        {"answer": answer},
    )

    assert result["checked"]
    assert result["supported"] is expected


@pytest.mark.parametrize(
    "answer,expected",
    [
        ("Mingomba's CapEx is $2 billion [S1].", True),
        ("Mingomba's CapEx is >$2.0B [S2].", True),
        ("Mingomba's CapEx is >$2.0B [S1].", False),
        ("Mingomba's CapEx is $2.0B [S2].", False),
        (
            "Mingomba's CapEx is >$2.0B [S2]. "
            "Another section gives $2 billion [S1].",
            True,
        ),
    ],
)
def test_mingomba_capex_comparisons(answer, expected):
    result = validate_factual_support(
        "What is Mingomba's estimated capital expenditure?",
        DOCUMENTS,
        {"answer": answer},
        evidence=EVIDENCE,
    )

    assert result["checked"]
    assert result["supported"] is expected


def test_no_evidence_is_not_claimed_as_verified():
    result = validate_factual_support(
        "What was Zambia's copper production in 2099?",
        {"route": "mining_statistics", "results": []},
        {"answer": "No matching records."},
    )

    assert result["checked"] is False
    assert result["supported"] is None


def test_rejects_extra_unsupported_production_amount():
    answer = (
        "Zambia produced 822,824 metric tonnes of copper in "
        "2024, not 999,999 metric tonnes. [S1]"
    )

    result = validate_factual_support(
        "What was Zambia's copper production in 2024?",
        STATISTICS,
        {"answer": answer},
    )

    assert result["checked"]
    assert result["supported"] is False


def test_rejects_uncited_additional_capex_amount():
    answer = (
        "Mingomba's CapEx is >$2.0B [S2]. "
        "A newer estimate is $9 billion."
    )

    result = validate_factual_support(
        "What is Mingomba's estimated capital expenditure?",
        DOCUMENTS,
        {"answer": answer},
        evidence=EVIDENCE,
    )

    assert result["checked"]
    assert result["supported"] is False


def test_rejects_only_uncited_capex_amount():
    result = validate_factual_support(
        "What is Mingomba's estimated capital expenditure?",
        DOCUMENTS,
        {"answer": "Mingomba's CapEx is $9 billion."},
        evidence=EVIDENCE,
    )

    assert result["checked"]
    assert result["supported"] is False


TREND_RECORDS = {
    "route": "mining_statistics",
    "statistics_intent": "trend",
    "results": [
        {
            "country": "Zambia",
            "commodity": "Copper",
            "year": 2023,
            "production": 732583.0,
            "unit": "metr. t",
        },
        {
            "country": "Zambia",
            "commodity": "Copper",
            "year": 2024,
            "production": 822824.0,
            "unit": "metr. t",
        },
    ],
}

GOLD_RECORDS = {
    "route": "mining_statistics",
    "results": [{
        "country": "Zambia",
        "commodity": "Gold",
        "year": 2024,
        "production": 3269.0,
        "unit": "kg",
    }],
}

TREND_ANSWER = (
    "Zambia's copper production increased from "
    "**732,583 metric tonnes in 2023** to "
    "**822,824 metric tonnes in2024**. "
    "The overall change was "
    "**90,241 metric tonnes (12.32%)**. [S1]"
)


@pytest.mark.parametrize(
    "answer,expected",
    [
        (TREND_ANSWER, True),
        (
            TREND_ANSWER.replace("90,241", "90,999"),
            False,
        ),
        (
            TREND_ANSWER.replace("12.32%", "45.00%"),
            False,
        ),
        (
            TREND_ANSWER.replace(
                "732,583 metric tonnes in 2023",
                "732,583 metric tonnes in 2024",
            ),
            False,
        ),
    ],
)
def test_copper_trend_claims(answer, expected):
    result = validate_factual_support(
        "How did Zambia's copper production change "
        "from 2023 to 2024?",
        TREND_RECORDS,
        {"answer": answer},
    )

    assert result["checked"]
    assert result["supported"] is expected, result


@pytest.mark.parametrize(
    "answer,expected",
    [
        (
            "Zambia produced 3,269 kg of gold in 2024. [S1]",
            True,
        ),
        (
            "Zambia produced 9,999 kg of gold in 2024. [S1]",
            False,
        ),
        (
            "Zambia produced 3,269 metric tonnes "
            "of gold in 2024. [S1]",
            False,
        ),
        (
            "Zambia produced 3,269 kg of gold in 2023. [S1]",
            False,
        ),
    ],
)
def test_gold_production_units(answer, expected):
    result = validate_factual_support(
        "What was Zambia's gold production in 2024?",
        GOLD_RECORDS,
        {"answer": answer},
    )

    assert result["checked"]
    assert result["supported"] is expected, result
