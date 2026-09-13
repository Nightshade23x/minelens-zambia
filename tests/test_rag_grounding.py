from __future__ import annotations

import pytest

from app.rag import (
    answer_from_evidence,
    filter_sources_by_citations,
    generate_licensing_answer,
    infer_application_fee,
    validate_answer_grounding,
    validate_currency_language,
    validate_numeric_grounding,
    extract_critical_minerals,
    format_natural_list,
    generate_critical_minerals_answer,
    is_critical_minerals_list_query,
)


FEE_EVIDENCE = [
    {
        "source_id": "S1",
        "evidence_type": (
            "document"
        ),
        "title": (
            "Prescribed Application Fees "
            "and Area Charges 2024"
        ),
        "document": (
            "zambia_fees.pdf"
        ),
        "pages": "1-2",
        "source_url": (
            "https://example.com/fees"
        ),
        "text": (
            "PRESCRIBED FEES, AREA CHARGES "
            "AND MAXIMUM AREAS "
            "FEES TYPE OF MINING RIGHT OR "
            "APPLICATION FEE UNITS AMOUNT (K) "
            "(1) Exploration License "
            "(a) Small-scale "
            "(b) Large-scale "
            "3000 10000 "
            "1,200.00 4,000.00 "
            "(2) Mining License "
            "(a) Artisanal "
            "(b) Small-scale "
            "(c) Large-scale "
            "3000 15000 160000 "
            "1,200.00 6,000.00 64,000.00 "
            "Mineral Processing License "
            "160000 64,000.00"
        ),
    }
]


LICENSING_EVIDENCE = [
    {
        "source_id": "S1",
        "evidence_type": (
            "licensing_record"
        ),
        "title": (
            "42553-HQ-LML - "
            "Nisco Industries Ltd"
        ),
        "document": (
            "licensing_results.html"
        ),
        "pages": None,
        "source_url": (
            "https://example.com/licensing"
        ),
        "text": (
            "Licence code 42553-HQ-LML."
        ),
        "record": {
            "licence_code": (
                "42553-HQ-LML"
            ),
            "licence_type": (
                "Large-Scale Mining Licence"
            ),
            "licence_type_code": (
                "LML"
            ),
            "applicant": (
                "Nisco Industries Ltd"
            ),
            "decision": (
                "Approved"
            ),
            "province": (
                "North Western"
            ),
            "districts": [
                "Solwezi"
            ],
            "commodities": [
                "Au",
                "Cu",
            ],
            "area_hectares": (
                9541.1303
            ),
            "area_text": (
                "9,541.1303 ha"
            ),
            "deadline": (
                "25th September 2026"
            ),
            "deadline_iso": (
                "2026-09-25"
            ),
        },
    }
]


def test_large_scale_mining_fee_is_extracted() -> None:

    result = infer_application_fee(
        question=(
            "how much does a large scale "
            "mining licence application cost"
        ),
        evidence=FEE_EVIDENCE,
    )

    assert result is not None

    assert (
        result[
            "amount"
        ]
        == "K64,000"
    )

    assert (
        result[
            "source_id"
        ]
        == "S1"
    )


def test_fee_answer_is_deterministic() -> None:

    result = answer_from_evidence(
        question=(
            "how much does a large scale "
            "mining licence application cost"
        ),
        evidence=FEE_EVIDENCE,
    )

    assert (
        result[
            "generation_method"
        ]
        == "deterministic-fee"
    )

    assert (
        "K64,000"
        in result[
            "answer"
        ]
    )

    assert (
        "160,000"
        not in result[
            "answer"
        ]
    )

    assert (
        result[
            "model"
        ]
        is None
    )


def test_licensing_answer_is_deterministic() -> None:

    result = answer_from_evidence(
        question=(
            "42553-HQ-LML"
        ),
        evidence=(
            LICENSING_EVIDENCE
        ),
    )

    assert (
        result[
            "generation_method"
        ]
        == "deterministic-licensing"
    )

    assert (
        "Nisco Industries Ltd"
        in result[
            "answer"
        ]
    )

    assert (
        "Approved"
        in result[
            "answer"
        ]
    )

    assert (
        "9,541.1303 ha"
        in result[
            "answer"
        ]
    )

    assert (
        "25th September 2026"
        in result[
            "answer"
        ]
    )


def test_licensing_answer_does_not_reinterpret_deadline() -> None:

    result = (
        generate_licensing_answer(
            LICENSING_EVIDENCE
        )
    )

    answer = result[
        "answer"
    ].lower()

    assert (
        "stipulated timeframe"
        in answer
    )

    assert (
        "compliance deadline"
        not in answer
    )


def test_numeric_grounding_rejects_invented_number() -> None:

    with pytest.raises(
        RuntimeError
    ):

        validate_numeric_grounding(
            answer=(
                "Production was "
                "999999 tonnes [S1]."
            ),
            evidence=[
                {
                    "source_id": "S1",
                    "evidence_type": (
                        "document"
                    ),
                    "title": "Example",
                    "text": (
                        "Production was "
                        "500 tonnes."
                    ),
                }
            ],
        )


def test_currency_language_rejects_outside_knowledge() -> None:

    with pytest.raises(
        RuntimeError
    ):

        validate_currency_language(
            answer=(
                "The fee is K64,000 "
                "in Kiswahili currency "
                "[S1]."
            ),
            evidence=FEE_EVIDENCE,
        )


