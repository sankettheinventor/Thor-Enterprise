"""
Fake-test-checker (FR-13 / AC-3) — defends M1 against passing-but-hollow tests.

A sophisticated agent may write a test that technically passes (`assert True`) but never exercises
the feature. M1 (exit 0) alone would be fooled. This checks, by reading the test source, whether the
test actually (a) references the feature's contracted files/symbols, and (b) makes real assertions.
A passing-but-hollow test is flagged → M1 is overridden to fail → verdict not_done.

(Static heuristic for the bootstrap; coverage-of-the-diff analysis strengthens it later / Toras v2.)
"""
from __future__ import annotations

import os
import re


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
    return False, "test exercises the feature and asserts non-trivially"
