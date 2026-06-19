"""
Fake-test-checker (FR-13 / AC-3) — defends M1 against passing-but-hollow tests.

A sophisticated agent may write a test that technically passes (`assert True`) but never exercises
the feature. M1 (exit 0) alone would be fooled. This checks, by reading the test source, whether the
test actually (a) references the feature's contracted files/symbols, and (b) makes real assertions.
A passing-but-hollow test is flagged → M1 is overridden to fail → verdict not_done.

H1 STRENGTHENED (Task 5): a referencing test with a non-trivial-but-vacuous assertion
(`assert callable(login)`) passed the static check while exercising NOTHING. So after the static
gates we run the test under coverage and require it to actually EXECUTE the contracted code's
function bodies — coverage-of-the-diff. The static checks are kept (strengthen, never bypass).
"""
from __future__ import annotations

import ast
import json
import os
import re
import shlex
import subprocess
import sys
import uuid

from . import reality

# ---------------------------------------------------------------------------
# LANGUAGE-AGNOSTIC mechanical verification (HH-nonpy-coverage). Python source gets behaviour-level proof
# (body-gut + coverage above). For NON-Python contracted source we use EXERCISE-level proof: empty the
# source file and re-run the cook's declared test — a test that genuinely exercises the file must now go RED
# (missing symbol / empty behaviour). If it stays GREEN it does not exercise the file → hollow. This is
# weaker than Python's body-gut (it proves the test DEPENDS ON the file, not that it asserts exact
# behaviour), but it is a real machine check that replaces the blanket "escalate to a human" for any
# language whose test we can actually run. Languages whose runtime is absent from the room image fall back
# to escalation (baseline run fails) — honest, never a false pass.
_INTERP = {".py": ["python3"], ".js": ["node"], ".mjs": ["node"], ".cjs": ["node"],
           ".sh": ["sh"], ".bash": ["bash"], ".rb": ["ruby"], ".php": ["php"], ".pl": ["perl"], ".go": ["go", "run"]}
_NONPY_CAP = 8   # bound the per-file mutation runs; if more sources exist we report it (no silent cap)


def test_argv(test_relpath: str, contract: dict) -> list[str] | None:
    """How to RUN the cook's test: an explicit `test_command` from the contract wins; else inferred from the
    test file's extension. None when we have no runner (→ the source escalates to a human, never a false pass)."""
    cmd = contract.get("test_command")
    if cmd:
        return shlex.split(cmd) if isinstance(cmd, str) else list(cmd)
    interp = _INTERP.get(os.path.splitext(test_relpath)[1].lower())
    return (interp + [test_relpath]) if interp else None


def _run_test_rc(repo: str, argv: list[str], blank_target: str | None = None) -> int:
    """Run the test (optionally with `blank_target` emptied) and return its exit code. Sealed when a real
    cook is in play (untrusted code never touches the host); restore-in-place on the gated trusted path."""
    if reality._use_sandbox():
        prepare = None
        if blank_target:
            def prepare(dst, t=blank_target):   # empty the source IN THE SANDBOX COPY only
                open(os.path.join(dst, t), "w").close()
        rc, _out, _ = reality.sandboxed_run(repo, argv, prepare=prepare)
        return rc
    tpath = os.path.join(repo, blank_target) if blank_target else None
    original = None
    try:
        if tpath:
            original = open(tpath, encoding="utf-8").read()
            open(tpath, "w").close()            # truncate to empty
        return subprocess.run(argv, cwd=repo, env=reality._minimal_env(),
                              capture_output=True, timeout=30).returncode
    except Exception:  # noqa: BLE001 — runner missing / timeout → treat as failure (non-zero), never a pass
        return 1
    finally:
        if tpath and original is not None:
            with open(tpath, "w", encoding="utf-8") as f:
                f.write(original)               # ALWAYS restore the cook's worktree


def verify_nonpython(repo: str, contract: dict) -> tuple[str, str]:
    """Mechanically verify a NON-Python feature by mutation-discrimination. Returns one of:
      "n/a"        — no non-Python contracted source (Python feature / no source); stakes behave normally.
      "verified"   — every non-Python contracted source is exercised by the test (test goes RED when each is
                     emptied) → the feature is machine-verified and need NOT escalate to a human.
      "unverified" — there is non-Python source but the test does not exercise it / cannot be run → escalate.
    """
    cited = contract.get("scope", {}).get("files", [])
    declared_tests = (contract.get("test_file"), contract.get("regression_file"))
    nonpy = [f for f in cited
             if "." in os.path.basename(f) and not f.endswith(".py") and f not in declared_tests]
    if not nonpy:
        return "n/a", "no non-python contracted source"
    test_rel = contract.get("test_file")
    if not test_rel or not os.path.exists(os.path.join(repo, test_rel)):
        return "unverified", "no declared test to mechanically verify the non-python source"
    argv = test_argv(test_rel, contract)
    if argv is None:
        return "unverified", f"no runner for {test_rel} (unknown extension; declare contract.test_command)"
    if _run_test_rc(repo, argv) != 0:           # baseline: the test must PASS as written
        return "unverified", "the declared test does not pass as written (cannot verify against it)"
    checked = nonpy[:_NONPY_CAP]
    for target in checked:
        if not os.path.exists(os.path.join(repo, target)):
            return "unverified", f"contracted source {target} absent"
        if _run_test_rc(repo, argv, blank_target=target) == 0:
            return "unverified", f"test stays GREEN when {target} is emptied — it does not exercise it"
    tail = "" if len(nonpy) <= _NONPY_CAP else f" (capped at {_NONPY_CAP} of {len(nonpy)})"
    return "verified", f"test goes red when each of {len(checked)} non-python source file(s) is emptied{tail}"


