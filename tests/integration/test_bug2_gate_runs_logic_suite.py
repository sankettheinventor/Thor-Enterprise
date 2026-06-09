"""
BUG-2 (HIGH — empty test gate).

The commit gate (`make test`, addopts `-m 'not deferred'`) runs 1 of 165 tests; the moat-LOGIC suites
(policy in tests/leash, divergence/panel/probes/trusted-claim in tests/govengine) are all marked
`deferred` and never run on a commit. So a reworded bypass sails through the gate.

This test asserts the DEFAULT (non-deferred) selection actually exercises the moat logic — not just
the single S12 string-grep. RED today (those suites are deferred). Docker-free, un-deferred.
"""
import os
import subprocess
import sys


def _default_selected_node_ids():
    """Collect (without running) the tests the commit gate selects by default (addopts applies)."""
    root = "/repo" if os.path.isdir("/repo") else os.getcwd()
    out = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q",
         "-p", "no:cacheprovider", "--rootdir", root, "tests"],
        cwd=root, capture_output=True, text=True,
    )
    return [ln.strip() for ln in out.stdout.splitlines() if "::" in ln]


def test_bug2_gate_runs_moat_logic_suite():
    nodes = _default_selected_node_ids()
    govengine = [n for n in nodes if n.startswith("tests/govengine/")]
    leash = [n for n in nodes if n.startswith("tests/leash/")]
    print(f"default-selected tests: {len(nodes)} | govengine={len(govengine)} leash={len(leash)}")
    assert govengine, (
        "the commit gate runs NO govengine moat-logic tests (divergence/panel/probes/trusted-claim) "
        f"— the gate is effectively empty (BUG-2). total default-selected={len(nodes)}"
    )
    assert leash, "the commit gate runs NO leash policy tests (BUG-2)"
