"""
Sub-module 12.8 — Substitution Harness (FR-14 / AC-7 / AC-8). The Strangler proof.

Swappability is only real if DEMONSTRATED, not claimed. This provides ALTERNATE backends implementing
the SAME THOR ports — a GitHub-style git backend and a v2 audit backend — and a harness that runs the
identical THOR-vocabulary flow against each. If an external type had leaked past an adapter, the
alternate wouldn't satisfy the port and the harness would fail. A clean swap = a clean seam.
"""
from __future__ import annotations

import json

from .contract import AuditPort, GitPort, IdentityPort


class GitHubBackend(GitPort):
    """A stub 'GitHub' host — same THOR vocabulary, different executor. Proves the Gitea→GitHub swap."""

    def __init__(self) -> None:
        self._prs: dict[str, dict] = {}
        self._n = 0

    def open_pr(self, repo: str, branch: str, meta: dict) -> dict:
        self._n += 1
        pid = f"gh-{self._n}"
        self._prs[pid] = {"branch": branch, "state": "open"}
        return {"pr_id": pid, "branch": branch}

    def ci_result(self, repo: str, branch: str) -> dict:
        return {"passed": True, "runs": [{"check": "github-actions", "passed": True}]}

    def merge(self, repo: str, pr_id: str, signature_ref: str | None, base: str = "main") -> dict:
        if not signature_ref:
            return {"merged": False, "reason": "no Signature 3 — THOR has not authorized the merge"}
        self._prs[pr_id]["state"] = "merged"
        return {"merged": True, "sha": f"github-merge-{pr_id}"}

    def list_issues(self, repo: str) -> list[dict]:
        return []


class V2InMemoryAudit(AuditPort):
    """A 'next AGT version' audit backend with a different internal shape but the SAME THOR vocabulary —
    and a full Manager drop-in (append / all_events / count), so `ThorManager(conn, audit=V2InMemoryAudit())`
    records + reads through it with NO change to THOR code. Proves the audit substrate is swappable."""

    def __init__(self) -> None:
        self._log: list[dict] = []

    def append_event(self, event_type: str, payload: dict, **kw) -> dict:
        seq = len(self._log)
        self._log.append({"seq": seq, "event_type": event_type, "payload": json.dumps(payload),
                          "actor": kw.get("actor", "manager"), "room_id": kw.get("room_id"),
                          "feature_id": kw.get("feature_id"), "hash": f"v2-{seq}"})
        return {"seq": seq, "hash": f"v2-{seq}"}

    def append(self, event_type: str, payload: dict, **kw) -> dict:
        return self.append_event(event_type, payload, **kw)

    def all_events(self) -> list[dict]:
        return list(self._log)

    def count(self) -> int:
        return len(self._log)

    def verify_chain(self) -> bool:
        return all(e["seq"] == i for i, e in enumerate(self._log))


class StubMeshIdentity(IdentityPort):
    """A 'next identity vendor' backend — same THOR IdentityPort vocabulary, a different scheme. Proves
    the identity substrate is swappable: mint/verify go through the port, never a concrete stamper type."""

    def __init__(self) -> None:
        self._issued: set[str] = set()

    def mint_room_identity(self, room_id: str, task_type: str = "build") -> dict:
        tok = f"stub-id::{room_id}::{task_type}"
        self._issued.add(tok)
        return {"identity_token": tok, "room_id": room_id}

    def verify_identity(self, token: str, room_id: str | None = None) -> dict:
        valid = token in self._issued and (room_id is None or token.split("::")[1] == room_id)
        return {"valid": valid, "room_id": room_id}

    def verify_signature(self, public_key_b64: str, material: str, signature_b64: str) -> dict:
        # this stub vendor signs as sha256(pub|material); a real vendor (AGT Mesh) does real crypto
        import hashlib
        expect = hashlib.sha256(f"{public_key_b64}|{material}".encode()).hexdigest()
        return {"valid": signature_b64 == expect, "signer": public_key_b64[:12]}


def prove_audit_swap(make_manager, audit_backend) -> dict:
    """Run the same THOR record→read flow against a Manager built on `audit_backend`. A clean swap =
    a clean seam (no concrete audit type leaked into THOR)."""
    mgr = make_manager(audit_backend)
    mgr._record("test.swap", {"k": "v"}, actor="manager")
    events = mgr.eventlog.all_events()
    return {"backend": type(audit_backend).__name__, "recorded": mgr.eventlog.count(),
            "read_back": any(e["event_type"] == "test.swap" for e in events)}


def prove_identity_swap(identity_backend: IdentityPort, room_id: str = "room-z") -> dict:
    """Mint + verify a room identity through whatever IdentityPort is handed — Mesh today, a new vendor
    tomorrow — identically. A forged token must fail on either."""
    minted = identity_backend.mint_room_identity(room_id, "build")
    good = identity_backend.verify_identity(minted["identity_token"], room_id)["valid"]
    forged = identity_backend.verify_identity("forged.token", room_id)["valid"]
    return {"backend": type(identity_backend).__name__, "good": good, "forged_rejected": not forged}


def prove_git_swap(backend: GitPort, repo: str, branch: str, signature_ref: str) -> dict:
    """
    The SAME THOR flow, run against whatever GitPort it's handed (Gitea local-git OR GitHub).
    THOR's authority (it provides the verified Signature 3) is identical across hosts.
    """
    pr = backend.open_pr(repo, branch, {"title": "swap test"})
    ci = backend.ci_result(repo, branch)
    merged = backend.merge(repo, pr["pr_id"], signature_ref) if ci["passed"] else {"merged": False}
    return {"backend": type(backend).__name__, "pr_id": pr["pr_id"],
            "ci_passed": ci["passed"], "merged": merged.get("merged")}
