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
import shlex
import shutil
import subprocess
import tempfile

from adapters import gitea_adapter


class RealityError(Exception):
    """Reality could not be read (git/CI/audit unavailable) — the engine must fail closed."""


# ---------------------------------------------------------------------------
# SANDBOXED VERIFICATION (RED-TEAM CRITICAL): the verifier/regression test is written BY THE COOK. Running
# it directly on the control plane is arbitrary code execution + secret exfiltration (the plane env holds
# the API token, DB creds, signing material). When a real cook is in play (THOR_COOK set), every test run
# happens inside a SEALED, NETWORK-DISABLED, minimal-env, non-root container against a COPY of the repo, so
# untrusted cook code can neither reach the host, its secrets, nor the network. The docker-free gated suite
# (trusted fixtures, THOR_COOK unset) runs a minimal-env host subprocess.
def _use_sandbox() -> bool:
    return bool(os.environ.get("THOR_COOK")) and os.environ.get("THOR_VERIFY_SANDBOX", "1") != "0"


def _minimal_env() -> dict:
    return {"PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
            "HOME": os.environ.get("HOME", "/tmp"), "PYTHONDONTWRITEBYTECODE": "1"}


def sandboxed_run(repo: str, argv: list[str], *, timeout: int = 30, prepare=None,
                  read_back: str | None = None) -> tuple[int, str, str | None]:
    """Run argv inside a sealed ephemeral container against a COPY of repo. `prepare(dst)` may mutate the
    copy before the run (e.g. gut function bodies). Returns (exit_code, output, read_back_contents|None)."""
    import docker as _docker

    from wall import config
    # Disk-fill guard: refuse to COPY a worktree bigger than the cap (a cook that filled /work could
    # otherwise double the bloat into the sandbox temp and exhaust the host). Early-exit once over the cap.
    cap = int(os.environ.get("THOR_VERIFY_MAX_MB", "1024")) * 1024 * 1024
    total = 0
    for root, _dirs, files in os.walk(repo):
        if os.path.basename(root) == ".git":
            continue
        for fn in files:
            try:
                total += os.path.getsize(os.path.join(root, fn))
            except OSError:
                pass
        if total > cap:
            return 1, f"worktree exceeds the {cap // (1024 * 1024)}MB verification cap (possible disk-fill)", None
    work = tempfile.mkdtemp(prefix="thor-verify-")
    dst = os.path.join(work, "r")
    container = None
    try:
        # symlinks=True copies links AS links (never the TARGET's content) — a cook symlink to a host
        # secret (e.g. the signing key) must not be slurped into the sandbox copy; it dangles harmlessly
        # in the sealed container instead (info-disclosure defence).
        shutil.copytree(repo, dst, symlinks=True, ignore=shutil.ignore_patterns(".git"))
        if prepare is not None:
            prepare(dst)
        client = _docker.from_env()
        container = client.containers.run(
            config.ROOM_IMAGE, entrypoint="", command=["sh", "-c", " ".join(shlex.quote(a) for a in argv)],
            working_dir="/work", mounts=[_docker.types.Mount("/work", dst, type="bind")],
            network_disabled=True, read_only=True, user="cook", cap_drop=["ALL"],
            security_opt=["no-new-privileges"], mem_limit="512m", pids_limit=256,
            tmpfs={"/tmp": "", "/home/cook": "uid=1000,gid=1000"},
            environment={"PYTHONDONTWRITEBYTECODE": "1", "HOME": "/home/cook",
                         "PATH": "/usr/local/bin:/usr/bin:/bin"},
            detach=True)
        try:
            rc = container.wait(timeout=timeout).get("StatusCode", 1)
        except Exception:  # noqa: BLE001 — timeout / docker hiccup → treat as a failed (non-zero) run
            rc = 124
        out = container.logs().decode("utf-8", "replace")[-4000:]
        content = None
        if read_back:
            try:
                with open(os.path.join(dst, read_back), encoding="utf-8") as f:
                    content = f.read()
            except OSError:
                content = None
        return rc, out, content
    finally:
        if container is not None:
            try:
                container.remove(force=True)
            except Exception:  # noqa: BLE001
                pass
        shutil.rmtree(work, ignore_errors=True)


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
    """Run the (cook-written) test and return (exit_code, output). exit 0 = pass. A MACHINE runs it —
    never the agent's word — and when a real cook is in play it runs SEALED (no host, no secrets, no net)."""
    if not test_relpath:
        return 1, "no test file declared"
    if not os.path.exists(os.path.join(repo, test_relpath)):
        return 1, f"test file missing: {test_relpath}"
    if _use_sandbox():
        rc, out, _ = sandboxed_run(repo, ["python3", test_relpath])
        return rc, out
    try:                                                   # docker-free gated suite (trusted fixtures)
        p = subprocess.run(["python3", os.path.join(repo, test_relpath)], capture_output=True, text=True,
                           timeout=30, cwd=repo, env=_minimal_env())
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
