# THOR ENTERPRISE — THE WIRING MANUAL  (HARD LAW. Follow exactly. No drift.)

PURPOSE: assemble the 17 built parts into ONE end-to-end running product, wired the way the REAL
original THOR works, then test it. Grounded in a file:line read of the actual original THOR source
(`_reference/`) — not memory, not the PRDs alone. Where this manual and your instinct differ, THIS
MANUAL WINS. Where this manual and the original THOR code differ, STOP and ask. Do not redesign.

> This manual supersedes the brain-framing in any earlier plan. It sits alongside
> `THOR-WIRING-RULES.md`, `THOR-WIRING-TASKLIST.md`, and `GAP-AND-RISK-REGISTER.md`.

## PART A — HOW THOR ACTUALLY WORKS (the architecture to wire to)

THOR is a governance layer OUTSIDE the AI. The AI (the "cook"/Builder) writes code; it can NEVER
govern itself, never touch the governance code, memory, or audit log. The HUMAN (CEO) holds the only
approval key. This is the soul. Do not weaken it.

Three guard-roles + the human + the builder:

1. **CTO = THE BRAIN (decides BEFORE the action).**
   - Every action the cook attempts is sent to the CTO first → AUTO-ALLOW / ALLOW+GUIDE (inject skill
     reminder) / BLOCK (stop+explain) / ESCALATE (CEO card).
   - The CTO also decides skills + scope per task. It is the only role that "reasons."
   - FAIL-CLOSED SPINE: if the CTO/governor is unreachable, ALL work is blocked until restarted.
     Silence = stop. Non-negotiable; THOR's core safety property.

2. **WATCHDOG-LINEAGE = THE ENFORCER + SUPERVISOR.** In Enterprise this is SPLIT cleanly into:
   - the **ROOM MECHANISM** (the "Thor Manager"): provisions/routes/destroys the sealed Docker rooms,
     and is the SINGLE writer of the audit ledger/EventLog. IT DECIDES NOTHING. It is the hands.
   - the **SENTINEL**: meta-governance/health — checks THOR itself is alive, loaded, connected,
     untampered, still-catching; CAN HALT.
   - file/scope **PROTECTION**: the cook may only write inside approved scope; governance code, memory,
     and the audit log are PROTECTED (read-only / revert unauthorized writes).

3. **PM = THE PLAN (heart):** the catalog of features, the scope per session, the SDLC rules (no
   feature without a spec, no commit without contracts).

+ **CEO** = the human. The ONLY approval key. Signs plan, rework, merge.
+ **COOK** = the AI builder. Writes code in approved scope only. Touches no governance.

