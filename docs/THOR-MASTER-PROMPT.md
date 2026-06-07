# THOR ENTERPRISE — MASTER WIRING PROMPT (Claude Code: your operating procedure. Hard law.)

You are wiring THOR Enterprise — 17 built modules — into ONE proven end-to-end product. Task 0 (run
target) and Task 1 (Wall, proven over live Docker) are DONE. You are continuing the same disciplined
pattern. This prompt is how you decide and act so you move FAST without drift, rework, or breaking
working code. Read it fully. It governs every move.

## YOUR REFERENCE SET (read these; they are the truth, in this priority order)
1. THE ACTUAL CODE in ~/thor-enterprise — the highest truth. When anything conflicts, the code wins.
2. THE ORIGINAL THOR in _reference/ — proven doctrine to PORT (never import, never extend).
3. THOR-INTEGRATION-PRD.md — the seams, golden flows, failure matrix, edge cases, the unified test
   suite, AND §7b "what is already correct — DO NOT change." This is your wiring blueprint.
4. THOR-WIRING-MANUAL.md — the architecture (CTO=brain, Manager=mechanism, etc.) + the 10 hard rules.
5. THOR-CTO-SCALING-DECISION.md — per-room Leash (cheap, mechanical) vs shared CTO (plans + escalations).
6. THOR-DRIFT-CHECK.md / THOR-UNDERSTANDING.md — how THOR really works; the 3 drifts to fix.

## THE TWO FAILURE MODES YOU MUST AVOID (this is why this prompt exists)
A. DRIFT — changing how THOR is supposed to work (e.g. routing decisions through the Manager, calling
   the Manager "the brain", loosening the verdict). Drift = wrong product.
B. REWRITING WORKING CODE — "improving" a module whose logic is already correct. The gaps are UNWIRED
   SEAMS, not broken logic. Rewriting working code = self-inflicted bugs + rework. (See Integration PRD §7b.)
The cure for both: wire the SEAM, leave the working MODULE alone, and when unsure STOP and ask.

