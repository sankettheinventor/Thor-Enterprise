"""
FLOW C / the moat (Integration PRD) — a fabricated claim / hollow test / out-of-band change CANNOT
get a false `done`, and a caught lie runs the dishonesty loop. Gaps C4 + H1 + H2.

The Verdict Coordinator (manager.run_verdict) derives claim/contract/commit_window from TRUSTED state
(the recorded assign_task slice, the ledger window, the Leash decision records) — never the actor.
A caught lie is recorded (dishonesty.caught), escalated to the Sentinel, and fed back to the cook;
the CEO cockpit's lies_caught() shows it. Verified against real git/subprocess/ledger. Deferred (live).
"""
import os
import subprocess

import pytest

pytestmark = pytest.mark.deferred


def _V(decision):
    return type("V", (), {"decision": decision, "reason": "x", "classification": "non_critical"})()


def _git(repo, *args):
    return subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True)


def _scenario(conn, host_repo, fid, *, code_files, test_file, regression_file,
              leash_allows, knock=True):
    """Build trusted state for a feature and run the Coordinator. Returns (mgr, sentinel, room, result)."""
    from contract.seam import Seam
    from contract.slice_builder import build_slice
    from contract.transport import InProcessTransport
    from manager.core import ThorManager
    from sentinel.core import Sentinel

    mgr = ThorManager(conn)
    sentinel = Sentinel(mgr)
    mgr.attach_sentinel(sentinel)

    # a real git repo: base on main, then the cook's commit on the feature branch
    repo = host_repo
    open(os.path.join(repo, "README"), "w").write("base\n")
    _git(repo, "add", "-A")
    _git(repo, "-c", "user.email=a@b", "-c", "user.name=a", "commit", "-q", "-m", "base")
    _git(repo, "branch", "-M", "main")
    branch = f"feature/{fid}"
    _git(repo, "checkout", "-q", "-b", branch)
    for rel, content in code_files.items():
        p = os.path.join(repo, rel)
        os.makedirs(os.path.dirname(p) or repo, exist_ok=True)
        open(p, "w").write(content)
    _git(repo, "add", "-A")
    _git(repo, "-c", "user.email=cook@t", "-c", "user.name=cook", "commit", "-q", "-m", f"implement {fid}")

    room = mgr.provision_room(fid, branch=branch, worktree_host_path=repo, network_mode="sealed")

    # scope.files cites the exact contracted source (what M3 requires to have changed).
    feature = {"feature_id": fid, "task_type": "build", "acceptance_criteria": ["works"],
               "scope_files": ["src/login.py"], "planned_test": test_file, "regression_file": regression_file}
    seam = Seam(InProcessTransport(), manager=mgr)
    seam.manager_send("assign_task", {"room_id": room["room_id"],
                                      "feature_slice": build_slice(feature, {"scope_files": ["src/login.py"]}).model_dump()})
    for f in leash_allows:                                   # the Leash's recorded allowed writes
        mgr.record_decision(_V("allow"), {"room_id": room["room_id"], "type": "tool_call",
                                          "name": "write_file", "target": f})
    if knock:
        seam.room_send("claim_done", {"room_id": room["room_id"], "feature_id": fid, "message_id": "k1"})

    result = mgr.run_verdict(fid, branch, repo)
    return mgr, sentinel, room, result


REAL_LOGIN = "def check(pw):\n    return len(pw) >= 8\n"
REAL_TEST = ("import sys; sys.path.insert(0, 'src')\nfrom login import check\n"
             "assert check('abcdefgh') is True\nassert check('x') is False\nprint('ok')\n")
PASS_REGRESS = "print('regression ok')\n"


