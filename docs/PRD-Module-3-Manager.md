# THOR Module 3 — The THOR Manager (Governance Brain + Room Lifecycle Authority)

**Module PRD + FRD.** Read alongside the Bible (P1–P9, §5 architecture, §5.3 one-Manager-not-per-room), the System Design & Flow doc (§1 topology, §4 end-to-end flow, §10 who-writes-what), Module 1 (Wall) and Module 2 (Leash).

> Saved from `THOR-Module3-Manager-PRD.pdf` (v1.0) on 2026-06-06, transcribed faithfully. Build to this PRD; flag drift (Rule 9).

- **Module:** 3 — The THOR Manager · **Pillar:** 2 (Governance) · **Kind:** BUILD (the spine; orchestrates adopted parts)
- **Build order:** Third — after Wall + Leash; the coordinator that ties them together.
- **One-line purpose:** Be the single brain and single authority — the only writer of the audit log, the owner of the room registry and frozen rules, the one everything instructs and reports to — so governance has one source of truth and one accountable seam.
- **Version:** 1.0

---

## 1. Overview
The THOR Manager is the spine of the whole system. Every other module talks to it: the CTO instructs it to provision; the Wall reports room readiness; the Leash records decisions and raises cards through it; the Scheduler drives it; the GovernanceEngine returns verdicts to it; the Dashboard reads from it; the Sentinel watches it. It is the one place where governance truth is single and authoritative.

The defining architectural decision (Bible §5.3, **locked**): **one THOR Manager, not one watchdog per room.** A per-room governor re-scatters state and multiplies races — the original THOR's disease. Each room's Leash does not *decide*, it *asks* the one Manager. Single source of governance truth, single audit-log writer, single frozen rule-set.

The Manager is also the **room lifecycle authority** — the only thing that tells the Wall to provision/destroy rooms, holding the registry of every live room. (System Design's "Room Manager" = same component.)

Critically, the Manager is a **coordinator, not a doer**: it does not run policy checks (Leash/AGT does), compute verdicts (GovernanceEngine does), decide skills (CTO does), or run agents (rooms do). It routes, records, owns state, and enforces single-source-of-truth discipline — staying off the path to a 6,000-line monolith (P8).

## 2. Sub-modules
- **3.1 Room Registry** — authoritative list of every room: `room_id, container, task_type, feature_id, branch, status, address, identity_token, timestamps`. Single source of "what rooms exist and their state."
- **3.2 Lifecycle Coordinator** — receives provision/destroy instructions (CTO/Scheduler), drives the Wall (M1) to create/destroy, verifies room identity, updates the registry.
- **3.3 EventLog Writer** — the **ONLY** writer of the append-only, signed, hash-chained EventLog. Every meaningful action becomes an event here.
- **3.4 Rules Custodian** — holds frozen governance rules (Kind B) + feature catalog (Kind C); serves slices to rooms (read-only); the only path rules are set (human, host-side) or amended (separate door).
- **3.5 Card & Signature Authority** — raises CEO cards (critical escalations, QA failures, merge approvals); receives/verifies human Ed25519 signatures; enforces the three signature points.
- **3.6 Verdict Coordinator** — on `claim_done`, drives QA then the GovernanceEngine; receives the verdict; decides next step.
- **3.7 Gitea Director** — on merge approval, directs the Gitea adapter to merge (peer handshake — Manager decides, Gitea executes).
- **3.8 State Projector** — rebuilds mutable state ([ThorDB] rows) from the EventLog on restart (event-sourcing recovery); serves current state to the Dashboard.
- **3.9 Health Responder** — answers the Sentinel's liveness/responsiveness probes; exposes its own health truthfully (it too is governed — P9).

## 3. Functional Requirements (FR)
- **FR-1** Exactly one THOR Manager per instance; no per-room governor. (Bible §5.3)
- **FR-2** The Manager SHALL be the only writer of the EventLog.
- **FR-3** The Manager SHALL own the authoritative Room Registry; no competing room list elsewhere.
- **FR-4** Provision a room only on instruction (CTO/Scheduler), never autonomously, by directing the Wall (M1).
- **FR-5** Verify a room's identity token (Wall's Identity Stamper) before trusting/routing to it.
- **FR-6** Serve each room only its own feature-slice + policy slice; never the full catalog or another room's data.
- **FR-7** Hold the frozen rules; settable only host-side (human), never by a room/agent. (P1)
- **FR-8** Record every governance decision, lifecycle change, verdict, card, and signature as a signed, hash-chained event. (P9)
- **FR-9** On `claim_done`, drive QA then the GovernanceEngine, then surface the result — never merge on the agent's claim alone. (P5)
- **FR-10** Raise CEO cards for the three signature points (plan, re-work ticket, merge) and for critical escalations.
- **FR-11** Verify human Ed25519 signatures before acting on an approval. (P6)
- **FR-12** Direct Gitea to merge only after a verified human merge-signature; Gitea executes, Manager decides. (Bible §9.5)
- **FR-13** On restart, rebuild current state by replaying the EventLog (deterministic recovery).
- **FR-14** Answer the Sentinel's health probes truthfully (alive AND responsive); subject to P9.
- **FR-15** Fail-closed on its own critical deps: if it cannot write the EventLog, it SHALL NOT allow governed actions (no unaudited actions). (P2)
- **FR-16** Destroy a room on command, confirming the branch persists (Gitea) while the container is removed.
- **FR-17** Support room recovery: on crash, instruct the Wall to re-provision and reload execution state (Kind A).
- **FR-18** Expose read APIs for the Dashboard (rooms, cards, audit feed) — derived from EventLog/registry, never a separate truth.
- **FR-19** Hold escalated actions pending a human decision; SHALL NOT auto-resolve (no timeout-to-allow).
- **FR-20** Enforce one-branch-one-room (refuse to provision a second room on a branch already owned).

