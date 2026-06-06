"""
ONE-TIME smoke demonstration of the Development-Governance Engine (Module 6) — THE MOAT.

Headline (PRD §15): AC-2 + AC-8 + AC-12 — a fabricated claim is caught (divergence), the engine
never returns a false `done` even when its inputs fail (fail-closed), and an adversarial gaming
suite cannot get a `done`. Runs against REAL git repos + REAL test execution + the REAL Manager
EventLog (Postgres).

NOT the formal proving suite (Rule 2). No faked results (Rule 11): real git SHAs, real exit codes.

Run (inside the WSL venv, from ~/thor-enterprise):  python tools/smoke_govengine.py
"""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
os.chdir(REPO)

import docker

from govengine.engine import GovernanceEngine, VerdictContext
from manager import db, pg
from manager.core import ThorManager

LOGIN = "def login(u, p):\n    return u == 'a' and p == 'b'\n"
TEST_LOGIN = ("import sys; sys.path.insert(0, 'src')\n"
              "from login import login\n"
              "assert login('a', 'b') is True\nassert login('x', 'y') is False\nprint('ok')\n")
REGRESS = "assert 1 + 1 == 2\n"
TEST_FAKE = "assert True\n"                      # hollow: no reference to the feature, trivial assert
TEST_PKG = "import json\nd = json.load(open('package.json'))\nassert 'name' in d\n"


def git(repo, *args):
    return subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True)


def new_repo(name: str) -> str:
    repo = REPO / ".smoke" / f"ge-{name}"
    if repo.exists():
        shutil.rmtree(repo)
    repo.mkdir(parents=True)
    git(str(repo), "init", "-q", "-b", "main")
    git(str(repo), "-c", "user.email=h@t", "-c", "user.name=h", "commit", "--allow-empty", "-q", "-m", "seed")
    return str(repo)


def commit(repo, branch, files: dict, msg):
    git(repo, "checkout", "-q", "-b", branch)
    for rel, content in files.items():
        p = os.path.join(repo, rel)
        os.makedirs(os.path.dirname(p) or repo, exist_ok=True)
        open(p, "w").write(content)
    git(repo, "add", "-A")
    git(repo, "-c", "user.email=c@t", "-c", "user.name=c", "commit", "-q", "-m", msg)


def file_hash(repo, rel):
    p = os.path.join(repo, rel)
    return hashlib.sha256(open(p, "rb").read()).hexdigest() if os.path.exists(p) else None


