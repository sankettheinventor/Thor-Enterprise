"""
P2 (H4 QA half): the QA adversary is genuinely hostile — it fuzzes a MATRIX of edge inputs (not just
zeros) and flags only REAL-bug crashes. It catches a NON-zeros bug (IndexError on an empty list, which a
zeros-only probe misses) WITHOUT false-flagging clean numeric code (no softening, no false positives).
Docker-free, un-deferred.
"""
import os
import tempfile

from sdlc.stages import QAStage


def _repo(code_rel, code):
    d = tempfile.mkdtemp(prefix="qaadv-")
    os.makedirs(os.path.join(d, os.path.dirname(code_rel)), exist_ok=True)
    with open(os.path.join(d, code_rel), "w") as f:
        f.write(code)
    return d


def test_clean_numeric_function_is_not_false_flagged():
    d = _repo("src/calc.py", "def add(a, b):\n    return a + b\n")
    new_tests, bugs = QAStage()._adversarial(d, {"code_file": "src/calc.py"})
    assert new_tests and not bugs, f"clean add() must NOT be flagged; got {bugs}"


def test_non_zeros_bug_is_caught():
    # first(items) returns items[0] with no empty-check. It crashes on [] (IndexError) — a REAL bug — but
    # NOT on 0 (0[0] is a TypeError, which we exclude). Only the richer edge matrix catches it.
    d = _repo("src/util.py", "def first(items):\n    return items[0]\n")
    _, bugs = QAStage()._adversarial(d, {"code_file": "src/util.py"})
    assert bugs and "first" in bugs[0] and "IndexError" in bugs[0], f"non-zeros bug missed: {bugs}"


def test_div_by_zero_still_caught():
    d = _repo("src/calc.py", "def div(a, b):\n    return a / b\n")
    _, bugs = QAStage()._adversarial(d, {"code_file": "src/calc.py"})
    assert bugs and "ZeroDivisionError" in bugs[0], f"div-by-zero must still be caught: {bugs}"
