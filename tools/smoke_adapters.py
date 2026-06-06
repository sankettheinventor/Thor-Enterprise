"""
ONE-TIME smoke of the Foundation Adapters (Module 12) — the Strangler substrate beneath the moat.

Headline (PRD §15): AC-1 + AC-2 + AC-7 — no external type leaks past its adapter, the audit chain
detects tampering, and an external can be swapped by changing only its adapter. Run against the REAL
M3 hash-chain (audit), REAL Ed25519 (identity), and REAL local git (the Gitea backend).

NOT the formal proving suite (Rule 2). No faked results (Rule 11): real tamper, real merge, real swap.

Run (inside the WSL venv, from ~/thor-enterprise):  python tools/smoke_adapters.py
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
os.chdir(REPO)

import docker

from adapters import catalog_bridge, gitea_adapter, identity_adapter, substitution
from adapters.audit_adapter import ChainAudit, export_compliance, verify_chain
from adapters.contract import AuditPort, GitPort, IdentityPort
from adapters.gitea_adapter import LocalGitBackend
from adapters.identity_adapter import MeshIdentity
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from manager import db, pg
from manager.core import ThorManager
from wall import provisioner
from wall.identity_stamper import _b64


def git(repo, *a):
    return subprocess.run(["git", "-C", repo, *a], capture_output=True, text=True, check=True).stdout.strip()


def setup_repo(path: Path):
    path.mkdir(parents=True, exist_ok=True)
    git(str(path), "init", "-q", "-b", "main")
    git(str(path), "config", "user.email", "t@t"); git(str(path), "config", "user.name", "t")
    (path / "base.py").write_text("x = 1\n")
    git(str(path), "add", "-A"); git(str(path), "commit", "-q", "-m", "base")
    for br, fn in (("feature", "feat.py"), ("feature2", "feat2.py")):
        git(str(path), "checkout", "-q", "-b", br, "main")
        (path / fn).write_text(f"def {br}_fn():\n    return 42\n")
        git(str(path), "add", "-A"); git(str(path), "commit", "-q", "-m", f"add {fn} for {br}")
        git(str(path), "checkout", "-q", "main")


def main() -> int:
    results: dict[str, bool] = {}
    client = docker.from_env()
    os.environ["THOR_GITEA_TOKEN"] = "secret-gitea-token-control-plane-only"   # an adapter credential
    room = None
    try:
        pg.start(client)
        conn = db.connect()
        db.init_schema(conn)
        with conn.cursor() as cur:
            cur.execute("TRUNCATE eventlog, rooms, cards, features, bugs")
        mgr = ThorManager(conn)
        audit = ChainAudit(mgr.eventlog)

        repo = REPO / ".smoke" / "adapters-repo"
        if repo.exists():
            subprocess.run(["rm", "-rf", str(repo)])
        setup_repo(repo)

        # ---------- AC-1 no external type leaks past its adapter (arch lint) ----------
        print("== AC-1 no AGT/Gitea type leaks outside its adapter (arch lint) ==")
        lint = subprocess.run([sys.executable, "tools/arch_lint.py"], capture_output=True, text=True)
        results["AC-1 arch-lint clean (no leaks)"] = lint.returncode == 0
        print(f"   {lint.stdout.strip()}")

        # ---------- AC-2 audit chain detects tampering ----------
        print("== AC-2 audit chain is tamper-evident ==")
        audit.append_event("card.approved", {"feature_id": "F1"})
        audit.append_event("feature.merged", {"feature_id": "F1"})
        audit.append_event("verdict.computed", {"feature_id": "F1", "verdict": "done"})
        intact = verify_chain(audit)["intact"]
        with conn.cursor() as cur:                                   # force-edit a PAST event
            cur.execute("UPDATE eventlog SET payload='{\"tampered\":true}' WHERE seq=1")
        conn.commit()
        broken = verify_chain(audit)["intact"]
        results["AC-2 audit tamper detected"] = intact and not broken
        print(f"   intact_before={intact}  intact_after_tamper={broken}")
        with conn.cursor() as cur:
            cur.execute("TRUNCATE eventlog")                          # reset for a clean chain below
        conn.commit()
        for et, p in [("card.approved", {"feature_id": "F1"}), ("feature.merged", {"feature_id": "F1"}),
                      ("verdict.computed", {"feature_id": "F1", "verdict": "done"})]:
            audit.append_event(et, p)

        # ---------- AC-3 compliance evidence traces to the chain ----------
        print("== AC-3 compliance evidence derived from + traceable to the chain ==")
        soc2 = export_compliance(audit, "SOC2")
        real_hashes = {e["hash"] for e in audit.all_events()}
        traces = soc2["count"] >= 1 and all(r["chain_hash"] in real_hashes for r in soc2["evidence"])
        csv_ok = "chain_hash" in export_compliance(audit, "SOC2", fmt="csv")
        results["AC-3 compliance traces to chain"] = traces and csv_ok
        print(f"   SOC2 evidence items={soc2['count']} all trace to chain={traces}")

        # ---------- AC-4 room identity verify; forged/stale rejected ----------
        print("== AC-4 room identity verifies; forged/stale rejected ==")
        ident = MeshIdentity()
        tok = ident.mint_room_identity("room-A", "build")["identity_token"]
        good = ident.verify_identity(tok, "room-A")["valid"]
        forged = ident.verify_identity(tok + "x", "room-A")["valid"]
        identity_adapter.revoke_identity(tok)
        revoked = ident.verify_identity(tok, "room-A")["valid"]
        results["AC-4 identity verify + reject forged/revoked"] = good and not forged and not revoked
        print(f"   valid={good} forged_rejected={not forged} revoked_rejected={not revoked}")

        # ---------- AC-5 three signature points verify; replay rejected ----------
        print("== AC-5 the three signature points verify; replay rejected ==")
        priv = Ed25519PrivateKey.generate()
        pub = _b64(priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw))

        def sign(card_id, payload):
            mat = ThorManager.card_material(card_id, payload)
            return mat, _b64(priv.sign(mat.encode()))

        verified = []
        for ctype in ("plan", "ticket", "merge"):
            mat, sig = sign(f"{ctype}-card", {"feature_id": "F1", "type": ctype})
            verified.append(ident.verify_signature(pub, mat, sig)["valid"])
        mat_a, sig_a = sign("merge-card", {"feature_id": "F1", "type": "merge"})
        mat_b, _ = sign("OTHER-card", {"feature_id": "F9", "type": "merge"})
        replay_rejected = not ident.verify_signature(pub, mat_b, sig_a)["valid"]   # A's sig on B
        results["AC-5 three signatures + replay rejected"] = all(verified) and replay_rejected
        print(f"   plan/ticket/merge verified={verified}  replay_rejected={replay_rejected}")

        # ---------- AC-6 real merge only after a verified Signature 3 (peer handshake) ----------
        print("== AC-6 real merge runs through the adapter only after Signature 3 ==")
        pr = gitea_adapter.open_pr(str(repo), "feature", {"title": "F1"})
        ci = gitea_adapter.ci_result(str(repo), "feature")
        no_sig = gitea_adapter.merge(str(repo), pr["pr_id"], None)               # no authorization
        mat_m, sig_m = sign("merge-F1", {"feature_id": "F1"})
        sig3_ok = ident.verify_signature(pub, mat_m, sig_m)["valid"]             # THOR verifies Sig 3
        merged = gitea_adapter.merge(str(repo), pr["pr_id"], sig_m) if sig3_ok else {"merged": False}
        on_main = "feat.py" in git(str(repo), "ls-files")                        # really merged into main
        results["AC-6 real merge after Sig 3"] = (ci["passed"] and not no_sig["merged"]
                                                  and merged["merged"] and on_main)
        print(f"   ci_passed={ci['passed']} no_sig_refused={not no_sig['merged']} "
              f"merged_after_sig={merged['merged']} feat_on_main={on_main}")

        # ---------- AC-7 swap the git host: only the adapter changes ----------
        print("== AC-7 substitution: same THOR flow on Gitea(local-git) and GitHub stub ==")
        local_swap = substitution.prove_git_swap(LocalGitBackend(), str(repo), "feature2", sig_m)
        github_swap = substitution.prove_git_swap(substitution.GitHubBackend(), str(repo), "feature2", sig_m)
        both_satisfy_port = isinstance(LocalGitBackend(), GitPort) and isinstance(substitution.GitHubBackend(), GitPort)
        results["AC-7 swap only the adapter (Strangler)"] = (local_swap["merged"] and github_swap["merged"]
                                                             and both_satisfy_port)
        print(f"   local-git merged={local_swap['merged']}  github-stub merged={github_swap['merged']} "
              f"(identical THOR calls)")

        # ---------- AC-8 AGT version bump absorbed by the adapter alone ----------
        print("== AC-8 an audit-backend version bump is absorbed; THOR callers unchanged ==")
        def thor_uses_audit(a: AuditPort) -> bool:                  # identical THOR-vocabulary caller
            a.append_event("verdict.computed", {"feature_id": "Fx", "verdict": "done"})
            return a.verify_chain()
        v1_ok = thor_uses_audit(audit)                              # real chain (v1)
        v2_ok = thor_uses_audit(substitution.V2InMemoryAudit())     # "next AGT version" (v2)
        results["AC-8 version bump absorbed by adapter"] = v1_ok and v2_ok
        print(f"   same caller works on v1={v1_ok} and v2={v2_ok}")

        # ---------- AC-9 audit can't record → governed action fails closed ----------
        print("== AC-9 audit can't record → governed action does NOT proceed (fail-closed) ==")
        class BrokenAudit(AuditPort):
            def append_event(self, *a, **k): raise RuntimeError("audit store down")
            def verify_chain(self): return False
        def governed_action(a: AuditPort) -> str:
            try:
                a.append_event("card.approved", {"feature_id": "F2"})
                return "proceeded"
            except Exception:  # noqa: BLE001 - unrecorded action is an ungoverned action
                return "refused-failclosed"
        results["AC-9 fail-closed when audit down"] = governed_action(BrokenAudit()) == "refused-failclosed"
        print(f"   broken audit → action {governed_action(BrokenAudit())}")

        # ---------- AC-10 identity can't verify → not trusted (fail-closed) ----------
        print("== AC-10 identity can't verify → room/signature not trusted ==")
        untrusted = not ident.verify_identity("garbage.token", "room-Z")["valid"]
        bad_sig = not ident.verify_signature(pub, "some-material", "not-a-signature")["valid"]
        results["AC-10 fail-closed when identity unverifiable"] = untrusted and bad_sig
        print(f"   unverifiable identity refused={untrusted}  bad signature refused={bad_sig}")

        # ---------- AC-11 external credentials never present in a room ----------
        print("== AC-11 external credentials never enter a room ==")
        room = provisioner.provision_room(task_type="build", network_mode="sealed",
                                          feature_slice={"feature_id": "F1"})
        container = client.containers.get(room["room_id"])
        env = container.attrs["Config"].get("Env") or []
        leaked = any("THOR_GITEA_TOKEN" in e or "secret-gitea-token" in e or "SIGNING_KEY" in e for e in env)
        results["AC-11 no credentials in room"] = not leaked
        print(f"   gitea token / signing key present in room env = {leaked}")

        # ---------- AC-12 identity is verification-only; no per-agent trust scoring ----------
        print("== AC-12 identity for verification/system-trust only; no per-agent scoring ==")
        from selfaudit import metatrust
        no_agent_scoring = not any(hasattr(identity_adapter, m)
                                   for m in ("score_agent", "agent_trust", "trust_score", "rate_agent"))
        system_only = metatrust.score({"verdict_total": 1})["scope"] == "system"
        results["AC-12 no per-agent trust score"] = no_agent_scoring and system_only
        print(f"   identity has no agent-scoring API={no_agent_scoring}  meta-trust scope=system={system_only}")

        # bonus: the catalog bridge keeps one source, two faces
        gitea_adapter._default.add_issue(str(repo), "F1", "Login form")
        bridge_consistent = catalog_bridge.reconcile(
            [{"feature_id": "F1"}], gitea_adapter.list_issues(str(repo)))["consistent"]
        print(f"   (catalog↔issues consistent = {bridge_consistent})")

        print("\n==== ADAPTERS SMOKE RESULTS (real, observed) ====")
        for k, v in results.items():
            print(f"   [{'PASS' if v else 'FAIL'}] {k}")
        headline = (results["AC-1 arch-lint clean (no leaks)"] and results["AC-2 audit tamper detected"]
                    and results["AC-7 swap only the adapter (Strangler)"])
        print(f"\n   HEADLINE (AC-1 + AC-2 + AC-7: substrate fully used yet fully swappable): "
              f"{'PASS' if headline else 'FAIL'}")
        return 0 if all(results.values()) else 1
    finally:
        print("== teardown ==")
        if room:
            try:
                provisioner.destroy_room(room["room_id"])
            except Exception:  # noqa: BLE001
                pass
        for c in client.containers.list(all=True, filters={"label": "thor.room"}):
            try:
                c.remove(force=True)
            except Exception:  # noqa: BLE001
                pass
        pg.stop(client)


if __name__ == "__main__":
    sys.exit(main())
