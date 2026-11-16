"""Safely wire Mushima North into the existing exploration search/answer path.

Run from MineLens project root. Re-runnable: existing integrations are skipped.
This script does not alter Kabwe's drill data or the router.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOKS = [
    (
        ROOT / "app" / "exploration_search.py", "has_exploration_intent", "is_mushima_query(query)",
        """    from app.mushima_exploration import is_mushima_query
    if is_mushima_query(query):
        return True

""",
    ),
    (
        ROOT / "app" / "exploration_search.py", "query_exploration", "return query_mushima(query, top_k=top_k)",
        """    from app.mushima_exploration import is_mushima_query, query_mushima
    if is_mushima_query(query):
        return query_mushima(query, top_k=top_k)

""",
    ),
    (
        ROOT / "app" / "exploration_answers.py", "answer_exploration_result", "return answer_mushima(question, evidence)",
        """    from app.mushima_exploration import is_mushima_query, answer_mushima
    if is_mushima_query(question):
        return answer_mushima(question, evidence)

""",
    ),
]


def apply_hook(source: str, function_name: str, existing_marker: str, insertion: str) -> tuple[str, bool]:
    tree = ast.parse(source)
    matches = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == function_name]
    if len(matches) != 1:
        raise RuntimeError(f"Expected exactly one {function_name} function")
    function = matches[0]
    lines = source.splitlines(keepends=True)
    function_lines = "".join(lines[function.lineno - 1:function.end_lineno])
    if existing_marker in function_lines:
        return source, False
    # Insert immediately after the function docstring, if any.
    first_stmt = function.body[0]
    if isinstance(first_stmt, ast.Expr) and isinstance(first_stmt.value, ast.Constant) and isinstance(first_stmt.value.value, str):
        index = first_stmt.end_lineno
    else:
        index = function.lineno
    lines.insert(index, "\n" + insertion)
    updated = "".join(lines)
    compile(updated, f"module with {function_name}", "exec")
    return updated, True


def main():
    if not (ROOT / "app" / "mushima_exploration.py").exists():
        raise RuntimeError("Missing app/mushima_exploration.py. Extract integration bundle first.")
    planned = {}
    for path, function, marker, insertion in HOOKS:
        if not path.exists():
            raise RuntimeError(f"Required existing module missing: {path}")
        raw = path.read_text(encoding="utf-8-sig")
        source = planned.get(path, raw).replace("\r\n", "\n")
        planned[path], changed = apply_hook(source, function, marker, insertion)
        print(("PATCH" if changed else "SKIP"), f"{path.name}.{function}")
    # All validation and parsing above happens before writing any file.
    for path, source in planned.items():
        original = path.read_text(encoding="utf-8-sig")
        if original.replace("\r\n", "\n") != source:
            backup = ROOT / "debug" / "mushima_backup" / path.name
            backup.parent.mkdir(parents=True, exist_ok=True)
            if not backup.exists():
                backup.write_text(original, encoding="utf-8")
            newline = "\r\n" if "\r\n" in original else "\n"
            path.write_text(source.replace("\n", newline), encoding="utf-8")
            print("SAVED", path)
    print("Integration hooks complete. Run the tests before committing.")


if __name__ == "__main__":
    main()