## 4. Technical Requirements
- **Language:** Python (control-plane backend).
- **Process model:** single long-running service on `:7100`; one logical authority (HA = single-leader, never two brains).
- **Persistence:** [ThorDB] (Postgres) for projected mutable state; [EventLog] append-only signed source (dedicated store or a Postgres table with hash-chaining + signatures).
- **Event signing:** Ed25519; each event carries `prev_hash`, `hash`, `signature`. Reuse identity primitives via adapter.
- **APIs:** HTTP/REST/JSON on `:7100` (internal); read endpoints proxied to DashboardAPI (`:7080`).
- **Concurrency:** many parallel rooms reporting; EventLog write path serialized (single writer) to preserve chain integrity; registry updates transactional.
- **Recovery:** EventLog replay on boot rebuilds registry + open cards + feature states; bounded replay (snapshot + tail) at scale.
- **No agent logic:** runs no LLM, makes no agent decisions — pure coordination + record-keeping.

## 5. The Logic
- **5.1 Single source of truth, enforced structurally** — the Manager's power is being the *only* EventLog writer and *only* registry owner. Others report; it records. One serialized place truth is written — prevents the original file-scatter races.
- **5.2 Coordinator, not doer** — every heavy job delegated (provision→Wall, judge→Leash/AGT, skills→CTO, verdict→GovernanceEngine, run→room). Manager code = routing + recording + state-ownership + signature-verification. (P8)
- **5.3 The lifecycle authority** — the only thing that creates/destroys rooms. CTO/Scheduler instructs → Lifecycle Coordinator drives Wall → ready identity-stamped room → verify identity → register → route `assign_task`. Destroy reverse; registry authoritative so Sentinel reconciles to reap orphans.
- **5.4 The three signature points, owned here** — Sig 1 (plan): no build room until signed. Sig 2 (re-work ticket): QA-fail loop-back waits for human. Sig 3 (merge): Gitea directed only on verified signature. Each Ed25519-verified, recorded; escalations held, never auto-resolved (FR-19) — silence is not consent.
- **5.5 Event-sourcing recovery** — every state change is an appended event, so the Manager is reconstructable. Restart replays (snapshot + tail) to rebuild registry/cards/feature-states. A crashed Manager loses nothing.
- **5.6 Fail-closed on its own dependencies** — if it cannot write a decision to the EventLog, it does not let governed actions proceed (an unrecorded action is an ungoverned action). Better to halt than act without an audit trail.

## 6. API Strategy
### 6.1 Endpoints the Manager EXPOSES (`:7100`)
```
# Lifecycle (CTO / Scheduler)
POST /rooms/provision { feature_id, task_type, skills[], scope{}, repo, base_branch, limits } -> { room_id, status }
POST /rooms/{id}/destroy -> { room_id, status:"destroyed", branch_preserved }
POST /rooms/{id}/recover -> { room_id, status:"recovered" }
GET  /rooms -> { rooms:[...] }     # registry view
GET  /rooms/{id} -> { room state }

# Reporting (Wall / Leash / rooms)
POST /events/append { event_type, actor, room_id?, feature_id?, payload } -> { seq, hash }
POST /cards/raise { type, feature_id, payload } -> { card_id }
POST /rooms/{id}/kill { reason } -> { status:"terminated" }
POST /claim_done { feature_id, room_id } -> { ack }

# Signatures (Dashboard / PhoneBridge)
POST /approve { card_id, signature } -> { verified:bool, action_taken }
POST /reject  { card_id, signature, reason } -> { verified:bool }

# Rules & catalog (host-side only for writes)
POST /rules/set { policy } [host-only] -> { frozen_at, hash }
GET  /rooms/{id}/slice -> { feature_slice, policy_slice }   # read-only to room

# Verdict coordination
POST /verdict/run { feature_id, branch } -> { verdict, blockers[], divergence }

# Read (DashboardAPI)
GET  /state/summary -> { rooms, open_cards, feature_states }
GET  /audit/feed?range -> { events[] }
GET  /health -> { alive, responsive, eventlog_writable, deps{} }
```
### 6.2 Endpoints the Manager CONSUMES
- → Wall API provision/destroy/health (M1)
- → Leash/AGT adapter (records decisions via `/events/append` — inbound to Manager)
- → GovernanceEngine `:7130` POST /verdict (8-probe)
- → CTO `:7120` (instructs the Manager; Manager may request a plan slice)
- → Gitea adapter `:7170` POST /git/merge (peer handshake, on signature)
- → [ThorDB], [EventLog] read/write projected state + append signed events