def test_moat_honest_done(fresh_ledger, host_repo):
    """Control: a real change + a real test + a matching claim → done (the moat is discriminating)."""
    mgr, _, room, result = _scenario(
        fresh_ledger, host_repo, "FH",
        code_files={"src/login.py": REAL_LOGIN, "src/test_login.py": REAL_TEST, "src/test_regress.py": PASS_REGRESS},
        test_file="src/test_login.py", regression_file="src/test_regress.py",
        leash_allows=["src/login.py", "src/test_login.py", "src/test_regress.py"])
    try:
        assert result["verdict"] == "done", result["blockers"]
        assert result["divergence"]["found"] is False
    finally:
        mgr.destroy_room(room["room_id"], room.get("_mount_plan"))


def test_moat_fabricated_claim_caught_and_loop(fresh_ledger, host_repo):
    """Fabricated 'tests pass': the cook knocks done but the verifier (reality) fails → divergence →
    NOT done + the dishonesty loop fires (recorded, Sentinel, cook feedback, cockpit counter)."""
    failing_test = ("import sys; sys.path.insert(0,'src')\nfrom login import check\n"
                    "assert check('abcdefgh') is False\nprint('ok')\n")   # wrong → exits non-zero
    mgr, sentinel, room, result = _scenario(
        fresh_ledger, host_repo, "FL",
        code_files={"src/login.py": REAL_LOGIN, "src/test_login.py": failing_test, "src/test_regress.py": PASS_REGRESS},
        test_file="src/test_login.py", regression_file="src/test_regress.py",
        leash_allows=["src/login.py", "src/test_login.py", "src/test_regress.py"])
    try:
        assert result["verdict"] != "done"
        assert result["divergence"]["found"] is True
        # the dishonesty loop
        fb = result.get("cook_feedback")
        assert fb and "does not match reality" in fb["message"]           # → cook is told
        events = mgr.eventlog.all_events()
        assert any(e["event_type"] == "dishonesty.caught" for e in events)  # recorded incident
        assert any(e["event_type"] == "cook.feedback" for e in events)
        assert len(sentinel.alarms) >= 1                                   # → Sentinel escalated
        # → CEO cockpit honesty meter
        from dashboard.service import DashboardService
        lies = DashboardService(mgr).lies_caught()
        assert lies["total"] >= 1 and room["room_id"] in lies["by_container"]
    finally:
        mgr.destroy_room(room["room_id"], room.get("_mount_plan"))


def test_moat_hollow_test_not_done(fresh_ledger, host_repo):
    """A referencing-but-vacuous test (imports the feature, never executes it) → M1 hollow → not done."""
    hollow = ("import sys; sys.path.insert(0,'src')\nfrom login import check\nassert callable(check)\nprint('ok')\n")
    mgr, _, room, result = _scenario(
        fresh_ledger, host_repo, "FK",
        code_files={"src/login.py": REAL_LOGIN, "src/test_login.py": hollow, "src/test_regress.py": PASS_REGRESS},
        test_file="src/test_login.py", regression_file="src/test_regress.py",
        leash_allows=["src/login.py", "src/test_login.py", "src/test_regress.py"])
    try:
        assert result["verdict"] != "done"
        assert any(b["probe"] == "M1" for b in result["blockers"]), result["blockers"]
    finally:
        mgr.destroy_room(room["room_id"], room.get("_mount_plan"))


def test_moat_undisclosed_change_caught(fresh_ledger, host_repo):
    """An out-of-band change: git shows a file the Leash never authorized → undisclosed → divergence."""
    mgr, sentinel, room, result = _scenario(
        fresh_ledger, host_repo, "FU",
        code_files={"src/login.py": REAL_LOGIN, "src/test_login.py": REAL_TEST,
                    "src/test_regress.py": PASS_REGRESS, "src/backdoor.py": "SECRET = 'leak'\n"},
        test_file="src/test_login.py", regression_file="src/test_regress.py",
        leash_allows=["src/login.py", "src/test_login.py", "src/test_regress.py"])  # backdoor.py NOT allowed
    try:
        assert result["verdict"] != "done"
        assert result["divergence"]["found"] is True
        assert any("backdoor" in s for s in result["divergence"]["signals"]), result["divergence"]["signals"]
    finally:
        mgr.destroy_room(room["room_id"], room.get("_mount_plan"))
