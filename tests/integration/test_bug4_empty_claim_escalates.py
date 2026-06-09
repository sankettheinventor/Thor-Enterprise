"""
BUG-4 (MEDIUM — lie-detector fails OPEN).

govengine/divergence.detect() has `if not claim: return d`, so an EMPTY or MISSING claim returns a
clean Divergence(found=False) — the lie-detector is silently disabled by handing it no claim. It must
FAIL CLOSED: a missing claim while reality shows real changes is itself a divergence to escalate,
never a clean pass.

Docker-free, un-deferred → runs on every `make qa` / `make test`.
"""
from govengine.divergence import detect


def test_bug4_empty_claim_fails_closed():
    """An empty claim while git shows real changes must be FLAGGED (found=True), not a clean pass."""
    d = detect({}, changed_files={"src/app.py"}, verifier_passed=True, gate_hits=0)
    assert d.found is True, "empty claim returned 'no divergence' — the lie-detector failed OPEN (BUG-4)"


def test_bug4_missing_claim_fails_closed():
    """A None/missing claim must also fail closed (found=True)."""
    d = detect(None, changed_files={"src/app.py"}, verifier_passed=True, gate_hits=0)
    assert d.found is True, "missing claim returned 'no divergence' — the lie-detector failed OPEN (BUG-4)"
