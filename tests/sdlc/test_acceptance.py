"""
The SDLC Stages — Acceptance Criteria AC-1..AC-12 (PRD §15).

PROVING PASS (Task 6). The transition/signature gates (now BOUND to verified Manager cards) prove
in-process; the Build/QA/Checker stage ACs verify over REAL sealed rooms. Deferred (live); run:
pytest -m deferred tests/sdlc.
"""
import os

import pytest

from sdlc.skills import FLOOR_SKILLS
from sdlc.transitions import MAX_QA_CYCLES, TransitionController

pytestmark = pytest.mark.deferred


def _approve(mgr, card_id, payload):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
    from wall.identity_stamper import _b64
    priv = Ed25519PrivateKey.generate()
    pub = _b64(priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw))
    return mgr.approve(card_id, _b64(priv.sign(mgr.card_material(card_id, payload).encode())), pub)


# ── transition / signature gates (in-process; the H9 binding) ───────────────
def test_ac1_order_enforced_no_skip_qa():
    ok, why = TransitionController().transition("F", "build", "verdict")
    assert ok is False and "QA" in why


def test_ac5_no_build_before_plan_signed(fresh_ledger):
    from manager.core import ThorManager
    mgr = ThorManager(fresh_ledger)
    tc = TransitionController(manager=mgr)
    assert tc.sign_plan("F", card_id=None) is False                  # no verified card → no Sig 1
    assert tc.transition("F", "genesis", "build")[0] is False
    card = mgr.raise_card("plan", "F", {"feature_id": "F"})
    _approve(mgr, card, {"feature_id": "F"})
    assert tc.sign_plan("F", card_id=card) is True                   # verified → Sig 1 flips
    assert tc.transition("F", "genesis", "build")[0] is True


def test_ac6_qa_fail_loops_only_after_signature2(fresh_ledger):
    from manager.core import ThorManager
    mgr = ThorManager(fresh_ledger)
    tc = TransitionController(manager=mgr)
    assert tc.on_qa_result("F", False) == "ticket"
    assert tc.authorize_ticket("F", card_id=None) is False           # needs Signature 2
    card = mgr.raise_card("qa_fail", "F", {"feature_id": "F"}, held=True)
    _approve(mgr, card, {"feature_id": "F"})
    assert tc.authorize_ticket("F", card_id=card) is True


def test_ac8_floor_skills_always_present():
    from sdlc.stages import BuildStage, QAStage
    for stage in (BuildStage(), QAStage()):
        assert all(f in stage.compose_brain().all_skills for f in FLOOR_SKILLS)


def test_ac9_new_stage_added_without_regression():
    from sdlc.anatomy import Stage
    from sdlc.stages import BuildStage

    class DocStage(Stage):
        name = "doc"
        def mandate(self): return "write docs"
        def edge_check(self, out): return True, "ok"
        def run(self, **kw): return {"ok": True}

    out = DocStage().execute()
    assert out["ok"] and out["_edge_ok"] and BuildStage().name == "build"   # existing stage untouched


def test_ac10_capability_gap_raises_card(fresh_ledger):
    from manager.core import ThorManager
    from sdlc.bridge import FindingsTicketBridge
    mgr = ThorManager(fresh_ledger)
    card = FindingsTicketBridge(mgr).raise_capability_gap_card("F", "ml-skill")
    assert mgr._get_card(card)["type"] == "capability_gap"


def test_ac11_build_qa_loop_bounded():
    tc = TransitionController()
    res = [tc.on_qa_result("F", False) for _ in range(MAX_QA_CYCLES)]
    assert res[-1] == "escalate_operator"


def test_ac12_three_signatures_enforced(fresh_ledger):
    from manager.core import ThorManager
    mgr = ThorManager(fresh_ledger)
    tc = TransitionController(manager=mgr)
    assert tc.sign_plan("F", None) is False and tc.authorize_ticket("F", None) is False   # Sig 1 + Sig 2 gated
    card = mgr.raise_card("merge", "F", {"feature_id": "F"})                                # Sig 3 gate
    assert mgr.is_card_approved(card) is False
    _approve(mgr, card, {"feature_id": "F"})
    assert mgr.is_card_approved(card) is True


# ── stage ACs (real sealed rooms) ───────────────────────────────────────────
def _feat(fid, code_file, code, planned_test):
    return {"feature_id": fid, "title": fid, "code_file": code_file, "planned_test": planned_test,
            "scope_files": ("src/",),
            "code_files": {code_file: code,
                           planned_test: f"import sys;sys.path.insert(0,'src')\nprint('ok')\n"}}


def test_ac2_qa_independent_of_build(fresh_ledger, host_repo):
    from manager.core import ThorManager
    from sdlc.stages import BuildStage, QAStage
    mgr = ThorManager(fresh_ledger)
    feat = _feat("F47", "src/calc.py", "def add(a, b):\n    return a + b\n", "src/test_calc.py")
    bout = BuildStage(capability_tags=["x"]).execute(feature=feat, repo=host_repo, manager=mgr)
    qout = None
    try:
        qout = QAStage().execute(feature=feat, repo=host_repo, branch=bout["branch"],
                                 build_room_id=bout["room_id"], manager=mgr)
        assert qout["independent"] and qout["qa_room_id"] != bout["room_id"]
    finally:
        mgr.destroy_room(bout["room_id"], bout["_room"].get("_mount_plan"))


def test_ac3_qa_writes_new_test_catches_edge_case(fresh_ledger, host_repo):
    from manager.core import ThorManager
    from sdlc.stages import BuildStage, QAStage
    mgr = ThorManager(fresh_ledger)
    feat = _feat("F48", "src/calc.py", "def div(a, b):\n    return a / b\n", "src/test_calc.py")
    bout = BuildStage().execute(feature=feat, repo=host_repo, manager=mgr)
    try:
        qout = QAStage().execute(feature=feat, repo=host_repo, branch=bout["branch"],
                                 build_room_id=bout["room_id"], manager=mgr)
        assert qout["new_tests"] and qout["bugs"], qout          # adversarial QA caught div-by-zero
    finally:
        mgr.destroy_room(bout["room_id"], bout["_room"].get("_mount_plan"))


def test_ac4_qa_findings_in_db_not_memory(fresh_ledger, host_repo):
    from manager.core import ThorManager
    from sdlc.stages import BuildStage, QAStage
    mgr = ThorManager(fresh_ledger)
    feat = _feat("F49", "src/calc.py", "def div(a, b):\n    return a / b\n", "src/test_calc.py")
    bout = BuildStage().execute(feature=feat, repo=host_repo, manager=mgr)
    try:
        QAStage().execute(feature=feat, repo=host_repo, branch=bout["branch"],
                          build_room_id=bout["room_id"], manager=mgr)
        assert len(mgr.list_bugs("F49")) >= 1                    # findings are DB rows, not agent memory
    finally:
        mgr.destroy_room(bout["room_id"], bout["_room"].get("_mount_plan"))


def test_ac7_checker_readonly_yet_findings(fresh_ledger, host_repo):
    from manager.core import ThorManager
    from sdlc.stages import CheckerStage
    mgr = ThorManager(fresh_ledger)
    os.makedirs(os.path.join(host_repo, "src"), exist_ok=True)
    open(os.path.join(host_repo, "src/legacy.py"), "w").write("x = eval('1+1')  # TODO fix\n")
    out = CheckerStage().execute(repo=host_repo, manager=mgr)
    assert out["repo_unchanged"] is True and len(out["findings"]) >= 1
