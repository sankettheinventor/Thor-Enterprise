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


def _verify_image() -> str:
    """The image the SEALED verdict runs the cook's test in. Defaults to the Python room image, but a
    non-Python project needs the right toolchain (e.g. node for JS/TS, go, ...) — set THOR_VERIFY_IMAGE to a
    polyglot image (the bundled `thor-room-claude` has python3 + node). The cook's image is separate."""
    from wall import config
    return os.environ.get("THOR_VERIFY_IMAGE") or config.ROOM_IMAGE


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
            _verify_image(), entrypoint="", command=["sh", "-c", " ".join(shlex.quote(a) for a in argv)],
            working_dir="/work", mounts=[_docker.types.Mount("/work", dst, type="bind")],
            network_disabled=True, read_only=True, user="cook", cap_drop=["ALL"],
            security_opt=["no-new-privileges"], mem_limit="512m", pids_limit=256,
            tmpfs={"/tmp": "", "/home/cook": "uid=1000,gid=1000"},
            environment={"PYTHONDONTWRITEBYTECODE": "1", "HOME": "/home/cook",
                         "PATH": "/usr/local/bin:/usr/bin:/bin",
                         # the project is importable like a real test suite: `src/` (src-layout) FIRST so the
                         # editable source (with generated build artifacts) shadows any built copy, then the
                         # repo ROOT (flat layout), then `.thor_libs` (declared deps installed by the trusted
                         # prep phase, if any). These are the dominant real-world conventions.
                         "PYTHONPATH": "/work/src:/work:/work/.thor_libs"},
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


# ---------------------------------------------------------------------------
# TRUSTED PROJECT PREP (real installable repos). The sealed verdict runs the cook's UNTRUSTED test offline,
# so it cannot itself install deps or run a build. But a real package needs a build/install first (e.g.
# setuptools-scm generates `_version.py`; third-party deps must be importable). So we split it:
#   1) TRUSTED PREP (network ON, one ephemeral container): build the project + install its DECLARED deps
#      into the worktree copy. This runs the PROJECT's build backend (trusted) and installs the user's own
#      declared deps — it does NOT execute the cook's runtime modules (an editable build only links them).
#   2) SEALED TEST (network OFF): the cook's untrusted test runs against the prepared copy, as always.
# SECURITY: prep is SKIPPED if the cook's diff touches ANY build/config file (setup.py / pyproject / etc.) —
# those changes already ESCALATE to a human (engine._stakes), and we must never run a cook-tampered build.
_BUILD_FILES = {"setup.py", "setup.cfg", "pyproject.toml", "manifest.in", "tox.ini", "noxfile.py",
                "conftest.py", "meson.build", "cmakelists.txt", "makefile", "build.py"}


def _is_build_file(path: str) -> bool:
    base = os.path.basename(path).lower()
    return (base in _BUILD_FILES or base.startswith("requirements")
            or base.endswith((".cfg", ".toml", ".in")))


def prepare_project(repo: str, changed_files) -> str:
    """Return a PREPARED copy of `repo` (build artifacts generated + declared deps installed) for the test
    runs, or `repo` unchanged when prep is not applicable/eligible. Only runs for a real cook (THOR_COOK set,
    sealed verdicts); the gated trusted suite is self-contained and skips this."""
    if not _use_sandbox() or os.environ.get("THOR_VERIFY_PREP", "1") == "0":
        return repo
    if not any(os.path.exists(os.path.join(repo, m)) for m in ("pyproject.toml", "setup.py", "setup.cfg")):
        return repo                                   # not an installable project — nothing to build
    if any(_is_build_file(f) for f in (changed_files or [])):
        return repo                                   # cook touched a build file -> never run that build (escalates)
    work = tempfile.mkdtemp(prefix="thor-prep-")
    dst = os.path.join(work, "r")
    try:
        # KEEP .git in the PREP copy — setuptools-scm and friends derive the version from git history; the
        # SEALED test copies (sandboxed_run) still exclude .git. Strip hooks so a cook-planted git hook can't
        # run during the build (the prep container is isolated + ephemeral, but defence in depth).
        shutil.copytree(repo, dst, symlinks=True,
                        ignore=shutil.ignore_patterns(".thor_libs", ".thor_venv"))
        shutil.rmtree(os.path.join(dst, ".git", "hooks"), ignore_errors=True)
        os.chmod(dst, 0o777)
        if _prep_build(dst):
            return dst
    except Exception:  # noqa: BLE001 — best-effort: any prep failure falls back to the un-prepared run
        pass
    shutil.rmtree(work, ignore_errors=True)
    return repo


