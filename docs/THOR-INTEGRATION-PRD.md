# THOR ENTERPRISE — INTEGRATION PRD (the system-as-one-app specification)

**The most detailed document in the suite. It specifies how THOR Enterprise behaves as ONE living
system — the end-to-end flows, every seam between modules, every failure mode and race, and the
unified test suite. Grounded in a file:line read of the actual codebase (not the module PRDs, not
memory). Written through three lenses: Business Analyst (what it must do for the user), Senior Eng
Head (where it breaks at scale), CTO (is the governance guarantee preserved across every seam).**

Version 1.0 · audited against the real `~/thor-enterprise` source · every seam cites file:line.

---

## 0. THE ORGANISM — THOR as one running app

THOR is ONE control-plane process (`tools/start_thor.py`) holding the roles as distinct peers that
share ONE Postgres ledger. It is NOT a microservice mesh; faculties talk in-process; only four true
boundaries are served over HTTP (Manager :7100, Dashboard :7080, Sentinel :7140, Self-Audit :7150).

THE ROLES (corrected, grounded in the code + the original THOR trio):
- **CTO = the brain** (decides BEFORE each action; plans skills+scope). Shared, invoked at task-start
  + escalations. *Today: `scheduler/cto_stub.py` planner; the per-room decide-before is the Leash.*
- **Manager = the room mechanism + the SOLE ledger writer. Decides nothing.** (`manager/core.py`)
- **PM = the plan** (catalog in the ledger + the SDLC stage library).
- **GovEngine = the verdict-from-reality** (the 8-probe moat; `govengine/engine.py`).
- **Sentinel = meta-governance/health** (reflexes; can halt; `sentinel/core.py`).
- **Self-Audit = the read-only correctness eyes** (cheap local model; reports + escalates).
- **CEO = the human** — the only approval key (the three signatures).
- **Cook = the AI builder** — works in a sealed Wall room, in approved scope only.

THE FUNDAMENTAL INTEGRATION INVARIANT (the soul, must hold across every seam):
  Every cook action is judged BEFORE it executes; "done" is computed from REALITY not the cook's word;
  the human signs what matters; nothing governed happens unrecorded; if a governor is down, work STOPS.
  A seam that breaks any of these is a CRITICAL integration defect, even if both modules "work alone."

---

## 1. THE GOLDEN FLOWS (the main journeys — each: trigger → steps → what's recorded → end state)