### 6.3 The write discipline
Only the Manager writes [EventLog]. Components POST to `/events/append`; the Manager validates, signs, chains, persists. Structural guarantee of single-source-of-truth (FR-2).

## 7. Diagram (described)
**Figure 1** — The Manager as the single hub: CTO/Scheduler instruct; Wall provision/destroy; Leash records decisions; GovernanceEngine returns verdict; Sentinel watches; DashboardAPI reads + signs; Gitea executes merge; [EventLog] signed·chained. It owns the registry, the EventLog, and the frozen rules.

## 8. Flows
- **8.1 Provision** — CTO → Manager `/rooms/provision` → Manager ensures worktree/branch (Gitea) → Wall provision → Wall returns ready room + identity token → Manager verifies identity → registers → appends `room.provisioned` → routes `assign_task`.
- **8.2 Record a decision** — Leash decides → Manager `/events/append {action.decided, verdict, reason}` → Manager validates, signs, chains, persists; if escalate → also raises a card.
- **8.3 Claim-done → verdict → merge** — Room `/claim_done` → Manager provisions QA → on pass `/verdict/run` → verdict done → raises merge card (Sig 3) → operator signs → Manager verifies → directs Gitea merge → destroys room → appends `feature.merged`.
- **8.4 Restart recovery** — Manager restarts → State Projector loads snapshot + replays tail → registry/cards/feature-states rebuilt deterministically → in-flight rooms re-verified or re-provisioned.
- **8.5 Fail-closed on EventLog** — store unwritable → Health Responder reports `eventlog_writable:false` → Sentinel alarms → Manager refuses to ack new governed actions → rooms pause until restored.

## 9. Use Cases / User Stories (story points)
- **US-1 (13)** one authoritative governance brain + one audit-log writer — truth single, races impossible.
- **US-2 (8)** any module instructs/reports to the Manager and keeps no competing records.
- **US-3 (8)** rebuild full state from the EventLog on restart — a crash loses nothing.
- **US-4 (8)** the three signature cards; won't proceed without a verified signature (HCD).
- **US-5 (5)** provision/destroy via the Wall + verify identity — only trusted rooms routed to.
- **US-6 (5)** each room gets only its own slice (data-layer isolation).
- **US-7 (8)** on `claim_done`, drive QA then verdict; never merge on the agent's word (P5).
- **US-8 (5)** every decision/lifecycle/verdict/signature a signed, chained event.
- **US-9 (5)** if it can't record an action it doesn't allow it (fail-closed on self).
- **US-10 (5)** Sentinel can probe the Manager's true health (P9).
- **US-11 (3)** escalations held until decided, never auto-allowed.
- **US-12 (5)** one branch maps to one room.

**Total: ~78 points for Module 3.**

## 10. Error & Edge Cases
| Case | Trigger | Handling |
|---|---|---|
| EventLog unwritable | store down/full | Fail-closed: pause governed actions; alarm; no unaudited acts |
| Manager crash | process dies | Restart → replay EventLog → rebuild state; rooms re-verified |
| Two provisions, same branch | scheduling bug | Refuse the second (one-branch-one-room, FR-20) |
| Room reports but identity fails | stale/sibling room | Refuse to route; quarantine/destroy; log security event |
| Signature verification fails | forged/expired sig | Reject the approval; card stays open; log |
| Card never answered | operator absent | Held indefinitely; no auto-resolve; surfaced as pending |
| Duplicate event (retry) | network retry | Idempotent append (dedupe by client-id); chain stays clean |
| Hash chain break detected | tamper/corruption | Halt + alarm (Sentinel); refuse to extend a broken chain |
| Verdict requested, GovernanceEngine down | dep failure | Hold the feature; alarm; do not merge |
| Gitea merge fails post-signature | conflict at merge | Return as fix task; do NOT mark merged; card reopens |
| Replay too slow at scale | huge log | Snapshot + tail replay; bounded recovery time |
| Concurrent registry updates | many rooms | Transactional updates; serialized EventLog writes |

