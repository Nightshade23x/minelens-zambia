from app.answer_reliability import audit_answer_reliability


QUESTION = (
    "What is the estimated capital expenditure for Lumwana?"
)


def source(source_id, text, document="compact"):
    return {
        "source_id": source_id,
        "canonical_source_id": document,
        "document": document + ".pdf",
        "pages": "8",
        "text": text,
    }


def answer(text, citations):
    return {
        "answer": text,
        "citations": citations,
    }


def test_consistent_estimates_pass():
    evidence = [
        source("S1", "Lumwana mine estimated at $2 billion."),
        source(
            "S2",
            "Lumwana mine expansion cost $2 billion.",
            "usgs",
        ),
    ]

    result = audit_answer_reliability(
        QUESTION,
        evidence,
        answer(
            "Lumwana expansion is $2 billion [S1] [S2].",
            ["S1", "S2"],
        ),
    )

    assert result["ok"]
    assert result["cited_document_count"] == 2


def test_distinct_estimate_omission_detected():
    evidence = [
        source("S1", "Lumwana mine CapEx $2 billion."),
        source(
            "S2",
            "Lumwana mine CapEx $3 billion.",
            "other",
        ),
    ]

    result = audit_answer_reliability(
        QUESTION,
        evidence,
        answer("Lumwana CapEx is $2 billion [S1].", ["S1"]),
    )

    assert not result["ok"]
    assert "answer_omits_distinct_estimate" in result["warnings"]
    assert result["missing_amounts_usd"] == [3_000_000_000]


def test_both_different_estimates_are_disclosed():
    evidence = [
        source("S1", "Lumwana mine CapEx $2 billion."),
        source(
            "S2",
            "Lumwana mine CapEx $3 billion.",
            "other",
        ),
    ]

    result = audit_answer_reliability(
        QUESTION,
        evidence,
        answer(
            "The retrieved figures are $2 billion [S1] "
            "and $3 billion [S2].",
            ["S1", "S2"],
        ),
    )

    assert result["ok"]
    assert result["estimate_status"] == "different_values"


def test_mingomba_inequality_is_preserved():
    evidence = [
        source("S1", "Mingomba mine expected CapEx $2 billion."),
        source(
            "S2",
            "Mingomba Copper KoBold Metals "
            "production potential >$2.0B",
        ),
    ]

    result = audit_answer_reliability(
        "What is the estimated CapEx for Mingomba?",
        evidence,
        answer(
            "Mingomba has an expected $2 billion [S1] "
            "and >$2.0B [S2].",
            ["S1", "S2"],
        ),
    )

    assert result["ok"]


def test_missing_inequality_is_detected():
    evidence = [
        source(
            "S1",
            "Mingomba mine production potential >$2.0B.",
        ),
    ]

    result = audit_answer_reliability(
        "What is the estimated CapEx for Mingomba?",
        evidence,
        answer("Mingomba costs $2 billion [S1].", ["S1"]),
    )

    assert "answer_omits_estimate_inequality" in result["warnings"]


def test_same_document_not_counted_twice():
    evidence = [
        source("S1", "Lumwana mine CapEx $2 billion."),
        source("S2", "Lumwana mine CapEx $2 billion."),
    ]

    result = audit_answer_reliability(
        QUESTION,
        evidence,
        answer("Lumwana costs $2 billion [S1] [S2].", ["S1", "S2"]),
    )

    assert result["cited_source_count"] == 2
    assert result["cited_document_count"] == 1


def test_false_independence_claim_detected():
    evidence = [
        source("S1", "Lumwana mine CapEx $2 billion."),
        source("S2", "Lumwana mine CapEx $2 billion."),
    ]

    result = audit_answer_reliability(
        QUESTION,
        evidence,
        answer(
            "Multiple independent sources confirm "
            "$2 billion for Lumwana [S1] [S2].",
            ["S1", "S2"],
        ),
    )

    assert "unsupported_independence_claim" in result["warnings"]


def test_unknown_source_citation_detected():
    evidence = [
        source("S1", "Lumwana mine CapEx $2 billion."),
    ]

    result = audit_answer_reliability(
        QUESTION,
        evidence,
        answer(
            "Lumwana costs $2 billion [S9].",
            ["S9"],
        ),
    )

    assert "citation_not_in_retrieved_evidence" in result["warnings"]


def test_unrelated_question_does_not_trigger_estimate_audit():
    result = audit_answer_reliability(
        "Who operates Kansanshi Mine?",
        [],
        answer("Kansanshi Mining plc.", []),
    )

    assert result["ok"]
    assert result["estimate_status"] == "not_applicable"


def test_false_consistency_claim_detected():
    evidence = [
        source("S1", "Lumwana mine CapEx $2 billion."),
        source(
            "S2",
            "Lumwana mine CapEx $3 billion.",
            "other",
        ),
    ]

    result = audit_answer_reliability(
        QUESTION,
        evidence,
        answer(
            "All estimates agree: $2 billion [S1] "
            "and $3 billion [S2].",
            ["S1", "S2"],
        ),
    )

    assert (
        "consistency_claim_with_different_figures"
        in result["warnings"]
    )
