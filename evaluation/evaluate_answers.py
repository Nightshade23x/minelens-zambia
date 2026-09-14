from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from app.evidence import normalize_evidence
from app.rag import answer_from_evidence
from app.router import search_mine


DEFAULT_QUESTIONS_PATH = (
    Path(__file__).parent
    / "answer_questions.json"
)


# ---------------------------------------------------------
# Loading
# ---------------------------------------------------------

def load_questions(
    path: Path,
) -> list[dict]:
    """
    Load answer-evaluation questions.
    """

    with path.open(
        "r",
        encoding="utf-8",
    ) as file:

        questions = json.load(
            file
        )

    if not isinstance(
        questions,
        list,
    ):

        raise ValueError(
            "Answer questions file "
            "must contain a JSON list."
        )

    return questions


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def normalize_text(
    value: Any,
) -> str:
    """
    Normalize text for case-insensitive matching.
    """

    if value is None:
        return ""

    return " ".join(
        str(value)
        .lower()
        .split()
    )


def contains_text(
    haystack: str,
    needle: str,
) -> bool:
    """
    Case-insensitive substring check.
    """

    return (
        normalize_text(
            needle
        )
        in normalize_text(
            haystack
        )
    )


def evaluate_concepts(
    answer: str,
    concepts: list[dict],
) -> dict:
    """
    Evaluate semantic concepts using acceptable phrase
    alternatives.

    Each concept passes if at least one phrase in its
    any_of list appears in the answer.
    """

    details: dict[
        str,
        bool,
    ] = {}

    matches: dict[
        str,
        str | None,
    ] = {}

    for concept in concepts:

        name = str(
            concept.get(
                "name",
                "unnamed concept",
            )
        )

        alternatives = (
            concept.get(
                "any_of",
                [],
            )
        )

        matched_phrase = None

        for phrase in alternatives:

            if contains_text(
                answer,
                str(
                    phrase
                ),
            ):

                matched_phrase = (
                    str(
                        phrase
                    )
                )

                break

        details[
            name
        ] = (
            matched_phrase
            is not None
        )

        matches[
            name
        ] = matched_phrase

    total = len(
        concepts
    )

    found = sum(
        details.values()
    )

    if total:

        recall = (
            found
            / total
        )

    else:

        recall = 1.0

    return {
        "found": found,
        "total": total,
        "recall": recall,
        "details": details,
        "matches": matches,
    }


def source_text(
    sources: list[dict],
) -> str:
    """
    Flatten source metadata for source checks.
    """

    parts: list[str] = []

    for source in sources:

        for key in (
            "title",
            "document",
            "source_url",
        ):

            value = source.get(
                key
            )

            if value:

                parts.append(
                    str(
                        value
                    )
                )

    return " ".join(
        parts
    )


# ---------------------------------------------------------
# Per-question evaluation
# ---------------------------------------------------------

