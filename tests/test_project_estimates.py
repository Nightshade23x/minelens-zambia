import pytest

from app.project_estimates import (
    project_from_question,
    analyze_project_estimates,
    extract_project_estimates,
)


EVIDENCE = [
    {
        "source_id": "S1",
        "document": "country_compact.pdf",
        "canonical_source_id": "country_compact",
        "pages": "8",
        "text": (
            "Kansanshi mine (approximately $1.25 billion CapEx), "
            "Barrick's Lumwana mine (estimated at $2 billion CapEx), "
            "KoBold Metals' Mingomba property "
            "(with an expected CapEx of $2 billion)."
        ),
    },
    {
        "source_id": "S2",
        "document": "country_compact.pdf",
        "canonical_source_id": "country_compact",
        "pages": "25-26",
        "text": (
            "Kansanshi Copper First Quantum Minerals "
            "Expansion and mine life extension ~$1.25B "
            "Lumwana Copper Barrick Gold "
            "Expansion to 240ktpa ~$2.0B "
            "Mopani Copper Mopani Copper Mines "
            "Potential expansion TBD "
            "Konkola Copper Vedanta Resources "
            "Reinvestment ~$2.5B "
            "Mingomba Copper KoBold Metals "
            "AI-driven exploration; 300ktpa "
            "production potential >$2.0B "
            "Enterprise Nickel First Quantum Minerals "
            "Greenfield development ~$100M"
        ),
    },
]


@pytest.mark.parametrize(
    "question,expected",
    [
        ("What is the estimated CapEx for Mingomba?", "Mingomba"),
        (
            "How much is the Mingomba project expected to cost?",
            "Mingomba",
        ),
        (
            "What is the capital expenditure for Lumwana?",
            "Lumwana",
        ),
        (
            "What is the estimated CapEx for Kansanshi?",
            "Kansanshi",
        ),
    ],
)
def test_recognizes_project_question(question, expected):
    assert project_from_question(question) == expected


@pytest.mark.parametrize(
    "project,amount,status",
    [
        ("Mingomba", 2_000_000_000, "qualifier_difference"),
        ("Lumwana", 2_000_000_000, "qualifier_difference"),
        ("Kansanshi", 1_250_000_000, "consistent"),
    ],
)
def test_extracts_correct_project_values(project, amount, status):
    result = analyze_project_estimates(project, EVIDENCE)

    assert result["status"] == status, result
    assert result["distinct_documents"] == 1
    assert len(result["estimates"]) == 2

    assert all(
        item["amount_usd"] == amount
        for item in result["estimates"]
    )


def test_does_not_borrow_next_project_amount():
    assert extract_project_estimates("Mopani", EVIDENCE) == []


def test_does_not_use_other_project_cost():
    result = extract_project_estimates("Mingomba", EVIDENCE)

    assert all(
        item["amount_usd"] == 2_000_000_000
        for item in result
    )


def test_unknown_project_has_no_estimates():
    result = analyze_project_estimates(
        "ImaginaryMoonMine", EVIDENCE
    )

    assert result["status"] == "no_estimates"
    assert result["estimates"] == []


def test_barrick_gold_not_a_project_boundary():
    from app.project_estimates import NEXT_PROJECT_RE

    text = "Copper Barrick Gold Expansion to 240ktpa"

    assert NEXT_PROJECT_RE.search(text) is None


def test_next_project_boundary_still_detected():
    from app.project_estimates import NEXT_PROJECT_RE

    text = (
        "Mopani Copper Mopani Copper Mines "
        "Potential expansion"
    )

    assert NEXT_PROJECT_RE.search(text) is not None


def test_does_not_attribute_mopani_investment_to_lumwana():
    evidence = [{
        "source_id": "S3",
        "document": "usgs.html",
        "pages": "1",
        "text": (
            "Barrick Gold Corp. completed a feasibility "
            "study for a $2 billion expansion project "
            "at the Lumwana Mine to double copper output "
            "by 2028. Mopani Copper Mines plc secured "
            "a \\$1.1 billion investment plan to "
            "increase production at Nkana and Mufulira."
        ),
    }]

    lumwana = extract_project_estimates("Lumwana", evidence)

    assert lumwana == []


def test_mopani_still_gets_its_own_investment():
    evidence = [{
        "source_id": "S3",
        "document": "usgs.html",
        "pages": "1",
        "text": (
            "The Lumwana Mine expansion was discussed. "
            "Mopani Copper Mines plc secured a "
            "\\$1.1 billion investment plan to increase "
            "production at Nkana and Mufulira."
        ),
    }]

    mopani = extract_project_estimates("Mopani", evidence)

    assert len(mopani) == 1
    assert mopani[0]["amount_usd"] == 1_100_000_000