def _prep_build(dst: str) -> bool:
    """Build the project IN PLACE (generate artifacts like `_version.py` into src) + install its declared deps
    into `<dst>/.thor_libs`, in ONE network-enabled, capability-dropped, ephemeral container. Best-effort."""
    import docker as _docker

    from wall import config
    # editable build -> writes generated version files into src; then deps into a portable target dir that the
    # sealed run adds to PYTHONPATH. `|| true` so a partial prep (e.g. artifacts only) still helps.
    script = ("pip install -e . --no-deps -q 2>&1 | tail -2 || true; "
              "pip install . --target=/work/.thor_libs -q 2>&1 | tail -2 || true")
    container = None
    try:
        client = _docker.from_env()
        container = client.containers.run(
            _verify_image(), entrypoint="", command=["sh", "-c", script], working_dir="/work",
            mounts=[_docker.types.Mount("/work", dst, type="bind")],
            network_disabled=False,            # TRUSTED PREP needs the network to build + fetch declared deps
            cap_drop=["ALL"], security_opt=["no-new-privileges"], mem_limit="1536m", pids_limit=512,
            detach=True)
        container.wait(timeout=int(os.environ.get("THOR_PREP_TIMEOUT", "240")))
        return True
    except Exception:  # noqa: BLE001
        return False
    finally:
        if container is not None:
            try:
                container.remove(force=True)
            except Exception:  # noqa: BLE001
                pass


def cleanup_prepared(test_repo: str | None, repo: str) -> None:
    """Remove the temp prep copy if one was made (test_repo lives under a `thor-prep-*` temp dir)."""
    if test_repo and test_repo != repo and os.path.basename(test_repo) == "r":
        shutil.rmtree(os.path.dirname(test_repo), ignore_errors=True)


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
def run_test(repo: str, test_relpath: str | None, argv: list[str] | None = None) -> tuple[int, str]:
    """Run the (cook-written) test and return (exit_code, output). exit 0 = pass. A MACHINE runs it —
    never the agent's word — and when a real cook is in play it runs SEALED (no host, no secrets, no net).

    `argv` is HOW to run it — LANGUAGE-AGNOSTIC: the caller passes the runner inferred from the test's
    extension (node/go/ruby/sh/...) or the contract's explicit `test_command`. Defaults to `python3 <test>`
    for back-compat. (Running a non-Python test needs that language's runtime IN the room image — set
    `THOR_COOK_IMAGE` to a toolchain image; an absent runtime returns 127, never a false pass.)"""
    if not test_relpath:
        return 1, "no test file declared"
    if not os.path.exists(os.path.join(repo, test_relpath)):
        return 1, f"test file missing: {test_relpath}"
    argv = argv or ["python3", test_relpath]
    if _use_sandbox():
        rc, out, _ = sandboxed_run(repo, argv)
        return rc, out
    try:                                                   # docker-free gated suite (trusted fixtures)
        ppath = os.pathsep.join([os.path.join(repo, "src"), repo, os.path.join(repo, ".thor_libs")])
        p = subprocess.run(argv, capture_output=True, text=True, timeout=30, cwd=repo,
                           env={**_minimal_env(), "PYTHONPATH": ppath})
        return p.returncode, (p.stdout + p.stderr)
    except FileNotFoundError as e:                         # the language runtime is absent from the image
        return 127, f"test runner not available ({e}) — the room image lacks this language's runtime"
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
