from app.router import search_mine
from app.evidence import normalize_evidence
from app.rag import answer_from_evidence


def test_large_scale_mining_fee_uses_authoritative_source():

    query = (
        "what is the large-scale "
        "mining licence fee?"
    )

    result = search_mine(
        query=query,
        top_k=5,
    )

    assert (
        result["route"]
        == "documents"
    )

    assert (
        result[
            "preferred_source_ids"
        ]
        == [
            "mining_fees_area_charges_2024"
        ]
    )

    evidence = normalize_evidence(
        search_result=result,
        max_evidence=5,
    )

    answer = answer_from_evidence(
        question=query,
        evidence=evidence,
    )

    assert (
        answer[
            "generation_method"
        ]
        == "deterministic-fee"
    )

    assert (
        answer[
            "model"
        ]
        is None
    )

    assert (
        "K64,000"
        in answer[
            "answer"
        ]
    )

    assert (
        answer[
            "sources"
        ]
    )

    assert any(
        source.get(
            "canonical_source_id"
        )
        == "mining_fees_area_charges_2024"
        for source
        in answer[
            "sources"
        ]
    )
