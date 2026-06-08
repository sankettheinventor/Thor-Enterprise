"""
The GovernanceEngine (the moat) — Acceptance Criteria AC-1..AC-12 (PRD §15).

PROVING PASS (Task 5). Engine-level proofs against REAL git + real subprocess test runs + a real
ledger window. The honest Verdict Coordinator that feeds trusted inputs is proven separately in
tests/integration/test_moat_adversarial.py; here we prove the engine/panel/divergence/probes behave.
Deferred (live); run: pytest -m deferred tests/govengine.
"""
import os
import subprocess

import pytest

pytestmark = pytest.mark.deferred

LOGIN = "def check(pw):\n    return len(pw) >= 8\n"
REAL_TEST = ("import sys; sys.path.insert(0,'src')\nfrom login import check\n"
             "assert check('abcdefgh') is True\nassert check('x') is False\nprint('ok')\n")
REGRESS = "print('ok')\n"


def _git(repo, *a):
    return subprocess.run(["git", "-C", repo, *a], capture_output=True, text=True)


def _repo(host_repo, fid, files, base_files=None):
    open(os.path.join(host_repo, "README"), "w").write("base\n")
    for rel, c in (base_files or {}).items():                 # files that exist BEFORE the feature branch
        p = os.path.join(host_repo, rel)
        os.makedirs(os.path.dirname(p) or host_repo, exist_ok=True)
        open(p, "w").write(c)
    _git(host_repo, "add", "-A")
    _git(host_repo, "-c", "user.email=a@b", "-c", "user.name=a", "commit", "-q", "-m", "base")
    _git(host_repo, "branch", "-M", "main")
    _git(host_repo, "checkout", "-q", "-b", f"feature/{fid}")
    for rel, c in files.items():
        p = os.path.join(host_repo, rel)
        os.makedirs(os.path.dirname(p) or host_repo, exist_ok=True)
        open(p, "w").write(c)
    _git(host_repo, "add", "-A")
    _git(host_repo, "-c", "user.email=c@t", "-c", "user.name=c", "commit", "-q", "-m", f"implement {fid}")
    return host_repo, f"feature/{fid}"


def _ctx(fresh_ledger, repo, branch, fid, **over):
    from govengine.engine import VerdictContext
    from manager.core import ThorManager
    base = dict(contract={"scope": {"files": ["src/login.py"]},
                          "contracts": [{"name": "works", "status": "done"}],
                          "test_file": "src/test_login.py", "regression_file": "src/test_regress.py"},
                claim={"files_touched": ["src/login.py", "src/test_login.py", "src/test_regress.py"],
                       "tests_passed": True},
                manager=ThorManager(fresh_ledger), commit_window=None, skill_results_ok=True)
    base.update(over)
    return VerdictContext(fid, branch, repo, **base)


def _green_files():
    return {"src/login.py": LOGIN, "src/test_login.py": REAL_TEST, "src/test_regress.py": REGRESS}


def _engine(ctx):
    from govengine.engine import GovernanceEngine
    return GovernanceEngine(ctx.manager).run_verdict(ctx)


def test_ac1_incomplete_not_done_m3_blocker(fresh_ledger, host_repo):
    repo, br = _repo(host_repo, "F1", {"src/other.py": "x=1\n"})       # cited src/login.py NOT changed
    r = _engine(_ctx(fresh_ledger, repo, br, "F1", claim={}))
    assert r["verdict"] == "not_done" and any(b["probe"] == "M3" for b in r["blockers"])


def test_ac2_fabricated_claim_caught_by_divergence(fresh_ledger, host_repo):
    repo, br = _repo(host_repo, "F2", _green_files())
    r = _engine(_ctx(fresh_ledger, repo, br, "F2", claim={"files_touched": ["src/ghost.py"], "tests_passed": True}))
    assert r["divergence"]["found"] and r["verdict"] == "escalate"


def test_ac3_hollow_fake_test_not_done(fresh_ledger, host_repo):
    hollow = "import sys; sys.path.insert(0,'src')\nfrom login import check\nassert callable(check)\nprint('ok')\n"
    repo, br = _repo(host_repo, "F3", {"src/login.py": LOGIN, "src/test_login.py": hollow, "src/test_regress.py": REGRESS})
    r = _engine(_ctx(fresh_ledger, repo, br, "F3", claim={}))
    assert any(b["probe"] == "M1" for b in r["blockers"]) and r["verdict"] != "done"


