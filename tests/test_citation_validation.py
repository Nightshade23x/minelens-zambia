import pytest

from app.citation_validation import validate_citation_integrity


@pytest.mark.parametrize(
    "answer,citations,source_ids,valid",
    [
        (
            "Kansanshi is operated by Kansanshi Mining plc. [S1]",
            ["S1"], ["S1"], True,
        ),
        (
            "Mingomba has two estimates. [S2] [S1]",
            ["S2", "S1"], ["S1", "S2"], True,
        ),
        (
            "No matching records were found.",
            [], [], True,
        ),
        (
            "The production was 100 tonnes. [S3]",
            ["S3"], ["S1"], False,
        ),
        (
            "The production was 100 tonnes. [S2]",
            ["S1"], ["S1"], False,
        ),
        (
            "The production was 100 tonnes. [S1]",
            ["S1"], [], False,
        ),
        (
            "The production was 100 tonnes. [S1]",
            ["S1"], ["S1", "S1"], False,
        ),
        (
            "The production was 100 tonnes. [S0]",
            ["S0"], ["S0"], False,
        ),
        (
            "The production was 100 tonnes. [S1]",
            [], ["S1"], False,
        ),
    ],
)
def test_citation_integrity(
    answer, citations, source_ids, valid
):
    result = validate_citation_integrity({
        "answer": answer,
        "citations": citations,
        "sources": [
            {"source_id": source_id}
            for source_id in source_ids
        ],
    })

    assert result["valid"] is valid, result


def test_citation_integrity_reports_missing_source():
    result = validate_citation_integrity({
        "answer": "A claim. [S2]",
        "citations": ["S2"],
        "sources": [{"source_id": "S1"}],
    })

    assert not result["valid"]
    assert any(
        "without source metadata" in issue
        for issue in result["issues"]
    )