THE FLOW (one feature, end to end — wire it in THIS shape):
CEO sets direction → CTO plans the feature (skills + scope) → ROOM MECHANISM provisions a sealed
room + puts the cook in → cook works; EVERY action goes to the CTO FIRST (decide-before) with top-1%
skills INJECTED before/during → PM enforces scope/SDLC → cook claims done (a knock, not a verdict) →
independent QA tries to break it → the VERDICT ENGINE computes "done" from 8 probes against REALITY
(never the cook's word) + the anti-hallucination/claim checker → CEO SIGNS the merge → Gitea executes
→ room destroyed → SENTINEL + Self-Audit watch the whole machine and can halt. Everything is an event
in the single ledger.

THE CRITICAL CORRECTION: There is NO single "Manager brain." The BRAIN is the CTO. The ENFORCER/HEALTH
is the Sentinel/protection. The PLAN is PM/SDLC. The "Thor Manager" is ONLY the room mechanism + the
single ledger writer. Do not route decisions through the Manager.

## PART B — THE THREE DRIFTS TO FIX (port the REAL solution from `_reference/`)

- **DRIFT 1 — R1 (skills-passed probe) hardcoded True.** Original fix: a real skill-verifier gathers
  the feature's commits+diffs and produces REAL per-skill verdicts. WIRE R1 to a real skill-verifier;
  R1 must be able to FAIL.
- **DRIFT 2 — fake-test detection is a weak regex.** Original fix: a LIVE anti-hallucination auditor
  (the "L2 auditor") + audit catches (ANTIHALLUCINATION_CAUGHT / CLAIM_BLOCK). A "done" is untrustworthy
  unless the auditor is AWAKE (fresh) and has caught no unbacked claims for that feature. WIRE this
  model, not a regex.
- **DRIFT 3 — the skill loop thinned to "compose a list."** Original model: top-1% expert skills are
  MATCHED to the task → INJECTED into the cook BEFORE/DURING the work → VERIFIED AFTER at done-time
  (that becomes R1). WIRE the full loop: match → inject-before/during → verify-after.

ALSO (moat hardening): the Verdict Coordinator must DERIVE claim/contract/commit_window from trusted
Manager/PM state, NEVER accept them from the actor (so claim={} can't disable the lie-detector);
enforce freshness before merge. RULE: wiring the moat must make a false "done" HARDER, never easier.

## PART C — THE WIRING ORDER (end-to-end FIRST; tests AFTER; dashboard must come up)

Goal sequence: (1) WIRE everything into one running end-to-end product. (2) THEN run unit/acceptance
tests. (3) THEN verify it really creates Docker rooms + Walls, the govern path works, and exercise
error cases + use cases. (4) The DASHBOARD MUST COME UP — if it doesn't run, we cannot see THOR working.

- **T0 [PLAN-FIRST] RUN TARGET** — one control-plane process (NOT a microservice mesh). One process
  holds the singletons (CTO, Room Mechanism/Manager + the one ledger, PM, GovEngine, Sentinel,
  Self-Audit) and shares them. Faculties talk in-process; serve real HTTP only at true boundaries
  (Dashboard :7080, Manager :7100, Sentinel :7140, Self-Audit :7150). Postgres in docker-compose;
  supervisor on the WSL host (`python tools/start_thor.py`). ONE documented start command. Boot order:
  DB → CTO → Room Mechanism+ledger → PM → GovEngine (coordinator) → Sentinel → Self-Audit → bind+serve
  → print "THOR up" banner.
- **T1 WALL** — confirm the Room Mechanism really provisions/destroys sealed Docker rooms over the run target.
- **T2 ROOM MECHANISM (Manager)** — make it the SOLE ledger writer for real; unify the split chains;
  give crash-replay a real caller. IT DECIDES NOTHING.
- **T3 CTO + LEASH** — put the CTO decide-BEFORE path in the REAL cook action loop: every cook action →
  CTO (allow/guide/block/escalate) BEFORE it executes. Wire the fail-closed spine (CTO down → block all).
  Wire the skill INJECT-before/during (DRIFT 3, first half).
- **T4 PM + SCHEDULER + CONTRACT** — PM enforces scope/SDLC for real; scheduler dispatches real waves
  (zero-LLM); the six-message contract is the live room↔control wire.
- **T5 [PLAN-FIRST] GOVENGINE (the moat)** — the honest Verdict Coordinator (derive inputs from trusted
  state); 8 probes against reality; FIX DRIFT 1 (real R1 skill-verifier), DRIFT 2 (live
  anti-hallucination auditor, not regex), DRIFT 3 second half (verify-after = R1); freshness before merge.
- **T6 SDLC STAGES** — Genesis → Build → independent QA → Verdict → merge; bind the 3 signatures to
  VERIFIED CEO cards; lifecycle drives the real merge after Signature 3.
- **T7 [PLAN-FIRST] DASHBOARD + MOBILE** — SERVE the dashboard HTTP for real; the cockpit Sign button must
  actually sign (real handler); show real rooms/stages/cost/audit. THE DASHBOARD MUST COME UP AND BE
  USABLE. Mobile shares the same data + signature model.
- **T8 [PLAN-FIRST] SENTINEL** — make halt() ACTUALLY halt (room destroy/pause + block work); real
  liveness/responsiveness probes of the live services; the canary; the silent-heartbeat base case.
- **T9 SELF-AUDIT** — stand up the real local model (Ollama/Qwen); zero frontier calls; URGENT→Sentinel.
- **T10 [PLAN-FIRST] ADAPTERS** — decide audit/identity Strangler (route THROUGH the adapter or drop the
  pretense); strengthen arch-lint beyond import-strings; real-or-representative ci/compliance.

THEN: (2) run the full unit/acceptance suite (un-skip the ~144 ACs as gated tests). (3) end-to-end live
checks: it really builds Docker rooms + Walls; the govern path denies a real out-of-scope action; the
verdict catches a fabricated claim + a fake test + a gamed gate; the Sentinel halts on a killed
governor; ERROR CASES + USE CASES exercised. (4) confirm the dashboard is up and shows a real feature go
plan→build→QA→verdict→signed-merge.

## PART D — HOW THE USER STARTS THE PRODUCT
Define ONE start experience, documented in `RUNBOOK.md`. Dev: `docker compose up` (Postgres) +
`python tools/start_thor.py` (control plane) → open the dashboard URL in the banner. Later/packaged: a
single-command installer/launcher — decide WITH the human, do not invent silently. Show the proposed
start flow BEFORE finalizing.

## PART E — HARD RULES
1. WIRE, DON'T REDESIGN. New problems → append to the gap register, don't fix inline.
2. THE GOVERN SYSTEM IS SACRED. Splitting the old watchdog into clean modules is fine; the RESULTING
   governance must guarantee the EXACT SAME thing: decide-before, judge-from-reality, fail-closed,
   human-signs, self-verifying. Weakening what it GUARANTEES is NOT allowed.
3. THE BRAIN IS THE CTO. The Manager is only the room mechanism + ledger writer. Never route a decision
   through the Manager.
4. FAIL-CLOSED EVERYWHERE. Governor down → block. Can't record → don't proceed. Can't verify →
   escalate/halt. Never "allow because it's convenient."
5. THE MOAT GETS HARDER, NEVER EASIER. If wiring would weaken the verdict, STOP + ask.
6. REAL EVIDENCE ONLY. No fake/assumed passes. Show real output.
7. BUILD UNGOVERNED (P7). WSL2/Linux paths only.
8. SINGLE LEDGER. Only the Room Mechanism writes the EventLog. No competing state stores.
9. ONE GAP/TASK AT A TIME, IN ORDER. Commit naming what was wired. Push a CLEAN, RUNNABLE checkpoint
   after each task. Never push a half-wired module.
10. SHOW THE PLAN FIRST on every [PLAN-FIRST] task. Ambiguity / a fork not in spec → STOP + ask. Reference
   `_reference/` (original THOR) to port proven doctrine; never import/extend it.

DEFINITION OF DONE (whole wiring pass): `start` brings the control plane up; the DASHBOARD opens and
shows live state; a real feature flows plan → build (in a real sealed Docker room) → independent QA →
verdict-from-reality → CEO signs → Gitea merges → room destroyed; a real out-of-scope action is BLOCKED
before it executes; a fabricated claim / fake test / gamed gate CANNOT get a false "done"; the Sentinel
HALTS on a killed governor; and the ~144 ACs run green as gated tests. THEN tag a release.
