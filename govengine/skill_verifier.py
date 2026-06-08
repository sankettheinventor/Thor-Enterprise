"""
Sub-module 6.6 — the Skill Verifier (the R1 producer). Closes H2.

R1 used to read `ctx.skill_results_ok`, which DEFAULTED True and was caller-supplied — a hollow probe.
This module produces REAL per-skill verdicts by running deterministic predicates against the
feature's artifacts (its changed source + test files), ported from the original `skill-verifier.js`
(F054). Pure, read-only, no LLM. R1 passes ONLY if every checkable skill passes; a feature with no
checkable artifacts is a vacuous pass (the mechanical probes still gate it).
"""
from __future__ import annotations

import os
import re


def _read(repo: str, rel: str) -> str:
    p = os.path.join(repo, rel)
    try:
        return open(p).read()
    except OSError:
        return ""


def _is_test(rel: str) -> bool:
    b = os.path.basename(rel)
    return b.startswith("test_") or b.endswith("_test.py")


# ── predicates (each returns (status, detail)) ──────────────────────────────
def check_assertions_are_literal(test_srcs):
    """testing_is_disproof — forbid trivially-true assertions in test files."""
    offenses = []
    for path, src in test_srcs:
        for a in re.findall(r"assert\s+(.+)", src):
            if a.strip().rstrip(",)").strip() in ("True", "1", "(True)", "bool(True)"):
                offenses.append(f"{path}: trivial `assert {a.strip()[:20]}`")
    return ("fail", "; ".join(offenses[:5])) if offenses else ("pass", "assertions are non-trivial")


def check_no_skipped_tests(test_srcs):
    """flaky_tests_are_bugs — forbid skip/only markers (test-runner cheats)."""
    forbidden = ("@pytest.mark.skip", "pytest.skip(", "@unittest.skip", ".only(", "@pytest.mark.xfail")
    offenses = [f"{p}: {pat}" for p, s in test_srcs for pat in forbidden if pat in s]
    return ("fail", "; ".join(offenses[:5])) if offenses else ("pass", "no skip/xfail/only markers")


def check_http_timeouts(src_files):
    """timeout_on_every_network_call — every network call must set a timeout."""
    net = re.compile(r"\b(requests\.(?:get|post|put|delete|request)|urlopen|httpx\.(?:get|post|request))\s*\(")
    offenses = []
    for path, src in src_files:
        for m in net.finditer(src):
            if "timeout" not in src[m.start():m.start() + 400]:
                offenses.append(f"{path}: {m.group(1)}(... no timeout")
    return ("fail", "; ".join(offenses[:5])) if offenses else ("pass", "network calls carry a timeout")


def check_no_empty_except(src_files):
    """error_messages_are_actionable — forbid a silent `except: pass`."""
    exc = re.compile(r"except[^\n:]*:\s*(?:#[^\n]*)?\n\s*pass\b")
    offenses = [f"{p}: silent `except: pass`" for p, s in src_files if exc.search(s)]
    return ("fail", "; ".join(offenses[:5])) if offenses else ("pass", "no silent exception swallowing")


def verify(repo: str, changed_files, test_files) -> tuple[bool, dict]:
    """Return (all_pass, {skill_id: {status, detail}}). `changed_files`/`test_files` from trusted state."""
    src = [(f, _read(repo, f)) for f in changed_files if f.endswith(".py") and not _is_test(f)]
    src = [(f, s) for f, s in src if s]
    tests = [(f, _read(repo, f)) for f in test_files if f]
    tests = [(f, s) for f, s in tests if s]
    skills = {
        "qa_tester.testing_is_disproof": check_assertions_are_literal(tests),
        "qa_tester.flaky_tests_are_bugs": check_no_skipped_tests(tests),
        "dev_backend.timeout_on_network": check_http_timeouts(src),
        "dev_backend.no_silent_catch": check_no_empty_except(src),
    }
    results = {k: {"status": s, "detail": d} for k, (s, d) in skills.items()}
    all_pass = all(v["status"] != "fail" for v in results.values())
    return all_pass, results
