"""
G3 — the LIVE FLOW-A build loop in the control plane (sdlc/build_driver). Proves the keystone:
a `ready` feature, driven through the control plane's ONE Manager, flows building -> in_qa ->
(done) -> a Signature-3 MERGE card + awaiting_signature — the exact card service._drive_merge needs.

The cook here is a deterministic ScriptedCook (no frontier call) so the LOOP wiring is proven free +
fast; the real-Claude cook on the same BuildStage path is proven elsewhere. Single-writer: every state
change goes through the Manager, so the hash-chain stays intact (H6). Deferred (live: room + Postgres).
"""
import json
import os
import subprocess

import pytest

pytestmark = pytest.mark.deferred

LOGIN = "def check(pw):\n    return len(pw) >= 8\n"
REAL_TEST = ("import sys; sys.path.insert(0,'src')\nfrom login import check\n"
             "assert check('abcdefgh') is True\nassert check('x') is False\nprint('ok')\n")


def _git(repo, *a):
    return subprocess.run(["git", "-C", repo, *a], capture_output=True, text=True)


def _base_repo(repo):
    open(os.path.join(repo, "README"), "w").write("base\n")
    _git(repo, "add", "-A")
    _git(repo, "-c", "user.email=a@b", "-c", "user.name=a", "commit", "-q", "-m", "base")
    _git(repo, "branch", "-M", "main")


def test_g3_loop_drives_ready_feature_to_merge_card(fresh_ledger, host_repo, monkeypatch):
    """run_feature on a `ready` feature → building → in_qa → awaiting_signature + a merge card whose
    payload carries repo/branch/snapshot_sha (exactly what the cockpit Sign → _drive_merge consumes)."""
    from cook.agent import ScriptedCook
    from manager.core import ThorManager
    from sdlc import build_driver, stages

    monkeypatch.delenv("THOR_COOK", raising=False)        # gated path = deterministic ScriptedCook
    _base_repo(host_repo)
    mgr = ThorManager(fresh_ledger)

    # a feature on the board, marked ready by the human (the loop's trigger)
    fid = "G3F"
    mgr.add_feature(fid, "Login length check", '{"acceptance_criteria":["len>=8 passes, short fails"]}', 0)
    mgr.set_feature_status(fid, "ready")

    # the cook the loop will drive: one in-scope write that satisfies the planted test
    cook = ScriptedCook([
        {"name": "write_file", "args": {"path": "src/login.py", "content": LOGIN}},
        {"name": "write_file", "args": {"path": "src/test_login.py", "content": REAL_TEST}},
    ])

    # slice the loop's feature so the cook's files are in-scope + the planted test is the contract test
    feat = {"feature_id": fid, "title": "Login length check"}
    real_slice = build_driver._slice_for(feat)
    real_slice.update({"scope_files": ["src/login.py", "src/test_login.py"],
                       "planned_test": "src/test_login.py", "regression_file": "src/test_login.py"})
    monkeypatch.setattr(build_driver, "_slice_for", lambda f: real_slice)

    # drive BuildStage with our scripted cook (the loop calls execute(); inject the cook the same way)
    _orig_execute = stages.BuildStage.execute
    monkeypatch.setattr(stages.BuildStage, "execute",
                        lambda self, **kw: _orig_execute(self, cook=cook, **kw))

    verdict = build_driver.run_feature(mgr, {"feature_id": fid, "title": "Login length check"}, host_repo)

    assert verdict == "done", f"expected a done verdict, got {verdict}"
    # the feature is now awaiting the human's signature
    frow = next(f for f in mgr.list_features() if f["feature_id"] == fid)
    assert frow["status"] == "awaiting_signature", frow

    # a merge card was raised with the payload _drive_merge consumes
    cards = [json.loads(e["payload"]) for e in mgr.eventlog.all_events()
             if e["event_type"] == "card.raised"]
    merge = next(c for c in cards if c["type"] == "merge" and c["feature_id"] == fid)
    p = merge["payload"]
    assert p["repo"] == host_repo and p["branch"] == f"feature/{fid}", p
    assert p.get("snapshot_sha"), "merge card must carry the snapshot for the R9 freshness gate"


def test_g3_loop_returns_unproven_work_to_queue(fresh_ledger, host_repo, monkeypatch):
    """A cook that does NOT satisfy the test → verdict not_done → NO merge card, feature back to `ready`.
    THOR never raises a Signature-3 card for unproven work — the moat holds inside the loop too."""
    from cook.agent import ScriptedCook
    from manager.core import ThorManager
    from sdlc import build_driver, stages

    monkeypatch.delenv("THOR_COOK", raising=False)
    _base_repo(host_repo)
    mgr = ThorManager(fresh_ledger)
    fid = "G3X"
    mgr.add_feature(fid, "Broken login", "{}", 0)
    mgr.set_feature_status(fid, "ready")

    # the cook writes code that FAILS the planted test (returns the wrong answer)
    cook = ScriptedCook([
        {"name": "write_file", "args": {"path": "src/login.py", "content": "def check(pw):\n    return True\n"}},
        {"name": "write_file", "args": {"path": "src/test_login.py", "content": REAL_TEST}},
    ])
    real_slice = build_driver._slice_for({"feature_id": fid, "title": "Broken login"})
    real_slice.update({"scope_files": ["src/login.py", "src/test_login.py"],
                       "planned_test": "src/test_login.py", "regression_file": "src/test_login.py"})
    monkeypatch.setattr(build_driver, "_slice_for", lambda f: real_slice)
    _orig_execute = stages.BuildStage.execute
    monkeypatch.setattr(stages.BuildStage, "execute",
                        lambda self, **kw: _orig_execute(self, cook=cook, **kw))

    verdict = build_driver.run_feature(mgr, {"feature_id": fid, "title": "Broken login"}, host_repo)

    assert verdict != "done", "a failing cook must not yield a done verdict"
    frow = next(f for f in mgr.list_features() if f["feature_id"] == fid)
    assert frow["status"] == "ready", f"unproven work returns to the queue, got {frow['status']}"
    merge_cards = [json.loads(e["payload"]) for e in mgr.eventlog.all_events()
                   if e["event_type"] == "card.raised" and json.loads(e["payload"])["type"] == "merge"
                   and json.loads(e["payload"])["feature_id"] == fid]
    assert not merge_cards, "NO merge card may be raised for unproven work"