def evaluate_question(
    case: dict,
    *,
    top_k: int = 5,
    evidence_k: int = 3,
) -> dict:
    """
    Run one question through the complete MineLens
    pipeline and evaluate the final answer.

    Generation failures become failed benchmark results
    rather than terminating the entire evaluation run.
    """

    question = str(
        case[
            "question"
        ]
    )

    # -----------------------------------------------------
    # Retrieval
    # -----------------------------------------------------

    search_result = search_mine(
        query=question,
        top_k=top_k,
    )

    evidence = normalize_evidence(
        search_result=(
            search_result
        ),
        max_evidence=(
            evidence_k
        ),
    )

    # -----------------------------------------------------
    # Answer generation
    # -----------------------------------------------------

    generation_error = None

    try:

        answer_result = (
            answer_from_evidence(
                question=question,
                evidence=evidence,
            )
        )

    except Exception as error:

        generation_error = (
            f"{type(error).__name__}: "
            f"{error}"
        )

        answer_result = {
            "answer": "",
            "model": None,
            "generation_method": (
                "error"
            ),
            "citations": [],
            "sources": [],
        }

    answer = str(
        answer_result.get(
            "answer",
            "",
        )
    )

    sources = answer_result.get(
        "sources",
        [],
    )

    citations = answer_result.get(
        "citations",
        [],
    )

    expected_facts = (
        case.get(
            "expected_facts",
            [],
        )
    )

    forbidden_facts = (
        case.get(
            "forbidden_facts",
            [],
        )
    )

    # -----------------------------------------------------
    # Fact recall
    # -----------------------------------------------------

    fact_results = {
        fact: contains_text(
            answer,
            fact,
        )
        for fact in expected_facts
    }

    facts_found = sum(
        fact_results.values()
    )

    facts_total = len(
        expected_facts
    )

    if facts_total:

        fact_recall = (
            facts_found
            / facts_total
        )

    else:

        fact_recall = 1.0

    # -----------------------------------------------------
    # Concept recall
    # -----------------------------------------------------

    expected_concepts = (
        case.get(
            "expected_concepts",
            [],
        )
    )

    concept_results = (
        evaluate_concepts(
            answer=answer,
            concepts=(
                expected_concepts
            ),
        )
    )

    minimum_concept_recall = float(
        case.get(
            "minimum_concept_recall",
            1.0,
        )
    )

    concept_recall_passed = (
        concept_results[
            "recall"
        ]
        >= minimum_concept_recall
    )

    # -----------------------------------------------------
    # Forbidden facts
    # -----------------------------------------------------

    forbidden_found = [
        fact
        for fact in forbidden_facts
        if contains_text(
            answer,
            fact,
        )
    ]

    no_forbidden_facts = (
        len(
            forbidden_found
        )
        == 0
    )

    # -----------------------------------------------------
    # Route
    # -----------------------------------------------------

    expected_route = (
        case.get(
            "expected_route"
        )
    )

    actual_route = (
        search_result.get(
            "route"
        )
    )

    route_correct = (
        expected_route is None
        or actual_route
        == expected_route
    )

    # -----------------------------------------------------
    # Generation method
    # -----------------------------------------------------

    expected_method = (
        case.get(
            "expected_generation_method"
        )
    )

    actual_method = (
        answer_result.get(
            "generation_method"
        )
    )

    generation_correct = (
        expected_method is None
        or actual_method
        == expected_method
    )

    # -----------------------------------------------------
    # Source
    # -----------------------------------------------------

    required_source = (
        case.get(
            "required_source_contains"
        )
    )

    flattened_sources = source_text(
        sources
    )

    source_correct = (
        required_source is None
        or contains_text(
            flattened_sources,
            required_source,
        )
    )

    # -----------------------------------------------------
    # Citation presence
    # -----------------------------------------------------

    citation_present = (
        len(
            citations
        )
        > 0
    )

    # -----------------------------------------------------
    # Overall
    # -----------------------------------------------------

    passed = all(
        (
            fact_recall == 1.0,
            concept_recall_passed,
            no_forbidden_facts,
            route_correct,
            generation_correct,
            source_correct,
            citation_present,
            generation_error is None,
        )
    )

    return {
        "id": (
            case.get(
                "id"
            )
        ),
        "question": question,
        "passed": passed,
        "error": (
            generation_error
        ),
        "route": {
            "expected": (
                expected_route
            ),
            "actual": (
                actual_route
            ),
            "correct": (
                route_correct
            ),
        },
        "generation": {
            "expected": (
                expected_method
            ),
            "actual": (
                actual_method
            ),
            "correct": (
                generation_correct
            ),
        },
        "facts": {
            "found": (
                facts_found
            ),
            "total": (
                facts_total
            ),
            "recall": (
                fact_recall
            ),
            "details": (
                fact_results
            ),
        },
        "concepts": {
            "found": (
                concept_results[
                    "found"
                ]
            ),
            "total": (
                concept_results[
                    "total"
                ]
            ),
            "recall": (
                concept_results[
                    "recall"
                ]
            ),
            "minimum_required": (
                minimum_concept_recall
            ),
            "passed": (
                concept_recall_passed
            ),
            "details": (
                concept_results[
                    "details"
                ]
            ),
            "matches": (
                concept_results[
                    "matches"
                ]
            ),
        },
        "forbidden": {
            "passed": (
                no_forbidden_facts
            ),
            "found": (
                forbidden_found
            ),
        },
        "source": {
            "required_contains": (
                required_source
            ),
            "correct": (
                source_correct
            ),
        },
        "citations": {
            "present": (
                citation_present
            ),
            "values": (
                citations
            ),
        },
        "answer": answer,
    }


