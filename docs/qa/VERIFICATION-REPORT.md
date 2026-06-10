# THOR Enterprise — Verification Campaign Report

**Date:** 2026-06-09 · **Branch:** `qa/verification-campaign` · **Environment:** WSL Ubuntu, Docker
29.1.3, Python 3.14.4, Postgres 16 (container), Ollama 0.30.7 + `qwen2.5:3b`, Node 24 (WSL).

## Headline (calibrated — not "no bugs")

> **All 4 named critical bugs are closed with red→green proof; the core mechanism is proven on the
> live system from clean (155 passed / 9 skipped, exit 0) and on one human-signed end-to-end merge.
> The audit surfaced 4 NEW issues (2 fail-open in the Sentinel halt path) — all now ALSO fixed with
> red→green proof (follow-up, post-sign-off); 9 acceptance tests remain deferred for named reasons;
> multi-process races are unverified.**

Testing reduces uncertainty; it does not prove zero bugs. What follows is exactly what passed and what
remains unchecked.

---

## 1. The four named bugs — fixed?

Every fix was proven RED first (Phase 1) and GREEN after (Phase 2), in the isolated QA room, with the
neighbours re-run. One fix per commit.

| Bug | Severity | Fixed | Red→Green evidence | Exercised live by |
|-----|----------|-------|--------------------|-------------------|
| **BUG-1** path-traversal / sandbox escape | CRITICAL | ✅ | `test_bug1_path_traversal_denied` 2 failed → 2 passed; policy `allow`→`deny`, proxy wrote-outside → no-escape | FLOW B (demo: `infra/secrets.tf → DENY, file on disk: False`); `policy_logic` gate |
| **BUG-2** empty test gate (1 of 165) | HIGH | ✅ | gate **1 → 25→27 selected**; `test_bug2_gate_runs_moat_logic_suite` red→green; AST S12 proven to catch a space-reworded bypass the grep missed | every `make qa`/`make test` |
| **BUG-3** optional replay lock | MED | ✅ | `test_bug3_nonce_mandatory` failed → passed (no-nonce signature now rejected); extended to the phone path | FLOW E (`replayed_nonce_rejected`); mobile 12 ACs; flow_a |
| **BUG-4** lie-detector fails open | MED | ✅ | `test_bug4_empty_claim_escalates` 2 failed → 2 passed (empty claim + green verifier → escalate) | govengine ac2 (fabricated claim escalates), ac1/ac9 stay `not_done` |

**Root causes + fixes:** BUG-1 — `policy._matches` matched the raw path string and `proxy._execute`
joined the raw target → reject `..`/absolute before scope match + realpath-containment at the disk
boundary. BUG-2 — the gate ran only the S12 grep → added docker-free policy/divergence/panel logic
tests to the gate + replaced the grep with an AST check. BUG-3 — nonce checked only `if not None` →
made it mandatory + wired the nonce round-trip through mobile. BUG-4 — `if not claim: return clean` →
empty claim with a green verifier now escalates (fail-closed), while an already-failing build stays
`not_done` (preserves the canary contract). No working guard was weakened; all 5 invariants preserved.

## 2. The core mechanism — proven on the live system

- **`make prove` from clean:** `155 passed, 9 skipped, 27 deselected — exit 0` in 8:02. Fresh Postgres
  + real Docker rooms; rooms empty before/after/teardown (deterministic).
- **Five golden flows green:** FLOW A (spine + stale-verdict-refused), FLOW B (out-of-scope blocked
  before disk), FLOW C (`moat_adversarial` — fabricated/hollow/undisclosed never reach `done`), FLOW D
  (governor dies → physical halt, proportionate, no flap-thrash, broken-canary halts), FLOW E (human
  signs; forged / replayed / no-nonce / unregistered all rejected).
- **One feature end-to-end (`make demo`):** DEMO1 → CTO scope → sealed room → in-scope build /
  out-of-scope blocked → independent QA room → verdict-from-reality (honest=DONE 8/8 probes;
  fabricated backdoor=ESCALATE, lie caught) → **CEO signs Ed25519 + nonce, verified=True → REAL git
  merge (`main` → `2a19847`) → room destroyed, branch persists** → governor dies → Sentinel HALT.
  Dashboard reflected it: `/lies total=1` (undisclosed `src/backdoor.py`), `/audit feed` ledger.
- **Database persistence / replay:** `rebuilt_matches=True` (replay proof) + manager
  `ac3_replay_rebuilds_exact_state` live — the EventLog is the source of truth.
- **Live Qwen self-audit:** `model=ollama-qwen, model_loaded=True, frontier_calls=0`,
  `PARALLEL_OVERLAP=True`, planted anomaly escalated URGENT to the Sentinel, and an EventLog write via
  the `selfaudit` role **DENIED** (`InsufficientPrivilege: permission denied for table eventlog`).

## 3. Suite accounting

