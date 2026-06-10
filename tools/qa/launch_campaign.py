"""
P8 — THE LAUNCH CAMPAIGN. Runs the 8 moat attacks against the ASSEMBLED system and asserts NONE earns a
false "done". Each attack maps to a moat invariant. All green = the launch gate is met.

Run (from ~/thor-enterprise):  PYTHONPATH=. .venv/bin/python tools/qa/launch_campaign.py
"""
import subprocess
import sys

ATTACKS = [
    ("1  fabricated claim caught (divergence vs reality)", "judge-from-reality",
     "tests/integration/test_moat_adversarial.py::test_moat_fabricated_claim_caught_and_loop"),
    ("2  hollow-but-referencing test rejected (coverage-of-diff)", "anti-fake-test",
     "tests/integration/test_moat_adversarial.py::test_moat_hollow_test_not_done"),
    ("2b test that asserts nothing rejected (must go RED)", "anti-fake-test",
     "tests/govengine/test_fake_test_discrimination.py::test_vacuous_covering_test_is_caught"),
    ("3  undisclosed/curated change caught (trusted claim)", "trusted-inputs (C4)",
     "tests/integration/test_moat_adversarial.py::test_moat_undisclosed_change_caught"),
    ("4  real non-zeros bug caught (adversarial QA)", "judge-from-reality",
     "tests/sdlc/test_qa_adversarial.py::test_non_zeros_bug_is_caught"),
    ("5  stale verdict refused before merge (R9)", "freshness",
     "tests/integration/test_flow_a_merge.py::test_flow_a_stale_verdict_refused"),
    ("6  out-of-scope write denied before disk (FLOW B)", "decide-before",
     "tests/integration/test_flow_b_out_of_scope_blocked.py"),
    ("7  killed governor halts work (FLOW D)", "fail-closed",
     "tests/integration/test_flow_d_governor_halts.py"),
]


def run_pytest(nodeid):
    # `-o addopts=` clears the project default (`-m 'not deferred'`) so an explicit node id runs whether
    # it is a fast gate test or a live `deferred` one — the campaign mixes both.
    r = subprocess.run([".venv/bin/python", "-m", "pytest", nodeid, "-o", "addopts=", "-q",
                        "-p", "no:cacheprovider"], capture_output=True, text=True)
    return r.returncode == 0


results = []
for name, invariant, nodeid in ATTACKS:
    ok = run_pytest(nodeid)
    results.append((name, invariant, ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {name:55s} | {invariant}")

cc = subprocess.run(["sh", "-c", "PYTHONPATH=. .venv/bin/python tools/qa/prove_concurrent_writer.py"],
                    capture_output=True, text=True)
cc_ok = "P0_CONCURRENT_WRITER_OK" in cc.stdout
results.append(("8  ledger chain holds under concurrency (no fork)", "single-writer", cc_ok))
print(f"[{'PASS' if cc_ok else 'FAIL'}] {'8  ledger chain holds under concurrency (no fork)':55s} | single-writer")

all_ok = all(ok for _, _, ok in results)
print()
print("=" * 70)
print("LAUNCH CAMPAIGN: " + ("GREEN — no attack earned a false done ✓" if all_ok
                             else "RED — an attack got through ✗"))
print("=" * 70)
sys.exit(0 if all_ok else 1)
