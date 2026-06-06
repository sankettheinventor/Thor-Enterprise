"""
Sub-module 12.8 — Substitution Harness (FR-14 / AC-7 / AC-8). The Strangler proof.

Swappability is only real if DEMONSTRATED, not claimed. This provides ALTERNATE backends implementing
the SAME THOR ports — a GitHub-style git backend and a v2 audit backend — and a harness that runs the
identical THOR-vocabulary flow against each. If an external type had leaked past an adapter, the
alternate wouldn't satisfy the port and the harness would fail. A clean swap = a clean seam.
"""
from __future__ import annotations

from .contract import AuditPort, GitPort


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
    """A 'next AGT version' audit backend with a different internal shape but the SAME THOR vocabulary."""

    def __init__(self) -> None:
        self._log: list[dict] = []

    def append_event(self, event_type: str, payload: dict, **kw) -> dict:
        seq = len(self._log)
        self._log.append({"seq": seq, "event_type": event_type, "payload": payload})
        return {"seq": seq, "hash": f"v2-{seq}"}

    def verify_chain(self) -> bool:
        return all(e["seq"] == i for i, e in enumerate(self._log))


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