## 11. Easy vs Difficult Parts
- **Easy:** REST API + Postgres-backed registry; provision/destroy orchestration (thin Wall calls); read endpoints (projections).
- **Moderate:** card & signature flow (raise, hold, verify Ed25519, record); idempotent event append; one-branch-one-room under concurrency.
- **Difficult / real risk:** (1) the **signed, hash-chained EventLog as single writer** — tamper-evidence (chaining, signatures, idempotency, serialization) while performant under many rooms. (2) **Event-sourcing recovery** — deterministic rebuild incl. in-flight rooms; subtle. (3) **Staying a coordinator, not a monolith** — resisting "just a bit of logic"; ongoing discipline.

## 12. Technical Difficulties
- **D1 — Tamper-evident single-writer log at scale.** Single serialized write path; batch-friendly append; snapshots for replay; idempotency keys; chain verified on read + by Sentinel canary.
- **D2 — Deterministic recovery.** Snapshot + tail replay; on recovery re-verify each registered room's actual container (reconcile with Wall); re-provision from execution state.
- **D3 — HA without two brains.** Single-leader (one active writer); standby replays; failover promotes — never two active writers.
- **D4 — Anti-monolith discipline.** Hard rule: Manager routes/records/owns-state/verifies-signatures and nothing else; judgment goes to a delegated service.
- **D5 — Signature trust.** Ed25519; signatures bound to card-id + payload hash + nonce; verified before any action; recorded as events.

## 13. What Needs To Be Built (checklist)
- [ ] Room Registry (authoritative, transactional)
- [ ] Lifecycle Coordinator (provision/destroy/recover via Wall; identity verify)
- [ ] EventLog Writer (single writer; Ed25519-signed; hash-chained; idempotent append)
- [ ] State Projector (snapshot + tail replay recovery)
- [ ] Rules Custodian (frozen Kind B + catalog Kind C; host-only writes; read-only slices)
- [ ] Card & Signature Authority (raise/hold/verify; three signature points)
- [ ] Verdict Coordinator (drive QA → GovernanceEngine → next step)
- [ ] Gitea Director (merge on verified signature; peer handshake)
- [ ] Health Responder (truthful alive+responsive; eventlog-writable status)
- [ ] Manager REST API (§6.1)
- [ ] Read/projection endpoints for the Dashboard
- [ ] HA single-leader model (standby replay + failover) — can defer to v1.1
- [ ] Recovery + reconciliation test suite (crash → replay → reconcile rooms)

## 14. Dependencies & Sequencing
**Depends on:** Module 1 (Wall) — provision/destroy rooms. Module 2 (Leash) — reports decisions to the Manager. [ThorDB] + [EventLog] stores. Identity primitive (Ed25519) — shared with M1/M2.

**Blocks / depended on by:** Module 4 (Scheduler) and CTO (instruct it). Module 6 (GovernanceEngine — Manager drives it, records verdicts). PM Surface (15) and Mobile (16) (read/sign through it). Sentinel (10) (watches it). Effectively the spine.

**Build-order note:** Build after Wall + Leash so there are real rooms and real decisions to coordinate. **Milestone:** a real governed action's decision is recorded as a signed, chained event; the Manager is killed and restarted; it replays the log and rebuilds exact state.

## 15. Test / Acceptance Criteria (evidence-based)
- **AC-1** Only the Manager can append to the EventLog; a direct write attempt by any other component fails.
- **AC-2** Each event carries a valid signature and correct `prev_hash→hash` chain; altering any past event breaks verification (tamper test).
- **AC-3** Killing the Manager and restarting rebuilds the exact registry, open cards, and feature states from the log (state-diff before/after).
- **AC-4** A build room is not provisioned until the plan is signed (Sig 1); merge doesn't happen without a verified merge-signature (Sig 3).
- **AC-5** A forged or wrong-card signature is rejected and the card stays open (negative test).
- **AC-6** On `claim_done`, the Manager drives QA then verdict; never merged on the agent's claim alone (attempt-to-skip fails).
- **AC-7** With the EventLog unwritable, the Manager refuses new governed actions (fail-closed).
- **AC-8** A room with a bad identity token is refused routing.
- **AC-9** A second provision on an already-owned branch is refused.
- **AC-10** The Sentinel can read the Manager's true health, including eventlog-writable status.
- **AC-11** An escalated card is never auto-resolved; it remains held with no human action (waiting test).
- **AC-12** Duplicate event appends (retries) are idempotent; the chain has no duplicates.

**Headline milestone:** AC-2 + AC-3 together — a tamper-evident signed log that the Manager can replay to rebuild exact state after a crash. That proves the single-brain design is both authoritative and crash-safe.

---

*End of THOR Module 3 — The THOR Manager PRD v1.0. Next module: 4 — The Scheduler (deterministic, zero-LLM task-graph executor that instructs the Manager what to run when).*