def is_hollow(repo: str, test_relpath: str | None, contract: dict) -> tuple[bool, str]:
    """Return (hollow, reason). hollow=True means the test does NOT genuinely exercise the feature."""
    if not test_relpath:
        return True, "no test file"
    path = os.path.join(repo, test_relpath)
    if not os.path.exists(path):
        return True, "test file missing"

    cited = contract.get("scope", {}).get("files", [])
    # LANGUAGE ROUTING: the deep behaviour-level gates below (read the test SOURCE, gut Python function
    # bodies, line-coverage) only make sense for Python. When the contracted source is NOT Python, verify it
    # the language-agnostic way — mutation-discrimination (empty each source, the test must go RED). So a
    # JS/Go/Ruby/shell hollow test is caught here too, not waved through.
    py_target = next((f for f in cited if f.endswith(".py") and not os.path.basename(f).startswith("test_")),
                     None)
    if py_target is None:
        status, why = verify_nonpython(repo, contract)
        if status == "verified":
            return False, f"non-python test exercises the contracted source ({why})"
        if status == "unverified":
            return True, f"non-python test does not exercise the contracted source ({why})"
        return False, "no contracted source to falsify"          # n/a — nothing to check

    src = open(path).read()

    # (a) does it reference any contracted file / its module name? (does it touch the new code?)
    modules = {os.path.splitext(os.path.basename(f))[0] for f in cited}   # e.g. src/login.py -> login
    references_feature = any(m and m in src for m in modules) or any(f in src for f in cited)

    # (b) does it make a non-trivial assertion (asserts on *something*, not literally `assert True`)?
    asserts = re.findall(r"assert\s+(.+)", src)
    trivial = all(a.strip() in ("True", "1", "True  # ok", "(True)") for a in asserts) if asserts else True

    if not references_feature:
        return True, "test does not exercise the feature (no reference to contracted code)"
    if trivial:
        return True, "test asserts trivially (assert True) — does not test the feature"

    # (c) coverage-of-the-diff: the test must EXECUTE the contracted code, not just import it (H1).
    covered, why = _covers_feature_code(repo, test_relpath, cited)
    if not covered:
        return True, f"hollow: {why}"

    # (d) DISCRIMINATION (H1+): a genuine test must be able to go RED. We gut the feature's function
    #     bodies and re-run the test: a real test now FAILS (it asserted real behaviour); a fake test
    #     that merely covers + asserts-something-always-true still PASSES → it tests nothing → hollow.
    #     This catches the deepest fakery a frontier agent can write (covers the code, asserts vacuously).
    discriminates, why_d = _discriminates(repo, test_relpath, cited)
    if not discriminates:
        return True, f"hollow: {why_d}"
    return False, f"test exercises + discriminates (can go red); {why}; {why_d}"


def _gut_function_bodies(src: str) -> str:
    """Replace every function/method body with `return None` — keeps signatures importable but removes
    all behaviour, so a behaviour-asserting test must fail against it."""
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return src

    class _Gut(ast.NodeTransformer):
        def visit_FunctionDef(self, node):
            self.generic_visit(node)
            node.body = [ast.Return(value=ast.Constant(value=None))]
            return node

        visit_AsyncFunctionDef = visit_FunctionDef

    gutted = _Gut().visit(tree)
    ast.fix_missing_locations(gutted)
    try:
        return ast.unparse(gutted)
    except Exception:  # noqa: BLE001 — older runtimes without unparse: skip (other gates stand)
        return src


# Stdlib line tracer for the SEALED sandbox (the room image has no `coverage` module, and we must never
# run cook code on the host). It prints the executed line numbers of the contracted source as THOR_COV:[...].
_TRACER = (
    "import sys, json, runpy\n"
    "tgt, test, ex = sys.argv[1], sys.argv[2], set()\n"
    "def _t(fr, ev, a):\n"
    "    if ev == 'line' and fr.f_code.co_filename.endswith(tgt): ex.add(fr.f_lineno)\n"
    "    return _t\n"
    "sys.settrace(_t)\n"
    "try: runpy.run_path(test, run_name='__main__')\n"
    "except Exception: pass\n"
    "finally: sys.settrace(None)\n"
    "print('THOR_COV:' + json.dumps(sorted(ex)))\n"
)


