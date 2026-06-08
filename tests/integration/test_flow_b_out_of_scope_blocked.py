"""
FLOW B (Integration PRD §1) — an out-of-scope action is blocked mid-build.  Gap C1.

Proves the P3 promise against the REAL wired BuildStage: the cook's writes now route through the
per-room Leash BEFORE they execute. In-scope is written; out-of-scope NEVER touches disk; a
dependency manifest escalates and is held; a down governor fails closed. Every decision is an
event in the Manager's single ledger (T2). Verified against reality (disk + ledger), not asserted.

Deferred (live). Run:  pytest -m deferred tests/integration  (or `make prove`).
"""
import os

import pytest

pytestmark = pytest.mark.deferred


def _manager(fresh_ledger):
    from manager.core import ThorManager
    return ThorManager(fresh_ledger)


def _decided(mgr, kind):
    import json
    return [json.loads(e["payload"]) for e in mgr.eventlog.all_events() if e["event_type"] == kind]


def test_flow_B_out_of_scope_blocked(fresh_ledger, host_repo):
    """In-scope allowed; out-of-scope (forbidden) denied + never created; manifest escalated + held."""
    from sdlc.stages import BuildStage

    mgr = _manager(fresh_ledger)
    feature = {
        "feature_id": "FB1", "title": "login",
        "scope_files": ("src/",),                       # CTO-declared scope — plan-owned
        "code_files": {
            "src/login.py": "# in scope\n",             # allowed
            "infra/secrets.tf": "leak = true\n",        # forbidden + out of scope -> deny
            "package.json": '{"deps":{}}',              # dependency manifest -> escalate + hold
        },
    }
    out = BuildStage().run(feature=feature, repo=host_repo, manager=mgr)
    try:
        # the Leash's verdicts on each proposed write
        assert out["decisions"]["src/login.py"] == "allow"
        assert out["decisions"]["infra/secrets.tf"] == "deny"
        assert out["decisions"]["package.json"] == "escalate"

        # GROUND TRUTH on disk: only the allowed file exists; the blocked ones were never created
        assert os.path.exists(os.path.join(host_repo, "src/login.py"))
        assert not os.path.exists(os.path.join(host_repo, "infra/secrets.tf")), "out-of-scope write must never touch disk"
        assert not os.path.exists(os.path.join(host_repo, "package.json")), "escalated write must be held, not written"

        # every decision is in the Manager's single ledger: 3 decisions + 1 escalation-hold
        assert len(_decided(mgr, "action.decided")) == 3
        assert len(_decided(mgr, "action.escalated")) == 1
        assert mgr.eventlog.verify_chain() is True
    finally:
        mgr.destroy_room(out["room_id"], out["_room"].get("_mount_plan"))


def test_flow_B_governor_down_denies(fresh_ledger, host_repo, monkeypatch):
    """Fail-closed: if the governor (adapter) is unreachable, even an in-scope write is DENIED."""
    from adapters import agt_adapter
    from sdlc.stages import BuildStage

    def _boom(action):
        raise ConnectionError("governor unreachable")

    monkeypatch.setattr(agt_adapter, "check_action", _boom)

    mgr = _manager(fresh_ledger)
    feature = {"feature_id": "FB2", "title": "login", "scope_files": ("src/",),
               "code_files": {"src/login.py": "# in scope but governor is down\n"}}
    out = BuildStage().run(feature=feature, repo=host_repo, manager=mgr)
    try:
        assert out["decisions"]["src/login.py"] == "deny"
        assert not os.path.exists(os.path.join(host_repo, "src/login.py")), "governor-down must fail closed (no write)"
    finally:
        mgr.destroy_room(out["room_id"], out["_room"].get("_mount_plan"))
