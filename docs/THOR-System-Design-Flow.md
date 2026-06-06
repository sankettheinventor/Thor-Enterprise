# THOR Enterprise — System Design & Flow

**Companion to the THOR Enterprise Bible. The connective tissue: end-to-end flow, API call sequences, port strategy, data model, and integration seams that every module PRD references.**

---

**Status:** Living reference. Read alongside the Bible (principles, modules, decisions).
**Version:** 1.0
**Scope:** How the 17 modules physically connect and communicate — the "how it actually runs" layer beneath the Bible's "what it is."

---

## Table of Contents
1. [System Topology](#1-system-topology)
2. [The Two Planes — Physical View](#2-the-two-planes)
3. [Port Strategy](#3-port-strategy)
4. [The Complete End-to-End Flow](#4-the-complete-end-to-end-flow)
5. [API Call Sequences](#5-api-call-sequences)
6. [The Data Model](#6-the-data-model)
7. [Integration Seams (Adapters)](#7-integration-seams)
8. [Error & Recovery Flows](#8-error-and-recovery-flows)
9. [Security & Network Boundaries](#9-security-and-network-boundaries)
10. [State & Event Flow](#10-state-and-event-flow)

---

## 1. System Topology

THOR is a set of cooperating services split across two planes. Naming convention used throughout: services are **PascalCase**, data stores are **[bracketed]**, external adopted systems are **‹angle-bracketed›**.

### 1.1 The services (control plane)
- **ThorManager** — the single governance brain + room lifecycle authority. The only writer of the audit log. Holds frozen rules and the room registry.
- **Scheduler** — deterministic task-graph executor (zero LLM in the loop). Decides what runs when.
- **CTO** — the planning intelligence. The one place a planning LLM call happens. Decides skills + scope per task, instructs ThorManager.
- **GovernanceEngine** — the 8-probe verdict + claim-vs-reality + contract-adherence (the moat). Invoked by ThorManager at verdict time.
- **Sentinel** — meta-governance health (liveness, loadedness, connectivity, integrity, canary). Can halt.
- **SelfAudit** — the zero-cost Qwen inspector. Read-only, reports to DB, URGENT-escalates to Sentinel.
- **DashboardAPI** — serves the web + mobile PM surface; read/approve face of ThorManager.
- **PhoneBridge** — the E2EE signed-approval relay (existing postman + Cloudflare worker).

### 1.2 The adopted externals
- **‹AGT›** — Microsoft Agent Governance Toolkit: the Leash (Agent OS policy engine), Sentinel substrate (SRE/Runtime), Audit (Merkle/Hypervisor), Identity (Mesh). Always reached *through a THOR-owned adapter*, never directly.
- **‹Gitea›** — git host: repos, branches, PRs, issues (= feature catalog), CI (Gitea Actions). Reached via its REST API.
- **‹Docker›** — container runtime for rooms.

### 1.3 The execution plane
- **Room** — a sealed Docker container; one cook, one git worktree, one task. Ephemeral. Types: `genesis`, `checker`, `build`, `qa`. Each runs the Leash locally (AGT plugin) reporting to the ThorManager.

### 1.4 The data stores
- **[ThorDB]** — primary store: rooms registry, feature catalog (Kind C), governance policy (Kind B), bugs, tickets, meta-trust score, SelfAudit reports.
- **[EventLog]** — append-only, signed, hash-chained event stream (the audit trail). The source of truth for replay.
- **[ExecState]** — per-room execution state (Kind A), for crash recovery.

---

## 2. The Two Planes

### 2.1 Control plane (light, always-on)
Runs on the operator's machine / cheap VPS / Oracle free tier. Contains: ThorManager, Scheduler, CTO, GovernanceEngine, Sentinel, SelfAudit (Qwen), DashboardAPI, PhoneBridge, [ThorDB], [EventLog], and the ‹Gitea› + ‹AGT› adapters. Resource-light: no heavy agent work happens here.

### 2.2 Execution plane (heavy, bursty, disposable)
Rooms. Local (Docker Compose, free tier, 2–4 rooms) or remote (K8s, paid, many rooms). Each room is created on demand, does one task, is destroyed. The control plane talks to rooms only over REST — never reaches into a room's filesystem.

### 2.3 The boundary rule
The control plane *commands*; the execution plane *executes*. All cross-plane communication is REST. No shared files, no shared memory, no direct FS access across the boundary. This is what makes rooms safely disposable and the system horizontally scalable.

---

## 3. Port Strategy

Clear, fixed port assignments so services find each other deterministically. All control-plane services bind to localhost (or the cluster's internal network); only DashboardAPI and PhoneBridge are externally reachable.

### 3.1 Control-plane ports (internal)
| Service | Port | Bind | Protocol |
|---|---|---|---|
| ThorManager | 7100 | localhost / cluster-internal | HTTP/REST |
| Scheduler | 7110 | localhost | HTTP/REST |
| CTO | 7120 | localhost | HTTP/REST |
| GovernanceEngine | 7130 | localhost | HTTP/REST |
| Sentinel | 7140 | localhost | HTTP/REST |
| SelfAudit | 7150 | localhost | HTTP/REST (read-only) |
| AGT adapter | 7160 | localhost | HTTP/REST |
| Gitea adapter | 7170 | localhost | HTTP/REST |
| [ThorDB] | 5432 | localhost | Postgres |
| [EventLog] | (append-only, via ThorManager only) | — | — |

### 3.2 Externally-reachable ports
| Service | Port | Bind | Protocol | Notes |
|---|---|---|---|---|
| DashboardAPI | 7080 | 0.0.0.0 (behind TLS) | HTTPS | Web + mobile read/approve |
| PhoneBridge | (via Cloudflare tunnel) | — | E2EE relay | No open inbound port; outbound tunnel only |
| ‹Gitea› | 3000 | as configured | HTTPS | Git host UI + API |

### 3.3 Room ports (execution plane)
| Endpoint | Port | Bind | Notes |
|---|---|---|---|
| Room agent-server (task I/O) | 8000 (per room) | room-internal, exposed to ThorManager only | OpenHands-style; receives task, reports status |
| Leash proxy (in-room) | 8001 (per room) | the ONLY network exit | All model + tool calls forced through here → AGT adapter |

### 3.4 The one-door rule
A room has **exactly one network exit: its Leash proxy (8001)**, enforced by container network rules (iptables/namespace). The cook inside cannot reach the internet, the LLM API, or Gitea except through 8001, which routes to the AGT adapter for policy check, then forwards approved traffic. This is P4 made physical. The room's agent-server (8000) is *inbound only* — ThorManager talks to it; it cannot initiate outbound except via 8001.

### 3.5 Port conflict & discovery
Per-room ports (8000/8001) are namespaced per container, so parallel rooms don't collide (each container has its own 8000/8001 internally; ThorManager maps them via the room registry). Control-plane services use fixed ports; the registry in [ThorDB] records each live room's reachable address. Identity verification (per the original THOR's F103) confirms a room belongs to this THOR instance before ThorManager trusts it.

---

## 4. The Complete End-to-End Flow

The life of THOR from install to a merged feature, every arrow. Phases map to the Bible's two-phase lifecycle.

### Phase 0 — Install & Onboarding

**0.1 Fresh install (no codebase yet):**
1. Operator installs THOR. Control plane boots: ThorManager, Scheduler, CTO, GovernanceEngine, Sentinel, SelfAudit, DashboardAPI, [ThorDB], [EventLog], adapters.
2. Sentinel runs boot self-test (P9): verifies all services alive, AGT adapter reachable, Gitea reachable, rules-hash baseline recorded. Fail → halt, alarm. Pass → ready.
3. ThorManager → CTO: "no catalog exists, run Genesis."

**0.2 Existing codebase (Project Checker — the aha moment):**
1. Operator grants read-only repo access.
2. ThorManager provisions a `checker` Room: codebase mounted **read-only**, Leash active.
3. Checker cook analyzes everything; emits findings (bad code, attack surface, dead code, patch-hacks, unwired code) → bugs/observations to [ThorDB].
4. DashboardAPI surfaces the findings to the operator — the "here is the truth about your codebase, we changed nothing" moment.
5. Room destroyed. Findings persist; inform the Genesis catalog.

### Phase 0b — Genesis (Plan, once)
1. ThorManager provisions a `genesis` Room (planning brain: PM + CTO + UX-strategy skills).
2. Cook interviews the operator (via DashboardAPI relay) and drafts: vision.md, state, metrics, outcomes, and the **feature catalog** (each feature: context, goals, non-goals, acceptance criteria/contract, task_type, capability tags).
3. Catalog written to [ThorDB] (Kind C). Each step logged to [EventLog].
4. **Operator approves the plan on the dashboard — Signature 1 (HCD).** Until approved, no build room may start.
5. Genesis Room destroyed. Kanban now populated.

### Phase 1 — Multi-Session Build (per feature, can run in parallel)

**1.1 Scheduling (deterministic, zero LLM):**
1. Operator (or a Manager policy) marks features ready on the kanban.
2. Scheduler reads the catalog + dependency graph; selects features whose dependencies are met (a "wave").
3. For each ready feature, Scheduler → CTO: "plan this task."

**1.2 Planning (the single LLM call):**
4. CTO determines skills + scope + capability tags for the task (one planning LLM call). Writes the task's governance policy slice (Kind B) for this room.
5. CTO → ThorManager: "provision a `build` room with these skills, this scope, this feature-slice."

**1.3 Provisioning:**
6. ThorManager creates a git worktree + branch in ‹Gitea›; provisions a `build` Room (Docker), network-locked (one door = Leash proxy 8001); loads the declared skills; mounts the feature-slice as read-only `/task/feature.json`.
7. ThorManager registers the room in [ThorDB] and verifies its identity.
8. ThorManager → Room agent-server (8000): `assign_task`.

**1.4 Build (governed live):**
9. Cook works. Every model call + tool call exits via Leash proxy (8001) → AGT adapter (7160) → policy check (pre-action, P3):
   - allow → forwarded (credentials injected for approved destination only)
   - deny → blocked with reason; cook told why, in real time
   - critical → escalated (manifest classification) → may raise a CEO card
10. Every decision → [EventLog] (signed, chained). Sentinel + SelfAudit observe continuously.

**1.5 Claim done:**
11. Cook finishes → emits `claim_done(feature_id)` over REST (a knock, not a verdict).

### Phase 2 — QA (fresh container, adversarial)
1. ThorManager provisions a fresh `qa` Room (tester brain by task-type), given the build branch + planned criteria + read access to the actual code.
2. QA: (a) verifies planned criteria; (b) reads the code, writes NEW tests for implementation-introduced edge cases; (c) tries to break it.
3. Findings → bugs to ThorManager API → [ThorDB]. Failures → CEO card.
4. **If failures: operator authorizes a re-work ticket — Signature 2 (HCD)** → loops back to a `build` room with specifics. QA Room destroyed.
5. If pass → proceed to verdict. QA Room destroyed.

### Phase 3 — Verdict & Merge
1. ThorManager → GovernanceEngine: run the 8-probe verdict on the branch.
2. GovernanceEngine reads git ground-truth (M1–M5), the CI signal from ‹Gitea›, the [EventLog] window (R2–R3), CTO skill results (R1); computes claim-vs-reality divergence; forms a panel verdict.
   - all pass + no divergence + within policy → eligible
   - not_done → blockers returned; build room re-opened
   - conflict/uncertainty → forced to human
3. Eligible → approval card → DashboardAPI + PhoneBridge.
4. **Operator signs the merge — Signature 3 (HCD).**
5. ThorManager → ‹Gitea› adapter: "merge PR" (peer handshake). Gitea runs final CI guards, merges to `main`.
6. ThorManager destroys the build room. Feature marked done in [ThorDB]. Full chain in [EventLog].

### The three signature points (HCD), visible in the flow
Signature 1 = approve the plan (Phase 0b). Signature 2 = authorize re-work ticket (Phase 2). Signature 3 = approve the merge (Phase 3).

---

## 5. API Call Sequences

Concrete request/response sequences for the key flows. All control-plane calls are HTTP/REST/JSON. Notation: `Caller → Callee: METHOD /path`.

### 5.1 Room provisioning (CTO → Manager → Room)
```
CTO → ThorManager: POST /rooms/provision
  { feature_id, task_type, skills[], scope{}, repo, base_branch }
ThorManager → Gitea adapter: POST /git/worktree
  { repo, base_branch, new_branch:"feature/F047" }
ThorManager → Docker: create container (image, ARM/x86, network-locked, mounts)
ThorManager → Room(8000): POST /assign_task
  { feature_slice (=/task/feature.json), task_type }
ThorManager → ThorDB: INSERT room {room_id, container, branch, status:"working"}
ThorManager → EventLog: APPEND {event:"room.provisioned", room_id, ...}
ThorManager → CTO: 200 { room_id, status:"working" }
```

### 5.2 A governed agent action (the leash, per action)
```
Cook (in room) → Leash proxy(8001): tool_call { name, args }   # forced exit
Leash proxy → AGT adapter(7160): POST /policy/check
  { room_id, action:{type, target, args}, scope_ref }
AGT adapter → ‹AGT Agent OS›: evaluate(policy.yaml, action)
AGT adapter → EventLog: APPEND {event:"action.decided", verdict, reason}
AGT adapter → Leash proxy: { decision:"allow"|"deny"|"escalate", reason }
  allow  → Leash proxy forwards to real destination (creds injected)
  deny   → Leash proxy returns GovernanceDenied{reason} to cook
  escalate → ThorManager raises CEO card; cook blocked pending decision
```

### 5.3 Claim-done → verdict → merge
```
Room(8000) → ThorManager: POST /claim_done { feature_id, room_id }
ThorManager → ThorManager: provision QA room (5.1 with task_type:"qa")
[QA runs; on pass:]
ThorManager → GovernanceEngine(7130): POST /verdict
  { feature_id, branch, contract_ref }
GovernanceEngine → Gitea adapter: GET /git/log?grep=F047   # M2
GovernanceEngine → Gitea adapter: GET /git/diff?branch=...  # M3
GovernanceEngine → Gitea adapter: GET /ci/result?branch=... # M1,M4 signal
GovernanceEngine → EventLog: GET /window?room_id&range=...  # R2,R3
GovernanceEngine → CTO: GET /skills/result?feature_id       # R1
GovernanceEngine → ThorManager: { verdict:"done"|"not_done", blockers[], divergence }
ThorManager → DashboardAPI + PhoneBridge: raise approval card
[operator signs:]
Operator → DashboardAPI: POST /approve { card_id, signature }
DashboardAPI → ThorManager: POST /merge_approved { feature_id, signature }
ThorManager → Gitea adapter: POST /git/merge { branch, signature_ref }
ThorManager → Docker: destroy room
ThorManager → EventLog: APPEND {event:"feature.merged", ...}
```

### 5.4 Health (continuous)
```
Sentinel(7140) → each service: GET /health   (every Ns; "responsive", not just up)
Sentinel → canary: fire planted must-fail action → expect deny; if allowed → ALARM + halt
SelfAudit(7150) → EventLog: GET /recent (read-only)
SelfAudit → ThorDB: WRITE report {findings, meta_trust_score}
SelfAudit → Sentinel: POST /urgent {finding}   # only for severe; Sentinel decides halt
```

### 5.5 Phone approval (E2EE)
```
ThorManager → PhoneBridge: approval card {card_id, summary}
PhoneBridge → ‹Cloudflare relay›: encrypted blob (relay never decrypts)
Phone → ‹Cloudflare relay›: encrypted { approve, card_id, Ed25519-signature }
PhoneBridge → ThorManager: POST /approve {card_id, signature}  # verified = CEO identity
```

---

## 6. The Data Model

### 6.1 [ThorDB] core tables (conceptual)
- **rooms** — `room_id, container_id, task_type, feature_id, branch, status, address, identity_token, created_at, destroyed_at`
- **features** (Kind C catalog) — `feature_id, title, context, goals, non_goals, contract, acceptance_criteria, task_type, capability_tags[], status, depends_on[], history[]`
- **policies** (Kind B) — `policy_id, feature_id, scope_files[], forbidden_patterns[], language_lock, frozen_at`
- **bugs** — `bug_id, feature_id, source(qa|checker), severity, description, status, found_at`
- **tickets** — `ticket_id, feature_id, bug_ids[], authorized_by, signature, status` (re-work, CEO-authorized)
- **cards** — `card_id, type(critical|qa_fail|merge), feature_id, payload, status, decided_by, signature, decided_at`
- **meta_trust** — `timestamp, component, success_count, fail_count, score`
- **selfaudit_reports** — `report_id, timestamp, scope, findings[], escalated(bool)`

### 6.2 [EventLog] (append-only, signed, hash-chained)
Each event: `{ seq, prev_hash, hash, timestamp, signature(Ed25519), event_type, actor, room_id?, feature_id?, payload }`. Event types include: room.provisioned, action.decided, action.denied, claim_done, qa.finding, ticket.authorized, verdict.computed, feature.merged, sentinel.alarm, selfaudit.urgent. **This is the audit trail and the replay source.** Altering any past entry breaks the chain visibly.

### 6.3 [ExecState] (per-room, Kind A)
Per room: the cook's in-flight work state, persisted outside the container so a crashed container can be replaced and resumed. Keyed by `room_id`. `[OPEN D2]` — store mechanism (Manager-side DB rows vs per-room volume).

### 6.4 State ownership recap (Bible §6)
Kind A (ExecState) = per-room, recoverable. Kind B (policies) = Manager-owned. Kind C (features) = Manager-owned, surfaced as kanban, backed by ‹Gitea› issues. Rooms never hold B or C — only their own slice.

---

## 7. Integration Seams (Adapters)

Every adopted external sits behind a THOR-owned adapter (Strangler-ready). The adapter is the only code that imports the external; everything else speaks THOR's vocabulary.

### 7.1 AGT adapter (port 7160)
- **THOR vocabulary it exposes:** `check_action(action) → ThorVerdict`, `record_decision(decision)`, `is_component_healthy(name) → bool`, `agent_identity(room_id)`.
- **Maps to AGT:** Agent OS (policy), SRE/Runtime (health/halt), Hypervisor (audit), Mesh (identity).
- **Why:** AGT is "Public Preview" — breaking changes expected. When AGT renames an API, only this adapter changes; the moat code is untouched. Enables piece-by-piece replacement later.

### 7.2 Gitea adapter (port 7170)
- **THOR vocabulary:** `create_worktree`, `open_pr`, `merge(branch, signature_ref)`, `ci_result(branch)`, `list_issues() → features`, `git_log/diff`.
- **Maps to:** Gitea REST API.
- **Why:** THOR owns merge *authority* portably; Gitea is a swappable executor. Swap for GitHub → only this adapter changes (Bible §9.5).

### 7.3 Cook adapter (in-room)
- **THOR vocabulary:** `start_task(slice)`, `status()`, `claim_done()`.
- **Maps to:** whatever agent runs (Claude Code plugin, or a generic agent-server). Cook-agnostic: the adapter normalizes different agents to the same contract.

### 7.4 The frozen contract (Bible D8)
Six messages, transport-swappable (docker-exec now, REST later): inbound `provision`, `assign_task`, `amend`; outbound `status`, `claim_done`, `result_decision`. Kept separate from the per-action leash channel.

---

## 8. Error & Recovery Flows

| Scenario | Detection | Response |
|---|---|---|
| Leash/AGT adapter down | Sentinel health probe fails | Fail-closed: all room actions denied; alarm; rooms pause |
| ThorManager crash | Sentinel / external supervisor | Restart → replay [EventLog] to rebuild state |
| Room container crash | Room health probe / agent-server unreachable | Provision new container → reload [ExecState] → resume |
| Cook hangs | Room-level timeout | Mark room failed → card to operator → re-provision or abandon |
| Host power loss | Boot self-test on restart | Control plane replays [EventLog]; in-flight rooms re-provisioned from [ExecState] |
| Free-tier out-of-capacity | Docker/K8s provision error | Queue the task, or burst to paid capacity (per D3 policy) |
| Merge conflict | Gitea merge attempt fails | Returned as a fix task to a build room; never force-merged |
| Egress to non-allowlisted host | Leash proxy / AGT egress layer | Blocked + logged as governance event; may escalate to security card |
| Tampered governance rules | Sentinel integrity crawler (hash mismatch) | Halt + alarm; refuse to proceed until operator re-verifies |
| Malicious file / tool detected | AGT MCP gateway / R3 probe | Kill-switch (max-severity): terminate room, quarantine, alarm |
| SelfAudit finds correctness drift | SelfAudit continuous inspection | Report to DB; if severe → URGENT to Sentinel → Sentinel decides halt |

### 8.1 The recovery invariant
Because [EventLog] is append-only and [ExecState] persists outside containers, **no single component crash loses governance truth or in-flight work.** The control plane is reconstructable by replay; rooms are reconstructable from execution state. This is why disposability is safe.

---

## 9. Security & Network Boundaries

### 9.1 The capability separation (P4)
- Cook: has task + skills, **no credentials, no direct network.**
- Leash proxy (8001): **the only exit**, holds nothing sensitive itself — forwards to AGT adapter.
- AGT adapter: holds credentials, injects them only for approved destinations after policy check.
- Result: the agent cannot exfiltrate or reach unapproved destinations because it has no path and no keys.

### 9.2 Network rules per room
- Inbound: only ThorManager → agent-server (8000).
- Outbound: only via Leash proxy (8001), enforced by iptables/namespace. No other route exists.
- Room-to-room: none. Rooms cannot see or reach each other.

### 9.3 Threat coverage (adopted from AGT)
MCP security gateway (tool-poisoning, typosquatting, hidden instructions); shadow-AI discovery (rogue unregistered agents — folds into Sentinel); kill-switch (max-severity termination). All via the AGT adapter.

### 9.4 Identity & signatures
- Each room verified (belongs to this THOR instance) before ThorManager trusts it.
- Every human signature (plan, ticket, merge) is Ed25519-signed; phone approvals carry the CEO's key.
- [EventLog] entries are signed and hash-chained.

---

## 10. State & Event Flow

### 10.1 The event-sourcing backbone
Every meaningful action — agent decision, room lifecycle change, verdict, signature, alarm — is an **immutable appended event** in [EventLog]. Mutable state ([ThorDB] rows, [ExecState]) is a *projection* of the event stream and can be rebuilt by replay. This gives: deterministic recovery, complete audit, debugging by replay, and the dashboard activity feed — all from one mechanism.

### 10.2 Who writes what
- **ThorManager** — the only writer of [EventLog] (single source of audit truth). Writes room/feature/card rows in [ThorDB].
- **GovernanceEngine** — computes verdicts (reads git/CI/log); writes verdict events via ThorManager.
- **SelfAudit** — writes only its own report rows + meta_trust; never writes [EventLog] directly (read-only inspector).
- **Sentinel** — writes alarm events via ThorManager; can trigger halt.
- **Rooms** — write nothing to control-plane stores directly; they report over REST and ThorManager records it.

### 10.3 The flow in one sentence
Operator directs (dashboard/phone) → Scheduler sequences → CTO plans → ThorManager provisions + governs (via AGT leash) → Cook works → QA breaks → GovernanceEngine judges → operator signs → Gitea merges — with Sentinel + SelfAudit watching the whole machine and every step appended, signed, to [EventLog].

---

*End of THOR Enterprise — System Design & Flow v1.0. Every module PRD references this document for topology, ports, API shapes, data model, and flow. Next: per-module PRDs in build order, starting with Module 1 (Wall).*
