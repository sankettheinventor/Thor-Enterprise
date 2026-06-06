# THOR Module 5 — The Task Handoff Contract (The Frozen Interface)

**Module PRD + FRD.** Read alongside the Bible (D8 the six-message contract, §6 three kinds of state, §10 the SDLC, P1/P5/P6), the System Design & Flow doc (§5 API sequences, §7.4 the frozen contract), and Modules 1–4 (Wall, Leash, Manager, Scheduler).

> Saved from `THOR-Module5-Contract-PRD.pdf` (v1.0) on 2026-06-06, transcribed faithfully. Build to this PRD; flag drift (Rule 9).

- **Module:** 5 — The Task Handoff Contract · **Pillar:** 2/1 (the seam between governance and isolation) · **Kind:** BUILD (a small, deliberately frozen interface)
- **Build order:** Fifth — formalizes the Manager↔Room interface that Modules 1–4 already use informally.
- **One-line purpose:** Define the one small, frozen, transport-swappable interface through which the Manager briefs a room, the room reports, and the verdict returns — so the isolation and governance layers can evolve independently forever.
- **Version:** 1.0

---

## 1. Overview
The narrow seam between the control plane (Manager) and the execution plane (rooms) — the smallest module by surface area and the most important to get exactly right, because every room is born, briefed, and judged through it. A clean frozen contract lets the Wall (isolation) and the Manager (governance) evolve independently.

Two parts: **(1) the six-message protocol** — inbound `provision`, `assign_task`, `amend`; outbound `status`, `claim_done`, `result_decision`. Nothing else crosses. **(2) the feature-slice** — a read-only `/task/feature.json` containing only that one feature's spec, never the catalog.

It embodies **P1** (room gets its task read-only, cannot rewrite scope), **P5** (room can only *claim* done — the verdict returns via `result_decision`), and transport-swappability (docker-exec now, REST later). It is **separate** from the per-action leash channel (Module 2): contract = lifecycle/task; leash = each action.

## 2. Sub-modules
- **5.1 Message Schema** — formal definition of the six messages: fields, types, required/optional, versioning. Single source of truth for what crosses the seam.
- **5.2 Feature-Slice Builder** — extracts one feature's slice (Kind C) + its policy slice (Kind B), packages as `/task/feature.json`. Never the full catalog or other features.
- **5.3 Slice Mounter** — coordinates with the Wall (M1) to mount the slice read-only at `/task/feature.json` (P1).
- **5.4 Transport Adapter** — the six messages over a transport. v1: docker-exec/local; v1.1+: REST/HTTP. Contract identical across transports; only this changes.
- **5.5 Message Validator** — validates every message against the schema, both directions; rejects malformed/out-of-contract (no silent coercion).
- **5.6 Claim Handler** — receives `claim_done` (a thin signal — feature_id + room_id, NOT a self-verdict), hands to the Manager's verdict coordination, routes `result_decision` back.
- **5.7 Amend Handler** — processes the rare, human-originated `amend`, applying it only with valid human authority (never agent-originated).

## 3. Functional Requirements (FR)
- **FR-1** Exactly six message types, no others: inbound `provision`/`assign_task`/`amend`; outbound `status`/`claim_done`/`result_decision`.
- **FR-2** Every message conforms to the schema; malformed/out-of-contract messages are rejected (not best-effort interpreted).
- **FR-3** `assign_task` delivers the slice as a read-only file at `/task/feature.json`; the cook cannot modify it (P1).
- **FR-4** A room receives ONLY its own feature's slice — never the catalog, never another feature's data (Kind C).
- **FR-5** The slice includes: `feature_id, context, goals, non_goals, contract/acceptance_criteria, scope, task_type, capability_tags`. NOT the roadmap or other features.
- **FR-6** `claim_done` is a thin signal (`feature_id, room_id`) — a knock, not a verdict. The room cannot assert "done"; only the Manager/GovernanceEngine produces a verdict (P5).
- **FR-7** `result_decision` carries the Manager's verdict (`approved` → proceed/destroy, or `rejected{reason}` → stay alive to fix); it is the only authoritative "done."
- **FR-8** `status` reports one of: `provisioning | working | claims_done | failed | blocked`.
- **FR-9** `amend` is processed only with valid human authority (signature/host-side); agent-originated amend is rejected (P1).
- **FR-10** Transport-swappable: the same six messages work over docker-exec (v1) and REST (v1.1+) with no change to message shape — only the Transport Adapter changes.
- **FR-11** Versioned; room and Manager agree on a contract version at provision; mismatches are rejected cleanly.
- **FR-12** SEPARATE from the per-action leash channel (M2); lifecycle/task and per-action governance are not conflated.
- **FR-13** Idempotent where applicable (a re-sent `claim_done` does not trigger duplicate verdicts).
- **FR-14** Carries no credentials, secrets, or another room's state across the seam (P4).
- **FR-15** All messages crossing the seam are recordable as events (the Manager logs them) for audit/replay.
- **FR-16** The feature-slice is the single source the room reads for its task; no other task source.

