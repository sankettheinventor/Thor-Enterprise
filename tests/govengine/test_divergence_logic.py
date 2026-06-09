"""
Moat-LOGIC gate test (BUG-2 fix): the Divergence detector (lie-detector), exercised DIRECTLY and
DOCKER-FREE so its honesty signals run on EVERY commit gate. The live ACs (tests/govengine, deferred)
prove the same against real git diffs; this guards the pure logic on every commit.

(The empty/missing-claim fail-closed case is BUG-4's own test; here we cover the contradiction signals.)
"""
from govengine.divergence import detect


def test_claim_matching_reality_is_clean():
    d = detect({"files_touched": ["src/a.py"], "tests_passed": True},
               changed_files={"src/a.py"}, verifier_passed=True, gate_hits=0)
    assert d.found is False and d.signals == []


def test_claimed_but_absent_is_flagged():
    d = detect({"files_touched": ["src/ghost.py"]},
               changed_files=set(), verifier_passed=True, gate_hits=0)
    assert d.found is True and any("untouched" in s for s in d.signals)


def test_undisclosed_change_is_flagged():
    d = detect({"files_touched": ["src/a.py"]},
               changed_files={"src/a.py", "src/sneaky.py"}, verifier_passed=True, gate_hits=0)
    assert d.found is True and any("undisclosed" in s for s in d.signals)


def test_claimed_pass_but_verifier_failed_is_flagged():
    d = detect({"files_touched": ["src/a.py"], "tests_passed": True},
               changed_files={"src/a.py"}, verifier_passed=False, gate_hits=0)
    assert d.found is True and any("verifier failed" in s for s in d.signals)


def test_gate_gaming_hits_flagged():
    d = detect({"files_touched": ["src/a.py"]},
               changed_files={"src/a.py"}, verifier_passed=True, gate_hits=3)
    assert d.found is True and any("gate-gaming" in s for s in d.signals)
