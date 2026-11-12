import pytest

from app.fee_support import (
    extract_application_fee_rows,
    validate_fee_support,
)


EVIDENCE = [{
    "source_id": "S2",
    "document": "mining_fees_2024.pdf",
    "pages": "1-2",
    "text": (
        "MINISTRY OF MINES AND MINERALS DEVELOPMENT "
        "PRESCRIBED FEES, AREA CHARGES AND MAXIMUM AREAS "
        "FEES TYPE OF MINING RIGHT OR APPLICATION "
        "FEE UNITS AMOUNT (K) "
        "(1) Exploration License "
        "(a) Small-scale (b) Large-scale "
        "3000 10000 1,200.00 4,000.00 "
        "(2) Mining License "
        "(a) Artisanal (b) Small-scale (c) Large-scale "
        "3000 15000 160000 "
        "1,200.00 6,000.00 64,000.00 "
        "(3) Transfer of Exploration License "
        "(a) Small-scale (b) Large-scale "
        "15000 160000 6,000.00 64,000.00"
    ),
}]


def result(text, citations=None):
    return {
        "answer": text,
        "citations": ["S2"] if citations is None else citations,
    }


CASES = [
    (
        "large scale mining licence application cost",
        "The prescribed application fee for a "
        "large-scale mining licence is K64,000. [S2]",
        64_000,
    ),
    (
        "large scale exploration licence application cost",
        "The prescribed application fee for a "
        "large-scale exploration licence is K4,000. [S2]",
        4_000,
    ),
    (
        "small scale mining licence application fee",
        "The prescribed application fee for a "
        "small-scale mining licence is K6,000. [S2]",
        6_000,
    ),
]


@pytest.mark.parametrize("question,answer,amount", CASES)
def test_correct_fee_supported(question, answer, amount):
    audit = validate_fee_support(
        question,
        EVIDENCE,
        result(answer),
    )

    assert audit["checked"]
    assert audit["supported"] is True, audit
    assert audit["expected_amount_kwacha"] == amount


def test_extracts_correct_table_rows():
    rows = extract_application_fee_rows(EVIDENCE)

    lookup = {
        (row["category"], row["scale"]):
        row["amount_kwacha"]
        for row in rows
    }

    assert lookup[("mining", "large")] == 64_000
    assert lookup[("mining", "small")] == 6_000
    assert lookup[("exploration", "large")] == 4_000
    assert len(rows) == 5


def test_fee_units_not_confused_with_kwacha():
    audit = validate_fee_support(
        CASES[0][0],
        EVIDENCE,
        result(
            "The application fee for a large-scale "
            "mining licence is K160,000. [S2]"
        ),
    )

    assert audit["supported"] is False
    assert "fee_amount_mismatch" in audit["issues"]


def test_wrong_licence_category_rejected():
    audit = validate_fee_support(
        CASES[0][0],
        EVIDENCE,
        result(
            "The application fee for a small-scale "
            "mining licence is K64,000. [S2]"
        ),
    )

    assert audit["supported"] is False
    assert "fee_category_mismatch" in audit["issues"]


def test_wrong_amount_rejected():
    audit = validate_fee_support(
        CASES[1][0],
        EVIDENCE,
        result(
            "The application fee for a large-scale "
            "exploration licence is K64,000. [S2]"
        ),
    )

    assert audit["supported"] is False


def test_unsupported_citation_rejected():
    audit = validate_fee_support(
        CASES[2][0],
        EVIDENCE,
        result(CASES[2][1], citations=["S9"]),
    )

    assert audit["supported"] is False
    assert "fee_citation_mismatch" in audit["issues"]


def test_transfer_question_not_checked_as_application():
    audit = validate_fee_support(
        "What is the transfer fee for a large-scale "
        "mining licence application?",
        EVIDENCE,
        result(CASES[0][1]),
    )

    assert audit["checked"] is False


def test_no_schedule_does_not_verify_fee():
    audit = validate_fee_support(
        CASES[0][0],
        [{
            "source_id": "S1",
            "text": "Mining area charges per hectare.",
        }],
        result(CASES[0][1]),
    )

    assert audit["checked"] is False
