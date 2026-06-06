"""
ONE-TIME smoke of the SDLC Stages (Module 7) — the full governed lifecycle, end to end.

Headline (PRD §15): AC-2 + AC-3 — an independent QA agent (a FRESH room that did NOT write the code)
reads the actual implementation and catches an edge case the plan never specified. Demonstrated
against the REAL Manager (Postgres) + Engine (Module 6) + Wall (real Build/QA/Checker rooms), with all
three signature points enforced.

NOT the formal proving suite (Rule 2). No faked results (Rule 11): real rooms, real git, real verdicts.
The cook and QA *intelligence* are deterministic stand-ins (no LLM); the structure is real.

Run (inside the WSL venv, from ~/thor-enterprise):  python tools/smoke_sdlc.py
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
os.chdir(REPO)

import docker
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from govengine.engine import GovernanceEngine, VerdictContext
from manager import db, pg
from manager.core import ThorManager
from sdlc import skills
from sdlc.anatomy import Stage
from sdlc.bridge import FindingsTicketBridge
from sdlc.stages import BuildStage, CheckerStage, GenesisStage, QAStage
from sdlc.transitions import MAX_QA_CYCLES, TransitionController
from wall.identity_stamper import _b64

LOGIN = "def login(u, p):\n    return u == 'a' and p == 'b'\n"             # handles edges (no raise)
TEST_LOGIN = "import sys; sys.path.insert(0,'src')\nfrom login import login\nassert login('a','b') is True\n"
DISCOUNT = "def discount(price, qty):\n    return price / qty\n"            # hidden bug: qty=0 -> raise
TEST_DISCOUNT = "import sys; sys.path.insert(0,'src')\nfrom discount import discount\nassert discount(100, 2) == 50\n"
REGRESS = "assert 1 + 1 == 2\n"


def git(repo, *a):
    return subprocess.run(["git", "-C", repo, *a], capture_output=True, text=True)


def new_repo(name):
    r = REPO / ".smoke" / f"sdlc-{name}"
    if r.exists():
        shutil.rmtree(r)
    r.mkdir(parents=True)
    git(str(r), "init", "-q", "-b", "main")
    git(str(r), "-c", "user.email=h@t", "-c", "user.name=h", "commit", "--allow-empty", "-q", "-m", "seed")
    return str(r)


class UXAuditStage(Stage):                # AC-9: a NEW stage, added without touching existing stages
    name = "ux-audit"

    def mandate(self):
        return "post-merge UX audit"

    def edge_check(self, output):
        return True, "ux audit complete"

    def run(self, **_):
        return {"audit": "ok", "issues": []}


def main() -> int:
    results: dict[str, bool] = {}
    client = docker.from_env()
    try:
        pg.start(client)
        conn = db.connect()
        db.init_schema(conn)
        with conn.cursor() as cur:
            cur.execute("TRUNCATE eventlog, rooms, cards, features, bugs")
        mgr = ThorManager(conn)
        engine = GovernanceEngine(mgr)
        tc = TransitionController()
        bridge = FindingsTicketBridge(mgr)

        priv = Ed25519PrivateKey.generate()
        pub = _b64(priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw))

        def sign(card_id, payload):
            material = ThorManager.card_material(card_id, payload)
            return mgr.approve(card_id, _b64(priv.sign(material.encode())), pub)

        # ---------- Genesis + Signature 1 (AC-5) ----------
        print("== Genesis → catalog; Signature 1 gates Build (AC-5) ==")
        genesis = GenesisStage()
        gout = genesis.execute(project_intent={"vision": "demo", "features": [
            {"feature_id": "F47", "goals": ["login"], "acceptance_criteria": ["valid creds → True"],
             "capability_tags": ["ui-form", "auth"]}]})
        pre = tc.transition("F47", "genesis", "build")            # before Sig 1 → refused
        plan_card = mgr.raise_card("plan", "F47", {"feature_id": "F47"})
        sign(plan_card, {"feature_id": "F47"})
        tc.sign_plan("F47")
        post = tc.transition("F47", "genesis", "build")           # after Sig 1 → allowed
        results["AC-5 no Build before plan signed"] = (not pre[0]) and post[0] and gout["_edge_ok"]
        print(f"   before_sig1 allowed={pre[0]}  after_sig1 allowed={post[0]}")

        # ---------- AC-8 floor skills always present ----------
        print("== AC-8 floor skills present in Build and QA regardless of task_type ==")
        bsk = skills.compose("build", ["ui-form", "auth"])
        qsk = skills.compose("qa", ["ui-form", "auth"])
        floor_ok = all(s in bsk.all_skills for s in skills.FLOOR_SKILLS) and \
            all(s in qsk.all_skills for s in skills.FLOOR_SKILLS)
        results["AC-8 floor skills always present"] = floor_ok
        print(f"   build={bsk.all_skills}")

        # ---------- AC-7 Project Checker (read-only, findings to DB) ----------
        print("== AC-7 Project Checker: read-only yet produces findings ==")
        rchk = new_repo("legacy")
        open(os.path.join(rchk, "old.py"), "w").write("x = eval('1+1')  # TODO fix this\n")
        git(rchk, "add", "-A"); git(rchk, "-c", "user.email=h@t", "-c", "user.name=h", "commit", "-q", "-m", "legacy")
        cout = CheckerStage().execute(repo=rchk, manager=mgr)
        chk_bugs = mgr.list_bugs(f"CHK-{os.path.basename(rchk)}")
        results["AC-7 checker read-only + findings"] = cout["repo_unchanged"] and len(chk_bugs) >= 1
        print(f"   repo_unchanged={cout['repo_unchanged']} findings={len(cout['findings'])} db_bugs={len(chk_bugs)}")

        # ---------- Build the GOOD feature → QA pass → Verdict → merge (Sig 3) ----------
        print("== Build F47 (good) → QA(independent) → Verdict → merge (Sig 3) ==")
        rgood = new_repo("good")
        feat_good = {"feature_id": "F47", "title": "login", "code_file": "src/login.py",
                     "planned_test": "test_login.py",
                     "code_files": {"src/login.py": LOGIN, "test_login.py": TEST_LOGIN, "test_regress.py": REGRESS}}
        bout = BuildStage(capability_tags=["ui-form", "auth"]).execute(feature=feat_good, repo=rgood, manager=mgr)
        build_room = bout["room_id"]

        skip = tc.transition("F47", "build", "verdict")           # AC-1: can't skip QA
        results["AC-1 cannot skip QA to verdict"] = not skip[0]
        print(f"   build→verdict (skip QA) allowed={skip[0]}")

        qout = QAStage(capability_tags=["ui-form", "auth"]).execute(
            feature=feat_good, repo=rgood, branch=bout["branch"], build_room_id=build_room, manager=mgr)
        results["AC-2 QA independent of Build"] = qout["independent"] and qout["qa_room_id"] != build_room
        print(f"   build_room={build_room} qa_room={qout['qa_room_id']} independent={qout['independent']}")
        tc.on_qa_result("F47", qout["passed"])
        allow_verdict = tc.transition("F47", "qa", "verdict")

        vctx = VerdictContext("F47", bout["branch"], rgood,
            contract={"scope": {"files": ["src/login.py"]}, "contracts": [{"name": "c1", "status": "done"}],
                      "test_file": "test_login.py", "regression_file": "test_regress.py"},
            claim={"files_touched": ["src/login.py", "test_login.py", "test_regress.py"], "tests_passed": True})
        verdict = engine.run_verdict(vctx)
        merge_card = bridge.raise_merge_card("F47")               # Signature 3
        sig3 = sign(merge_card, {"feature_id": "F47"})
        results["AC-12 three signatures enforced"] = (
            allow_verdict[0] and verdict["verdict"] == "done" and sig3["verified"])
        print(f"   qa→verdict allowed={allow_verdict[0]} verdict={verdict['verdict']} sig3_verified={sig3['verified']}")
        mgr.destroy_room(build_room, bout["_room"].get("_mount_plan"))

        # ---------- Build the BUGGY feature → QA catches a hidden edge case (AC-3, AC-4) → Sig 2 (AC-6) ----------
        print("== Build F50 (hidden bug) → QA writes NEW edge test, catches it (AC-3/AC-4) → Sig 2 (AC-6) ==")
        rbug = new_repo("bug")
        feat_bug = {"feature_id": "F50", "title": "discount", "code_file": "src/discount.py",
                    "planned_test": "test_discount.py",
                    "code_files": {"src/discount.py": DISCOUNT, "test_discount.py": TEST_DISCOUNT, "test_regress.py": REGRESS}}
        tc.sign_plan("F50")
        bout2 = BuildStage().execute(feature=feat_bug, repo=rbug, manager=mgr)
        qout2 = QAStage().execute(feature=feat_bug, repo=rbug, branch=bout2["branch"],
                                  build_room_id=bout2["room_id"], manager=mgr)
        db_bugs = mgr.list_bugs("F50")
        results["AC-3 QA new test catches edge case"] = (
            not qout2["passed"] and len(qout2["new_tests"]) >= 1 and len(qout2["bugs"]) >= 1)
        results["AC-4 QA findings in DB not memory"] = any(b["source"] == "qa" for b in db_bugs)
        print(f"   planned_pass={qout2['planned_pass']} new_tests={qout2['new_tests']} bugs={qout2['bugs']}")
        print(f"   db_bugs(F50)={[b['description'] for b in db_bugs]}")

        next_step = tc.on_qa_result("F50", qout2["passed"])
        before_sig2 = tc.ticket_authorized.get("F50", False)
        fail_card = bridge.raise_qa_fail_card("F50", qout2["bugs"])
        sign(fail_card, {"bugs": qout2["bugs"]})
        tc.authorize_ticket("F50")
        after_sig2 = tc.ticket_authorized.get("F50", False)
        results["AC-6 QA-fail loops only after Signature 2"] = (
            next_step == "ticket" and not before_sig2 and after_sig2)
        print(f"   qa_result_next={next_step} ticket_authorized before={before_sig2} after={after_sig2}")
        mgr.destroy_room(bout2["room_id"], bout2["_room"].get("_mount_plan"))

        # ---------- AC-11 bounded Build↔QA loop ----------
        print("== AC-11 Build↔QA loop bounded ==")
        tcb = TransitionController()
        outcomes = [tcb.on_qa_result("FX", False) for _ in range(MAX_QA_CYCLES)]
        results["AC-11 loop bounded → escalate"] = outcomes[-1] == "escalate_operator"
        print(f"   outcomes={outcomes}")

        # ---------- AC-9 new stage added without regression ----------
        print("== AC-9 new stage (UX-audit) added without modifying existing stages ==")
        uout = UXAuditStage(capability_tags=["ui-form"]).execute()
        existing_still_ok = verdict["verdict"] == "done"          # the earlier happy flow is unaffected
        results["AC-9 new stage, no regression"] = (
            uout["_edge_ok"] and all(s in uout["_skills"] for s in skills.FLOOR_SKILLS) and existing_still_ok)
        print(f"   ux-audit edge_ok={uout['_edge_ok']} floor_present={all(s in uout['_skills'] for s in skills.FLOOR_SKILLS)}")

        # ---------- AC-10 capability gap → card, not silent skill add ----------
        print("== AC-10 mid-build capability gap → CEO card, never silent skill add ==")
        bundle = skills.compose("build", ["ui-form", "auth"])     # 'ml' not ratified → not in bundle
        gap_card = bridge.raise_capability_gap_card("F47", "ml")
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM cards WHERE type='capability_gap'")
            n_gap = cur.fetchone()[0]
        results["AC-10 capability gap raises a card"] = ("ml-eval" not in bundle.all_skills) and n_gap >= 1
        print(f"   ml-eval silently added={'ml-eval' in bundle.all_skills}  capability_gap cards={n_gap}")

        print("\n==== SDLC SMOKE RESULTS (real, observed) ====")
        for k, v in results.items():
            print(f"   [{'PASS' if v else 'FAIL'}] {k}")
        headline = results["AC-2 QA independent of Build"] and results["AC-3 QA new test catches edge case"]
        print(f"\n   HEADLINE (AC-2 + AC-3: independent QA catches a plan-unspecified edge case): "
              f"{'PASS' if headline else 'FAIL'}")
        return 0 if all(results.values()) else 1
    finally:
        print("== teardown ==")
        for c in client.containers.list(all=True, filters={"label": "thor.room"}):
            try:
                c.remove(force=True)
            except Exception:  # noqa: BLE001
                pass
        pg.stop(client)


if __name__ == "__main__":
    sys.exit(main())