def test_ac4_ci_pass_diff_mismatch_escalate(fresh_ledger, host_repo):
    # login.py exists on main (so it is NOT in the feature diff). The verifier passes (M1) and the
    # contracts are done (M5), but the cited file didn't change in this branch (M3) → conflict → escalate.
    repo, br = _repo(host_repo, "F4", {"src/test_login.py": REAL_TEST, "src/test_regress.py": REGRESS,
                                       "src/decoy.py": "y=1\n"}, base_files={"src/login.py": LOGIN})
    ctx = _ctx(fresh_ledger, repo, br, "F4", claim={})        # cited src/login.py, but it's not in the diff
    assert _engine(ctx)["verdict"] == "escalate"


def test_ac5_verdict_read_only(fresh_ledger, host_repo):
    repo, br = _repo(host_repo, "F5", _green_files())
    before = _git(repo, "status", "--porcelain").stdout
    _engine(_ctx(fresh_ledger, repo, br, "F5"))
    assert _git(repo, "status", "--porcelain").stdout == before, "a verdict must change nothing"


def test_ac6_deterministic_replay(fresh_ledger, host_repo):
    repo, br = _repo(host_repo, "F6", _green_files())
    a = _engine(_ctx(fresh_ledger, repo, br, "F6"))["deterministic_hash"]
    b = _engine(_ctx(fresh_ledger, repo, br, "F6"))["deterministic_hash"]
    assert a == b


def test_ac7_stale_verdict_freshness(fresh_ledger, host_repo):
    from govengine.engine import GovernanceEngine
    repo, br = _repo(host_repo, "F7", _green_files())
    ctx = _ctx(fresh_ledger, repo, br, "F7")
    eng = GovernanceEngine(ctx.manager)
    r = eng.run_verdict(ctx)
    assert eng.is_fresh(r, ctx) is True
    open(os.path.join(repo, "src/login.py"), "a").write("# moved\n")        # branch HEAD moves
    _git(repo, "add", "-A")
    _git(repo, "-c", "user.email=c@t", "-c", "user.name=c", "commit", "-q", "-m", "move")
    assert eng.is_fresh(r, ctx) is False                                    # R9 — stale, must re-run


def test_ac8_inputs_unreadable_fail_closed(fresh_ledger, host_repo):
    assert _engine(_ctx(fresh_ledger, "/no/such/repo", "feature/F8", "F8", claim={}))["verdict"] == "escalate"


def test_ac9_canary_always_not_done(fresh_ledger, host_repo):
    from govengine.engine import GovernanceEngine
    repo, br = _repo(host_repo, "F9", {"src/other.py": "x=1\n"})            # deliberately incomplete
    ctx = _ctx(fresh_ledger, repo, br, "F9", claim={})
    status = GovernanceEngine(ctx.manager).canary_status(ctx)
    assert status["healthy"] is True and status["actual"] == "not_done"


def test_ac10_high_stakes_requires_signature(fresh_ledger, host_repo):
    repo, br = _repo(host_repo, "F10", {"src/login.py": LOGIN, "src/test_login.py": REAL_TEST,
                                        "src/test_regress.py": REGRESS, "requirements.txt": "x\n"})
    ctx = _ctx(fresh_ledger, repo, br, "F10",
               contract={"scope": {"files": ["src/login.py"]}, "contracts": [{"name": "c", "status": "done"}],
                         "test_file": "src/test_login.py", "regression_file": "src/test_regress.py"},
               claim={"files_touched": ["src/login.py", "src/test_login.py", "src/test_regress.py", "requirements.txt"],
                      "tests_passed": True})
    r = _engine(ctx)
    assert r["stakes"] == "high" and r["verdict"] == "escalate"


def test_ac11_verdict_recorded_event(fresh_ledger, host_repo):
    from manager.core import ThorManager
    mgr = ThorManager(fresh_ledger)
    repo, br = _repo(host_repo, "F11", _green_files())
    _engine(_ctx(fresh_ledger, repo, br, "F11", manager=mgr))
    assert any(e["event_type"] == "verdict.computed" for e in mgr.eventlog.all_events())


def test_ac12_adversarial_no_false_done(fresh_ledger, host_repo):
    repo, br = _repo(host_repo, "F12", {"src/login.py": LOGIN, "src/test_login.py": REAL_TEST,
                                        "src/test_regress.py": REGRESS, "src/sneak.py": "S=1\n"})
    r = _engine(_ctx(fresh_ledger, repo, br, "F12",
                     claim={"files_touched": ["src/login.py", "src/test_login.py", "src/test_regress.py"],
                            "tests_passed": True}))
    assert r["verdict"] != "done" and r["divergence"]["found"]