- **Live (`make prove -m deferred`):** 155 passed, **0 failed**, 9 skipped.
- **Gate (`make qa` / `make test`, docker-free):** 27 passed, 0 failed (was 1 before BUG-2).
- **The 9 skips — each a NAMED deferral, none a failure:**
  | Skip | Reason |
  |------|--------|
  | leash ac5 raw-HTTP bypass | Phase 2b one-door network lock (M2) |
  | leash ac6 no credentials in container | AGT credential injector (M12) |
  | leash ac8 second cook same leash | non-Claude cook adapter (M12) |
  | leash ac9 malicious-tool killswitch | exercised by smoke_leash_2b (M12) |
  | leash ac10 no-unaudited-allow under load | load test (M2 Phase 2b) |
  | leash ac12 AGT version bump | Strangler test (T10/M12) |
  | manager ac6 claim_done drives QA | needs the full live cook |
  | wall ac8 crash recovery resumes | crash-recovery harness |
  | wall ac9 same image compose & k8s | k8s parity |

## 4. New issues found by the audit — all FIXED in the post-sign-off follow-up

Each was reported first (Phase 3), then fixed after sign-off with red→green proof, one commit each.

1. **FINDING-B (HIGH)** `sentinel/core.py` `_destroy_rooms` — a halt that couldn't read Manager state
   destroyed **zero** rooms silently. **FIXED** (`9fe5c44`): alarm + fall back to killing rooms by
   Docker label (reality). Test: `test_finding_bc_halt_failclosed` (red→green, right reason).
2. **FINDING-C (MED)** `sentinel/core.py` `_destroy_rooms` — a room that failed to die was swallowed as
   "already gone". **FIXED** (`9fe5c44`): verify via Docker `health.alive`; a still-alive room raises a
   critical alarm and is not reported as killed.
3. **FINDING-A (LOW–MED)** `wall/provisioner.py` — import-time `docker.from_env()`. **FIXED** (`2a18f14`):
   lazy `_ensure_client()`; import no longer needs a daemon; the QA room is re-sealed (no docker socket).
   Test: `test_finding_a_lazy_docker`.
4. **Minor** `sentinel/core.py:111` — unaudited-halt swallow. **FIXED** (`9fe5c44`): a halt whose ledger
   record fails now surfaces `rec.recorded=False`/`audit_error`. `ruff`: 4× F401 unused imports
   **removed** (`c4e9596`) — ruff now All-checks-passed; compileall + arch-lint clean.

Neighbours verified green after the fixes: Sentinel ACs + FLOW D real-halt = 16 passed live; `make qa`
= 30 passed. (Full `make prove` re-run after the fixes — see §2.)

## 5. What we did NOT / COULD NOT verify (the honest gaps)

- **The 4 new findings are now fixed + regression-tested** (docker-free unit tests assert the
  fail-closed alarms; neighbours green). What remains unproven there: the *real* DB-down / wedged-
  container conditions are simulated with fakes, not reproduced against a genuinely crashed Postgres or
  a real stuck Docker container — the fail-closed *logic* is proven, the *physical* extreme is not.
- **Multi-process races:** R6 (governor flap-thrash under concurrency) and load tests (many parallel
  rooms) are single-process-tested or deferred — true concurrency is unverified.
- **The 9 deferred ACs** above (k8s parity, crash recovery, raw-HTTP egress lock, real non-Claude cook,
  credential isolation, killswitch, AGT version bump) are unproven in this environment.
- **A BUG-3 regression escaped the Phase-2 commit** (6 nonce-less test helpers) and was only caught by
  the full `make prove` in Phase 4; no product code was affected, fixed in `f0c35c8`. The neighbour
  check at commit time was too narrow — a process gap, now closed by running full prove.
- **No exhaustive fuzzing / no security pentest** beyond the targeted adversarial suite. "No bugs" is
  not claimed — only that these specific checks passed.
- **Dashboard UX** is a known clutter problem, parked separately in `DASHBOARD-UX-BACKLOG.md` (not a
  correctness defect).

## 6. Commits (branch `qa/verification-campaign`)

```
c4e9596 chore(lint): remove 4 F401 unused imports + mark findings A/B/C/minor FIXED
9fe5c44 fix(FINDING-B/C): the Sentinel HALT now fails CLOSED (C3 must always enforce)
2a18f14 fix(FINDING-A): create the Docker client lazily — import no longer needs a daemon
68b5590 qa(phase5): final verification report + parked dashboard UX backlog
b82f722 qa(phase4): live end-to-end proof artifacts (replay + live-Qwen self-audit)
f0c35c8 fix(BUG-3 followup): supply the now-mandatory nonce in signature-gate test helpers
348c8e3 qa(phase3): edge tests (R7 heartbeat, R11 maintenance) + audit findings register
e241ea6 fix(BUG-4): empty/missing claim fails CLOSED in divergence.detect()
45409b0 fix(BUG-3): make the one-time nonce mandatory in approve()
3b4c109 fix(BUG-2): make the commit gate exercise the moat logic (was 1 of 165) + AST S12
140532e fix(BUG-1): block path-traversal/absolute writes (sandbox escape) — defense in depth
f9058b0 qa(lab): isolated throwaway QA room (Phase 0) + THOR_PG env switch
```
