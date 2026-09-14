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
    """

    question = str(
        case[
            "question"
        ]
    )

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

    answer_result = (
        answer_from_evidence(
            question=question,
            evidence=evidence,
        )
    )

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
            no_forbidden_facts,
            route_correct,
            generation_correct,
            source_correct,
            citation_present,
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
        "Route accuracy:        "
        f"{route_accuracy:.3f}"
    )

    print(
        "Generation accuracy:   "
        f"{generation_accuracy:.3f}"
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