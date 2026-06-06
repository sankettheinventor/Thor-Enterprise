# THOR — WIRING PHASE TASK LIST (the ordered plan; work top to bottom)

Each task = wire the seam, then make that module's ACs real gated tests, then commit (naming the
gap), then update the register row to CLOSED. Push to GitHub after each module is green.
"Show the plan first" applies to every task marked [PLAN-FIRST].

## TASK 0 — The run target (fixes C2) [PLAN-FIRST]   ← do this first; it unblocks everything
The system must actually run as a system. Stand up ONE start path:
  - serve the FastAPI apps (real uvicorn, real ports per System Design 3) OR one supervisor process,
  - fill docker-compose.yml so the control plane comes up,
  - one documented "start THOR" entry point.
Done when: `start THOR` brings the control plane up and modules talk over the real transport
(not in-process inside smokes). No module logic changes yet — just make it runnable.

## TASK 1 — Wall (the most real; lightest wiring)
Wire: confirm Manager→provision/destroy/verify-identity runs over the real run target.
Prove: un-skip Wall ACs (AC-1..AC-12) as gated tests against the running Wall.
(Note: one-door egress AC-5/6/9 stays in its sealed-shut form unless we do the host-firewall path;
flag if it must be done now.)

## TASK 2 — Manager (fixes H6, H7, M1, M4) [PLAN-FIRST]
Wire: make Manager the SOLE EventLog writer for real — route the 5 bypassing modules
(govengine, sentinel, dashboard, mobile, contract) through Manager._record; unify the Leash's
separate JSONL chain into the Manager (kill the split-brain, H7); give crash-replay a real caller (M1).
Prove: Manager ACs gated, incl. tamper-evident chain + crash-replay against the running Manager.

## TASK 3 — Leash (fixes C1) [PLAN-FIRST]   ← a critical one
Wire: put the InRoomProxy / check_action in the REAL cook action path. The SDLC BuildStage must
route its writes/actions THROUGH the leash, so an out-of-scope write is actually intercepted and
denied before it executes. This is the P3 promise made real.
Prove: Leash ACs gated against the wired path — incl. a real out-of-scope action denied, fail-closed
when the governor is down, every decision a Manager-recorded signed event.

## TASK 4 — Contract + Scheduler (fixes M2, M3)
Wire: Contract is the live six-message wire format between Manager and rooms (not smoke-only);
Scheduler actually dispatches via CTO→Manager in the running system.
Prove: Contract P5 (read-only slice) tested over the real Docker-exec transport; Scheduler
deterministic-wave + budget ACs gated.

## TASK 5 — GovEngine, the MOAT (fixes C4, H1, H2) [PLAN-FIRST]   ← most important + most dangerous
Wire: build the HONEST Verdict Coordinator (run_verdict) that DERIVES claim/contract/commit_window
from trusted Manager + Contract state — never from the actor. (Closes C4: claim={} can no longer
disable the lie-detector.)
Harden: replace the regex fake-test check with execution-based evidence (does the test actually
exercise the changed code? coverage/mutation) (H1); implement R1 against real CTO skill results (H2);
enforce freshness before merge.
Prove: the adversarial suite — a fabricated claim, a hollow-but-referencing fake test, a gamed/narrow
window, a curated scope — NONE can get a false "done". This is THE test that matters most.

## TASK 6 — SDLC (fixes H9; notes H4)
Wire: bind the three signature gates to VERIFIED Manager cards (not plain setters); make the
lifecycle actually drive the merge via gitea_adapter after Signature 3.
Prove: Genesis→Build→QA→Verdict→merge end-to-end with real signature verification at each gate.
(H4 — cook/QA are deterministic stand-ins — is a known limit; flag whether real-model QA is in scope
now or deferred. Don't silently pretend QA is adversarial when it's zeros-only.)

## TASK 7 — Dashboard + Mobile (fixes M5, M6)
Wire: serve the Dashboard HTTP API; make the cockpit Sign button actually sign (real handler);
real per-feature spend (not estimate-as-spend). Mobile: confirm the E2EE path works over the real
run target; relay/push remain documented stand-ins unless the real Cloudflare worker is in scope.
Prove: a verified-signature merge driven from the served Dashboard; phone signs over E2EE end-to-end.

## TASK 8 — Sentinel (fixes C3) [PLAN-FIRST]   ← a critical one
Wire: make halt() ACTUALLY halt — call Wall destroy/pause and Manager kill on confirmed failure;
real liveness/responsiveness probes of the running services (not in-process lambdas).
Prove: a deliberately-killed leash is detected and the scope fail-closes for real; a forced-pass
canary triggers a real halt; the silent-heartbeat base case works.

## TASK 9 — Self-Audit (fixes M7)
Wire: stand up a real local model (Ollama/Qwen) for the inspector; confirm zero frontier calls;
URGENT→Sentinel escalation over the real path.
Prove: zero-token-cost inspection runs continuously; a seeded anomaly escalates; read-only enforced.

## TASK 10 — Adapters: the Strangler decision (fixes H5, H3, M8, M9) [PLAN-FIRST]
Decide + wire: either route Manager/Wall THROUGH audit_adapter/identity_adapter (make the Strangler
real) OR drop the adapter pretense for those two (H5). Strengthen arch_lint beyond import-strings (M8).
ci_result (H3) and compliance (M9) are improved or explicitly marked representative.
Prove: the substitution harness proves a real swap for whatever adapters we keep.

## FINAL — full-system proving
All ~144 ACs un-skipped and green as gated CI tests, running against the WIRED system end-to-end.
The thesis demonstrated for real: human in command, isolated, governed, judged-from-reality,
auditable, self-verifying. THEN tag a release and push.

## The loop for every task
plan-first (if marked) → wire the seam → un-skip + gate the ACs → real output, no fakes →
commit naming the gap → update register row to CLOSED → push when the module is green → next.
