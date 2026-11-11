from app.estimate_consistency import (
    extract_mingomba_capex,
    analyze_mingomba_capex,
    audit_mingomba_answer,
    draft_mingomba_comparison,
)


EVIDENCE = [
    {
        "source_id": "S1",
        "canonical_source_id": "country_compact_2026",
        "document": "country_compact.pdf",
        "pages": "8",
        "text": (
            "KoBold Metals' Mingomba property "
            "(with an expected CapEx of $2 billion) "
            "to produce 300,000 tpa."
        ),
    },
    {
        "source_id": "S2",
        "canonical_source_id": "country_compact_2026",
        "document": "country_compact.pdf",
        "pages": "25-26",
        "text": (
            "Mingomba Copper KoBold Metals AI-driven "
            "exploration; 300ktpa production potential "
            ">$2.0B Enterprise Nickel Greenfield "
            "development $100M"
        ),
    },
]


def test_extracts_both_estimates():
    estimates = extract_mingomba_capex(EVIDENCE)

    assert len(estimates) == 2
    assert estimates[0]["amount_usd"] == 2_000_000_000
    assert estimates[1]["amount_usd"] == 2_000_000_000
    assert estimates[0]["operator"] == "reported"
    assert estimates[1]["operator"] == ">"
    assert estimates[0]["pages"] == "8"
    assert estimates[1]["pages"] == "25-26"


def test_classifies_qualifier_difference():
    result = analyze_mingomba_capex(EVIDENCE)

    assert result["status"] == "qualifier_difference"
    assert result["distinct_documents"] == 1
    assert result["requires_comparison"]


def test_detects_omitted_source():
    result = audit_mingomba_answer(
        EVIDENCE,
        "Mingomba CapEx is >$2.0B [S2].",
    )

    assert result["complete_comparison"] is False
    assert result["missing_source_ids"] == ["S1"]


def test_accepts_both_sources():
    result = audit_mingomba_answer(
        EVIDENCE,
        "Expected $2 billion [S1]; table lists >$2.0B [S2].",
    )

    assert result["complete_comparison"] is True
    assert result["missing_source_ids"] == []


def test_drafts_source_grounded_comparison():
    answer = draft_mingomba_comparison(EVIDENCE)

    assert "$2 billion [S1]" in answer
    assert ">$2.0B [S2]" in answer
    assert "same document" in answer
    assert "confirmed final cost" in answer


def test_no_adjacent_project_contamination():
    evidence = [{
        "source_id": "S1",
        "document": "country_compact.pdf",
        "text": (
            "Mingomba Copper KoBold Metals "
            "production potential TBD "
            "Enterprise Nickel development $100M"
        ),
    }]

    assert extract_mingomba_capex(evidence) == []


def test_single_estimate_needs_no_comparison():
    result = analyze_mingomba_capex(EVIDENCE[:1])

    assert result["status"] == "single_estimate"
    assert not result["requires_comparison"]


def test_matching_estimates_are_consistent():
    duplicated = [
        dict(EVIDENCE[0]),
        dict(EVIDENCE[0], source_id="S3"),
    ]

    result = analyze_mingomba_capex(duplicated)

    assert result["status"] == "consistent"
    assert not result["requires_comparison"]