## THE DECISION PROTOCOL (run this for EVERY change, before you write code)
1. WHICH GAP am I closing? Name it (C1/C3/C4/H6/H7/H9/...). One gap per change. If I can't name it, stop.
2. IS THE TARGET A SEAM OR A MODULE? 
   - SEAM (two modules don't talk, or talk to the wrong place) → wire it. PROCEED.
   - MODULE LOGIC (the behavior inside a working module) → is it in Integration PRD §7b "do not change"?
     If yes → STOP, ask. If it's genuinely broken (not just "improvable") → STOP, show me why, ask.
3. DOES THIS PRESERVE THE INVARIANT? (decide-before · judge-from-reality · record-everything ·
   human-signs · fail-closed). If the change would weaken any → STOP, ask. The moat gets HARDER, never easier.
4. IS IT PLAN-FIRST? (T3 Leash, T5 Verdict Coordinator, T8 Sentinel, T10 Adapters, or anything touching
   the moat/governance core) → show me the PLAN in plain words, wait for approval, THEN code.
   Non-moat mechanical wiring → proceed, show real output.
5. AM I GUESSING? Any ambiguity, any architectural fork not in the refs → STOP, ask. A question is
   cheaper than unwinding a wrong assumption.

## THE PER-TASK LOOP (the rhythm that worked for Task 1 — repeat it exactly)
For each task, in order (T2 → T10):
  a. READ FIRST — read the real files the task touches + the Integration PRD seam(s) + §7b. Tell me what
     you read and what you found (as you did for Task 1).
  b. PLAN (if PLAN-FIRST) — plain-words design of the seam wiring; name what you wire and what you LEAVE
     ALONE; wait for my OK.
  c. WIRE THE SEAM — connect the modules. Do NOT rewrite the working module behind the seam.
  d. PROVE OVER THE LIVE PLANE — run the real thing (live Docker/Postgres/the booted control plane),
     observe real output (not asserted). Then un-skip that module's ACs as real gated tests
     (`pytest -m deferred tests/<module>`) AND add the Integration PRD's seam/flow test.
  e. HONESTLY DEFER what truly can't run yet — keep it `skip` with a NAMED reason (like Task 1's
     AC-8/AC-9). Never fake green (Rule 11).
  f. NAME ANY STRUCTURAL FIX you had to make (like Task 1's package-shadow + deferred-deselect). No silent fixes.
  g. COMMIT — one gap, named message; push a fully-wired GREEN module. Never push a half-wired module.
  h. UPDATE the register row → CLOSED with file:line; tell me; STOP for the next task's go-ahead.

## THE TASK ORDER (with the gap each closes + PLAN-FIRST marks)
T2  Manager — make sole-writer REAL: route the 8 bypassers through `_record` (H6); unify the Leash's
    local JSONL chain into the Manager via `record_decision` (H7); give crash-replay a real caller (M1);
    note the thread-lock-not-DB-lock concurrency limit (M4, hardening-list, don't fix now).
T3  [PLAN-FIRST] CTO + Leash — wire `InRoomProxy` into the REAL cook action path so every cook write
    goes through it BEFORE executing (C1); per-room cheap Leash, shared CTO for plan+escalation
    (CTO-SCALING doc); fail-closed if governor down; skill inject-before (drift-3 first half).
    DO NOT change `leash/policy.py` logic — it's correct (§7b); wire it in + route records through Manager.
T4  PM + Scheduler + Contract — PM enforces scope/SDLC for real; scheduler dispatches real waves;
    the six-message contract is the live room↔control wire.
T5  [PLAN-FIRST] GovEngine (the moat) — build the HONEST Verdict Coordinator (`manager.run_verdict`)
    that DERIVES claim/contract/commit_window from trusted Manager+PM+Contract state, never the actor (C4);
    wire R1 to a real skill-verifier, stop defaulting to pass (H2); STRENGTHEN (don't replace) the
    fake-test check toward coverage-of-diff (H1); enforce freshness before merge (R9). DO NOT loosen the
    panel/divergence — they're correct (§7b). The moat gets HARDER.
T6  SDLC — bind the signature-gate setters to VERIFIED Manager cards (H9 — `is_card_approved`); drive the
    bridge's merge-card from a live `done` verdict; wire lifecycle→merge after Sig3. DO NOT change the
    transition-ordering logic — it's correct (§7b).
T7  [PLAN-FIRST] Dashboard + Mobile — serve the dashboard; make the Sign button actually sign (real
    Ed25519 handler, verified by the Manager); show real rooms/stages/cost/audit; the deferred button
    until now shown disabled-with-reason. FLOW A must be visible end-to-end on the dashboard.
T8  [PLAN-FIRST] Sentinel — make `halt()` ACTUALLY halt: call Wall destroy/pause + block new work (C3);
    real liveness probes of the live services; add a brief re-probe before halting to avoid flap-thrash (R6).
T9  Self-Audit — stand up the real local model (Ollama/Qwen); zero frontier calls; URGENT→Sentinel.
T10 [PLAN-FIRST] Adapters — the Strangler decision (route Manager/Wall THROUGH audit/identity adapters,
    or drop the pretense — decide WITH me); strengthen arch-lint beyond import-strings.
FINAL — full unified suite green (integration seams + all ~144 ACs) over the booted system; tag a release.

## WHAT "USE OPENHANDS" MEANS (the split, held)
- OpenHands = mechanical muscle ONLY: un-skipping ACs, plumbing, the dashboard UI wiring, the
  integration-test scaffolding. Clear-right-answer grunt work.
- HAND-WIRED with me, plan-first: T3 Leash, T5 Verdict Coordinator, T8 Sentinel — the moat. An
  autonomous agent never wires the thing that catches its own lies.

## OUTPUT DISCIPLINE (every turn)
- Say which gap, whether it's a seam or module, and (if module) why it's not §7b.
- Real observed output, never asserted/faked. Name every structural fix. WSL/Linux paths only.
- THOR does NOT govern its own build (P7) — no watchdog/governance banner on this work.
- End each task: committed green module + register row CLOSED + STOP for go-ahead. One gap at a time.

## THE DEFINITION OF DONE (the whole product)
`start` brings the plane up; the DASHBOARD shows FLOW A live; a real feature goes plan → build (sealed
Docker room) → independent QA → verdict-from-reality → CEO signs → Gitea merges → room destroyed; a real
out-of-scope action is BLOCKED before it executes; a fabricated claim / hollow test / gamed gate CANNOT
get a false done; the Sentinel HALTS on a killed governor; and the unified suite (seams + ~144 ACs) is
green over the booted system. THEN tag the release. That is THOR Enterprise, proven.
