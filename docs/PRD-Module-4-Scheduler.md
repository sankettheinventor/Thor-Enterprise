# THOR Module 4 — The Scheduler (Deterministic Zero-LLM Task-Graph Executor)

**Module PRD + FRD.** Read alongside the Bible (§13 module map, §10.6 task decomposition, §12.5 cost controls), the System Design & Flow doc (§4 Phase 1 scheduling, §5.1 provisioning sequence), and Modules 1–3 (Wall, Leash, Manager).

> Saved from `THOR-Module4-Scheduler-PRD.pdf` (v1.0) on 2026-06-06, transcribed faithfully. Build to this PRD; flag drift (Rule 9).

- **Module:** 4 — The Scheduler · **Pillar:** 2/3 (orchestration — the connective tissue) · **Kind:** BUILD (study Bernstein's pattern; build our own — Bernstein is noncommercial)
- **Build order:** Fourth — after the Manager; it instructs the Manager what to run when.
- **One-line purpose:** Decide what runs when — purely deterministically, with zero LLM calls in the loop — so coordination is predictable, replayable, and costs no tokens.
- **Version:** 1.0

---

## 1. Overview
The Scheduler is the conductor. Given a feature catalog with dependencies, it decides which features are ready, in what order, and in what parallel waves — then instructs the THOR Manager to provision rooms. Its defining property (proven by Bernstein at scale — 12 agents, 737 tasks): **the orchestrator makes no LLM calls.** The single act of intelligence — decomposing a goal into a task graph — happens once, upstream, in the CTO/Genesis stage. After that, scheduling is plain deterministic code.

This matters for three reasons: **predictability** (same inputs → same schedule), **replayability** (replay yesterday's plan → yesterday's schedule), **cost** (zero tokens on coordination). The Scheduler is **dumb about content** — it reads the dependency graph + readiness flags, applies wave logic, respects concurrency limits, tells the Manager to provision. Intelligence about *what* to build lives upstream (CTO/Genesis); governance of *how* lives in the Leash/Manager. The Scheduler is pure sequencing.

## 2. Sub-modules
- **4.1 Graph Loader** — reads the catalog (Kind C), builds the in-memory task DAG (nodes=features, edges=deps); validates (no cycles, all deps exist).
- **4.2 Readiness Evaluator** — a task is *ready* iff all deps `done`, marked `ready` (operator/auto-ready), and not already running/blocked. Pure boolean, no AI.
- **4.3 Wave Planner** — groups ready tasks into a "wave" (can run simultaneously), respecting dependency levels.
- **4.4 Concurrency Governor** — caps the wave to available room capacity (free-tier per-host limit; paid autoscale ceiling). Now vs queue.
- **4.5 Provision Dispatcher** — for each runnable task: asks the CTO to plan it (the one LLM call, upstream), then instructs the Manager to provision. The Scheduler never calls an LLM.
- **4.6 Completion Listener** — listens (Manager events) for `feature.merged`/`feature.failed`; updates states; triggers the next wave.
- **4.7 Cost Estimator & Budget Guard** — estimates token cost per wave, shows it, enforces hard caps + dry-run preview (Bible §12.5). Halts dispatch if a cap would be exceeded.
- **4.8 Replay/Audit Hook** — replays a recorded plan to reproduce the exact schedule (debug/audit/dry-run).

## 3. Functional Requirements (FR)
- **FR-1** NO LLM calls in the scheduling loop. The only LLM call is the upstream CTO/Genesis planning call, once per task.
- **FR-2** Build a task DAG from the catalog and validate it (reject cycles, missing deps).
- **FR-3** A task is ready only when all deps are `done` AND marked ready AND not already running/blocked.
- **FR-4** Run ready tasks in dependency waves: a task runs only after every prerequisite completes.
- **FR-5** Cap concurrent rooms to configured/available capacity.
- **FR-6** When ready tasks exceed capacity, queue the overflow and dispatch as capacity frees (no dropping, no overload).
- **FR-7** Identical inputs (catalog + readiness + capacity) → identical schedule (determinism).
- **FR-8** Instruct the Manager to provision; SHALL NOT provision directly (Manager is the lifecycle authority).
- **FR-9** Update task states from the Manager's events (`feature.merged`, `feature.failed`, re-work ticket); trigger the next wave.
- **FR-10** Estimate token cost for a wave before dispatch and display it.
- **FR-11** Enforce hard budget caps; if a wave would exceed the cap, halt and require operator action.
- **FR-12** Support dry-run: compute + show the full schedule + cost WITHOUT provisioning anything.
- **FR-13** Be replayable: re-running a recorded plan reproduces the same schedule.
- **FR-14** Handle re-work loop-backs: a feature returned from QA re-enters as ready WITHOUT re-running its done deps.
- **FR-15** Respect Genesis-first: in a fresh project, no build tasks schedulable until the plan is approved (Signature 1).
- **FR-16** Surface current plan/wave state to the Dashboard (running/queued/blocked/done).
- **FR-17** Be restartable: rebuild task states from the Manager's event log (no scheduling truth only in memory).
- **FR-18** SHALL NOT make governance or content decisions; it sequences only.

## 4. Technical Requirements
- **Language:** Python. **Process:** service on `:7110`; source of truth is the Manager's catalog + event log (rebuild on restart, FR-17).
- **Graph:** in-memory DAG (networkx or a small custom structure); topological levels; cycle detection on load.
- **Determinism:** no randomness, no wall-clock-dependent ordering, no LLM; ties broken by stable sort (feature_id order).
- **Trigger:** event-driven (Manager completion events) + periodic reconcile tick; not polling files.
- **Cost model:** per-task token estimate from historical/declared usage; budget caps per run/project; dry-run computes without side effects.
- **Capacity source:** config (free=fixed cap; paid=autoscale ceiling) + Manager's live room count.
- **No persistence of its own truth:** task states derive from the Manager's events; the Scheduler holds a rebuildable working projection.

## 5. The Logic
- **5.1 Intelligence once, then pure code** — the expensive nondeterministic act (goal → task graph) happens once upstream (CTO/Genesis LLM call). The Scheduler then does only arithmetic: which tasks have all deps done + are ready → runnable set → cap to capacity → tell the Manager. No tokens, fully predictable (Bernstein's insight).
- **5.2 Wave scheduling** — DAG by dependency; compute levels; level-0 runs first; within a level independent tasks run in parallel (a wave), capped by concurrency; as tasks complete, re-evaluate and dispatch the next wave. Standard deterministic DAG execution.
- **5.3 Concurrency and capacity** — the Wave Planner may yield more ready tasks than capacity; the Concurrency Governor caps the dispatched set; overflow queues; as rooms free, queued tasks dispatch. Same schedule runs on 4-room free or 30-room paid — only how many run at once differs.
- **5.4 The dispatch handoff** — Scheduler → CTO: "plan task F047" (the one LLM call) → CTO → Manager: provision → Manager → Wall: create room. The Scheduler triggers the planning call but never makes it (zero-token property preserved).
- **5.5 Cost as a first-class gate** — before a wave, sum per-task estimates; Budget Guard checks the cap. Show estimate; hard-stop if exceeded; offer dry-run. Gating at dispatch is where cost control belongs.
- **5.6 Determinism → replay → trust** — schedule is a pure function of (catalog, readiness, capacity) → replayable. Gives debugging, audit, safe dry-runs. Determinism is cheaper *and* more trustworthy.

## 6. API Strategy
### 6.1 Endpoints the Scheduler EXPOSES (`:7110`)
```
POST /schedule/plan        { catalog_ref }                          -> { dag, levels, validation }
POST /schedule/dry_run     { catalog_ref, capacity }               -> { waves[], cost_estimate }  # no side effects
POST /schedule/run         { catalog_ref, capacity, budget_cap }   -> { wave_dispatched[], queued[] }
POST /schedule/mark_ready  { feature_id }                          -> { ready:bool }
GET  /schedule/state       -> { running[], queued[], blocked[], done[], current_wave }
GET  /schedule/cost        { wave } -> { per_task[], total_estimate }
GET  /health               -> { alive, responsive, dag_loaded }
```
### 6.2 Endpoints the Scheduler CONSUMES
- → ThorManager `:7100` GET `/state/summary` (catalog + feature states)
- → ThorManager `:7100` (subscribes to events: `feature.merged`/`feature.failed`/`ticket.authorized`)
- → CTO `:7120` POST `/plan_task { feature_id }` (the ONE LLM call, upstream)
- → ThorManager `:7100` POST `/rooms/provision` (via CTO's instruction; Scheduler doesn't provision directly)

### 6.3 The handoff discipline
Scheduler decides *what* and *when*; the CTO plans (LLM call lives there); the CTO instructs the Manager (lifecycle authority). Three roles: Scheduler sequences, CTO plans, Manager provisions. The Scheduler touches no LLM and no Docker.

### 6.4 Port summary
| Component | Port | Role |
|---|---|---|
| Scheduler | `:7110` | sequencing, waves, cost gate |
| CTO | `:7120` | the one planning LLM call |
| ThorManager | `:7100` | provisioning authority + events |

## 7. Diagrams (described)
- **Figure 1** — Wave scheduling over a DAG: level-0 (F12/F13/F14) run first in parallel up to capacity; level-1 (F20 needs F12; F21 needs F13,F14) run as prereqs complete; level-2 (F30 needs F20,F21). Capacity only limits how many at once, never the order.
- **Figure 2** — The deterministic loop: one upstream LLM call (CTO/Genesis → task graph), then pure code — load+validate DAG, evaluate readiness, plan wave + cap, budget gate, dispatch via CTO/Manager, listen for completion, repeat. ZERO LLM in the loop.
- **Figure 3** — Same schedule, different capacity: identical task order on a 4-room free box vs a many-room paid cluster; only concurrency differs.

## 8. Flows
- **8.1 Happy path** — operator marks ready → load DAG → runnable {F12,F13,F14} (level-0) → cap to 3 (fits) → cost under budget → for each: Scheduler→CTO plan→Manager provision → on F12 merge, F20 becomes ready → dispatched next.
- **8.2 Capacity overflow** — 8 ready, capacity 3 → dispatch 3, queue 5; as each completes the next queued dispatches; order deterministic (stable sort).
- **8.3 Budget gate** — wave cost > cap → Budget Guard halts; surfaces "~$X over your $Y cap"; operator raises cap / reduces / stops; nothing provisioned until resolved.
- **8.4 Re-work loop-back** — F30 fails QA → operator authorizes ticket (Sig 2) → Manager emits `ticket.authorized` → Scheduler marks F30 ready → re-dispatches; done deps NOT re-run.
- **8.5 Dry-run** — compute full wave plan + cost, provision NOTHING; operator previews before committing.
- **8.6 Restart** — Scheduler restarts; in-memory projection lost; reads Manager's catalog + event log, rebuilds task states, resumes from the correct wave.

## 9. Use Cases / User Stories (story points)
- **US-1 (13)** scheduling makes zero LLM calls — coordination free + predictable.
- **US-2 (8)** same inputs → same schedule (deterministic + replayable).
- **US-3 (8)** dependency waves — nothing before prereqs; independent work parallelizes.
- **US-4 (8)** wave cost shown before run + hard cap stops overruns (cost gate).
- **US-5 (5)** dry-run the whole plan with zero provisioning.
- **US-6 (5)** ready tasks beyond capacity queue + dispatch as rooms free.
- **US-7 (5)** same schedule on a 4-room free box or 30-room cluster.
- **US-8 (5)** QA re-work re-enters without re-running done deps.
- **US-9 (5)** no build scheduled until the plan is signed (Genesis-first).
- **US-10 (5)** rebuild state from Manager events on restart.
- **US-11 (3)** replay a recorded plan to reproduce the exact schedule.
- **US-12 (3)** see what's running/queued/blocked/done.

**Total: ~73 points for Module 4.**

## 10. Error & Edge Cases
| Case | Trigger | Handling |
|---|---|---|
| Cyclic dependency | bad catalog | Reject the graph on load; surface the cycle; don't schedule |
| Missing dependency | dep → unknown feature | Reject/flag; the dependent stays blocked |
| Capacity = 0 | no rooms | Queue everything; surface "no capacity"; burst-to-paid (D3) |
| Budget cap hit mid-plan | costs accumulate | Halt next dispatch; running rooms finish; operator decides |
| Completion event missed | network blip | Periodic reconcile tick re-reads Manager state, catches up |
| Task stuck running | room hung | Manager times out → emits `failed` → Scheduler unblocks/queues |
| Operator marks ready, deps not done | premature ready | Readiness still requires deps done; stays blocked |
| Duplicate dispatch | retry/race | Idempotent: a task already running isn't dispatched again (registry check) |
| Re-work creates a loop | F fails QA repeatedly | Bounded: repeated failures surface to operator (not infinite auto-loop) |
| Restart mid-wave | Scheduler crash | Rebuild from events; running rooms reconciled, not duplicated |
| Plan changed mid-run | operator edits catalog | Re-validate DAG; new tasks enter ready when deps clear; running unaffected |
| Cost estimate wildly off | bad model | Estimates advisory; the hard cap is the real guard |

## 11. Easy vs Difficult Parts
- **Easy:** DAG construction + topo levels + cycle detection; wave dispatch loop; dry-run (skip the provision calls).
- **Moderate:** event-driven completion + periodic reconcile; cost estimation; capacity capping + queue management across tiers.
- **Difficult / real risk:** (1) **True determinism** — hidden nondeterminism via map ordering, concurrent events, wall-clock tie-breaks; needs stable sorting everywhere + careful event ordering. (2) **Restart correctness** — rebuild exact state without double-dispatching running rooms or missing a freshly-completed one. (3) **Resisting the urge to add intelligence** — an LLM "smart order" would destroy zero-token + determinism + replay; holding the line is discipline.

## 12. Technical Difficulties
- **D1 — Determinism guarantees.** Stable sort by feature_id for ties; no wall-clock in ordering; events processed in a defined order; a determinism test that runs the same inputs N times and asserts identical schedules.
- **D2 — Exactly-once dispatch.** The Manager's registry is authoritative (one-branch-one-room, M3 FR-20); the Scheduler checks "already running?" before dispatch; idempotent.
- **D3 — Restart reconciliation.** Rebuild from the event log; reconcile against the Manager's live registry; never assume in-memory survived.
- **D4 — Useful cost estimates.** Estimate from historical actuals per task-type; treat as advisory; the hard budget cap (on accumulating spend) is the real guard.
- **D5 — Capacity portability.** Capacity is a parameter; wave order is from the DAG (capacity limits how many at once, never which order) — schedule identical, only throughput differs.

## 13. What Needs To Be Built (checklist)
- [ ] Graph Loader (catalog → DAG; cycle + missing-dep validation)
- [ ] Readiness Evaluator (deps-done + marked-ready + not-running — pure boolean)
- [ ] Wave Planner (dependency levels → parallel waves)
- [ ] Concurrency Governor (cap to capacity; queue overflow)
- [ ] Provision Dispatcher (→ CTO plan → Manager provision; never direct)
- [ ] Completion Listener (event-driven + periodic reconcile)
- [ ] Cost Estimator + Budget Guard (estimate, show, hard-cap, dry-run)
- [ ] Replay/Audit hook (deterministic re-run of recorded plans)
- [ ] State rebuild on restart (from Manager events)
- [ ] Scheduler REST API (§6.1)
- [ ] Dashboard state endpoint (running/queued/blocked/done)
- [ ] Determinism test harness (same inputs N times → identical schedule)

## 14. Dependencies & Sequencing
**Depends on:** Module 3 (Manager) — the Scheduler instructs it to provision and consumes its events. **Hard dependency.** CTO — for the per-task planning call (the one LLM call); **can be stubbed** (return fixed skills) for Scheduler-isolated testing. Feature catalog (Kind C) — the input graph; produced by Genesis (M10) but **can be hand-seeded for testing**.

**Blocks / depended on by:** the whole multi-session build flow (nothing parallel runs without the Scheduler); the SDLC Build stage (M12) receives its tasks via the Scheduler.

**Build-order note:** Build after the Manager. Can be developed against a hand-seeded catalog + stubbed CTO. **Milestone:** a multi-feature catalog with dependencies runs in correct deterministic waves on a capacity-capped set of rooms, with dry-run + budget gate working — and the same catalog replays to the identical schedule.

## 15. Test / Acceptance Criteria (evidence-based)
- **AC-1** Running the same catalog + readiness + capacity twice produces byte-identical schedules (determinism).
- **AC-2** The Scheduler makes zero LLM calls during scheduling (only the CTO makes the planning call).
- **AC-3** A task with an unmet dependency never dispatches before its prerequisite completes (multi-level DAG).
- **AC-4** Independent tasks within a level run in parallel up to the capacity cap; the (cap+1)-th queues.
- **AC-5** A dry-run produces a full wave plan + cost estimate and provisions nothing (zero rooms created).
- **AC-6** A wave that would exceed the budget cap is halted before any dispatch (negative test).
- **AC-7** The identical catalog runs in the same order on capacity=3 and capacity=10; only concurrency differs.
- **AC-8** A QA re-work re-dispatches the failed feature without re-running its done dependencies.
- **AC-9** No build task is schedulable before the plan is signed (Genesis-first).
- **AC-10** Killing and restarting the Scheduler rebuilds correct task state from events and resumes without double-dispatching.
- **AC-11** A cyclic catalog is rejected at load with the cycle identified.
- **AC-12** A replayed recorded plan reproduces the exact schedule.

**Headline milestone:** AC-1 + AC-2 together — a deterministic schedule produced with zero LLM calls in the loop, reproducible on replay. That proves the Bernstein-style property THOR depends on for predictable, free, auditable coordination.

---

*End of THOR Module 4 — The Scheduler PRD v1.0. Next module: 5 — The Task Handoff Contract (the frozen six-message REST interface and the read-only /task/feature.json slice that connects the Manager to every room).*
