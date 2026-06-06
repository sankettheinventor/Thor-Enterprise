# THOR — Enterprise Bible

**Governed Agentic Development Platform**

> The single source of truth for what THOR is, why it exists, how it is built, and what is decided versus still open. This document is the map. Everything else — sub-PRDs, code, dashboards — hangs off it.

---

**Document status:** Living reference. `[LOCKED]` = deliberately chosen, do not reopen without cause. `[OPEN]` = not yet settled. `[DEFER]` = future/north-star, out of v1 scope.

**Version:** 2.0 — Consolidated
**Owner:** Sanket Toraskar (CEO)
**Spine principle:** Build ungoverned first; switch governance on only when whole.

**How to read the two framings:** THOR is described at two levels that must stay consistent. **Pillars** (§4) are the four high-level groupings used for explanation and build-order. **Modules** (§13) are the seventeen concrete buildable units. Every module belongs to exactly one pillar; §13 shows the mapping. Pillars are the chapters; modules are the parts.

---

## Table of Contents

1. [What THOR Is](#1-what-thor-is)
2. [First Principles (P1–P9)](#2-first-principles)
3. [The Competitive Landscape](#3-the-competitive-landscape)
4. [The Four Pillars](#4-the-four-pillars)
5. [Architecture — Control Plane vs Execution Plane](#5-architecture)
6. [The Three Kinds of State](#6-the-three-kinds-of-state)
7. [The Leash — Cook-Agnostic Interception](#7-the-leash)
8. [The Governance Models — THOR's Brain](#8-the-governance-models)
9. [The Authority & Verdict Model](#9-the-authority-and-verdict-model)
10. [The Hybrid Agentic SDLC — Typed Stages](#10-the-hybrid-agentic-sdlc)
11. [The Three Health Layers — Sentinel, Self-Audit, Human](#11-the-three-health-layers)
12. [Infrastructure, Cost & Hosting Tiers](#12-infrastructure-cost-hosting)
13. [The Module Map (17 modules)](#13-the-module-map)
14. [Enterprise Concerns](#14-enterprise-concerns)
15. [Build Order — The Bootstrap Fix](#15-build-order)
16. [Competitive Reality & The Re-Scope](#16-competitive-reality-rescope)
17. [Adoption Decisions — What We Take, Reject, Build](#17-adoption-decisions)
18. [Future Layers — Toras & Self-Evolution](#18-future-layers)
19. [Glossary](#19-glossary)
20. [Open Decisions Register](#20-open-decisions-register)

---

## 1. What THOR Is

### 1.1 One-sentence definition
THOR is a platform that lets a human direct multiple AI coding agents to build software in parallel, where every agent works inside a sealed environment it cannot escape, every action it takes is judged *before* it happens against rules the agent cannot touch, and nothing reaches the real codebase without passing a governance gate and a human signature.

### 1.2 The thesis
Every agentic coding system today solves **isolation** (keep the agent in a box) or **orchestration** (make agents talk to each other). None solve **governance of conduct**: stopping an agent from faking results, hallucinating, drifting out of scope, silently changing the tech stack, or declaring work "done" when it isn't.

THOR's bet: as AI writes more production code, the bottleneck stops being *can the agent write code* (it can) and becomes *can you trust what it did, and can you prove it.* THOR is the trust-and-proof layer.

### 1.3 What makes THOR different
Two things at once that nobody has combined:
- **A governance runtime** — governs agent *behaviour* live, not just agent *escape*. Enforces honesty (evidence-based "done"), scope adherence, stack integrity.
- **A project-management tool over agentic AI** — a kanban/approval surface where a human directs features, reviews proposals, signs merges, from desktop or phone.

Governance + project management + multi-agent parallelism, with the human as the accountable authority. That triple is the product.

### 1.4 What THOR is NOT
- Not a coding agent — it governs whatever agent works (cook-agnostic).
- Not a git host or CI system — uses Gitea underneath.
- Not an isolation primitive — uses Docker; THOR is the governance *on top*.
- Not a replacement for the customer's pipeline — it gates what *enters* it.

---

## 2. First Principles

The laws. Every design decision is checkable against them. Violating one is how the original THOR failed.

- **P1 — External Authority.** Governance lives outside the agent, in a layer it cannot read, edit, or negotiate with. The governed never holds the pen that writes its own rules. *(Lesson of the original `reverted/` graveyard: builder and governor were the same entity.)*
- **P2 — Fail-Closed.** If the governor is unreachable, default is deny. The agent cannot work without the governor alive and answering. Silence = refusal.
- **P3 — Pre-Action Interception.** Governance acts *before* an action executes. Merge-time-only judging produces infinite reject-loops. The first forbidden action is blocked at attempt, with a reason.
- **P4 — OS-Enforced Boundary.** The boundary is a physical fact (container network rules, FS permissions, kernel isolation), not a convention the agent is asked to honor. The agent cannot bypass the leash because the leash *is* the only door the network allows.
- **P5 — Evidence-Based Done.** "Done" is never the agent's self-report. A feature is done only when external verification confirms it against its declared contract. The agent proposes done; the system disposes.
- **P6 — Human Signature.** Final authority to merge is a human, cryptographically identified. The agent proposes, the gate evaluates, the human signs. The core of Human Command Development (HCD).
- **P7 — Build Ungoverned First.** A governance system must be fully built before it governs anything — including its own development. Do not erect the fence while pouring the concrete it stands in. Bootstrap is a one-time ungoverned exception. *(Fix for the bootstrap paradox.)*
- **P8 — Separation of Concerns.** Isolation, governance, project-management, remote-control are separate layers with defined interfaces, never one file. *(The original `watchdog.js` hit 6,000 lines by mixing all of them.)*
- **P9 — Self-Verifying Governance.** Every governance and execution component must continuously prove it is alive, loaded, connected, and doing its job — and fail-closed and alarm when it cannot. A governor that cannot verify itself is assumed broken. Silent success is forbidden: always distinguish "passed because it checked" from "passed because the checker was dead."

---

## 3. The Competitive Landscape

Why THOR exists, validated against the field as of mid-2026.

- **OpenHands** — mature (70k-star, MIT) coding-agent runtime; production sandbox, REST agent-server. *Lacks* governance of conduct — walls the agent, doesn't judge it. **THOR:** reference + construction-crew, never a dependency. Borrow the pattern (Docker isolation, caller↔box thin interface), not the codebase.
- **CrewAI / AutoGen** — conversation orchestration; LLM personas passing text; no sandbox/git/merge. **Take:** discipline (declarative definition split from execution; one typed state object) and the *event-driven core* principle (independently confirmed by both — strong signal).
- **AI Gateways** (LangChain, WSO2, Gravitee, Google Agent Gateway, MLflow, PipeLab, Sandbox0, MCPGuard) — the industry converged on THOR's instinct: governance *outside* the agent, at the tool/model boundary, enforced before execution. *Lack:* they treat it as generic *security*, not *development governance* tied to a feature's contract. None ask "did the agent fake this result." **THOR's edge:** the chokepoint is a borrowable proven pattern; THOR adds the governance *semantics* (honesty, contract-adherence).
- **Gitea** — self-hosted MIT all-in-one git host (code, PRs, issues, CI/CD, packages). **THOR:** the offloaded backbone. Don't rebuild git/PR/CI; talk to its API; surface in THOR's own UI.
- **Bernstein** — closest orchestration analog (Goal→Planner→task graph→parallel agents→Janitor→merge; deterministic scheduler; zero coordination tokens; state outside agent memory). *But:* noncommercial license (study-only), and ungoverned + human-absent ("while you sleep").
- **Microsoft AGT** — production governance substrate (MIT): policy engine (leash), privilege rings + kill-switch, SRE (chaos/circuit-breakers), compliance mapping, crypto identity. *But:* governs *agent safety*, not *software-development correctness/honesty*.

**The unoccupied corner:** isolation solved, orchestration solved, security-gateway solved. **Honest, contract-bound, human-accountable governance of real code execution, built as a product — empty.** That is THOR.

---

## 4. The Four Pillars

The high-level grouping. Each pillar contains specific modules (§13). Built in dependency order (§15).

- **Pillar 1 — Isolation (the Wall).** Sealed container per task; kernel-enforced; the agent cannot see host FS, other rooms, or the network except through THOR's one door. Dumb about policy; smart only about forcing every action through the chokepoint and making the leash untouchable. *Contains modules 1.* *Net-new, built first.*
- **Pillar 2 — Governance (Leash + Manager + Models).** The behavioural governor. One **THOR Manager** (not one-per-room) holds the models, decides allow/deny pre-action, gates merges. *Contains modules 2,3,4,5,14, and the security/health layers (§11).* *Adopt AGT for the substrate; build the development-governance moat on top.*
- **Pillar 3 — Project Management (the human surface).** Kanban, approval queue, audit view, the three signature points, cost preview. THOR's own UI over Gitea's API + the event log. *Contains modules 6,15.* *Evolve the existing CEO dashboard to N parallel rooms.*
- **Pillar 4 — Mobile / Remote.** Direct the system from a phone; E2EE, signed approvals, allowlisted commands; legible refusal. *Contains module 16.* *Extend the existing phone bridge.*

Orchestration (modules 7,8,9) and the SDLC stages (10,11,12,13 in §13's numbering) span Pillars 1–3 — they are the connective tissue that moves work through the pillars; §10 and §13 detail them.

### The seams
- **P1 ↔ P2:** the room forces all agent traffic through the Manager's leash via container network rules. Room is dumb; Manager judges.
- **P2 ↔ P3:** the dashboard reads the Manager's event log + approval queue; the human acts; actions return to the Manager.
- **P2 ↔ Gitea:** Manager reads issues as feature-slices, opens/gates PRs, triggers CI.
- **P3 ↔ P4:** phone is a remote head on the same data, with signed commands.

---

## 5. Architecture

### 5.1 Control Plane vs Execution Plane `[LOCKED]`
The structural answer to "how do we run this without crushing one laptop."

**Control Plane** (lightweight, always-on, runs on laptop / cheap VPS / Oracle free tier): THOR Manager (governance brain + event log + frozen rules), Deterministic Scheduler, PM dashboard, Gitea, the Leash/AGT, the Sentinel, the Self-Audit (Qwen) model.

**Execution Plane** (heavy, bursty, scales horizontally, remote): the rooms — Docker containers, one per active task, each running a coding agent. Created on demand, **disposable**, destroyed when done.

The operator machine never holds 10 containers; it holds the control plane and talks to N remote rooms over REST. Control plane is small and near-free; execution plane scales and is pay-per-active-room.

### 5.2 The provisioning chain `[LOCKED]`
**CTO (intelligence — decides skills + scope) → THOR Manager (mechanism — provisions container) → Cook (Claude Code / any agent — works inside).** CTO thinks, THOR Manager acts, cook works. The CTO never touches Docker; the THOR Manager never decides skills (it is told). The single planning LLM call lives with the CTO.

### 5.3 The lifecycle (one feature, end to end)
1. A feature is selected from the kanban (a Gitea issue) — by the human, or by a Manager policy on ready features.
2. **CTO** decides the skills + scope for the task; instructs the **THOR Manager**.
3. **THOR Manager** provisions a room: git worktree/branch, sealed container with the chosen cook, network-locked so the only exit is THOR's proxy. Hands the room **only that one feature-slice** as read-only `/task/feature.json` over REST (never the catalog).
4. Cook works. Every model + tool call is forced through the **leash** (§7); the Manager judges each against the governance models (§8) pre-action: allow, or block-with-reason.
5. Cook claims done (a thin signal — it cannot self-certify).
6. Work moves to the **QA stage** (fresh container, adversarial tester — §10) before any merge consideration.
7. On QA pass, the **Development-Governance Engine** runs the 8-probe verdict + claim-vs-reality (§9) from git ground-truth, not the agent's word.
8. Pass → approval card to dashboard + phone → **human signs** (P6). Fail → blockers returned; room stays alive to fix.
9. On signature, Manager directs Gitea to merge the PR (peer handshake, §9); Room Manager destroys the room.
10. Every step is an appended, signed event in the audit log (§14).

### 5.4 One THOR Manager, not one-per-room `[LOCKED]`
A watchdog-per-room re-scatters governance state (the original disease) and multiplies processes/races/ports. One Manager = single source of governance truth, single audit-log writer, single frozen rule-set. Each room's leash does not *decide*; it *asks* the one Manager (the original `hook-gate.js`→watchdog client/server split, now pointed at the single Manager).

---

## 6. The Three Kinds of State `[LOCKED]`

There is no single source of truth — there are three kinds, three owners. Conflating them was a root cause of the original failure.

- **Kind A — Execution State** (per room, disposable-recoverable). The agent's in-flight work. One persisted object per room, so a crashed container can be replaced and resumed. The container is disposable; the state is not.
- **Kind B — Governance Policy** (Manager-owned, outside all rooms). Scope rules, forbidden patterns, language locks, what-needs-an-ask. Consulted at decision time, never handed into the room. *(Corrected role of the old `scope.json`.)*
- **Kind C — Feature Catalog** (Manager-owned, surfaced as kanban, backed by Gitea issues). The full feature list. Each room receives only its own slice as its task brief. *(Corrected role of the old `tdd.json`.)*

**Deleted:** `room.json` (registry lives in the Manager's state); bell files / inbox / outbox / processing dirs (replaced by REST + event-driven messaging — this file-queue was the race disease).

---

## 7. The Leash — Cook-Agnostic Interception

The mechanism by which THOR governs *any* coding agent, live, before each action.

### 7.1 Principle
Every agent must do two things: call a model and call tools. Control those two paths and you control the agent. THOR sits on both — not by hooking a specific agent's internals (wouldn't generalize) but on the universal paths every agent uses. **This is what makes it cook-agnostic.**

### 7.2 The two-layer chokepoint
- **Layer A — MCP-aware proxy** (structured tool-call governance): intercepts the structured tool protocol (e.g. MCP JSON-RPC) both directions; understands "agent is calling write_file with these args"; allow/deny on semantics.
- **Layer B — Egress network proxy** (raw-traffic governance): inline on the room's network; catches raw HTTP bypass attempts, exfiltration, web fetches, DNS tricks.
- **Layer C — The sandbox** (Pillar 1): keeps the agent off the host FS and out of other rooms.

### 7.3 The un-negotiable property (P4)
Real only if the room's network rules **physically force all traffic through THOR's proxy.** Enforced capability separation: the agent has credentials but no direct network; the proxy has network but injects credentials only for approved destinations. The agent cannot unset the leash because the leash *is* the network.

### 7.4 Fail-closed + auditable
If THOR cannot safely inspect a request, it denies. Every allow/deny is a structured, recorded event — denied calls are first-class governance facts, not buried in a transcript.

### 7.5 Two tiers of what it enforces
- **Common-pattern governance** (learnable): scope violations, forbidden-file touches, dependency adds, mass deletions, manifest classification. *(The gateways do roughly this, as generic security.)*
- **Core agent-behaviour governance** (THOR-specific, the moat): faked results, claims-without-evidence, contract drift, silent scope/stack changes. Held in the governance models (§8).

### 7.6 Implementation
ADOPT AGT (Agent OS policy engine + Claude Code plugin + YAML policy) behind a THOR-owned adapter (Strangler-ready, §17). AGT explicitly recommends running each agent in a separate container — exactly our wall+leash split.

---

## 8. The Governance Models — THOR's Brain

The THOR Manager holds these models — the *intelligence* that decides. The leash is the *mechanism*. Proven logic from the original watchdog/PM/CTO, re-housed clean.

- **8.1 Scope model** — CEO-approved set of files/areas a feature may touch, with a full change-log of expansions + who approved. Out-of-scope edits denied at attempt (P3).
- **8.2 Manifest classification** — every change classified by impact: *critical* (human card: protected file, dependency manifest, new interpreter file, mass deletion, out-of-scope), *denied* (blocked), *non-critical* (auto within scope).
- **8.3 Evidence-based done** (the moat — P5) — done only if a fresh verifier verdict exists (or a valid human override token), the verifier reads actual git commits/diffs against the contract, and claimed work has evidence (claim-gate / evidence-ledger). The agent cannot mark its own feature done.
- **8.4 SDLC / contract model** — no feature without a spec; no commit without contracts; if code and design disagree, stop and fix the spec. Blocks edits on empty contracts. Includes the **canary invariant** (a deliberately-empty-contract feature kept so the guard keeps proving it works).
- **8.5 Stack-integrity** — no silent language changes, undeclared dependencies, or framework swaps; detected at the chokepoint, escalated to a human card.
- **8.6 Anti-hallucination / honesty** — did the agent fabricate a result, claim an unrun test, assert completion without proof. This + 8.3 make THOR a conscience, not just a cage.
- **8.7 How rules are set & frozen** — set by the human, frozen at session 0, mounted read-only into the room (editable only host-side). Mid-session changes are a separate human action through a separate door — never the agent's.

---

## 9. The Authority & Verdict Model `[LOCKED]`

### 9.1 Two completion signals, two vantage points
- **Signal 1 — the agent's claim** (OpenHands-style `finished`): a clean REST event = `claim_done(feature_id)`. A knock on the door, *not* a verdict — tells THOR *when* to check.
- **Signal 2 — THOR's own verdict** (the 8-probe engine): triggered by Signal 1, computes "done" from reality. THOR trusts only this.

### 9.2 The 8-probe done-engine (un-fakeable; from the real THOR source)
"Done" iff **all 8 pass**, else `not_done` + specific blockers. Each probe is a read-only query against reality.
- **M1** verifier exit code 0 · **M2** commit landed (`git log --grep FXXX` → real SHA) · **M3** diff matches the contracts' cited files · **M4** regression test exits 0 · **M5** every contract `status:done`.
- **R1** CTO skills all passed · **R2** zero claim-gate/patch-detect hits in the audit during the commit window · **R3** zero backdoor/injection alarms in the window.
- **R2 + R3 are the genuine moat** — auditing *behaviour during the work*, which neither OpenHands nor Gitea does.

### 9.3 The verdict model — a panel that trusts nothing blindly `[LOCKED]`
THOR forms its verdict from multiple independent mechanisms (git ground-truth, the CI signal, claim-vs-reality divergence, contract satisfaction) — trusting none on its own. **Consensus → verdict. Conflict/uncertainty → human signature.** This matches the existing THOR (multiple cross-checking verifiers + human tie-break). Even Gitea's CI is a *signal on the panel*, not the chair. Verification depth tiers by stakes; critical changes always require a human (HCD), regardless of confidence.

### 9.4 Claim-vs-reality divergence (the lie-detector)
THOR also reads the agent's *claim* and compares it to git ground-truth. The gap is a recorded honesty signal feeding 8.6. (This is the unique addition OpenHands lacks — it pipes CI failures back but never checks whether the agent *lied about* what it did.)

### 9.5 Authority: THOR owns the verdict, portably; Gitea executes `[LOCKED]`
THOR holds the **governance authority independently and portably** — its verdict exists regardless of which git host is underneath. Gitea executes the merge and runs CI. They talk **as peers through a defined handshake**: THOR directs Gitea ("run CI, report"; "approved, merge" / "rejected"); Gitea retains its own hard guarantees (won't merge with conflicts). THOR is **not** a check living inside Gitea's branch-protection — it is a peer authority Gitea consults and obeys. Swap Gitea for GitHub → only the adapter changes, never the authority. The moat always lives in THOR; the git host is a replaceable executor.

### 9.6 Who owns `main`
Gitea owns `main` mechanically (branch protection, PR merge, CI). THOR + human own the *decision* of whether a PR may merge at all. THOR gates before Gitea executes. Post-merge CI/CD is Gitea Actions' job; THOR governs what *enters* the pipeline, not the pipeline itself.

---

## 10. The Hybrid Agentic SDLC — Typed Stages `[LOCKED]`

### 10.1 The reframe
THOR is not a "room system" — it is a **Hybrid Agentic SDLC.** Containers are not generic boxes differing only by task text; they are **typed lifecycle stages**, each with its own brain, skills, memory. This dissolves the Docker-vs-THOR confusion: Docker provides the typed *stages* (nodes); THOR is the *lifecycle process* moving work through them and governing every transition. (LangGraph-shaped: nodes = stage-containers, edges = governed transitions, state = the feature flowing through.)

### 10.2 Universal stage anatomy (every stage, same skeleton)
1. **Input** (over REST) · 2. **Brain + Skills** (composed for stage and task-type) · 3. **Mandate** (one job) · 4. **Edge check** (what THOR verifies before work leaves) · 5. **Output** (to next stage + persisted to DB). New stages slot in without breaking because they share the anatomy.

### 10.3 The stages
- **PLAN — Genesis** (once, at first setup). Planning brain: PM + CTO + UX-strategy. Interviews the human; produces vision.md, state, metrics, outcomes, the feature catalog (each feature with acceptance criteria). Human **approves the plan (signature 1)**. Container destroyed.
- **PLAN — Project Checker** (for *existing* codebases). **READ-ONLY** full-codebase analysis; shows bad code, attack surface, dead code, patch-hacks, unwired code to the human — the install "aha moment." Changes nothing (read-only mount is the trust guarantee). *(Pattern proven: Bernstein knowledge graph, Intent context engine.)*
- **BUILD — Dev** (many, parallel). Building brain composed by task-type (frontend → frontend+UX+UI+code-reviewer; backend → backend+API-design+code-reviewer; infra → infra/devops+security+code-reviewer). Builds one feature within scope; leash governs every action live.
- **TEST — QA** (fresh container per feature, destroyed after). Tester brain by task-type (frontend → QA+UX-testing+accessibility+visual-regression; backend → QA+API-contract+load/security). Independent — did NOT write the code. Mandate: (a) verify planned criteria; (b) read the actual code and write NEW tests for hidden patterns the implementation introduced; (c) try to break it. Output: findings → bugs to PM via API → DB; failures → CEO card → **CEO authorizes ticket (signature 2)** → back to Build; on pass → verdict gate.
- **VERDICT GATE** (the Manager itself, not a container). The 8-probe engine (§9). On approval + **human merge signature (signature 3)** → directs Gitea to merge.

### 10.4 QA mandate — structure + skills, not deterministic-vs-agentic `[LOCKED]`
A false choice for THOR. QA = a governed QA template (predictable, reproducible, gate-trustworthy) executed by an agent with top-1% QA skills (the intelligence). Skills make testing smart; the template keeps it governed. **This is the architectural strength of the whole SDLC:** each stage is structure + swappable skills, so any stage improves by *adding a skill or check* — isolated, composable, non-breaking (the opposite of the old `fNNN` sediment).

### 10.5 Three signature points (HCD)
Human signs: the **plan** (Genesis), the **re-work tickets** (QA), the **merge** (gate). Consistent accountable authority throughout.

### 10.6 Task decomposition & "multiple agents per task"
One task → one container → one cook (with that task's skills). A job needing frontend + backend + DB is *three dependent tasks*, each its own container, sequenced by the task graph — never multiple agents crammed in one box. Decompose finer; let dependencies sequence them.

---

## 11. The Three Health Layers — Sentinel, Self-Audit, Human `[LOCKED]`

THOR governs the agents — so who governs THOR? Three layers, distinct jobs.

### 11.1 Sentinel (meta-governance — the reflexes)
Mechanical, deterministic, binary. Continuously verifies THOR's own components:
1. **Liveness** — every component alive AND responsive (not just process-on).
2. **Loadedness** — did each stage's declared skills load before work began?
3. **Connectivity** — are REST channels (Manager↔room↔Gitea↔DB) open?
4. **Integrity** — have rules/code been tampered since freeze (hash crawler)?
5. **Efficacy (canary)** — fire a planted must-fail action; if the leash lets it through, the leash is broken.
6. **Fail-closed + alarm** — any failure → affected stage fail-closes (no silent pass) → alarm.
**Can HALT.** ADOPT AGT Agent SRE + Runtime behind an adapter. The **canary base case** stops the infinite regress: a detector whose *silence is itself the alarm* needs no further watcher.

### 11.2 Self-Audit Model (Qwen — the watching eyes)
Where the Sentinel asks "are you alive?", this asks "are you doing your job *correctly*?" — bringing *understanding* to health-watching without bringing cost.
- A small, cheap, always-on local model (Qwen-class) in its own container. **Zero token cost** (self-hosted; runs continuously without touching frontier-model budget). **Read-only** (changes nothing — same trust guarantee as the Project Checker). **Output → DB** (reports, audit findings, "is the system working correctly," the system meta-trust score).
- **Power (escalation path):** reports/flags normally; **can flag URGENT to the Sentinel, which decides whether to halt.** The cheap, fallible model never halts directly, but escalates to the deterministic enforcer that can.
- Becomes the **Toras runtime checker in v2** (observe→report grows into observe→understand→correct; cheaper because it corrects drift early).

### 11.3 Human (the judgment)
Acts on flags; holds final authority. The three signature points (§10.5) are where this authority is exercised.

### 11.4 System trust, not agent trust `[LOCKED]`
THOR rejects per-agent trust-scoring (AGT's model — built for managing unreliable long-lived agents). THOR *corrects* short-lived agents per-action instead. A decaying score on inherently-inconsistent agents is meaningless and risks "all agents low → system stalls." Instead, the **meta-trust score lives on THOR's own machinery** — how often the *system* fails to produce required output — computed by the Self-Audit model. Score the thing that should be reliable (the system), not the thing that never will be (any single agent).

### 11.5 Why separation is SAFE
A monolith hides internal failures; a separated system where each piece self-reports turns every failure into a visible signal. Separation + self-verification is *more* governable than a monolith, not less.

---

## 12. Infrastructure, Cost & Hosting `[LOCKED]`

### 12.1 Docker or Kubernetes — both, in sequence
Different layers, not competitors. Docker builds/runs the room; Kubernetes orchestrates many rooms *only when scale demands*. Now: Docker Compose on one host (K8s threshold — 50+ containers, multi-node, dedicated platform team — is far away; early K8s is the common mistake). Later: K8s, same OCI image migrates unchanged. **Build the room as a clean OCI image now, ARM (free tier) + x86 (paid).**

### 12.2 Cost shape
Software is all free/open-source. **Compute is not** — every running room burns real CPU/RAM. But the **dominant cost is LLM tokens**, not compute: the container is nearly free; the intelligence inside it is the cost. Destroyed rooms cost nothing (scale-to-zero). The Self-Audit Qwen model adds zero token cost.

### 12.3 The two hosting tiers
- **Free / Self-Hosted** (small firm, solo): Oracle Always-Free (4 ARM OCPU / 24 GB / never expires) or a cheap VPS, Docker Compose. Holds the full control plane (Manager, Scheduler, PM surface, Gitea, Leash/AGT, Sentinel, Self-Audit Qwen) + **~2–4 concurrent rooms**. Low concurrency, features mostly sequential. ~Zero infra; tokens the only real cost. Constraints: ARM images; ~one full box, no headroom.
- **Paid / Scale** (larger firm, production): managed scale-to-zero or K8s (same x86 OCI image). Control plane + **many concurrent rooms** (10–30+), autoscaled. Pay-per-active-room. Firms pay for parallel speed — the throughput is the value.

### 12.4 The rule
Free = low concurrency, self-hosted, near-zero infra. Paid = high concurrency, managed/K8s, pay-per-active-room. Same software, same image; only the number of simultaneous rooms — and the bill — changes.

### 12.5 Cost controls (woven through Scheduler + Self-Audit)
Cost estimate before a run; hard budget caps; dry-run preview; semantic caching of repeated patterns; the zero-LLM deterministic scheduler (no coordination tokens); the cheap Qwen model for reports/audits. Retro/benchmark run occasionally and cheaply (reports over existing data, not new frontier runs).

---

## 13. The Module Map (17 modules) `[LOCKED]`

Each module is ADOPT (use external), BUILD (ours), or STUDY-then-build. Each belongs to a pillar (§4).

**Foundation / Pillar 1–2 (mostly ADOPT)**
1. **Wall** — sealed container per task. ADOPT Docker + thin BUILD provisioning wrapper; read-only mounts where required.
2. **Leash** — pre-action policy (P3, fail-closed). ADOPT AGT Agent OS + Claude Code plugin + YAML, behind adapter.
3. **Sentinel** — meta-governance self-verification (P9, §11.1). ADOPT AGT SRE + Runtime, behind adapter.
4. **Audit Trail** — tamper-evident decision log. ADOPT AGT Merkle/HMAC + Hypervisor, behind adapter.
5. **Identity** — crypto agent identity. ADOPT AGT Agent Mesh (Ed25519/DID), behind adapter. *(System-trust only, not agent-trust — §11.4.)*

**Pillar 3 backbone (ADOPT)**
6. **Git/PR/CI backbone** — repo, branches, PR, CI. ADOPT Gitea + Gitea Actions via API; THOR owns merge authority (§9.5).

**Orchestration (BUILD; study Bernstein/OpenHands)**
7. **Deterministic Scheduler** — ONE planning LLM call → skill-tagged task graph; plain code schedules in dependency waves; zero coordination tokens. One-cook-per-task.
8. **THOR Manager (Room Manager)** — spawns/routes/destroys containers on the CTO's instruction; delivers task over REST (OpenHands resolver pattern).
9. **Task Handoff Contract** — six-message REST contract (`provision`, `assign_task`, `amend` / `status`, `claim_done`, `result_decision`); feature-slice as read-only `/task/feature.json`; `task_type` field. The frozen interface.

**SDLC Stages (BUILD — the moat surface)**
10. **Genesis (Plan)** — once; PM+CTO+UX-strategy; produces catalog; human approves (sig 1).
11. **Project Checker** — existing codebases; READ-ONLY full analysis; the "aha moment"; changes nothing.
12. **Build (Dev)** — parallel; skills by task-type; leash governs live.
13. **QA (Test)** — fresh per feature; structure + top-1% QA skills; verify criteria + write new tests; bugs→DB, failures→CEO ticket (sig 2).

**Governance Engine (BUILD — the core moat)**
14. **Development-Governance Engine** — 8-probe verdict (M1–M5,R1–R3), claim-vs-reality divergence, contract-adherence, anti-hallucination. THE MOAT. Port doctrine from done-check.js / skill-verifier / evidence-ledger, clean.

**Human Surface (BUILD — the moat)**
15. **PM Surface** — kanban, approval cards, audit view, 3 signature points, cost preview/budgets. Evolve ceo.html/cockpit; pull from Gitea API + DB + event log.
16. **Mobile/Remote + Legible Refusal** — E2EE signed phone control (keep existing postman + Cloudflare bridge); plain-language "why refused" on AGT deny-reasons.

**Health (BUILD on adopted substrate — §11)**
17. **Self-Audit Model (Qwen)** — zero-cost, read-only, continuous correctness inspection; reports + URGENT-escalates to Sentinel; becomes Toras in v2.

**Woven through:** security responses (kill-switch as max-severity outcome reject→quarantine→terminate; MCP Security Gateway; Shadow-AI discovery — all ADOPT from AGT, fold into Leash/Sentinel) and cost controls (§12.5).

---

## 14. Enterprise Concerns

The error paths between the happy-path arrows.

- **14.1 Secrets & credentials** — the agent never holds long-lived network credentials; the proxy holds them and injects only for approved destinations (capability separation, §7.3). Scoped, short-lived, clear blast radius. Secrets redacted before leaving or being logged. `[OPEN D1]` exact backend (Vault / cloud KMS / minimal sealed store).
- **14.2 Audit / compliance** — event sourcing: every action + every Manager decision is an immutable appended event (the audit log *is* the event log). Signed receipts (Ed25519), hash-chained, tamper-evident, verifiable offline. One mechanism = compliance evidence + deterministic replay + the dashboard feed. Compliance mapping (EU AI Act, HIPAA, SOC2, NIST, OWASP) ADOPT from AGT — high-leverage for THOR's liable-enterprise buyers.
- **14.3 Recovery & resumability** — container dies → execution state (Kind A) persists outside it → new container reloads + resumes. Manager restarts → replay the event log. Merge half-applies → Gitea's PR transaction is the unit; failed merge leaves branch intact + room alive. `[OPEN D2]` persistence store (Manager DB vs per-room volume).
- **14.4 Failure modes** — leash down → fail-closed deny; Manager down → rooms can't act, replay on restart; container crash → disposable, reload state; agent hangs → room timeout → marked failed; host power loss → control-plane replay + re-provision; out-of-capacity (free tier) → queue or burst to paid; merge conflict → returned as fix task, never force-merged; egress to non-allowlisted host → blocked + logged.
- **14.5 Concurrency limits** — per-host room cap (resource-driven; free box ≈ 2–4). `[OPEN D3]` scheduling when over capacity (queue/burst/reject).
- **14.6 Observability** — per-room logs/status streamed read-only; metrics (per-room token spend, latency percentiles, allow/deny counts, health). `[OPEN D4]` stack (Prometheus + OTel conventional).
- **14.7 CI/CD coexistence** — THOR gates *before* the PR enters the customer's pipeline; doesn't replace it. Native via Gitea Actions; existing GitHub/GitLab pipelines integrate at the PR boundary.
- **14.8 Security threats** — kill-switch (max-severity response), MCP Security Gateway (tool-poisoning, typosquatting, hidden instructions), Shadow-AI discovery (rogue unregistered agents — folds into the Sentinel). ADOPT from AGT.
- **14.9 Enterprise access** `[OPEN D6]` — SAML SSO, RBAC/namespaces, K8s autoscaling runners, enhanced audit; map to Gitea-enterprise + K8s-native vs THOR-native.

---

## 15. Build Order — The Bootstrap Fix `[LOCKED]`

### 15.1 The bootstrap rule (P7 as process)
**During THOR's own construction, governance is OFF.** Claude (and any agent) builds THOR as ordinary software, no THOR-fence on the building. Governance switches on only once it's a complete, external, frozen system — then it governs *future* production work, never its own birth. Builder and governor as the same entity at the same moment caused the original bloat and self-reverts.

### 15.2 The sequence
1. **Pillar 1 — Wall** (module 1). Build first. Prove one cook does real work in a real sealed container and produces a clean branch + manifest. **Stub the gate as "always approve."** Net-new; nothing stands without it.
2. **Pillar 2 — Governance** (modules 2–5, 14, 7–9). Replace the stub with the real Manager + adopted AGT leash/sentinel/audit/identity (behind adapters). Port-and-clean the development-governance moat (module 14). Prove allow/deny pre-action, fail-closed, across >1 agent type.
3. **Pillar 3 — PM** (modules 6, 15) + SDLC stages (10–13). Extend the dashboard to N rooms; wire Gitea; the typed stages.
4. **Pillar 4 — Mobile** (module 16) + Self-Audit (17).

### 15.3 Why this order
1 is net-new and load-bearing. 2–4 largely re-house proven assets onto 1. **Extract the doctrine, reimplement the structure clean** (the OpenHands V0→V1 discipline) — not lift-and-shift the 6,000-line watchdog.

---

## 16. Competitive Reality & The Re-Scope `[LOCKED — strategic]`

By mid-2026 nearly every *individual* pillar of THOR exists in open source, often more mature than a small team will match. **This is validation, not threat** — independent serious teams (incl. Microsoft) converging on the same patterns proves the architecture is correct. The patterns are the wheel; THOR's value is the vehicle.

**The two halves exist separately; nobody joined them:** Bernstein = orchestration (ungoverned, human-absent); AGT = governance (agent-*safety*, not software-development correctness/honesty). **THOR is the fusion** + the human accountability + honesty-verification both omit.

**Four concrete differentiators:** (1) software-development governance, not just agent-safety; (2) human accountability as the design center (HCD) against an industry racing to remove the human; (3) legible refusal for non-technical operators; (4) the fusion itself.

**The re-scope:** ADOPT AGT (governance substrate) + Gitea (git/PR/CI) + Docker (isolation). STUDY Bernstein (build own orchestration) + Intent + OpenHands. BUILD only the moat: development-governance engine, SDLC stages, PM surface, legible refusal, mobile bridge. A dramatically smaller, focused build — energy only on the unoccupied seam.

---

## 17. Adoption Decisions — What We Take, Reject, Build `[LOCKED]`

- **ADOPT (behind THOR-owned adapters, Strangler-ready):** AGT — leash (Agent OS), sentinel (SRE/Runtime), audit (Merkle/Hypervisor), identity (Mesh), MCP security gateway, shadow-AI discovery, compliance mapping, kill-switch. Gitea — git/PR/CI. Docker — isolation. *AGT is MIT (commercial OK); it's "Public Preview" so it may have breaking changes — hence the adapter, so churn touches one file.*
- **STUDY (build own):** Bernstein (deterministic scheduler, cost controls, agent catalogs — PolyForm-Noncommercial, study-only). Intent (living-spec / context-engine — commercial/macOS). OpenHands (room/agent-server REST patterns — MIT but brings its own agent).
- **BUILD (the moat, never adopted):** development-governance engine (8-probe/divergence/contract), SDLC stages, PM surface, legible refusal, mobile bridge.
- **REJECT (with reason):** per-agent trust scoring (THOR corrects per-action, doesn't statistically distrust); privilege rings (THOR's agents are short-lived/disposable — scope-per-task already is the useful "ring").
- **RE-HOMED:** the scoring concept moves from agents to the *system* (meta-trust, §11.4).
- **Language (per Strangler strategy)** `[DIRECTION]`: AGT-facing adapters + governance engine in Python (full AGT stack native; Bernstein/OpenHands ecosystem). PM web UI in JS/TS. Mobile bridge stays JS. Languages swap per-piece behind adapters as pieces are owned over time.

---

## 18. Future Layers — Toras & Self-Evolution `[DEFER — north-star]`

- **Toras runtime checker (v2)** — the Self-Audit model evolves from observe→report into a programmable governance runtime that checks what a model *exposes/declares* against what the agent *actually did*, adjudicating truthfulness at the semantic level. **Corrects rather than cages** — guides the agent back to honesty instead of ever-tighter hard blocks (a conscience, not a prison). Cheaper because it catches drift early (correction-early beats rejection-late). The foundation must be built to *admit* this — clean seams, event-sourced truth, swappable models — without scoping it now.
- **Governed self-evolution** — THOR governing its own improvements: measure → hypothesize a prompt/routing change → sandbox-test → auto-apply safe (L0), block risky for human review (L3), SHA-lock critical files, circuit-breaker on regression. A natural extension of P9 into self-improvement. Deferred — most complex, least essential to v1.

---

## 19. Glossary

- **Cook / agent** — the coding AI inside a room (Claude Code, Cursor, Aider...). THOR is cook-agnostic.
- **Room** — a sealed Docker container; one cook, one git worktree, one task.
- **Room Manager / THOR Manager** — the mechanism that spawns/routes/destroys rooms and is the single governance brain.
- **CTO** — the intelligence that decides skills + scope per task; instructs the Manager.
- **Leash** — the cook-agnostic chokepoint (MCP proxy + egress proxy) every action is forced through, pre-action.
- **Wall** — the container's kernel-enforced isolation (Pillar 1 / module 1).
- **Gate / Verdict Gate** — the merge checkpoint where the 8-probe verdict runs and the human signs.
- **Manifest** — machine-readable proof of what a room did (files, tests, diffs, SHA); THOR reconstructs the truth from git.
- **Feature slice** — the single feature's spec handed to one room (`/task/feature.json`), never the catalog.
- **Sentinel** — meta-governance; checks THOR is alive/loaded/connected/untampered/still-catching; can halt.
- **Self-Audit Model** — zero-cost read-only Qwen-class inspector; reports + URGENT-escalates to the Sentinel; becomes Toras.
- **Control / Execution plane** — light always-on layer vs heavy bursty scalable rooms.
- **HCD** — Human Command Development; humans direct and remain accountable for AI-created work.
- **Bootstrap paradox** — governing THOR with THOR during its own construction; the original failure (P7 is the fix).

---

## 20. Open Decisions Register

| # | Decision | § | Notes |
|---|---|---|---|
| D1 | Secrets backend (Vault / KMS / sealed store) | 14.1 | Before Pillar 2 |
| D2 | Execution-state persistence (Manager DB vs per-room volume) | 14.3 | Affects recovery |
| D3 | Scheduling when over capacity (queue/burst/reject) | 14.5 | Affects cost |
| D4 | Metrics/telemetry stack (Prometheus+OTel likely) | 14.6 | Conventional |
| D5 | Optional post-merge governance hook | 9.6 | Future, not v1 |
| D6 | Enterprise features native vs delegated (Gitea/K8s) | 14.9 | SSO, RBAC, autoscaling |
| D7 | Structured governance for non-MCP agents | 7.2 | Egress covers safety; structured governance needs definition |

### Locked (do not reopen without cause)
One THOR Manager not one-per-room · Gitea owns `main` mechanically, THOR+human own the decision, peer handshake · Docker now / K8s later, same OCI image · zero-dollar control plane + light load, pay-per-concurrent-room, tokens dominant · cook-agnostic two-layer OS-enforced leash · build ungoverned first · three kinds of state · six-message task contract, read-only `/task/feature.json` · two-phase lifecycle (Genesis then multi-session) · 8-probe verdict + claim-vs-reality + panel-with-human-tiebreak · Hybrid Agentic SDLC typed stages · QA = structure + top-1% skills, bugs→DB, failures→CEO ticket · three signature points · Sentinel/Self-Audit/Human three health layers · system-trust not agent-trust · reject trust-scoring + rings · adopt-behind-adapters (Strangler) · CTO→Manager→Cook provisioning.

---

*End of THOR Enterprise Bible v2.0. Consolidated, internally consistent. Close the Open Decisions, then derive per-module PRDs in build order (Wall first).*
