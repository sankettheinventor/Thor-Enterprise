"""
Sub-module 6.1 — the Probe Runner. The 8 read-only probes (FR-3); all must pass for `done` (FR-2).

  Mechanical (objective): M1 verifier exit 0 · M2 commit landed (real SHA) · M3 diff touched the
                          contracts' cited files · M4 regression exit 0 · M5 every contract status:done.
  Review (behaviour during the work — the moat): R1 CTO skills passed · R2 zero gate-gaming hits in
                          the commit window · R3 zero security alarms in the window.

Each probe returns a ProbeResult(pass, evidence). Nothing here is trusted from the agent.
"""
from __future__ import annotations

from dataclasses import dataclass

from . import fake_test, reality

PROBE_ORDER = ("M1", "M2", "M3", "M4", "M5", "R1", "R2", "R3")


@dataclass
class ProbeResult:
    name: str
    passed: bool
    evidence: str


def run_all(ctx) -> list[ProbeResult]:
    """Run the 8 probes against reality. Raises reality.RealityError if reality can't be read (FR-15)."""
    c = ctx.contract
    repo, branch = ctx.repo, ctx.branch

    # ---- M1: verifier exit 0, but a hollow test is overridden to fail (fake-test-checker, FR-13) ----
    rc, out = reality.run_test(repo, c.get("test_file"))
    hollow, why = fake_test.is_hollow(repo, c.get("test_file"), c)
    if rc == 0 and hollow:
        m1 = ProbeResult("M1", False, f"verifier exited 0 but test is hollow: {why}")
    else:
        m1 = ProbeResult("M1", rc == 0, f"verifier exit={rc}" + (f"; {why}" if rc == 0 else f"; {out[:80]}"))

    # ---- M2: a real commit for this feature landed ----
    sha = reality.commit_sha(repo, ctx.feature_id, branch)
    m2 = ProbeResult("M2", bool(sha), f"commit={sha[:10] if sha else 'NONE'}")

    # ---- M3: the diff touched the files the contracts cited ----
    changed = reality.changed_files(repo, branch, ctx.base_branch)
    cited = set(c.get("scope", {}).get("files", []))
    missing = cited - changed
    m3 = ProbeResult("M3", not missing, f"cited={sorted(cited)} changed={sorted(changed)}"
                     + (f" MISSING={sorted(missing)}" if missing else ""))

    # ---- M4: regression/preventive test exit 0 ----
    rrc, rout = reality.run_test(repo, c.get("regression_file"))
    m4 = ProbeResult("M4", rrc == 0, f"regression exit={rrc}" + ("" if rrc == 0 else f"; {rout[:80]}"))

    # ---- M5: every contract for the feature is status:done ----
    contracts = c.get("contracts", [])
    open_ = [k.get("name") for k in contracts if k.get("status") != "done"]
    m5 = ProbeResult("M5", not open_ and bool(contracts), f"open_contracts={open_}" if open_
                     else f"all {len(contracts)} contracts done")

    # ---- R1: CTO skill checks (stub: read from context; CTO is a later module) ----
    skills_ok = ctx.skill_results_ok
    r1 = ProbeResult("R1", skills_ok, "skills passed" if skills_ok else "a CTO skill check failed")

    # ---- R2: zero gate-gaming hits in the window + the diff STAYS WITHIN SCOPE (the moat) ----
    # Containment (defense-in-depth, C2): an out-of-scope, non-test file in the diff is an escape — caught
    # HERE at the verdict even if no in-room decide-before denied it (a cook with no hook, or one that
    # bypassed it). COOK.md: the hook is courtesy; the verdict is the enforcement. `changed`/`cited` reuse M3.
    hits = reality.gate_hits(ctx.manager, ctx.commit_window)
    out_of_scope = sorted(f for f in changed if f not in cited and not _is_test_file(f, c))
    r2_ok = not hits and not out_of_scope
    ev = f"gate_hits={len(hits)}" + (f" {[h['event_type'] for h in hits]}" if hits else "")
    r2 = ProbeResult("R2", r2_ok, ev + (f" OUT-OF-SCOPE={out_of_scope}" if out_of_scope else ""))

    # ---- R3: zero security alarms in the window (the moat) ----
    alarms = reality.security_alarms(ctx.manager, ctx.commit_window)
    r3 = ProbeResult("R3", not alarms, f"security_alarms={len(alarms)}")

    return [m1, m2, m3, m4, m5, r1, r2, r3]


def _is_test_file(path: str, c: dict) -> bool:
    """Exempt from scope-containment (R2): the cook is expected to write the contracted verifier/regression
    tests (named in the contract) plus conventional test files."""
    base = path.rsplit("/", 1)[-1]
    return (path in (c.get("test_file"), c.get("regression_file"))
            or base.startswith("test_") or base.endswith("_test.py"))
