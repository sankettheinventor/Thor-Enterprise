"""
Reading reality (all read-only) — sub-modules 6.2 / 6.3 / 6.5.

  Git Ground-Truth (6.2)  — real commits/diffs via the Gitea adapter (M2, M3, reality manifest).
  Test/CI Verdict (6.3)   — runs the verifier/regression test in a fresh subprocess and reads the
                            exit code (M1, M4). A MACHINE runs it — never the agent's "tests passed."
  Audit-Window Scanner (6.5) — scans the Manager EventLog for the commit window (R2, R3).

If any reader cannot read its source, it raises RealityError → the engine fails closed (FR-15).
"""
from __future__ import annotations

import os
import subprocess

from adapters import gitea_adapter


class RealityError(Exception):
    """Reality could not be read (git/CI/audit unavailable) — the engine must fail closed."""


# ---- 6.2 Git Ground-Truth Reader ----
def commit_sha(repo: str, feature_id: str, branch: str | None = None) -> str | None:
    try:
        return gitea_adapter.commit_sha(repo, feature_id, branch)
    except Exception as e:  # noqa: BLE001
        raise RealityError(f"cannot read git log: {e}") from e


def changed_files(repo: str, branch: str, base: str = "main") -> set[str]:
    try:
        return set(gitea_adapter.diff_files(repo, branch, base))
    except Exception as e:  # noqa: BLE001
        raise RealityError(f"cannot read git diff: {e}") from e


def head_sha(repo: str, ref: str = "HEAD") -> str:
    try:
        return gitea_adapter.head_sha(repo, ref)
    except Exception as e:  # noqa: BLE001
        raise RealityError(f"cannot read git head: {e}") from e


# ---- 6.3 Test/CI Verdict Reader (trigger a fresh verification run; CI proper = Module 12) ----
def run_test(repo: str, test_relpath: str | None) -> tuple[int, str]:
    """Run a test file in a fresh subprocess; return (exit_code, output). exit 0 = pass."""
    if not test_relpath:
        return 1, "no test file declared"
    path = os.path.join(repo, test_relpath)
    if not os.path.exists(path):
        return 1, f"test file missing: {test_relpath}"
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}   # don't litter __pycache__ (read-only spirit)
    try:
        p = subprocess.run(["python3", path], capture_output=True, text=True, timeout=30,
                           cwd=repo, env=env)
        return p.returncode, (p.stdout + p.stderr)
    except subprocess.TimeoutExpired:
        raise RealityError("verification run timed out")


# ---- 6.5 Audit-Window Scanner (R2/R3 from the Manager EventLog) ----
_GATE_EVENTS = ("claim_gate.hit", "patch_detect.hit")
_SECURITY_EVENTS = ("sentinel.kill", "security.alarm")


def _events_in_window(manager, window: tuple[int, int] | None) -> list[dict]:
    if manager is None:
        raise RealityError("no Manager → cannot scan the audit window (R2/R3)")
    events = manager.eventlog.all_events()
    if window:
        lo, hi = window
        events = [e for e in events if lo <= e["seq"] <= hi]
    return events


def gate_hits(manager, window: tuple[int, int] | None) -> list[dict]:
    """R2 — claim-gate / patch-detect hits in the window (the agent tried to game the gate)."""
    return [e for e in _events_in_window(manager, window) if e["event_type"] in _GATE_EVENTS]


def security_alarms(manager, window: tuple[int, int] | None) -> list[dict]:
    """R3 — security / backdoor / injection alarms in the window."""
    return [e for e in _events_in_window(manager, window) if e["event_type"] in _SECURITY_EVENTS]