# ---------------------------------------------------------
# Failure diagnostics
# ---------------------------------------------------------

def print_failure_details(
    result: dict,
) -> None:
    """
    Print useful diagnostics for one failed benchmark
    question.
    """

    if result.get(
        "error"
    ):

        print(
            "  Generation error: "
            f"{result['error']}"
        )

    if not result[
        "route"
    ][
        "correct"
    ]:

        print(
            "  Route mismatch: "
            f"expected "
            f"{result['route']['expected']}, "
            f"got "
            f"{result['route']['actual']}"
        )

    if not result[
        "generation"
    ][
        "correct"
    ]:

        print(
            "  Generation mismatch: "
            f"expected "
            f"{result['generation']['expected']}, "
            f"got "
            f"{result['generation']['actual']}"
        )

    missing_facts = [
        fact
        for fact, found
        in result[
            "facts"
        ][
            "details"
        ].items()
        if not found
    ]

    if missing_facts:

        print(
            "  Missing facts: "
            + ", ".join(
                missing_facts
            )
        )

    missing_concepts = [
        name
        for name, found
        in result[
            "concepts"
        ][
            "details"
        ].items()
        if not found
    ]

    if missing_concepts:

        print(
            "  Missing concepts: "
            + ", ".join(
                missing_concepts
            )
        )

    if not result[
        "concepts"
    ][
        "passed"
    ]:

        print(
            "  Concept recall: "
            f"{result['concepts']['recall']:.3f} "
            "(minimum "
            f"{result['concepts']['minimum_required']:.3f})"
        )

    if result[
        "forbidden"
    ][
        "found"
    ]:

        print(
            "  Forbidden facts: "
            + ", ".join(
                result[
                    "forbidden"
                ][
                    "found"
                ]
            )
        )

    if not result[
        "source"
    ][
        "correct"
    ]:

        print(
            "  Required source "
            "was not cited."
        )

    if not result[
        "citations"
    ][
        "present"
    ]:

        print(
            "  No evidence citation."
        )

    answer = result.get(
        "answer",
        "",
    )

    if answer:

        print(
            "  Answer: "
            f"{answer}"
        )


# ---------------------------------------------------------
# Benchmark
# ---------------------------------------------------------

def evaluate_all(
    questions: list[dict],
    *,
    include_ollama: bool = False,
    top_k: int = 5,
    evidence_k: int = 3,
) -> list[dict]:
    """
    Run the answer benchmark.
    """

    results: list[dict] = []

    for case in questions:

        if (
            case.get(
                "requires_ollama",
                False,
            )
            and not include_ollama
        ):

            continue

        print()
        print(
            "-" * 72
        )

        print(
            f"Evaluating: "
            f"{case.get('id')}"
        )

        result = (
            evaluate_question(
                case,
                top_k=top_k,
                evidence_k=evidence_k,
            )
        )

        results.append(
            result
        )

        status = (
            "PASS"
            if result[
                "passed"
            ]
            else "FAIL"
        )

        print(
            f"Result: {status}"
        )

        if not result[
            "passed"
        ]:

            print_failure_details(
                result
            )

    return results


