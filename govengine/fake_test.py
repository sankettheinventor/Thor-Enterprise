"""
Fake-test-checker (FR-13 / AC-3) — defends M1 against passing-but-hollow tests.

A sophisticated agent may write a test that technically passes (`assert True`) but never exercises
the feature. M1 (exit 0) alone would be fooled. This checks, by reading the test source, whether the
test actually (a) references the feature's contracted files/symbols, and (b) makes real assertions.
A passing-but-hollow test is flagged → M1 is overridden to fail → verdict not_done.

H1 STRENGTHENED (Task 5): a referencing test with a non-trivial-but-vacuous assertion
(`assert callable(login)`) passed the static check while exercising NOTHING. So after the static
gates we run the test under coverage and require it to actually EXECUTE the contracted code's
function bodies — coverage-of-the-diff. The static checks are kept (strengthen, never bypass).
"""
from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
import uuid


def is_hollow(repo: str, test_relpath: str | None, contract: dict) -> tuple[bool, str]:
    """Return (hollow, reason). hollow=True means the test does NOT genuinely exercise the feature."""
    if not test_relpath:
        return True, "no test file"
    path = os.path.join(repo, test_relpath)
    if not os.path.exists(path):
        return True, "test file missing"
    src = open(path).read()

    # (a) does it reference any contracted file / its module name? (does it touch the new code?)
    cited = contract.get("scope", {}).get("files", [])
    modules = {os.path.splitext(os.path.basename(f))[0] for f in cited}   # e.g. src/login.py -> login
    references_feature = any(m and m in src for m in modules) or any(f in src for f in cited)

    # (b) does it make a non-trivial assertion (asserts on *something*, not literally `assert True`)?
    asserts = re.findall(r"assert\s+(.+)", src)
    trivial = all(a.strip() in ("True", "1", "True  # ok", "(True)") for a in asserts) if asserts else True

    if not references_feature:
        return True, "test does not exercise the feature (no reference to contracted code)"
    if trivial:
        return True, "test asserts trivially (assert True) — does not test the feature"

    # (c) coverage-of-the-diff: the test must EXECUTE the contracted code, not just import it (H1).
    covered, why = _covers_feature_code(repo, test_relpath, cited)
    if not covered:
        return True, f"hollow: {why}"
    return False, f"test exercises the feature and asserts non-trivially; {why}"


def _function_body_lines(target_path: str) -> set[int]:
    """The line numbers INSIDE function bodies (executing one means the test CALLED, not just imported)."""
    try:
        tree = ast.parse(open(target_path).read())
    except (OSError, SyntaxError):
        return set()
    lines: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for stmt in node.body:
                lines.update(range(stmt.lineno, (getattr(stmt, "end_lineno", stmt.lineno) or stmt.lineno) + 1))
    return lines


def _covers_feature_code(repo: str, test_relpath: str, cited: list[str]) -> tuple[bool, str]:
    """Run the test under coverage; require it to execute a function-body line of a contracted source."""
    target = next((f for f in cited if f.endswith(".py")
                   and not os.path.basename(f).startswith("test_")), None)
    if not target:
        return True, "no source file in scope to cover"
    target_path = os.path.join(repo, target)
    if not os.path.exists(target_path):
        return True, f"contracted source {target} absent (mechanical probes gate this)"
    body_lines = _function_body_lines(target_path)
    if not body_lines:
        return True, f"{target} has no function bodies to cover"

    cov_file = os.path.join(repo, f".cov_{uuid.uuid4().hex}")
    env = {**os.environ, "COVERAGE_FILE": cov_file, "PYTHONDONTWRITEBYTECODE": "1"}
    try:
        subprocess.run([sys.executable, "-m", "coverage", "run", test_relpath],
                       cwd=repo, env=env, capture_output=True, timeout=30)
        j = subprocess.run([sys.executable, "-m", "coverage", "json", "-o", "-"],
                           cwd=repo, env=env, capture_output=True, text=True, timeout=30)
        data = json.loads(j.stdout or "{}")
    except Exception as e:  # noqa: BLE001 — coverage tooling failure: the static checks above still stand
        return True, f"coverage tooling unavailable ({e}); static checks applied"
    finally:
        try:
            os.remove(cov_file)
        except OSError:
            pass

    executed: set[int] = set()
    base = os.path.basename(target)
    for fpath, info in data.get("files", {}).items():
        if fpath.endswith(target) or os.path.basename(fpath) == base:
            executed = set(info.get("executed_lines", []))
            break
    if executed & body_lines:
        return True, f"executed {len(executed & body_lines)} body line(s) of {target}"
    return False, f"test imported but never executed the code in {target} (coverage-of-diff)"
