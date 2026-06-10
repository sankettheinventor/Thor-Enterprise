"""
Anti-fake-test HARDENING (H1+): a frontier agent may write a test that RUNS the feature code AND makes
a non-trivial-looking assertion that is nevertheless ALWAYS TRUE (tests nothing). Coverage alone passes
it. The discrimination gate catches it: gut the feature code, re-run — a genuine test goes RED, a fake
one still passes. THOR proves the test can fail, trusting no model. Docker-free, un-deferred.
"""
import os
import tempfile

from govengine.fake_test import is_hollow

LOGIN = "def check(pw):\n    return len(pw) >= 8\n"
CONTRACT = {"scope": {"files": ["src/login.py"]}}

GENUINE = ("import sys; sys.path.insert(0, 'src')\n"
           "from login import check\n"
           "assert check('abcdefgh') is True\n"
           "assert check('x') is False\n"
           "print('ok')\n")

# covers check() AND asserts non-trivially — but isinstance(_, object) is ALWAYS true: it tests nothing.
FAKE_COVERS_BUT_VACUOUS = ("import sys; sys.path.insert(0, 'src')\n"
                           "from login import check\n"
                           "r = check('abcdefgh')\n"
                           "assert isinstance(r, object)\n"
                           "print('ok')\n")


def _repo(test_src):
    d = tempfile.mkdtemp(prefix="faketest-")
    os.makedirs(os.path.join(d, "src"))
    with open(os.path.join(d, "src/login.py"), "w") as f:
        f.write(LOGIN)
    with open(os.path.join(d, "src/test_login.py"), "w") as f:
        f.write(test_src)
    return d


def test_genuine_test_passes_the_discrimination_gate():
    hollow, why = is_hollow(_repo(GENUINE), "src/test_login.py", CONTRACT)
    assert hollow is False, why


def test_vacuous_covering_test_is_caught():
    d = _repo(FAKE_COVERS_BUT_VACUOUS)
    hollow, why = is_hollow(d, "src/test_login.py", CONTRACT)
    assert hollow is True, f"a test that passes on gutted code must be flagged fake; got: {why}"
    assert "gutted" in why or "red" in why, why
    # and the gate RESTORED the worktree (no lingering mutation)
    assert "len(pw) >= 8" in open(os.path.join(d, "src/login.py")).read(), "feature source must be restored"