## 4. Technical Requirements
- **Schema:** formal (JSON Schema / Pydantic) for the six messages; versioned; the single shared artifact both sides import.
- **Slice format:** JSON file (`/task/feature.json`), mounted read-only (Wall M1 FR-6).
- **Transport v1:** docker-exec / local stdin-stdout or unix socket (simplest for solo/free tier; no ports).
- **Transport v1.1+:** REST/HTTP (room agent-server `:8000`) for remote/scale; same messages.
- **Validation:** schema validation both directions; reject-and-log; no silent coercion.
- **Versioning:** semantic contract version negotiated at `provision`; must match/compatible or the room is not trusted.
- **Idempotency:** message ids / dedupe keys (esp. `claim_done`, `result_decision`).
- **Language:** schema language-neutral (JSON Schema); THOR's side in Python.

## 5. The Logic
- **5.1 Why frozen and small** — if only six messages ever cross, the Wall/Manager/transport/cook can each be rebuilt without breaking the other side. A wide/drifting interface re-couples the layers (the original disease). Small is the feature.
- **5.2 The six messages, in order of a room's life** — `provision` (Manager→Wall: create room) → `assign_task` (Manager→room: deliver read-only slice) → `status` (room→Manager: progress) → `claim_done` (room→Manager: a knock) → `result_decision` (Manager→room: the only "done") → `amend` (Manager→room, human-only, rare).
- **5.3 The feature-slice: one feature, read-only** — `assign_task` delivers only that one feature's spec. Serves Kind C discipline (no roadmap leak) + P1 (read-only). The slice is the room's complete and only task source (FR-16).
- **5.4 Claim vs verdict: the P5 boundary** — the room can `claim_done` but cannot *be* done. `claim_done` carries no trusted self-assessment. The Manager drives QA + GovernanceEngine and returns `result_decision`. **The protocol has no field for self-certifying — the lie can't be told because there's no field for it.**
- **5.5 Transport-swappable by design** — messages defined independently of delivery. v1 docker-exec; switch to REST changes only the adapter. Start dead-simple, scale to distributed without a protocol rewrite.
- **5.6 Separate from the leash** — contract = lifecycle/task (a handful of messages over a room's life); leash = every action (thousands of pre-action checks). Conflating them creates races/coupling.

## 6. API Strategy
### 6.1 The six messages (the complete contract)
```
# INBOUND (Manager -> room)
provision      { room_id, task_type, skills[], scope{}, repo, base_branch, limits{}, contract_version }
                 -> handled by the Wall (M1); creates the room
assign_task    { room_id, feature_slice }     # delivered as read-only /task/feature.json
                 -> { ack, slice_hash }
amend          { room_id, change{}, human_authority{signature} }   # rare, human-only
                 -> { applied:bool, reason? }
# OUTBOUND (room -> Manager)
status         { room_id, state:"provisioning|working|claims_done|failed|blocked", detail? }  -> { ack }
claim_done     { room_id, feature_id, message_id }   # a knock, NOT a verdict
                 -> { ack }   # verdict returns later via result_decision
# INBOUND reply (Manager -> room), the authoritative "done"
result_decision{ room_id, feature_id, decision:"approved|rejected", reason?, message_id }  -> { ack }
```
### 6.2 The feature-slice schema (`/task/feature.json`, read-only)
```json
{
  "feature_id": "F047", "task_type": "build",
  "context": "why this feature exists",
  "goals": ["what it must achieve"], "non_goals": ["explicitly out of scope"],
  "contract": { "acceptance_criteria": ["testable conditions of done"] },
  "scope": { "files": ["allowed paths/areas"] },
  "capability_tags": ["ui-form", "auth"]
}
```
NOT included: the full catalog, other features, dependencies' internals, credentials. (FR-4, FR-5, FR-14)

### 6.3 Transport
| Version | Transport | When |
|---|---|---|
| v1 | docker-exec / local socket | now — free tier, local, simplest |
| v1.1+ | REST/HTTP (room `:8000`) | scale — remote rooms |

Same six messages either way; only the Transport Adapter (5.4) differs.

### 6.4 What does NOT cross this seam
Per-action governance (the leash, M2, on `:8001`). Credentials (injected outbound by the leash, never handed to the room). Another room's data. The full catalog.

## 7. Diagrams (described)
- **Figure 1** — The six-message contract over a room's life: `provision`, `assign_task`→`/task/feature.json` (ro), `status`, `claim_done` (a knock, not a verdict), `result_decision` (the only authoritative done), and the rare human-only `amend`. Nothing else crosses.
- **Figure 2** — The feature-slice: from the catalog (F045/F046/**F047←this room**/F048) only F047's slice is mounted read-only as `/task/feature.json` — the room's complete and only task source; the catalog and other features never cross.
- **Figure 3** — Claim vs verdict (P5): the room can only knock (`claim_done`, feature_id only) → Manager drives QA + 8-probe verdict → `result_decision: approved|rejected`. NO self-certify field — the protocol has none; the lie has no field to live in.

## 8. Flows
- **8.1 Birth and brief** — Manager `provision` (Wall) → room created → Manager builds the slice → `assign_task` → Slice Mounter mounts `/task/feature.json` read-only → room reads task, replies `status: working`.
- **8.2 Claim → verdict → result** — room `claim_done {feature_id, room_id}` (knock) → Manager acks, drives QA + GovernanceEngine (room waits) → `result_decision: approved` → teardown; or `rejected{reason}` → room stays alive, fixes, re-claims.
- **8.3 Human amend (rare)** — operator changes scope/rules host-side, signed → Manager `amend {change, human_authority}` → Amend Handler verifies authority → applies; an agent-originated amend is rejected (FR-9).
- **8.4 Transport switch (v1→v1.1)** — same six messages + slice schema; swap the Transport Adapter docker-exec→REST; no change to Manager/room logic or message shape.
- **8.5 Malformed message** — doesn't match schema → Validator rejects (not best-effort) + logs; nothing undefined crosses.

## 9. Use Cases / User Stories (story points)
- **US-1 (8)** exactly six messages cross the seam → isolation and governance evolve independently.
- **US-2 (8)** a room receives only its one feature read-only → can't see the roadmap or rewrite scope (Kind C + P1).
- **US-3 (13)** a room can knock but cannot declare itself done — the protocol has no field for it (P5 structural). *Most important behavioral guarantee.*
- **US-4 (8)** same contract over docker-exec now and REST later — start simple, scale without rewrite.
- **US-5 (5)** malformed messages rejected, not guessed.
- **US-6 (5)** operator can amend scope with authority; an agent cannot (P1).
- **US-7 (5)** lifecycle contract separate from the per-action leash.
- **US-8 (3)** every seam message loggable as an event.
- **US-9 (5)** idempotent messages — retries don't double-trigger.
- **US-10 (3)** contract versions negotiated at provision — mismatches fail cleanly.
- **US-11 (3)** no credentials/other-room data ever cross (P4).

**Total: ~66 points for Module 5.**

## 10. Error & Edge Cases
| Case | Trigger | Handling |
|---|---|---|
| Malformed message | bad/old client | Validator rejects + logs; nothing undefined crosses |
| Version mismatch | room vs Manager | Negotiation fails at provision; room not trusted; clean error |
| Room writes `/task/feature.json` | self-modify scope | Read-only mount denies (Wall FR-6); logged |
| Agent-originated amend | injection | Rejected (no human authority); logged as security signal |
| Duplicate `claim_done` | retry/race | Idempotent (message_id dedupe); single verdict |
| `result_decision` lost | network blip | Idempotent re-send; room state machine tolerates re-delivery |
| Slice includes catalog | builder bug | Schema/validation forbids; builder emits one feature only |
| Credentials in a message | mistake | Schema forbids credential fields; validator rejects |
| Status never reported | room silent | Manager/Sentinel timeout marks room failed |
| `claim_done` before work | premature | The verdict (QA + 8-probe) rejects; claim alone changes nothing (P5) |
| Transport mid-switch | partial deploy | Version negotiation guards; mixed-transport per room |
| Oversized slice | huge spec | Size bounds; reject/trim with a clear error |

## 11. Easy vs Difficult Parts
- **Easy:** six message schemas (JSON Schema/Pydantic); slice JSON + read-only mount; validation both directions.
- **Moderate:** idempotency (must be correct for claim_done/result_decision); version negotiation; the Transport Adapter abstraction (docker-exec→REST a one-component swap).
- **Difficult / real risk:** (1) **Resisting contract growth** — keeping it *six*; every "just add one field" erodes the freeze. (2) **Getting the P5 boundary exactly right** — genuinely no path for a room to self-certify (not via claim_done, status, or a trusted manifest). (3) **Slice minimality** — the builder never leaks the catalog/another feature across all task_types.

## 12. Technical Difficulties
- **D1 — Keeping the contract frozen.** Treat it as a governed constitution; changes require version bumps + review; default question: "can this be done without touching the seam?"
- **D2 — Structural P5 (no self-certify path).** Audit the whole contract for any path where room-supplied data becomes a verdict; `claim_done` provably thin; the only "done" is `result_decision` computed by the Manager.
- **D3 — Transport swap without shape change.** Define messages above transport (request/reply with ids); the adapter normalizes delivery; a conformance test runs the same suite over both.
- **D4 — Idempotency correctness.** Message ids + dedupe on the Manager; room state machine tolerates re-delivery; verdicts keyed by feature_id+attempt.
- **D5 — Slice minimality.** The builder emits a whitelisted set of fields for one feature only; validated against the slice schema; tested to never include catalog/other-feature data.

## 13. What Needs To Be Built (checklist)
- [ ] Message Schema (six messages, JSON Schema/Pydantic, versioned)
- [ ] Feature-Slice Builder (one feature + policy slice; whitelisted fields; no catalog leak)
- [ ] Slice Mounter (read-only `/task/feature.json` with the Wall)
- [ ] Transport Adapter (docker-exec v1; REST v1.1; same messages)
- [ ] Message Validator (both directions; reject-and-log)
- [ ] Claim Handler (thin `claim_done` → Manager verdict → `result_decision`)
- [ ] Amend Handler (human-authority-only; reject agent-originated)
- [ ] Idempotency layer (message ids, dedupe)
- [ ] Version negotiation at provision
- [ ] Conformance test suite (same messages over both transports; P5 no-self-certify proof)

## 14. Dependencies & Sequencing
**Depends on:** Module 1 (Wall) — read-only slice mount + room transport endpoint. Module 3 (Manager) — sends/receives + logs these messages; drives the verdict that becomes `result_decision`. Modules 2 & 4 already use this seam informally — this formalizes and freezes it.

**Blocks / depended on by:** Module 6 (GovernanceEngine) — its verdict is delivered via `result_decision`. The SDLC stages (10–13) — briefed via `assign_task`, judged via `result_decision`. Effectively every room interaction.

**Build-order note:** Formalizes the interface Modules 1–4 already touch; build it as the explicit, versioned schema + adapters so the seam is locked before the SDLC stages. **Milestone:** a room briefed via `assign_task` with a one-feature read-only slice, reports status, knocks via `claim_done`, and receives an authoritative `result_decision` — with proof the room has no path to self-certify.

## 15. Test / Acceptance Criteria (evidence-based)
- **AC-1** Only the six defined messages are accepted; a seventh/undefined message is rejected.
- **AC-2** A room receives a slice containing exactly one feature; no other feature and no catalog (inspect the delivered `/task/feature.json`).
- **AC-3** Writing to `/task/feature.json` from inside the room fails (read-only — coordinated with Module 1 AC-5).
- **AC-4** No message or field lets a room mark itself done; the only "done" is a Manager-issued `result_decision` (contract audit + negative test).
- **AC-5** The identical six-message suite passes over both docker-exec and REST transports (conformance on both).
- **AC-6** A malformed message is rejected and logged, not best-effort interpreted.
- **AC-7** An agent-originated `amend` is rejected; a human-authority `amend` is applied (both verified).
- **AC-8** A duplicate `claim_done` produces exactly one verdict (idempotency).
- **AC-9** A version mismatch at provision fails cleanly (room not trusted), not silently.
- **AC-10** No message ever carries credentials or another room's data (schema + audit).
- **AC-11** Every seam message is recorded as an event by the Manager (in the EventLog).
- **AC-12** Switching the Transport Adapter (docker-exec → REST) requires no change to Manager or room logic or message shape (diff).

**Headline milestone:** AC-2 + AC-4 together — a room briefed with only its one feature, read-only, with structurally no way to declare itself done. That proves the contract enforces Kind-C isolation and P5 at the protocol level.

---

*End of THOR Module 5 — The Task Handoff Contract PRD v1.0. The orchestration core (Modules 1–5) is now fully specified. Next module: 6 — The Development-Governance Engine (the 8-probe verdict, claim-vs-reality divergence, contract-adherence — the core moat).*
