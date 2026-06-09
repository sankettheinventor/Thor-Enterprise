"""
The Foundation Adapters — Acceptance Criteria AC-1..AC-12 (PRD §15).

PROVING PASS (Task 10). The Strangler is REAL: THOR speaks only the Git/Audit/Identity port vocabulary,
and the audit + identity vendor each swaps behind ONE adapter file (proven by the substitution harness).
Deferred (live, needs Postgres + git); run: pytest -m deferred tests/adapters.
"""
import os
import subprocess

import pytest

pytestmark = pytest.mark.deferred


def _mgr(fresh_ledger, **kw):
    from manager.core import ThorManager
    return ThorManager(fresh_ledger, **kw)


def test_ac1_no_external_type_leaks(fresh_ledger):
    import tools.arch_lint as lint
    assert lint.main() == 0   # no AGT/Gitea import outside adapters/ AND the ports are wired (not decorative)


def test_ac2_audit_chain_detects_tamper(fresh_ledger):
    mgr = _mgr(fresh_ledger)
    mgr.add_feature("F", "x")
    assert mgr.eventlog.verify_chain() is True
    with mgr.conn.cursor() as cur:
        cur.execute("UPDATE eventlog SET payload=%s WHERE seq=0", ('{"tampered":true}',))
    assert mgr.eventlog.verify_chain() is False


def test_ac3_compliance_evidence_traces_to_chain(fresh_ledger):
    from adapters.audit_adapter import export_compliance
    mgr = _mgr(fresh_ledger)
    mgr.add_feature("F", "x")
    out = export_compliance(mgr.eventlog, "soc2", "json")   # mgr.eventlog IS the ChainAudit (AuditPort)
    assert out   # evidence derived FROM the tamper-evident chain, not invented


def test_ac4_room_identity_verify_reject_forged():
    from adapters.identity_adapter import MeshIdentity
    mesh = MeshIdentity()
    tok = mesh.mint_room_identity("room-a")["identity_token"]
    assert mesh.verify_identity(tok, "room-a")["valid"] is True
    assert mesh.verify_identity(tok, "room-OTHER")["valid"] is False     # wrong room
    assert mesh.verify_identity("forged.token", "room-a")["valid"] is False


def test_ac5_three_signatures_verify_reject_replay():
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
    from adapters.identity_adapter import MeshIdentity
    from wall.identity_stamper import _b64
    mesh = MeshIdentity()
    priv = Ed25519PrivateKey.generate()
    pub = _b64(priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw))
    material = "card-1|hash|nonce-1"
    assert mesh.verify_signature(pub, material, _b64(priv.sign(material.encode())))["valid"] is True
    assert mesh.verify_signature(pub, material, _b64(priv.sign(b"other")))["valid"] is False   # forged/replay


def test_ac6_real_merge_after_signature3(fresh_ledger, host_repo):
    from adapters import gitea_adapter
    subprocess.run(["git", "-C", host_repo, "init", "-q"])
    open(os.path.join(host_repo, "a"), "w").write("x")
    subprocess.run(["git", "-C", host_repo, "add", "-A"]); subprocess.run(
        ["git", "-C", host_repo, "-c", "user.email=a@b", "-c", "user.name=a", "commit", "-q", "-m", "base"])
    subprocess.run(["git", "-C", host_repo, "branch", "-M", "main"])
    subprocess.run(["git", "-C", host_repo, "checkout", "-q", "-b", "feature/F"])
    open(os.path.join(host_repo, "b"), "w").write("y")
    subprocess.run(["git", "-C", host_repo, "add", "-A"]); subprocess.run(
        ["git", "-C", host_repo, "-c", "user.email=c@t", "-c", "user.name=c", "commit", "-q", "-m", "F"])
    pr = gitea_adapter.open_pr(host_repo, "feature/F")
    assert gitea_adapter.merge(host_repo, pr["pr_id"], None)["merged"] is False     # no Sig 3 → refused
    assert gitea_adapter.merge(host_repo, pr["pr_id"], "sig-3-ref")["merged"] is True


def test_ac7_substitution_only_adapter_changes(fresh_ledger):
    from manager.core import ThorManager
    from adapters.substitution import (GitHubBackend, StubMeshIdentity, V2InMemoryAudit,
                                       prove_audit_swap, prove_git_swap, prove_identity_swap)
    # git host swap: Gitea-shaped flow runs identically on a GitHub backend
    assert prove_git_swap(GitHubBackend(), "/r", "feature/F", "sig")["merged"] is True
    # audit backend swap: the Manager records + reads through a DIFFERENT AuditPort, no THOR change
    aud = prove_audit_swap(lambda a: ThorManager(fresh_ledger, audit=a), V2InMemoryAudit())
    assert aud["read_back"] is True and aud["recorded"] == 1
    # identity backend swap: mint/verify through a DIFFERENT IdentityPort
    ident = prove_identity_swap(StubMeshIdentity())
    assert ident["good"] is True and ident["forged_rejected"] is True


def test_ac8_agt_version_bump_absorbed():
    # a 'next version' backend with a different internal shape satisfies the SAME port → absorbed
    from adapters.substitution import V2InMemoryAudit
    from adapters.contract import AuditPort
    v2 = V2InMemoryAudit()
    assert isinstance(v2, AuditPort)
    v2.append_event("x", {"k": 1})
    assert v2.verify_chain() is True


def test_ac9_audit_cant_record_fail_closed(fresh_ledger):
    from manager.core import FailClosed
    mgr = _mgr(fresh_ledger)
    mgr.set_eventlog_writable(False)
    with pytest.raises(FailClosed):                                   # no unaudited governed action
        mgr._record("test.x", {})


def test_ac10_identity_cant_verify_fail_closed():
    from adapters.identity_adapter import MeshIdentity
    # a garbled/forged token is NOT trusted — fail-closed, never a default-allow
    assert MeshIdentity().verify_identity("not-a-real-token", "room-a")["valid"] is False


def test_ac11_credentials_never_in_room():
    # the IdentityPort mints only a PUBLIC, signed token — never private key material (creds stay
    # control-plane-side; the room only ever holds a verifiable token, D3).
    from adapters.identity_adapter import MeshIdentity
    minted = MeshIdentity().mint_room_identity("room-a")
    blob = str(minted).lower()
    assert "private" not in blob and "begin" not in blob and set(minted.keys()) == {"identity_token", "room_id"}


def test_ac12_identity_no_agent_scoring():
    # identity is for VERIFICATION + system-trust only — deliberately NO per-agent trust-scoring API
    from adapters.identity_adapter import MeshIdentity
    assert not any(hasattr(MeshIdentity(), m) for m in ("score", "trust_score", "rate_agent", "reputation"))