def test_grounded_answer_with_citation_passes() -> None:

    citations = (
        validate_answer_grounding(
            question=(
                "What year was it published?"
            ),
            answer=(
                "The document is from "
                "2024 [S1]."
            ),
            evidence=[
                {
                    "source_id": "S1",
                    "evidence_type": (
                        "document"
                    ),
                    "title": (
                        "Mining Strategy 2024"
                    ),
                    "text": (
                        "Mining Strategy 2024"
                    ),
                }
            ],
        )
    )

    assert citations == [
        "S1"
    ]


def test_sources_are_filtered_to_used_citations() -> None:

    evidence = [
        {
            "source_id": "S1",
            "title": "Source One",
            "document": "one.pdf",
            "pages": "1",
            "source_url": (
                "https://example.com/one"
            ),
        },
        {
            "source_id": "S2",
            "title": "Source Two",
            "document": "two.pdf",
            "pages": "2",
            "source_url": (
                "https://example.com/two"
            ),
        },
    ]

    sources = (
        filter_sources_by_citations(
            evidence=evidence,
            citations=[
                "S1"
            ],
        )
    )

    assert len(
        sources
    ) == 1

    assert (
        sources[
            0
        ][
            "source_id"
        ]
        == "S1"
    )

from app.rag import (
    repair_single_source_list_citation,
)


def test_list_answer_repairs_missing_single_source_citation() -> None:

    evidence = [
        {
            "source_id": "S1",
            "evidence_type": (
                "document"
            ),
            "title": (
                "Critical Minerals Strategy"
            ),
            "text": (
                "Critical minerals include "
                "Lithium, Tin and Graphite."
            ),
        }
    ]

    repaired = (
        repair_single_source_list_citation(
            question=(
                "what are Zambia's "
                "critical minerals"
            ),
            answer=(
                "Zambia's critical minerals "
                "include Lithium, Tin and "
                "Graphite."
            ),
            evidence=evidence,
        )
    )

    assert repaired.endswith(
        "[S1]"
    )


def test_non_list_answer_is_not_auto_cited() -> None:

    evidence = [
        {
            "source_id": "S1",
            "evidence_type": (
                "document"
            ),
            "title": "Example",
            "text": "Example evidence.",
        }
    ]

    answer = (
        "This is an uncited answer."
    )

    repaired = (
        repair_single_source_list_citation(
            question=(
                "how much does it cost"
            ),
            answer=answer,
            evidence=evidence,
        )
    )

    assert repaired == answer

def test_critical_minerals_question_detected() -> None:

    assert (
        is_critical_minerals_list_query(
            "what are Zambia's "
            "critical minerals"
        )
    )


def test_critical_minerals_are_extracted_completely() -> None:

    evidence = [
        {
            "source_id": "S1",
            "evidence_type": (
                "document"
            ),
            "title": (
                "National Critical "
                "Minerals Strategy"
            ),
            "text": (
                "2.1.2 Occurrence of Critical Minerals. "
                "Among the notable critical minerals "
                "in Zambia include: Lithium. "
                "Tin occurrences are reported. "
                "Graphite occurrences are widespread. "
                "Coltan (Columbite-Tantalum) occurs "
                "in Southern Province. "
                "Rare Earth Elements (REEs) occur "
                "in Muchinga Province. "
                "Manganese mineralization occurs "
                "in Zambia. "
                "Nickel deposits include Munali "
                "and Enterprise."
            ),
        }
    ]

    minerals, source_id = (
        extract_critical_minerals(
            evidence
        )
    )

    assert minerals == [
        "Lithium",
        "Tin",
        "Graphite",
        "Coltan (Columbite-Tantalum)",
        "Rare Earth Elements (REEs)",
        "Manganese",
        "Nickel",
    ]

    assert source_id == "S1"


def test_critical_minerals_answer_is_deterministic() -> None:

    evidence = [
        {
            "source_id": "S1",
            "evidence_type": (
                "document"
            ),
            "title": (
                "National Critical "
                "Minerals Strategy"
            ),
            "document": (
                "critical_strategy.pdf"
            ),
            "pages": "12-14",
            "source_url": (
                "https://example.com/"
                "strategy.pdf"
            ),
            "text": (
                "Occurrence of Critical Minerals. "
                "Among the notable critical minerals "
                "in Zambia include: Lithium. "
                "Tin occurrences are reported. "
                "Graphite occurrences are widespread. "
                "Coltan (Columbite-Tantalum). "
                "Rare Earth Elements (REEs). "
                "Manganese mineralization occurs. "
                "Nickel deposits are known."
            ),
        }
    ]

    result = (
        generate_critical_minerals_answer(
            question=(
                "what are Zambia's "
                "critical minerals"
            ),
            evidence=evidence,
        )
    )

    assert result is not None

    assert (
        result[
            "generation_method"
        ]
        == (
            "deterministic-"
            "critical-minerals"
        )
    )

    assert (
        "Nickel"
        in result[
            "answer"
        ]
    )

    assert (
        "Rare Earth Elements (REEs)"
        in result[
            "answer"
        ]
    )

    assert (
        "RareEarth"
        not in result[
            "answer"
        ]
    )

    assert (
        result[
            "model"
        ]
        is None
    )


def test_natural_list_formatting() -> None:

    result = format_natural_list(
        [
            "Lithium",
            "Tin",
            "Nickel",
        ]
    )

    assert result == (
        "Lithium, Tin, and Nickel"
    )

def test_licensing_decision_has_correct_spacing() -> None:

    result = (
        generate_licensing_answer(
            LICENSING_EVIDENCE
        )
    )

    assert (
        "decision is Approved."
        in result[
            "answer"
        ]
    )

    assert (
        "isApproved"
        not in result[
            "answer"
        ]
    )