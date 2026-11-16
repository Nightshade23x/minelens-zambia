"""Guard against attributing small-scale mining appendix items to large-scale mining."""

from app.large_scale_requirements import (
    REQUIREMENTS,
    build_large_scale_mining_requirements_answer,
    large_scale_appendices,
)
from app.mining_requirements_support import (
    validate_large_scale_mining_requirements_support,
)

QUESTION = "What are the requirements for a large-scale mining licence in Zambia?"
FORM = {
    "source_id": "S1", "canonical_source_id": "application_for_mining_right",
    "source_authority": "government", "evidence_type": "document",
    "text": """(a) Exploration Licence Appendix No. 1 Any further information.
    (b) Mining Licence - Large Scale
    Appendix No. 1 A comprehensive statement of the mineral deposits, ore resources and mining conditions
    Appendix No. 2 Feasibility study for mining operations including forecast capital investment, recovery rate, treatment and disposal
    Appendix No. 3 Approved Environmental Impact Statement
    Appendix No. 4 Details of expected infrastructure requirements
    Appendix No. 5 Proposals for employment and training of citizens of Zambia
    Appendix No. 6 Proposals for promotion of local business development
    Appendix No. 7 Tax clearance certificate issued under Income Tax Act (Cap. 323)
    Appendix No. 8 Plan of proposed mining area
    Appendix No. 9 In the case of gemstones, plan for cutting, polishing and faceting gemstone in Zambia
    Appendix No. 10 Any further information which the Director of Mining Cadastre may require
    (c) Mining Licence - Small-Scale
    Appendix No. 1 Small-scale prospecting report
    Appendix No. 4 Statement of duration (not exceeding ten years)
    Appendix No. 6 Approved Environmental Project Brief
    Appendix No. 7 Pegging Certificate""",
}
COMPANY = {
    "source_id": "S2", "canonical_source_id": "application_for_mining_right",
    "source_authority": "government", "evidence_type": "document",
    "text": "NOTE 1. An application for large-scale or small-scale mining shall only be made by a company.",
}


def make_answer(evidence=None):
    return build_large_scale_mining_requirements_answer(QUESTION, evidence or [FORM, COMPANY])


def test_scoped_appendices_are_only_large_scale():
    sections = large_scale_appendices(FORM["text"])
    assert len(sections) == 10
    assert "environmental impact statement" in sections[3][0]
    assert "environmental project brief" not in " ".join(sum(sections.values(), []))


def test_generator_cites_ten_large_scale_appendices():
    answer = make_answer()
    assert answer is not None
    assert answer["generation_method"] == "deterministic-mining-requirements"
    assert answer["answer"].count("\n- ") == len(REQUIREMENTS)
    assert answer["citations"] == ["S1", "S2"]
    assert "Environmental Impact Statement" in answer["answer"]
    assert "Environmental Project Brief" not in answer["answer"]
    assert "Pegging Certificate" not in answer["answer"]
    assert "not exceed 10 years" not in answer["answer"]


def test_validator_accepts_source_scoped_answer():
    answer = make_answer()
    audit = validate_large_scale_mining_requirements_support(QUESTION, [FORM, COMPANY], answer)
    assert audit["checked"] is True
    assert audit["supported"] is True


def test_validator_rejects_small_scale_ebp_substitution():
    answer = make_answer()
    answer["answer"] = answer["answer"].replace("Environmental Impact Statement", "Environmental Project Brief")
    audit = validate_large_scale_mining_requirements_support(QUESTION, [FORM, COMPANY], answer)
    assert audit["supported"] is False


def test_validator_rejects_invented_extra_requirement():
    answer = make_answer()
    answer["answer"] += "\n- Submit a fictitious tax bond. [S1]"
    audit = validate_large_scale_mining_requirements_support(QUESTION, [FORM, COMPANY], answer)
    assert audit["supported"] is False


def test_validator_rejects_incorrect_citation():
    answer = make_answer()
    answer["citations"] = ["S1", "S9"]
    audit = validate_large_scale_mining_requirements_support(QUESTION, [FORM, COMPANY], answer)
    assert audit["supported"] is False


def test_missing_large_scale_appendix_fails_closed():
    source = dict(FORM)
    source["text"] = source["text"].replace("Approved Environmental Impact Statement", "")
    assert build_large_scale_mining_requirements_answer(QUESTION, [source, COMPANY]) is None


def test_small_scale_only_fails_closed():
    source = dict(FORM)
    source["text"] = source["text"].split("(c) Mining Licence - Small-Scale")[1]
    assert build_large_scale_mining_requirements_answer(QUESTION, [source, COMPANY]) is None


def test_unrelated_answer_is_unchecked():
    result = validate_large_scale_mining_requirements_support(
        "What are Zambia's critical minerals?", [FORM],
        {"generation_method": "deterministic-critical-minerals", "answer": "hi", "citations": ["S1"]},
    )
    assert result["checked"] is False
