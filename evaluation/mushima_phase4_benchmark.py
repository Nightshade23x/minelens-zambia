"""Permanent end-to-end checks for the 9 Nov 2026 Mushima North Phase 4 data.

Run with: python -m evaluation.mushima_phase4_benchmark
Does not modify the existing answer benchmark or production modules.
"""

from __future__ import annotations

from app.mushima_exploration import SOURCE_ID


CASES = (
    {
        "id": "mushima_highest_silver_interval",
        "question": "Which Mushima North hole has the highest silver interval grade?",
        "expected": ("26TMNRC-078", "84 g/t Ag", "6 m", "interval grade"),
    },
    {
        "id": "mushima_highest_individual_copper",
        "question": "What was the highest individual copper assay at Mushima North?",
        "expected": ("26TMNRC-078", "1.08 % Cu", "individual peak assays"),
    },
    {
        "id": "mushima_hole_078_intervals",
        "question": "Show drilling results for 26TMNRC-078",
        "expected": ("26TMNRC-078", "70 m", "31 g/t Ag", "6 m", "84 g/t Ag"),
        "top_k": 20,
    },
    {
        "id": "mushima_all_phase4_holes",
        "question": "List all Mushima North drill holes",
        "expected": tuple(f"26TMNRC-{n:03d}" for n in range(75, 83)),
        "top_k": 20,
    },
    {
        "id": "mushima_unknown_hole_abstention",
        "question": "What are the assays for 26TMNRC-999?",
        "no_results": True,
    },
    {
        "id": "mushima_phase5_not_reported",
        "question": "Mushima North Phase 5 assay results",
        "no_results": True,
    },
)


def evaluate_case(case: dict) -> dict:
    """Use the public search -> normalize -> answer path, without altering it."""
    from app.router import search_mine
    from app.evidence import normalize_evidence
    from app.rag import answer_from_evidence
    from app.citation_validation import validate_citation_integrity

    errors = []
    answer_text = ""
    top_k = case.get("top_k", 10)
    try:
        # Use query= intentionally: it is the public router API.
        search = search_mine(query=case["question"], top_k=top_k)
        if search.get("route") != "exploration":
            errors.append(f"Wrong route: {search.get('route')!r}")

        rows = search.get("results") or []
        evidence = normalize_evidence(search_result=search, max_evidence=top_k)

        if case.get("no_results"):
            if rows:
                errors.append(f"Expected zero results, got {len(rows)}")
            if evidence:
                errors.append("Unknown or unreported data produced evidence")
        else:
            if not rows or not evidence:
                errors.append("No records/evidence for a known Phase 4 question")
            else:
                for item in evidence:
                    record = item.get("record") or {}
                    if record.get("project") != "Mushima North":
                        errors.append("Missing Mushima record or cross-project leakage")
                        break

                answer = answer_from_evidence(case["question"], evidence)
                answer_text = str(answer.get("answer") or "")
                for fact in case.get("expected", ()):
                    if fact.casefold() not in answer_text.casefold():
                        errors.append(f"Missing answer fact: {fact}")
                if answer.get("generation_method") != "structured-exploration":
                    errors.append("Wrong generation method")
                if not answer.get("citations"):
                    errors.append("Missing citations")
                if not validate_citation_integrity(answer).get("valid"):
                    errors.append("Invalid citation integrity")
                if not any(
                    s.get("canonical_source_id") == SOURCE_ID
                    for s in (answer.get("sources") or [])
                ):
                    errors.append("Missing Tertiary Minerals canonical source")
    except Exception as exc:
        errors.append(f"{type(exc).__name__}: {exc}")

    return {
        "id": case["id"],
        "passed": not errors,
        "errors": errors,
        "answer": answer_text,
    }


def main() -> int:
    results = [evaluate_case(case) for case in CASES]
    for result in results:
        print(f"{'PASS' if result['passed'] else 'FAIL'}: {result['id']}")
        for error in result["errors"]:
            print(f"  - {error}")
    passed = sum(item["passed"] for item in results)
    print(f"Mushima Phase 4 benchmark: {passed}/{len(results)} passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
