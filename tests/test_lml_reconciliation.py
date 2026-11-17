from app.lml_source_scope import (
    is_lml_requirements_query,
    prioritize_lml_results,
    source_kinds,
    supplement_lml_answer,
)

FORM = {
    "source_id": "S1", "canonical_source_id": "application_for_mining_right",
    "text": "(b) Mining Licence - Large Scale Appendix No. 1 ... Approved Environmental Impact Statement ... Appendix No. 10",
}
COMPANY = {
    "source_id": "S2", "canonical_source_id": "application_for_mining_right",
    "text": "NOTE 1. An application for large-scale or small-scale mining shall only be made by a company.",
}
START = {
    "source_id": "S3", "canonical_source_id": "mining_rights_requirements",
    "text": "Mining Rights (Large Scale) Licence (LML) Duly completed Form I ... Feasibility Study ...",
}
CONTINUE = {
    "source_id": "S4", "canonical_source_id": "mining_rights_requirements",
    "text": "for Mining Operations. Approved Environmental Impact Statement. Detailed geographical report on the Area' Pegging Certificate. Statement of duration should not exceed 25 years. Mineral Processing Licence (MPL)",
}
SMALL = {
    "source_id": "S5", "canonical_source_id": "mining_rights_requirements",
    "text": "Small Scale Mining ... Environmental Project Brief ... Pegging Certificate ... 10 years.",
}
QUESTION = "What are the requirements for a large-scale mining licence in Zambia?"
BASE = {
    "answer": "Form I requires an Environmental Impact Statement. [S1] The applicant is a company. [S2]",
    "generation_method": "deterministic-mining-requirements",
    "citations": ["S1", "S2"],
    "sources": [],
}


def test_lml_intent():
    assert is_lml_requirements_query(QUESTION)
    assert not is_lml_requirements_query("large-scale exploration licence requirements")
    assert not is_lml_requirements_query("small-scale mining licence requirements")
    assert not is_lml_requirements_query("large-scale mining licence application fee")


def test_source_scoping_excludes_small_scale():
    assert source_kinds([SMALL]) == [None]


def test_prioritize_brings_necessary_passages_into_five():
    filler = [{"text": "Irrelevant mining document text repeated elsewhere"} for _ in range(10)]
    hits = filler + [SMALL, CONTINUE, START, COMPANY, FORM]
    top = prioritize_lml_results(hits, 5)
    assert set(source_kinds(top)) == {
        "form_appendices", "form_company", "lml_beginning", "lml_continuation", None
    }


def test_supplement_cites_correct_lml_sources():
    result = supplement_lml_answer(QUESTION, [FORM, COMPANY, START, CONTINUE, SMALL], BASE)
    assert "Pegging Certificate" in result["answer"]
    assert "25 years" in result["answer"]
    assert "[S4]" in result["answer"]
    assert result["citations"] == ["S1", "S2", "S3", "S4"]
    assert len(result["sources"]) == 4


def test_small_scale_pegging_never_supplements_lml():
    result = supplement_lml_answer(QUESTION, [FORM, COMPANY, SMALL], BASE)
    assert result == BASE


def test_missing_start_does_not_supplement():
    result = supplement_lml_answer(QUESTION, [FORM, COMPANY, CONTINUE], BASE)
    assert result == BASE


def test_unrelated_method_not_modified():
    other = dict(BASE, generation_method="deterministic-fee")
    assert supplement_lml_answer(QUESTION, [START, CONTINUE], other) == other


def test_public_lml_pipeline_is_source_scoped():
    from app.router import search_mine
    from app.evidence import normalize_evidence
    from app.document_answer_selection import select_document_answer_evidence
    from app.rag import answer_from_evidence
    from app.citation_validation import validate_citation_integrity

    search = search_mine(QUESTION, top_k=5)
    assert search["route"] == "documents"
    evidence = normalize_evidence(search_result=search, max_evidence=5)
    evidence = select_document_answer_evidence(question=QUESTION, evidence=evidence)
    text = [item.get("text", "") for item in evidence]
    assert any("Mining Rights (Large Scale) Licence (LML)" in t for t in text)
    assert any("Pegging Certificate" in t and "25 years" in t for t in text)
    answer = answer_from_evidence(QUESTION, evidence)
    assert "Pegging Certificate" in answer["answer"]
    assert "25 years" in answer["answer"]
    assert "Environmental Impact Statement" in answer["answer"]
    assert "Environmental Project Brief" not in answer["answer"]
    assert validate_citation_integrity(answer)["valid"]


def test_prioritize_uses_normalized_context_not_only_raw_chunks():
    from app.lml_source_scope import prioritize_lml_results

    # A PDF's raw chunk can lack the appendices that normalization restores
    # from adjacent chunks. The former v1 installer failed on this case.
    raw = [
        {"text": "Mining Licence - Large Scale Appendix No. 1"},
        COMPANY,
        {"text": "Small-scale requirements"},
        START,
        CONTINUE,
    ]
    normalized = [
        dict(FORM, text=FORM["text"]),
        COMPANY,
        {"text": "Small-scale requirements"},
        START,
        CONTINUE,
    ]
    for index, row in enumerate(normalized, start=1):
        row["source_id"] = f"S{index}"

    reordered = prioritize_lml_results(raw, 4, normalized_evidence=normalized)
    assert raw[0] in reordered
    assert COMPANY in reordered
    assert START in reordered
    assert CONTINUE in reordered


def test_validator_accepts_scoped_form_and_lml_checklist():
    from app.large_scale_requirements import (
        REQUIREMENTS,
        build_large_scale_mining_requirements_answer,
    )
    from app.mining_requirements_support import (
        validate_large_scale_mining_requirements_support,
    )

    form_text = (
        "(b) Mining Licence - Large Scale "
        + " ".join(
            f"Appendix No. {number} " + ", ".join(anchors)
            for number, _, anchors in REQUIREMENTS
        )
        + " (c) Mining Licence - Small-Scale Appendix No. 1 Small-scale form"
    )
    form = dict(FORM, text=form_text)
    evidence = [form, COMPANY, START, CONTINUE]
    base = build_large_scale_mining_requirements_answer(QUESTION, evidence)
    assert base is not None
    result = supplement_lml_answer(QUESTION, evidence, base)
    assert "Pegging Certificate" in result["answer"]
    audit = validate_large_scale_mining_requirements_support(
        QUESTION, evidence, result
    )
    assert audit["checked"] and audit["supported"], audit

    tampered = dict(result, answer=result["answer"].replace("25 years", "10 years"))
    rejected = validate_large_scale_mining_requirements_support(
        QUESTION, evidence, tampered
    )
    assert rejected["checked"] and not rejected["supported"], rejected