# ---------------------------------------------------------
# Summary
# ---------------------------------------------------------

def print_summary(
    results: list[dict],
) -> None:
    """
    Print aggregate answer-quality metrics.
    """

    total = len(
        results
    )

    if total == 0:

        print(
            "No evaluation questions were run."
        )

        return

    passed = sum(
        1
        for result in results
        if result[
            "passed"
        ]
    )

    average_fact_recall = (
        sum(
            result[
                "facts"
            ][
                "recall"
            ]
            for result in results
        )
        / total
    )

    average_concept_recall = (
        sum(
            result[
                "concepts"
            ][
                "recall"
            ]
            for result in results
        )
        / total
    )

    route_accuracy = (
        sum(
            result[
                "route"
            ][
                "correct"
            ]
            for result in results
        )
        / total
    )

    generation_accuracy = (
        sum(
            result[
                "generation"
            ][
                "correct"
            ]
            for result in results
        )
        / total
    )

    source_accuracy = (
        sum(
            result[
                "source"
            ][
                "correct"
            ]
            for result in results
        )
        / total
    )

    citation_rate = (
        sum(
            result[
                "citations"
            ][
                "present"
            ]
            for result in results
        )
        / total
    )

    hallucination_free_rate = (
        sum(
            result[
                "forbidden"
            ][
                "passed"
            ]
            for result in results
        )
        / total
    )

    generation_success_rate = (
        sum(
            result.get(
                "error"
            )
            is None
            for result in results
        )
        / total
    )

    print()
    print(
        "=" * 72
    )

    print(
        "MINELENS ANSWER EVALUATION"
    )

    print(
        "=" * 72
    )

    print(
        f"Questions:             {total}"
    )

    print(
        "Overall pass rate:     "
        f"{passed / total:.3f}"
    )

    print(
        "Fact recall:           "
        f"{average_fact_recall:.3f}"
    )

    print(
        "Concept recall:        "
        f"{average_concept_recall:.3f}"
    )

    print(
        "Route accuracy:        "
        f"{route_accuracy:.3f}"
    )

    print(
        "Generation accuracy:   "
        f"{generation_accuracy:.3f}"
    )

    print(
        "Generation success:    "
        f"{generation_success_rate:.3f}"
    )

    print(
        "Source accuracy:       "
        f"{source_accuracy:.3f}"
    )

    print(
        "Citation rate:         "
        f"{citation_rate:.3f}"
    )

    print(
        "Forbidden-fact clean:  "
        f"{hallucination_free_rate:.3f}"
    )

    if passed != total:

        print()
        print(
            "Failed questions:"
        )

        for result in results:

            if not result[
                "passed"
            ]:

                print(
                    "  - "
                    f"{result['id']}"
                )


# ---------------------------------------------------------
# CLI
# ---------------------------------------------------------

def main() -> None:

    parser = argparse.ArgumentParser(
        description=(
            "Evaluate final MineLens "
            "answer quality."
        )
    )

    parser.add_argument(
        "--questions",
        type=Path,
        default=(
            DEFAULT_QUESTIONS_PATH
        ),
    )

    parser.add_argument(
        "--include-ollama",
        action="store_true",
        help=(
            "Include benchmark questions "
            "that require Ollama."
        ),
    )

    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
    )

    parser.add_argument(
        "--evidence-k",
        type=int,
        default=3,
    )

    args = parser.parse_args()

    if args.top_k <= 0:

        raise ValueError(
            "--top-k must be greater "
            "than zero."
        )

    if args.evidence_k <= 0:

        raise ValueError(
            "--evidence-k must be greater "
            "than zero."
        )

    questions = load_questions(
        args.questions
    )

    results = evaluate_all(
        questions,
        include_ollama=(
            args.include_ollama
        ),
        top_k=args.top_k,
        evidence_k=(
            args.evidence_k
        ),
    )

    print_summary(
        results
    )


if __name__ == "__main__":
    main()