def main() -> int:
    results: dict[str, bool] = {}
    client = docker.from_env()
    try:
        pg.start(client)
        conn = db.connect()
        db.init_schema(conn)
        with conn.cursor() as cur:
            cur.execute("TRUNCATE eventlog, rooms, cards, features")
        mgr = ThorManager(conn)
        engine = GovernanceEngine(mgr)

        def window():
            lo = mgr.eventlog.count()
            return (lo, lo + 1000)

        # ---------- happy path (a genuine done) ----------
        print("== happy path — a genuine done ==")
        r = new_repo("happy")
        commit(r, "feature/F1", {"src/login.py": LOGIN, "test_login.py": TEST_LOGIN,
                                 "test_regress.py": REGRESS}, "implement login [F1]")
        ctx_happy = VerdictContext("F1", "feature/F1", r,
            contract={"scope": {"files": ["src/login.py"]}, "contracts": [{"name": "c1", "status": "done"}],
                      "test_file": "test_login.py", "regression_file": "test_regress.py"},
            claim={"files_touched": ["src/login.py", "test_login.py", "test_regress.py"],
                   "tests_passed": True}, commit_window=window())
        v = engine.run_verdict(ctx_happy)
        results["happy → done"] = v["verdict"] == "done"
        print(f"   verdict={v['verdict']} probes={ {k: p['pass'] for k, p in v['probes'].items()} }")

        # ---------- AC-1 incomplete → not_done with M3 blocker ----------
        print("== AC-1 — genuinely incomplete (contracted file untouched) → not_done (M3) ==")
        r = new_repo("ac1")
        commit(r, "feature/F2", {"src/login.py": LOGIN, "test_login.py": TEST_LOGIN,
                                 "test_regress.py": REGRESS}, "partial [F2]")
        v = engine.run_verdict(VerdictContext("F2", "feature/F2", r,
            contract={"scope": {"files": ["src/login.py", "src/extra.py"]},
                      "contracts": [{"name": "c1", "status": "open"}],
                      "test_file": "test_login.py", "regression_file": "test_regress.py"},
            commit_window=window()))
        blk = [b["probe"] for b in v["blockers"]]
        results["AC-1 incomplete → not_done (M3)"] = v["verdict"] == "not_done" and "M3" in blk
        print(f"   verdict={v['verdict']} blockers={blk}")

        # ---------- AC-2 fabricated claim → divergence → escalate ----------
        print("== AC-2 — fabricated claim caught by divergence ==")
        r = new_repo("ac2")
        commit(r, "feature/F3", {"src/login.py": LOGIN, "test_login.py": TEST_LOGIN,
                                 "test_regress.py": REGRESS}, "implement login [F3]")
        v = engine.run_verdict(VerdictContext("F3", "feature/F3", r,
            contract={"scope": {"files": ["src/login.py"]}, "contracts": [{"name": "c1", "status": "done"}],
                      "test_file": "test_login.py", "regression_file": "test_regress.py"},
            claim={"files_touched": ["src/validation.py"], "tests_passed": True},  # LIE: never touched
            commit_window=window()))
        results["AC-2 fabricated claim → not done (divergence)"] = (
            v["verdict"] != "done" and v["divergence"]["found"])
        print(f"   verdict={v['verdict']} divergence={v['divergence']['signals']}")

        # ---------- AC-3 hollow fake test → not_done ----------
        print("== AC-3 — passing-but-hollow fake test → not_done ==")
        r = new_repo("ac3")
        commit(r, "feature/F4", {"src/feat.py": "def feat():\n    return 1\n", "test_fake.py": TEST_FAKE,
                                 "test_regress.py": REGRESS}, "implement feat [F4]")
        v = engine.run_verdict(VerdictContext("F4", "feature/F4", r,
            contract={"scope": {"files": ["src/feat.py"]}, "contracts": [{"name": "c1", "status": "done"}],
                      "test_file": "test_fake.py", "regression_file": "test_regress.py"},
            commit_window=window()))
        m1 = v["probes"]["M1"]
        results["AC-3 hollow test → not_done"] = v["verdict"] == "not_done" and not m1["pass"]
        print(f"   verdict={v['verdict']} M1={m1}")

        # ---------- AC-4 CI passes but diff mismatch → escalate (conflict) ----------
        print("== AC-4 — verifier+contracts say done but diff mismatch → escalate (conflict) ==")
        r = new_repo("ac4")
        commit(r, "feature/F5", {"src/login.py": LOGIN, "test_login.py": TEST_LOGIN,
                                 "test_regress.py": REGRESS}, "implement [F5]")
        v = engine.run_verdict(VerdictContext("F5", "feature/F5", r,
            contract={"scope": {"files": ["src/login.py", "src/missing.py"]},
                      "contracts": [{"name": "c1", "status": "done"}],   # contracts say done...
                      "test_file": "test_login.py", "regression_file": "test_regress.py"},
            commit_window=window()))                                      # ...but missing.py untouched
        results["AC-4 conflict → escalate"] = v["verdict"] == "escalate" and "conflict" in v["reason"]
        print(f"   verdict={v['verdict']} reason={v['reason']}")

        # ---------- AC-5 read-only ----------
        print("== AC-5 — running the verdict changes nothing (read-only) ==")
        before = file_hash(ctx_happy.repo, "src/login.py")
        engine.run_verdict(ctx_happy)
        after = file_hash(ctx_happy.repo, "src/login.py")
        clean = git(ctx_happy.repo, "status", "--porcelain").stdout.strip()
        results["AC-5 read-only (no changes)"] = (before == after) and clean == ""
        print(f"   file unchanged={before == after}  git status clean={clean == ''!r}")

        # ---------- AC-6 determinism ----------
        print("== AC-6 — same snapshot → identical verdict (replay) ==")
        a = engine.run_verdict(ctx_happy)
        b = engine.run_verdict(ctx_happy)
        results["AC-6 deterministic replay"] = (a["deterministic_hash"] == b["deterministic_hash"]
                                                and a["verdict"] == b["verdict"])
        print(f"   hash a==b: {a['deterministic_hash'] == b['deterministic_hash']}")

        # ---------- AC-7 freshness ----------
        print("== AC-7 — a stale verdict (branch changed) does not count ==")
        prior = engine.run_verdict(ctx_happy)
        fresh_now = engine.is_fresh(prior, ctx_happy)
        commit(ctx_happy.repo, "feature/F1b", {"src/login.py": LOGIN + "# tweak\n"}, "tweak [F1]")
        git(ctx_happy.repo, "checkout", "-q", "feature/F1")
        git(ctx_happy.repo, "merge", "-q", "feature/F1b")           # branch HEAD moves
        stale_after = engine.is_fresh(prior, ctx_happy)
        results["AC-7 freshness (stale invalidated)"] = fresh_now and not stale_after
        print(f"   fresh_before={fresh_now} fresh_after_change={stale_after}")

        # ---------- AC-8 fail-closed ----------
        print("== AC-8 — git/audit unreadable → escalate, never done (fail-closed) ==")
        v = engine.run_verdict(VerdictContext("F9", "feature/F9", "/nonexistent-repo",
            contract={"scope": {"files": []}, "contracts": []}, commit_window=window()))
        results["AC-8 fail-closed (never false done)"] = v["verdict"] == "escalate"
        print(f"   verdict={v['verdict']} reason={v['reason']}")

        # ---------- AC-9 canary ----------
        print("== AC-9 — the canary (deliberately incomplete) always verdicts not_done ==")
        r = new_repo("canary")
        cstat = engine.canary_status(VerdictContext("CANARY", "main", r,
            contract={"scope": {"files": []}, "contracts": []}, commit_window=window()))
        results["AC-9 canary not_done (healthy)"] = cstat["healthy"] and cstat["actual"] == "not_done"
        print(f"   canary={cstat}")

        # ---------- AC-10 high-stakes ----------
        print("== AC-10 — high-stakes change (dep manifest) requires a human signature ==")
        r = new_repo("ac10")
        commit(r, "feature/F10", {"package.json": '{"name":"thor-demo"}', "test_pkg.py": TEST_PKG,
                                  "test_regress.py": REGRESS}, "bump deps [F10]")
        v = engine.run_verdict(VerdictContext("F10", "feature/F10", r,
            contract={"scope": {"files": ["package.json"]}, "contracts": [{"name": "c1", "status": "done"}],
                      "test_file": "test_pkg.py", "regression_file": "test_regress.py"},
            claim={"files_touched": ["package.json", "test_pkg.py", "test_regress.py"],
                   "tests_passed": True}, commit_window=window()))
        results["AC-10 high-stakes → escalate"] = v["verdict"] == "escalate" and v["stakes"] == "high"
        print(f"   verdict={v['verdict']} stakes={v['stakes']}")

        # ---------- AC-11 recorded events ----------
        print("== AC-11 — every verdict + divergence is a recorded event ==")
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM eventlog WHERE event_type='verdict.computed'")
            n_verdicts = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM eventlog WHERE event_type='divergence.detected'")
            n_div = cur.fetchone()[0]
        results["AC-11 verdicts recorded as events"] = n_verdicts >= 10 and n_div >= 1
        print(f"   verdict.computed events={n_verdicts}  divergence.detected events={n_div}")

        # ---------- AC-12 adversarial: no gaming gets a done ----------
        print("== AC-12 — adversarial gaming suite cannot obtain a false done ==")
        # gamed gate: a clean-looking feature, but a claim-gate hit in the work window (R2)
        r = new_repo("gamed")
        commit(r, "feature/F12", {"src/login.py": LOGIN, "test_login.py": TEST_LOGIN,
                                  "test_regress.py": REGRESS}, "implement [F12]")
        lo = mgr.eventlog.count()
        mgr.eventlog.append("claim_gate.hit", {"feature_id": "F12", "detail": "tried to game the gate"})
        gamed = engine.run_verdict(VerdictContext("F12", "feature/F12", r,
            contract={"scope": {"files": ["src/login.py"]}, "contracts": [{"name": "c1", "status": "done"}],
                      "test_file": "test_login.py", "regression_file": "test_regress.py"},
            claim={"files_touched": ["src/login.py"], "tests_passed": True},
            commit_window=(lo, lo + 100)))
        adversarial_verdicts = {
            "fabricated_claim": results["AC-2 fabricated claim → not done (divergence)"],
            "fake_test": results["AC-3 hollow test → not_done"],
            "gamed_gate": gamed["verdict"] != "done",
        }
        results["AC-12 no gaming gets a done"] = all(adversarial_verdicts.values())
        print(f"   gamed_gate verdict={gamed['verdict']}  adversarial={adversarial_verdicts}")

        print("\n==== GOVERNANCE-ENGINE SMOKE RESULTS (real, observed) ====")
        for k, val in results.items():
            print(f"   [{'PASS' if val else 'FAIL'}] {k}")
        headline = (results["AC-2 fabricated claim → not done (divergence)"]
                    and results["AC-8 fail-closed (never false done)"]
                    and results["AC-12 no gaming gets a done"])
        print(f"\n   HEADLINE (AC-2 + AC-8 + AC-12: the moat holds — honest, un-fakeable done): "
              f"{'PASS' if headline else 'FAIL'}")
        return 0 if all(results.values()) else 1
    finally:
        print("== teardown ==")
        pg.stop(client)


if __name__ == "__main__":
    sys.exit(main())