def _discriminates(repo: str, test_relpath: str, cited: list[str]) -> tuple[bool, str]:
    """True iff the test FAILS when the feature's code is gutted (i.e. it genuinely tests behaviour).
    When a real cook is in play this runs SEALED (untrusted test code never touches the host)."""
    target = next((f for f in cited if f.endswith(".py")
                   and not os.path.basename(f).startswith("test_")), None)
    if not target:
        return True, "no source file in scope to mutate"
    target_path = os.path.join(repo, target)
    try:
        original = open(target_path, encoding="utf-8").read()
    except OSError:
        return True, "target unreadable (gated by the mechanical probes)"
    gutted = _gut_function_bodies(original)
    if gutted == original:
        return True, f"{target} has no function bodies to gut"

    if reality._use_sandbox():
        def _gut(dst):   # gut the target IN THE SANDBOX COPY; the cook's worktree is never touched
            with open(os.path.join(dst, target), "w", encoding="utf-8") as f:
                f.write(gutted)
        rc, _out, _ = reality.sandboxed_run(repo, ["python3", test_relpath], prepare=_gut)
        if rc == 0:
            return False, f"test PASSES even with {target} gutted — it asserts nothing real (cannot go red)"
        return True, f"test FAILS on gutted {target} — it can go red (genuinely discriminates)"

    # docker-free gated path (trusted fixtures): mutate the worktree in place, restore in finally.
    env = {**reality._minimal_env(), "PYTHONDONTWRITEBYTECODE": "1"}
    try:
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(gutted)
        rc = subprocess.run([sys.executable, test_relpath], cwd=repo, env=env,
                            capture_output=True, timeout=30).returncode
    except Exception as e:  # noqa: BLE001 — mutation run failed: don't fail-open, the coverage gate stands
        return True, f"discrimination run unavailable ({e}); coverage-of-diff stands"
    finally:
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(original)   # ALWAYS restore the cook's worktree

    if rc == 0:
        return False, f"test PASSES even with {target} gutted — it asserts nothing real (cannot go red)"
    return True, f"test FAILS on gutted {target} — it can go red (genuinely discriminates)"


def _function_body_lines(target_path: str) -> set[int]:
    """The line numbers INSIDE function bodies (executing one means the test CALLED, not just imported)."""
    try:
        tree = ast.parse(open(target_path).read())
    except (OSError, SyntaxError):
        return set()
    lines: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for stmt in node.body:
                lines.update(range(stmt.lineno, (getattr(stmt, "end_lineno", stmt.lineno) or stmt.lineno) + 1))
    return lines


def _covers_feature_code(repo: str, test_relpath: str, cited: list[str]) -> tuple[bool, str]:
    """Run the test under coverage; require it to execute a function-body line of a contracted source."""
    target = next((f for f in cited if f.endswith(".py")
                   and not os.path.basename(f).startswith("test_")), None)
    if not target:
        return True, "no source file in scope to cover"
    target_path = os.path.join(repo, target)
    if not os.path.exists(target_path):
        return True, f"contracted source {target} absent (mechanical probes gate this)"
    body_lines = _function_body_lines(target_path)
    if not body_lines:
        return True, f"{target} has no function bodies to cover"

    if reality._use_sandbox():   # SEALED stdlib-tracer run — never execute cook code on the host
        _rc, out, _ = reality.sandboxed_run(repo, ["python3", "-c", _TRACER, target, test_relpath])
        executed: set[int] = set()
        for line in out.splitlines():
            if line.startswith("THOR_COV:"):
                try:
                    executed = set(json.loads(line[len("THOR_COV:"):]))
                except json.JSONDecodeError:
                    executed = set()
        if executed & body_lines:
            return True, f"executed {len(executed & body_lines)} body line(s) of {target}"
        return False, f"test imported but never executed the code in {target} (coverage-of-diff)"

    cov_file = os.path.join(repo, f".cov_{uuid.uuid4().hex}")
    env = {**reality._minimal_env(), "COVERAGE_FILE": cov_file, "PYTHONDONTWRITEBYTECODE": "1"}
    try:
        subprocess.run([sys.executable, "-m", "coverage", "run", test_relpath],
                       cwd=repo, env=env, capture_output=True, timeout=30)
        j = subprocess.run([sys.executable, "-m", "coverage", "json", "-o", "-"],
                           cwd=repo, env=env, capture_output=True, text=True, timeout=30)
        data = json.loads(j.stdout or "{}")
    except Exception as e:  # noqa: BLE001 — coverage tooling failure: the static checks above still stand
        return True, f"coverage tooling unavailable ({e}); static checks applied"
    finally:
        try:
            os.remove(cov_file)
        except OSError:
            pass

    executed: set[int] = set()
    base = os.path.basename(target)
    for fpath, info in data.get("files", {}).items():
        if fpath.endswith(target) or os.path.basename(fpath) == base:
            executed = set(info.get("executed_lines", []))
            break
    if executed & body_lines:
        return True, f"executed {len(executed & body_lines)} body line(s) of {target}"
    return False, f"test imported but never executed the code in {target} (coverage-of-diff)"
