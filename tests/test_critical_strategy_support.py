from app.critical_strategy_support import (
    validate_critical_strategy_support,
)


SOURCE = {
    "source_id": "S1",
    "evidence_type": "document",
    "canonical_source_id": (
        "national_critical_minerals_strategy_2024_2028"
    ),
}

MINERAL_EVIDENCE = {
    **SOURCE,
    "text": (
        "Among the notable the critical minerals in Zambia include: "
        "Lithium Lithium occurrences are located in Chilobe. "
        "Tin Tin occurrences are reported in Southern Province. "
        "Graphite Graphite occurrences are widespread in Zambia. "
        "Coltan (Columbite-Tantalum) Reported occurrences of coltan "
        "includes Misika. "
        "Rare Earth Elements (REEs) Known occurrences of rare earth "
        "elements in Zambia include Isoka. "
        "Manganese There are many occurrences of manganese "
        "mineralization in Zambia. "
        "Nickel The two well-known Nickel deposits are Munali "
        "and Enterprise. 2.1.3 Demand for Critical Minerals"
    ),
}

SKILLS_EVIDENCE = {
    **SOURCE,
    "text": (
        "Government needs to develop the skills and expertise to: "
        "Identify and restrict areas of potential deposits for bids "
        "by viable investors; "
        "Meet the technical challenges of exploration, production, "
        "processing and refining; and "
        "Manage the sustainability of the critical minerals industry. "
        "3. STRATEGIC VISION"
    ),
}

MINERAL_QUESTION = "what are Zambia's critical minerals"

MINERAL_ANSWER = (
    "According to Zambia's National Critical Minerals Strategy, "
    "the notable critical minerals identified in the retrieved "
    "section are Lithium, Tin, Graphite, "
    "Coltan (Columbite-Tantalum), Rare Earth Elements (REEs), "
    "Manganese, and Nickel. [S1]"
)

SKILLS_QUESTION = (
    "what skills and expertise does Zambia need "
    "for its critical minerals industry"
)

SKILLS_ANSWER = (
    "According to Zambia's National Critical Minerals Strategy, "
    "the government needs to develop skills and expertise to:\n\n"
    "- Identify and restrict areas of potential deposits "
    "for bids by viable investors.\n"
    "- Meet the technical challenges of exploration, "
    "production, processing and refining.\n"
    "- Manage the sustainability of the critical "
    "minerals industry.\n\n[S1]"
)


def check(question, evidence, text, method, citations=None):
    return validate_critical_strategy_support(
        question=question,
        evidence=[evidence],
        answer_result={
            "answer": text,
            "citations": ["S1"] if citations is None else citations,
            "generation_method": method,
        },
    )


def test_official_minerals_list_passes():
    result = check(
        MINERAL_QUESTION,
        MINERAL_EVIDENCE,
        MINERAL_ANSWER,
        "deterministic-critical-minerals",
    )
    assert result["supported"] is True


def test_invented_mineral_is_rejected():
    result = check(
        MINERAL_QUESTION,
        MINERAL_EVIDENCE,
        MINERAL_ANSWER.replace("Nickel.", "Cobalt."),
        "deterministic-critical-minerals",
    )
    assert result["supported"] is False


def test_missing_mineral_is_rejected():
    result = check(
        MINERAL_QUESTION,
        MINERAL_EVIDENCE,
        MINERAL_ANSWER.replace("Lithium, ", ""),
        "deterministic-critical-minerals",
    )
    assert result["supported"] is False


def test_official_skills_list_passes():
    result = check(
        SKILLS_QUESTION,
        SKILLS_EVIDENCE,
        SKILLS_ANSWER,
        "deterministic-critical-skills",
    )
    assert result["supported"] is True


def test_invented_skill_is_rejected():
    result = check(
        SKILLS_QUESTION,
        SKILLS_EVIDENCE,
        SKILLS_ANSWER.replace(
            "Manage the sustainability of the critical "
            "minerals industry.",
            "Develop aerospace navigation systems.",
        ),
        "deterministic-critical-skills",
    )
    assert result["supported"] is False


def test_extra_skill_is_rejected():
    result = check(
        SKILLS_QUESTION,
        SKILLS_EVIDENCE,
        SKILLS_ANSWER.replace(
            "\n\n[S1]",
            "\n- Develop rocket engines.\n\n[S1]",
        ),
        "deterministic-critical-skills",
    )
    assert result["supported"] is False


def test_unrelated_source_is_rejected():
    evidence = {
        **MINERAL_EVIDENCE,
        "canonical_source_id": "unrelated_document",
        "document": "unrelated.pdf",
    }
    result = check(
        MINERAL_QUESTION,
        evidence,
        MINERAL_ANSWER,
        "deterministic-critical-minerals",
    )
    assert result["supported"] is False


def test_invalid_citation_is_rejected():
    result = check(
        MINERAL_QUESTION,
        MINERAL_EVIDENCE,
        MINERAL_ANSWER,
        "deterministic-critical-minerals",
        citations=["S9"],
    )
    assert result["supported"] is False


def test_missing_strategy_section_remains_unchecked():
    result = check(
        MINERAL_QUESTION,
        {**MINERAL_EVIDENCE, "text": "Lithium and cobalt."},
        MINERAL_ANSWER,
        "deterministic-critical-minerals",
    )
    assert result["checked"] is False


def test_unrelated_answer_type_not_intercepted():
    result = check(
        "What is the estimated CapEx for Lumwana?",
        MINERAL_EVIDENCE,
        "Lumwana costs $2 billion.",
        "deterministic-project-estimate",
    )
    assert result["checked"] is False
