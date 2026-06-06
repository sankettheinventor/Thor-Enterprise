"""
Gitea adapter (Module 12) — STUB for Modules 1–11 (Rule 5).

THOR vocabulary it exposes (PRD §6.2 / System Design §7.2):
    create_worktree, open_pr, merge, ci_result, list_issues, git_log, git_diff.

Day-one stub: backed by LOCAL git only (a git worktree on the host). No Gitea server. This is
enough for the Wall to get a real branch a cook can commit to (AC-1) and for destroy to confirm
the branch persists after the container is gone (AC-7). Real Gitea wiring is Module 12.

This is the ONLY file (with agt_adapter.py) allowed to import an external backbone (Rule 4).
"""
from __future__ import annotations

import subprocess
from pathlib import Path


def _git(repo: str, *args: str) -> str:
    out = subprocess.run(
        ["git", "-C", repo, *args], capture_output=True, text=True, check=True
    )
    return out.stdout.strip()


def create_worktree(repo: str, base_branch: str, new_branch: str, worktree_path: str) -> dict:
    """
    Create a git worktree + branch (local-git stand-in for Gitea's worktree API).
    The worktree dir becomes the room's read-write /work mount (FR-8).
    """
    Path(worktree_path).parent.mkdir(parents=True, exist_ok=True)
    _git(repo, "worktree", "add", "-b", new_branch, worktree_path, base_branch)
    return {"branch": new_branch, "worktree_path": worktree_path, "repo": repo}


def branch_exists(repo: str, branch: str) -> bool:
    """Used to confirm a branch persists after a room is destroyed (AC-7)."""
    try:
        _git(repo, "rev-parse", "--verify", branch)
        return True
    except subprocess.CalledProcessError:
        return False


def git_log(repo: str, grep: str | None = None) -> str:
    args = ["log", "--oneline"]
    if grep:
        args += ["--grep", grep]
    return _git(repo, *args)


def git_diff(repo: str, branch: str, base: str = "HEAD") -> str:
    return _git(repo, "diff", f"{base}..{branch}")


def commit_sha(repo: str, feature_id: str, branch: str | None = None) -> str | None:
    """Real SHA of the commit landing this feature (git log --grep) — powers M2. None if absent."""
    args = ["log", "--grep", feature_id, "--format=%H"]
    if branch:
        args.append(branch)
    out = _git(repo, *args)
    return out.splitlines()[0] if out else None


def diff_files(repo: str, branch: str, base: str = "main") -> list[str]:
    """The files actually changed on the branch (git diff --name-only) — the reality manifest (M3)."""
    out = _git(repo, "diff", "--name-only", f"{base}..{branch}")
    return [ln for ln in out.splitlines() if ln]


def head_sha(repo: str, ref: str = "HEAD") -> str:
    """Current SHA of a ref — used for the verdict's freshness/snapshot key."""
    return _git(repo, "rev-parse", ref)


# =========================================================================================
# Module 12 — the seam FILLED IN. Real local-git backend (the PRD-sanctioned "local-git
# stand-in"); a live Gitea server / GitHub swaps in behind the SAME GitPort (substitution.py).
# THOR owns the authority (decides); the backend EXECUTES — the peer handshake (FR-8, Bible §9.5).
# =========================================================================================
from .contract import GitPort  # noqa: E402


class LocalGitBackend(GitPort):
    """GitPort over real local git. PR/issue metadata is held control-plane-side (as Gitea would)."""

    def __init__(self) -> None:
        self._prs: dict[str, dict] = {}
        self._pr_seq = 0
        self._issues: dict[str, list[dict]] = {}

    def open_pr(self, repo: str, branch: str, meta: dict) -> dict:
        self._pr_seq += 1
        pr_id = f"pr-{self._pr_seq}"
        self._prs[pr_id] = {"repo": repo, "branch": branch, "meta": meta, "state": "open"}
        return {"pr_id": pr_id, "branch": branch}

    def ci_result(self, repo: str, branch: str) -> dict:
        """Real CI-style gate: compile the .py files the branch ADDS/MODIFIES (feeds verdict M1/M4)."""
        # --diff-filter=AM => only files present at the branch tip (skip deletions relative to base)
        out = _git(repo, "diff", "--name-only", "--diff-filter=AM", f"main..{branch}")
        runs = []
        for f in (ln for ln in out.splitlines() if ln.endswith(".py")):
            try:
                compile(_git(repo, "show", f"{branch}:{f}"), f, "exec")
                runs.append({"file": f, "passed": True})
            except (SyntaxError, subprocess.CalledProcessError) as e:
                runs.append({"file": f, "passed": False, "error": str(e)[:80]})
        return {"passed": all(r["passed"] for r in runs), "runs": runs}

    def merge(self, repo: str, pr_id: str, signature_ref: str | None, base: str = "main") -> dict:
        """Execute the merge ONLY after THOR's verified Signature 3 (the peer handshake)."""
        if not signature_ref:
            return {"merged": False, "reason": "no Signature 3 — THOR has not authorized the merge"}
        pr = self._prs.get(pr_id)
        if pr is None:
            return {"merged": False, "reason": "unknown pr"}
        if pr["state"] == "merged":
            return {"merged": True, "idempotent": True, "sha": pr.get("sha")}
        branch = pr["branch"]
        _git(repo, "checkout", base)
        _git(repo, "merge", "--no-ff", "-m", f"merge {branch} (sig {signature_ref[:8]})", branch)
        sha = _git(repo, "rev-parse", "HEAD")
        pr.update(state="merged", sha=sha)
        return {"merged": True, "sha": sha}

    def list_issues(self, repo: str) -> list[dict]:
        return self._issues.get(repo, [])

    def add_issue(self, repo: str, number: str, title: str, body: str = "") -> dict:
        issue = {"number": number, "title": title, "body": body, "open": True}
        self._issues.setdefault(repo, []).append(issue)
        return issue


# Default backend instance — module-level THOR-vocabulary delegators keep M1–M11 callers unchanged.
_default = LocalGitBackend()


def open_pr(repo: str, branch: str, meta: dict | None = None) -> dict:
    return _default.open_pr(repo, branch, meta or {})


def ci_result(repo: str, branch: str) -> dict:
    return _default.ci_result(repo, branch)


def merge(repo: str, pr_id: str, signature_ref: str | None, base: str = "main") -> dict:
    return _default.merge(repo, pr_id, signature_ref, base)


def list_issues(repo: str) -> list[dict]:
    return _default.list_issues(repo)