### FLOW A — a feature from plan to signed merge (the spine of the product)
  1. CEO adds a feature on the Dashboard → Manager `add_feature` → event `feature.added` → catalog (Kind C).
  2. CEO marks it ready → `set_feature_status(ready)` → Scheduler picks it in the next wave.
  3. Genesis stage drafts/ī confirms acceptance criteria → CEO signs the plan (Signature 1, a verified card).
  4. CTO plans skills+scope for the feature → a FrozenPolicy for the room.
  5. Manager `provision_room` → Wall creates a SEALED Docker room, identity-stamped + verified → event
     `room.provisioned`. The cook is placed in it.
  6. Cook works. EVERY action → the in-room Leash → CTO decide-before (allow/guide/block/escalate)
     BEFORE it executes; skills injected during. Each decision → event `action.decided` (via Manager).
  7. Cook emits claim_done (a knock, not a verdict).
  8. Independent QA stage (fresh room, didn't write the code) verifies criteria + writes NEW edge
     tests + tries to break it → bugs → `qa.finding` events. QA-fail → CEO ticket (Signature 2).
  9. GovEngine Verdict Coordinator computes the 8-probe verdict from REALITY (git, tests, audit) +
     divergence (claim vs reality). `done` only if all 8 pass + no divergence + within policy →
     event `verdict.computed` (+ `divergence.detected` if any).
 10. On `done` → Manager raises a merge card → CEO signs (Signature 3, verified Ed25519).
 11. Manager directs the Gitea adapter to merge → event `feature.merged` → room destroyed
     (`room.destroyed`; branch preserved).
 12. Sentinel + Self-Audit watch the whole flow; either can halt/escalate.

### FLOW B — an out-of-scope action is blocked mid-build (the P3 promise)
  Cook tries to write `billing/secret.py`, outside its scope → Leash `evaluate` → forbidden/out-of-scope
  → `deny` BEFORE the file is touched → event `action.decided{deny}` → cook gets a legible reason.
  THE SIDE EFFECT NEVER HAPPENS. (Today: GAP C1 — see §2; the cook path does not yet run through the Leash.)

### FLOW C — a fabricated claim is caught (the lie-detector / the moat)
  Cook claims "added validation, tests pass" but git shows the file untouched / the test never ran →
  GovEngine builds the reality manifest (git diff + audit) → divergence found → verdict ≠ done →
  `divergence.detected` recorded as a dishonesty signal → escalate to the human.

### FLOW D — a governor dies → fail-closed halt (the safety spine)
  The CTO/Leash (or the Manager) becomes unreachable → the in-room proxy DENIES every action (can't
  reach the governor) → the Sentinel's liveness probe sees a critical component unresponsive → HALT
  (systemic scope) → all work stops until restarted. Silence = stop. (Today: GAP C3 — halt records an
  event but does not physically kill rooms; see §2.)

### FLOW E — the human signs from the dashboard (HCD made real)
  A card appears in the Approval Queue with a legible reason → CEO clicks Sign → Ed25519 signature
  bound to card-id+payload-hash → Manager `approve` verifies → event `card.approved` → the gated
  action proceeds. A forged/replayed signature → card stays open. (Today: Sign button deferred to T7.)

---

## 2. THE CRITICAL SEAM GAPS (confirmed by grep, with file:line — these BREAK the golden flows)

These are not module bugs — both modules work alone. They are INTEGRATION defects: the seam is unwired.

| Gap | The seam that's broken | Evidence (file:line) | Which golden flow it breaks |
|---|---|---|---|
| **C1** | The cook's actions do NOT route through the Leash. VERIFIED: `BuildStage` has NO leash/proxy reference at all (only the word "Leash" in its mandate docstring, `sdlc/stages.py:113`); it writes files directly (`open(p,"w").write(content)`) and commits. `InRoomProxy` (`leash/proxy.py:29`) is built only in smokes/tests. | grep: BuildStage has no `proxy`/`check_action`/`InRoom`; writes direct | **FLOW B entirely** — out-of-scope is NOT intercepted in product |
| **C4** | The verdict has no honest caller. `GovernanceEngine.run_verdict` is REAL and well-built (verified: panel requires all 8 + no divergence + no conflict; fail-closed). The gap is the INPUTS: `VerdictContext` takes `claim`/`contract`/`commit_window`/`skill_results_ok` as PASSED-IN params (`govengine/engine.py:50`). Verified: `divergence.detect` returns empty `if not claim` (`govengine/divergence.py`), so `claim={}` disables the lie-detector. `manager.run_verdict` is `NotImplementedError` (`manager/core.py:249`). | `govengine/engine.py:50`; `govengine/divergence.py` (`if not claim`); `manager/core.py:249` | **FLOW C** — the lie-detector is off unless an honest caller supplies the claim from trusted state |
| **C3** | `Sentinel.halt()` records an event but never physically halts. No call to `destroy_room`/kill/pause anywhere in `sentinel/`. | `sentinel/core.py:90-98` (halt = append rec); grep: no room-kill in sentinel/ | **FLOW D** — the governor can detect but cannot enforce |
| **H6** | "Manager is the sole ledger writer" is violated. 8 product modules call `eventlog.append` directly, bypassing `Manager._record`'s fail-closed gate + projector. | `govengine/engine.py:90,95`; `contract/seam.py:49`; `sentinel/core.py:95,110`; `mobile/bridge.py:32,51`; `dashboard/service.py:91,113`; `leash/decision.py:90` | the fail-closed audit gate is bypassable; projections can drift |
| **C2** | (CLOSED at T0) the run target now boots the system. | `tools/start_thor.py` | — |

The wiring pass must close these AT THE SEAM, then prove the golden flow they restore.

---

## 3. THE SEAM CATALOG (every module-to-module handoff; what must be true at each)

For each seam: PRODUCER → CONSUMER · the contract · current status · what must hold.

S1. CEO/Dashboard → Manager (add/ready feature, sign card). HTTP :7080→in-proc. WIRED (read path);
    Sign WRITE path = T7. Must: every operator action is an event; signatures verified (Ed25519).
S2. Scheduler → CTO → Manager (dispatch a ready feature; plan it). in-proc. PARTIAL (cto_stub).
    Must: deterministic wave; the CTO plan yields the FrozenPolicy the room is sealed with.
S3. Manager → Wall (provision/destroy room). in-proc Docker SDK. WIRED + identity-verified
    (`manager/core.py provision_room` verifies the stamp; refuses on failure). Must: a room is trusted
    only after stamp verification; destroy preserves the branch.
S4. Cook → Leash → CTO (decide-before each action). **UNWIRED (C1).** Must: the proxy is the cook's
    ONLY exit; side effect only on allow; deny/escalate recorded; fail-closed if governor down.
S5. Leash → Manager (record each decision). **BYPASS (H7/H6):** `leash/decision.py:90` writes its own
    chain, not through `Manager.record_decision` (which exists, `manager/core.py`, but is called only
    in a smoke). Must: one ledger; the Leash records THROUGH the Manager.
S6. Build → QA (handoff the branch for independent testing). in-proc. WIRED (QA gets a fresh room,
    different id). Must: QA room ≠ build room (independence, AC-2); QA reads real code.
S7. QA/Build → GovEngine (compute the verdict). **UNWIRED honest path (C4):** no coordinator derives
    the inputs from trusted state. Must: claim/contract/window DERIVED from Manager+PM+Contract, never
    from the actor; freshness checked before merge.
S8. GovEngine → Manager (record the verdict; raise the merge card). PARTIAL: the engine records
    `verdict.computed` directly via `eventlog.append` (H6, route through `_record`). The merge-card +
    qa-fail-ticket bridge IS built (`sdlc/bridge.py:24,33` raise_card("merge"/"qa_fail")) — but is
    only called from the SDLC smoke, not driven by a live verdict→bridge wire. Must: a `done` verdict
    automatically drives `bridge` to raise the merge card; the qa-fail drives the ticket.
S9. Manager → Gitea adapter (merge after Signature 3). The SDLC ORDER + signature gates ARE enforced
    (`transitions.py`: no Build before Sig1, no verdict before QA, bounded QA loop) — verified, keep it.
    GAPS: (a) `sign_plan`/`authorize_ticket` are plain setters not yet BOUND to verified Manager card
    approvals (H9 — bind them to `is_card_approved`); (b) `direct_merge` is `NotImplementedError`
    (`manager/core.py:252`); (c) nothing drives lifecycle→merge after Sig3. Must: gates flip only on a
    Manager-verified signature; merge runs through the Gitea adapter only then; THOR decides, Gitea executes.
S10. Sentinel → Wall/Manager (halt). **UNWIRED (C3):** halt records only. Must: a confirmed critical
     failure physically destroys/pauses the affected scope + blocks new work.
S11. Self-Audit → Sentinel (URGENT escalation). WIRED (`sentinel.receive_urgent`); Self-Audit model is
     a stand-in (T9). Must: the cheap model never halts directly; the Sentinel decides.
S12. All modules → Manager EventLog (the single ledger). **PARTIAL (H6):** 8 modules bypass `_record`.
     Must: every governed record goes through `Manager._record` (fail-closed + projection).

---

## 4. THE FAILURE MATRIX (for every seam: downstream slow / dead / lying / garbage → required behavior)

The governance value lives here. For each seam, the FAIL-CLOSED behavior must be explicit + tested.

| Seam | downstream SLOW | downstream DEAD | downstream LYING | garbage/malformed |
|---|---|---|---|---|
| Cook→Leash (S4) | treat as deny after timeout | DENY (governor_unavailable) — code already does this (`proxy.py`) | n/a (cook is the actor; Leash judges it) | unknown action type → DENY (`policy.py evaluate`) |
| Leash→Manager record (S5) | hold the action until recorded | cannot record → DENY (no unaudited action; `proxy.py`) | n/a | malformed action → normalized by inspector or denied |
| Manager→Wall (S3) | provision ret/timeout → fail the provision | Docker down → provision raises → feature not started, alarm | a forged identity token → room REFUSED + destroyed (code does this) | bad room spec → ValueError, no room |
| →GovEngine (S7) | verdict slow → not on critical path; await | reality unreadable → `escalate` (engine fail-closes, code does this) | caller supplies claim={}/curated contract → **MUST derive from trusted state (C4 fix)** | malformed ctx → escalate |
| Manager→Gitea (S9) | merge slow → await/queue | Gitea down → merge not reported done; do not mark merged | merge says ok but lost → idempotent re-check | conflict → not merged, surface |
| Sentinel→halt (S10) | n/a | **must still physically stop work (C3 fix)** | self-audit false-positive → Sentinel evaluates, may decline | — |
| any→EventLog (S12) | serialize (single writer) | unwritable → FailClosed, governed action refused (code does this in `_record`) | two writers race seq → single-writer lock (run target `_LockedConn`); proper = DB lock (M4) | — |

---

## 5. EXHAUSTIVE EDGE & RACE CASES (the things we never considered that can be fatal)

R1. Two rooms race the same branch — guarded: `provision_room` checks one-branch-one-room
    (`manager/core.py`, SELECT ... status='working'). TEST it under concurrency.
R2. Verdict arrives AFTER the room was destroyed — the verdict is about the BRANCH (persists), not the
    room; must still record + raise the card. Confirm the coordinator doesn't assume a live room.
R3. Signature replay — `card_material` binds card-id+payload-hash; a replayed sig on an already-approved
    card → "card not open" (code: `approve` checks status). TEST replay + cross-card reuse.
R4. EventLog unwritable mid-flow — `_record` raises FailClosed; the in-flight governed action must abort,
    not half-commit. TEST: toggle `set_eventlog_writable(False)` mid-build.
R5. Docker full / cannot create container — provision fails; feature stays backlog; alarm; no phantom room.
R6. Governor flaps (up/down/up) — Sentinel must not thrash halts; needs a brief re-probe before halting
    (today probe_all halts immediately on one bad probe — RISK of flap-induced halt; note for hardening).
R7. Canary goes silent — the heartbeat base case: `heartbeat_alive(last_seen)` false → external alarm.
    TEST: stop ticking, assert detection.
R8. Two operators sign the same card — Manager dedupes (status flips to approved; second → "card not open").
R9. A verdict's snapshot SHA is stale (branch moved) — `is_fresh` false → must re-run before merge (C4/freshness).
    Today nothing enforces freshness before merge — RISK. Must be wired in S7/S9.
R10. Self-Audit confidently wrong (cheap model) — `receive_urgent` without confirmed_critical → note only,
     never halts. TEST a false URGENT does not halt.
R11. Maintenance window left open — `tick` auto-closes after N; never silences outside the window. TEST expiry.
R12. Projection drift — if a module bypasses `_record` (H6), the rooms/cards/features tables diverge from
     the ledger. `rebuild_from_log` must reconstruct identical state. TEST: bypass, then replay, assert equal.
R13. A QA room that equals the build room — independence broken (AC-2); `provision_room` must yield a new id.
R14. Forbidden + in-scope conflict — deny precedence (forbidden wins) — code does this; TEST the ordering.
R15. Dependency-manifest edit mid-build — escalates (critical) even if in scope — code does this; TEST.
R16. Cook tries to weaken its own policy — FrozenPolicy is immutable (frozen dataclass + tuples); TEST mutation raises.

---

## 6. THE UNIFIED TEST SUITE (integration seams + the ~144 module ACs, one suite — for OpenHands to build)

Structure: `tests/integration/` (NEW — the seams + golden flows + edge/race) and the existing
`tests/<module>/` (the ~144 ACs, un-skipped). One `pytest` run is the standing gate.

INTEGRATION TESTS (new — each names the seam/flow/gap it proves; runs against the WIRED system):
- test_flow_A_plan_to_merge — the full spine end to end (real room, real verdict, real signed merge).
- test_flow_B_out_of_scope_blocked — a real cook write outside scope is DENIED before the file exists (C1).
- test_flow_C_fabricated_claim_caught — claim={changed X} but git shows untouched → verdict≠done (C4).
- test_flow_D_governor_dies_halts — kill the Leash/CTO → actions denied + Sentinel physically halts (C3).
- test_flow_E_human_signs — Sign from the dashboard → verified → action proceeds; forged sig → stays open.
- test_seam_S5_leash_records_through_manager — one ledger, no split chain (H6/H7).
- test_seam_S12_no_bypass_writers — assert NO module calls eventlog.append except via _record (H6).
- test_edge_R1..R16 — the race/edge cases in §5, each asserting the required behavior.
- test_moat_adversarial — fabricated claim / hollow fake test / gamed window / curated scope: NONE → done.

MODULE ACs (existing ~144, un-skipped as gated tests, per the wire-then-prove rule — a test counts only
against the WIRED path, not an in-process stand-in).

GATE: the whole suite runs green in CI against `python tools/start_thor.py` (a real booted system).

---

## 7. GAP CLOSE-OUT MAP (every register item → the flow that exercises it → the test that proves it)

| Gap | Closed by wiring (task) | Proven by (test) | Golden flow restored |
|---|---|---|---|
| C1 Leash not in cook path | T3 — route BuildStage cook actions through InRoomProxy | test_flow_B_out_of_scope_blocked | FLOW B |
| C2 no run target | T0 (DONE) | system boots; surfaces answer | all |
| C3 halt halts nothing | T8 — Sentinel.halt calls Wall destroy/pause + blocks work | test_flow_D_governor_dies_halts | FLOW D |
| C4 no honest verdict caller | T5 — Verdict Coordinator derives inputs from trusted state | test_flow_C + test_moat_adversarial | FLOW C |
| H6 sole-writer bypassed | T2 — route all 8 modules through Manager._record | test_seam_S12_no_bypass_writers | S12 |
| H7 split-brain chains | T2 — Leash records through Manager.record_decision | test_seam_S5 | S5 |
| H1 fake-test is a STATIC heuristic (references+non-trivial-assert, `govengine/fake_test.py`), wired into M1 — NOT a pure regex, but beatable by a referencing+non-trivial hollow test | T5 — strengthen to execution/coverage-of-diff (the original L2 anti-hallucination model) | test_moat_adversarial | FLOW C |
| H2 R1 reads `ctx.skill_results_ok` which DEFAULTS True + is caller-supplied (`govengine/probes.py`) — not literally hardcoded, but no real skill-verifier is wired | T5 — wire R1 to a real skill-verifier (original's fix); stop defaulting to pass | test_moat_adversarial | FLOW C |
| freshness not enforced (R9) | T5/T6 — is_fresh before merge | test_edge_R9 | FLOW A |

---

## 7b. WHAT IS ALREADY CORRECT — DO NOT "FIX" THESE (verified against the code)

Telling Claude Code to change working code IS drift. The brutal re-read confirmed these are RIGHT;
wire AROUND them, do not rewrite them:
- The panel adjudicator is correct: `done` requires all 8 probes pass AND no divergence AND no
  conflict AND stakes normal; divergence/conflict/high-stakes → escalate; errors → escalate
  (fail-closed). (`govengine/panel.py`) DO NOT loosen this.
- The fake-test check IS wired into M1 and overrides a hollow pass to fail (`probes.py` M1 +
  `fake_test.is_hollow`). It checks (a) references the contracted code and (b) non-trivial asserts.
  STRENGTHEN it (coverage-of-diff) — do NOT remove or bypass it.
- Divergence correctly flags claimed-but-absent, undisclosed, claimed-pass-but-verifier-failed,
  and gate-gaming (`govengine/divergence.py`). The ONLY gap is that `claim` must come from a trusted
  caller. Fix the CALLER (C4), not the detector.
- The Leash policy is correct: deny-precedence, manifest→escalate, out-of-scope→deny, unknown→deny,
  FrozenPolicy immutable (`leash/policy.py`). DO NOT change the policy logic — wire it into the cook
  path (C1) and route its records through the Manager (H7).
- The Manager `_record` fail-closed gate + event-sourcing + replay are correct (`manager/core.py`).
  The fix is routing the 8 bypassers THROUGH it (H6) — not changing `_record`.
- `provision_room` already verifies the room identity stamp and refuses on failure. Correct. Keep it.
- The SDLC TransitionController enforces the order + signature gates correctly (`sdlc/transitions.py`:
  no Build before Sig1, verdict only from QA, bounded QA loop). DO NOT change the ordering logic —
  the gap is only BINDING the gate setters to verified Manager cards (H9).
- The bridge that raises the merge card + qa-fail ticket is correct (`sdlc/bridge.py`). The gap is
  DRIVING it from a live verdict, not rewriting it.

THE RULE FOR CLAUDE CODE: these gaps are about UNWIRED SEAMS, not broken logic. Wire the seam; do not
rewrite the working module behind it. If you believe a working module must change, STOP and ask first.

## 8. THE THREE-LENS REVIEW (so this is a product, not just wiring)

BUSINESS ANALYST: the product the user experiences is FLOW A (plan → see it build → sign → shipped) +
the dashboard being genuinely usable + the legible "why" on every block. If FLOW A doesn't run
end-to-end on the dashboard, there is no product. That is the acceptance bar for "THOR works."

SENIOR ENG HEAD: the scale risks are the seams under concurrency — S12 (single-writer is a thread lock,
not a DB lock — M4, fix with a pool/advisory lock before multi-process), S3 (Docker provisioning under
many parallel rooms), R6 (halt flapping). None block the first product; all must be on the hardening list.

CTO (governance integrity): the soul survives ONLY if every seam preserves the invariant (§0). The four
critical gaps (C1/C3/C4/H6) each break one invariant today. The wiring pass is not "make it run" — it is
"make each seam preserve decide-before / judge-from-reality / record-everything / fail-closed." That is
the real definition of done, and §6's integration tests are how we prove it.
