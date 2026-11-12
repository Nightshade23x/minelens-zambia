"""Run reliability checks against document benchmark cases."""

import json
from collections import Counter
from pathlib import Path

from app.router import search_mine
from app.evidence import normalize_evidence
from app.document_answer_selection import (
    select_document_answer_evidence,
)
from app.rag import answer_from_evidence
from app.reliability_gate import assess_answer_quality


def main():
    benchmark = Path("evaluation/answer_questions.json")
    cases = json.loads(
        benchmark.read_text(encoding="utf-8-sig")
    )

    results = []

    for case in cases:
        if case.get("expected_route") != "documents":
            continue

        if case.get("requires_ollama", False):
            continue

        question = case["question"]

        search_result = search_mine(
            question,
            top_k=5,
        )

        if search_result.get("route") != "documents":
            results.append({
                "id": case["id"],
                "status": "review_required",
                "issues": ["unexpected_route"],
            })
            print(
                case["id"],
                "| review_required | unexpected_route",
            )
            continue

        evidence = normalize_evidence(
            search_result=search_result,
            max_evidence=5,
        )

        evidence = select_document_answer_evidence(
            question=question,
            evidence=evidence,
        )

        answer = answer_from_evidence(
            question=question,
            evidence=evidence,
        )

        gate = assess_answer_quality(
            question=question,
            search_result=search_result,
            evidence=evidence,
            answer_result=answer,
        )

        results.append({
            "id": case["id"],
            "question": question,
            "generation_method": answer.get(
                "generation_method"
            ),
            "answer": answer.get("answer"),
            "status": gate["status"],
            "issues": gate["issues"],
            "factual_support_checked": (
                gate["factual_support"].get("checked")
                if gate["factual_support"]
                else None
            ),
        })

        print(
            case["id"],
            "|",
            gate["status"],
            "|",
            ", ".join(gate["issues"]) or "none",
        )

    output = Path("debug/benchmark_reliability_review.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(results, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    counts = Counter(item["status"] for item in results)

    print("\nRELIABILITY REVIEW SUMMARY")
    print("=" * 50)
    print("Questions reviewed:", len(results))

    for status in (
        "checks_passed",
        "review_required",
        "insufficient_evidence",
    ):
        print(status + ":", counts[status])

    print("\nSaved:", output)


if __name__ == "__main__":
    main()
