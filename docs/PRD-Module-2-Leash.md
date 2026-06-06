# THOR Module 2 — The Leash (Cook-Agnostic Pre-Action Interception)

**Module PRD + FRD.** Part of the THOR Enterprise PRD suite. Read alongside the Bible (P1–P9, §7 the leash), the System Design & Flow doc (§3 ports, §5.2 the governed-action sequence, §7.1 the AGT adapter), and Module 1 (the Wall, which builds the door the Leash lives in).

> Saved from the user-provided `THOR-Module2-Leash-PRD.pdf` (v1.0) on 2026-06-06, transcribed faithfully so it survives independently of chat context. Build to this PRD; flag drift (Rule 9).

- **Module:** 2 — The Leash · **Pillar:** 2 (Governance) · **Kind:** ADOPT (Microsoft AGT, behind a THOR-owned adapter) + thin BUILD (the in-room proxy + the adapter)
- **Build order:** Second — after the Wall; replaces the build-order stub gate with real pre-action governance.
- **One-line purpose:** Force every model call and tool call an agent makes through a single point that judges it *before* it executes, allow/deny/escalate against rules the agent cannot touch — for *any* agent, fail-closed.
- **Version:** 1.0

---

## 1. Overview
The Leash is THOR's live behavioural governor. Where the Wall guarantees the agent *cannot escape*, the Leash governs *what the agent does* while inside — in real time, before each action, not after.

It embodies three principles at once: **P3** (pre-action interception — judge before execute), **P4** (the chokepoint is the one door the Wall enforces), and **P2** (fail-closed — if the governor can't decide, deny). It is also what makes THOR **cook-agnostic**: it doesn't hook a specific agent's internals; it sits on the two paths *every* agent must use — calls to a model and calls to tools.

The Leash is **NOT the brain**. It is the *enforcement mechanism*; the *judgment* (scope, contracts, manifest classification, the development-governance models) lives in Module 14 and the THOR Manager. The Leash asks "may this action proceed?" and enforces the answer. This separation (P8) keeps the Leash thin and governance evolvable.

**Adopt vs build:** the policy *engine* is Microsoft AGT's Agent OS (battle-tested, MIT, sub-millisecond, pre-action `ToolCallInterceptor`). THOR builds: (a) the in-room proxy that forces traffic to AGT, (b) the THOR-owned AGT adapter (Strangler-ready), and (c) the THOR policy *content* (YAML rules for scope/forbidden-patterns) — not the engine.

## 2. Sub-modules
- **2.1 In-Room Proxy** — runs inside the container on `:8001` (the Wall's one door). Every model/tool call hits it first. Does not decide; forwards the structured action to the AGT adapter and enforces the verdict (forward / block / hold).
- **2.2 MCP-Aware Inspector (Layer A)** — understands the structured tool-call protocol (MCP JSON-RPC): tool name, args, responses. Enables semantic policy ("writing to a forbidden path", "adding a dependency").
- **2.3 Egress Inspector (Layer B)** — inspects raw outbound traffic the structured layer can't see (raw HTTP, web fetches, DNS). Catches bypass attempts and exfiltration.
- **2.4 AGT Adapter** — the THOR-owned wrapper around Microsoft AGT. The **ONLY** component that imports AGT. Exposes THOR vocabulary (`check_action`, `record_decision`); translates to AGT; isolates THOR from AGT's preview-stage churn (Strangler-ready).
- **2.5 Policy Loader** — loads the frozen, per-room governance policy (Kind B) — scope, forbidden patterns, language lock — as AGT-format policy. Read-only to the cook; settable only host-side.
- **2.6 Credential Injector** — holds destination credentials (LLM API keys, Gitea tokens); injects them ONLY into approved, allowed outbound requests, never into the room. The other half of capability separation (P4).
- **2.7 Decision Recorder** — emits every allow/deny/escalate as a structured, signed event to the EventLog (via ThorManager). Denied calls are first-class governance facts.
- **2.8 Escalation Router** — for `critical`-classified actions, raises a CEO card via ThorManager and holds the action pending the human decision.

## 3. Functional Requirements (FR)
- **FR-1** Every model call and every tool call from the cook SHALL pass through the In-Room Proxy (`:8001`) before reaching any destination. (P3, P4)
- **FR-2** The Leash SHALL evaluate each action and return one of: `allow`, `deny`, `escalate` — before the action executes.
- **FR-3** On `allow`, the proxy SHALL forward the request to its real destination with credentials injected by the Credential Injector (never by the cook).
- **FR-4** On `deny`, the action SHALL NOT execute; the cook SHALL receive a structured reason in real time.
- **FR-5** On `escalate`, the action SHALL be held; a CEO card SHALL be raised; the action proceeds only on human approval, else is denied.
- **FR-6** If the AGT adapter / policy engine is unreachable or cannot decide, the Leash SHALL deny (fail-closed). (P2)
- **FR-7** The Leash SHALL be cook-agnostic: govern any agent by intercepting the model-call and tool-call paths, requiring no agent-specific code. (Cooks normalize via the Cook adapter.)
- **FR-8** Layer A (MCP-aware) SHALL inspect structured tool calls (name, args, result).
- **FR-9** Layer B (egress) SHALL inspect raw outbound traffic and block any not matching an allowed, inspected request.
- **FR-10** The per-room policy SHALL be loaded read-only and frozen at session 0; the cook SHALL NOT read its edit-controls or modify it. (P1)
- **FR-11** Every decision (allow/deny/escalate) SHALL be recorded as a signed event in the EventLog. (audit)
- **FR-12** The Credential Injector SHALL never place credentials inside the container; creds live only in the adapter, injected outbound per approved destination.
- **FR-13** The Leash SHALL classify actions by impact (non-critical / critical / denied) per the manifest-classification model (Module 14 logic), escalating critical ones.
- **FR-14** The AGT adapter SHALL be the only component importing AGT; all other THOR code SHALL call the adapter's THOR-vocabulary interface. (Strangler-ready)
- **FR-15** The Leash SHALL detect and block stack-drift actions: undeclared dependency adds, new-interpreter files, language changes (escalate to critical).
- **FR-16** The Leash SHALL operate at low latency (target sub-50ms per decision for common-pattern checks).
- **FR-17** The Leash SHALL support the MCP Security Gateway checks (tool-poisoning, typosquatting, hidden-instruction scanning) on tool definitions. (ADOPT from AGT)
- **FR-18** On a max-severity security finding (malicious tool/file, injection), the Leash SHALL trigger the kill-switch path (terminate the room) via ThorManager.

## 4. Technical Requirements
- **In-room proxy:** lightweight process bundled in the Wall image, listening on `:8001`; the only egress route (enforced by Module 1's Network Enforcer). Language: Python or a small Go/Rust binary — **[OPEN]** exact lang; must be tiny and fast.
- **Policy engine:** Microsoft AGT Agent OS (`pip install agent-governance-toolkit`), pre-action `ToolCallInterceptor` + `PolicyProviderInterface`. Policy formats: YAML (default), OPA Rego, Cedar.
- **AGT adapter:** Python (AGT full stack is Python-native). The single import boundary for AGT.
- **MCP inspection:** parse MCP JSON-RPC; for Claude Code, use AGT's native Claude Code governance plugin; for other cooks, the Cook adapter normalizes their tool protocol.
- **Egress inspection:** inline proxy on the room's network; TLS-terminating inspection for outbound; DNS routed through the proxy; IPv6 disabled (per Module 1 D1).
- **Credential store:** held in the adapter / control plane; **[OPEN D1]** backend (Vault / KMS / sealed store).
- **Latency budget:** common-pattern decisions sub-50ms; AGT advertises sub-ms eval — budget is mostly network round-trip room→adapter.
- **Identity:** decisions tied to the room's verified identity token (from Module 1's Identity Stamper).

## 5. The Logic
### 5.1 The interception path (per action)
1. Cook attempts an action (tool/model call). The Wall's one-door rule means the only place it can go is the In-Room Proxy (`:8001`).
2. The proxy classifies traffic: structured tool call → Layer A (MCP); raw network → Layer B (egress).
3. The proxy packages `{room_id, type, target, args, scope_ref}` and calls the AGT adapter (`:7160`) `POST /policy/check`.
4. The adapter translates to an AGT policy evaluation against the room's frozen policy (scope, forbidden patterns, classification).
5. AGT returns a decision; the adapter maps it to a `ThorVerdict {allow|deny|escalate, reason, classification}`.
6. The Decision Recorder appends a signed event.
7. The proxy enforces: `allow` → Credential Injector adds creds for the approved destination → forward → return result; `deny` → return `GovernanceDenied{reason}` (no execution); `escalate` → hold; Escalation Router raises a CEO card; on approval forward, on rejection deny.

### 5.2 Why this is cook-agnostic
The Leash never asks "which agent is this?" It only sees actions on the two universal paths. The Cook adapter normalizes different agents' tool protocols into the same structured action shape. Adding a new cook = a new Cook-adapter mapping, not new Leash logic.

### 5.3 The two layers, and why both are needed
Layer A (MCP) sees *meaning* ("write_file to /etc") but not raw HTTP a bypass might use. Layer B (egress) sees *bytes* (raw HTTP, DNS) but not workspace semantics. Neither alone suffices; together they close each other's blind spots. The Wall (Layer C) covers process/FS isolation beneath both.

### 5.4 Fail-closed as the default (P2)
If the adapter is down, AGT errors, the policy won't load, or inspection can't safely parse the action — the verdict is **deny**. The cook literally cannot act without a live, answering governor. Silence equals refusal. Failure mode is "nothing happens", never "everything is allowed".

### 5.5 The adapter as the Strangler seam
All AGT contact is through the adapter (FR-14). THOR calls `adapter.check_action(...)` and gets a `ThorVerdict` — never sees AGT types. When AGT changes its API (Public Preview), only the adapter changes. If AGT is replaced (THOR's own engine, or Toras v2), only the adapter is rewritten. The moat is THOR's; the substrate is swappable.

## 6. API Strategy
### 6.1 Endpoints the AGT Adapter EXPOSES (consumed by the In-Room Proxy + ThorManager)
```
POST /policy/check
  req: { room_id, action:{ type:"tool_call"|"model_call"|"egress", target, args, scope_ref }, identity_token }
  res: { decision:"allow"|"deny"|"escalate", reason, classification:"non_critical"|"critical"|"denied", decision_id }

POST /policy/load
  req: { room_id, policy:{ scope_files[], forbidden_patterns[], language_lock }, frozen_at }
  res: { room_id, loaded:true, policy_hash }

GET  /policy/health
  res: { agt_reachable:bool, policy_engine:bool, last_eval_ms }

POST /security/scan_tool        # MCP security gateway
  req: { tool_definition }
  res: { safe:bool, findings:[ {type:"poisoning"|"typosquat"|"hidden_instruction", detail} ] }
```
### 6.2 Endpoints the Leash CONSUMES
- → ThorManager (`:7100`) `POST /events/append` (record each decision, signed)
- → ThorManager (`:7100`) `POST /cards/raise` (escalate critical → CEO card)
- → ThorManager (`:7100`) `POST /rooms/{id}/kill` (max-severity security → kill-switch)
- → Credential store `get_credential(destination)` (inject creds outbound only)
- → ‹AGT Agent OS› `evaluate(policy, action)` (via the adapter, the only AGT import)

### 6.3 In-room proxy (`:8001`) — the cook's only exit
The cook does not call a THOR API; it attempts normal model/tool calls and the proxy transparently intercepts them. Denials surface to the cook as the tool/model call failing with a governance reason.

### 6.4 Port summary
| Component | Port | Role |
|---|---|---|
| In-Room Proxy | `:8001` (per room) | the one door; intercepts all egress |
| AGT Adapter | `:7160` (control plane) | policy check + AGT boundary |
| ThorManager | `:7100` | events, cards, kill-switch |

## 7. Diagrams (described)
- **Figure 1** — The two-layer chokepoint: Cook → In-Room Proxy `:8001` → Layer A (MCP, structured) **and** Layer B (egress, raw) → AGT adapter `:7160` (the only AGT import) against the frozen policy (Kind B); the Wall (Layer C) beneath as process/FS isolation.
- **Figure 2** — Per-action decision logic: action intercepted → classify + evaluate vs frozen policy → AGT verdict → `allow` (creds injected, forward) / `deny` (reason→cook, no exec) / `escalate` (CEO card, hold); every decision a signed event. Unreachable / cannot decide / timeout → **DENY (P2)**.
- **Figure 3** — The AGT adapter as the Strangler seam: THOR code speaks THOR vocabulary (`check_action`, `record_decision`, `is_healthy`) → `ThorVerdict` (never sees AGT types); the adapter is the only AGT import; AGT churn or replacement touches one file.

## 8. Flows
- **8.1 Happy path (allowed):** `write_file(src/login.js)` → Layer A parses → adapter→AGT: in scope, not forbidden → `allow, non_critical` → signed event → proxy executes write → success.
- **8.2 Denied (out-of-scope):** `write_file(infra/secrets.tf)` → not in scope → `deny, denied` → event recorded → cook gets `GovernanceDenied: path outside approved scope` → course-corrects in real time (P3, no reject-loop).
- **8.3 Escalated (dependency add):** add dep to package.json → Layer A flags manifest change → `critical` → `escalate` → CEO card → held → operator approves→forward / rejects→deny.
- **8.4 Fail-closed (adapter down):** any action → adapter connection fails → fail-closed `deny, governor_unavailable` → Sentinel alarming → rooms pause until restored.
- **8.5 Security (malicious tool):** tool def with hidden instruction → `POST /security/scan_tool` flags `hidden_instruction` → Leash triggers `POST /rooms/{id}/kill` → room terminated, quarantined, alarmed.

## 9. Use Cases / User Stories (story points)
- **US-1 (13)** Every agent action is judged before it executes — misbehaviour prevented, not just detected. (Core pre-action loop — highest value.)
- **US-2 (8)** Govern any coding agent without agent-specific code (cook-agnostic).
- **US-3 (8)** If the governor is unreachable the agent cannot act (fail-closed).
- **US-4 (5)** Denials reach the cook with a clear reason in real time.
- **US-5 (8)** AGT wrapped behind one adapter — churn/replacement touches one file (Strangler seam).
- **US-6 (5)** Critical actions (deps, language, protected files) escalate to a CEO card.
- **US-7 (8)** Raw-traffic bypass attempts caught by the egress layer.
- **US-8 (5)** Credentials never inside the room; injected only outbound.
- **US-9 (5)** Every decision a signed event (complete, tamper-evident trail).
- **US-10 (8)** Malicious tools/files trigger the kill-switch.
- **US-11 (5)** Per-room policy frozen and read-only to the cook.

**Total: ~78 points for Module 2.**

## 10. Error & Edge Cases
| Case | Trigger | Handling |
|---|---|---|
| Adapter unreachable | network / crash | Fail-closed deny; Sentinel alarm; rooms pause |
| AGT eval error | bad policy / AGT bug | Fail-closed deny; log; surface to operator |
| Policy won't load | malformed Kind B | Refuse to start the room (a room without policy is forbidden) |
| Unparseable action | novel tool protocol | Fail-closed deny (can't inspect safely → don't allow) |
| Latency spike | slow eval | Decision still required before execute; timeout → fail-closed deny |
| Cook floods actions | runaway loop | Rate-limit at the proxy; repeated denies → escalate / mark failed |
| Egress bypass attempt | raw socket / DNS | Layer B + Wall network rules drop it; logged as security event |
| Credential request, unapproved dest | exfil attempt | Injector refuses; no creds released; logged |
| Escalation never answered | operator absent | Action stays held; card persists; room waits (does NOT auto-allow) |
| MCP scan false positive | benign tool flagged | Operator reviews the card; tune policy; never auto-kill on a soft signal |
| Conflicting policies | overlapping rules | Deny-wins precedence; ambiguity → escalate to human |
| Decision event write fails | EventLog issue | Fail-closed: if we can't record it, we can't allow it (no unaudited actions) |

## 11. Easy vs Difficult Parts
- **Easy:** calling AGT's `govern()` / policy check; YAML policy content; recording decisions as events.
- **Moderate:** the AGT adapter abstraction (stable THOR vocabulary w/o leaking AGT types); escalation routing + holding pending human; classification wired to escalation.
- **Difficult / real risk:** (1) the in-room proxy intercepting **ALL** egress reliably (US-7) — any escaped path = a hole; cover structured, raw HTTP, DNS, IPv6; tight coupling with Module 1's network lock. (2) Cook-agnostic normalization (US-2) — uniform action shape across agents; grows per cook. (3) Latency without holes — sub-50ms without ever shortcutting to "allow" under load; fail-closed must hold even when slow.

## 12. Technical Difficulties
- **D1 — Total egress coverage.** One un-intercepted path = a hole. Proxy is the ONLY route (M1 enforces); Layer A + B cover structured + raw; DNS through proxy; IPv6 off; Sentinel canary fires must-deny actions continuously.
- **D2 — Cook-agnostic action normalization.** A Cook-adapter per agent maps its protocol to THOR's action shape; AGT's native Claude Code plugin for the primary cook; document a Cook-adapter contract.
- **D3 — AGT preview churn.** Adapter is the single import boundary (FR-14); pin AGT versions; adapter has its own test suite asserting the THOR vocabulary holds across upgrades.
- **D4 — Fail-closed under load.** The proxy's default branch is **deny**; timeouts route to deny; load-test asserts denies-under-pressure, not allows.
- **D5 — Credential isolation.** Creds never enter the room; injected only into approved outbound by the adapter; egress layer scans responses for accidental secret echo.

## 13. What Needs To Be Built (checklist)
- [ ] In-Room Proxy (`:8001`) — bundled in the Wall image; intercepts all egress
- [ ] Layer A — MCP-aware structured inspector
- [ ] Layer B — egress raw-traffic inspector (TLS-terminating, DNS-through-proxy)
- [ ] AGT Adapter (the single AGT import; THOR-vocabulary interface) + its test suite
- [ ] Policy Loader (Kind B → AGT policy format; frozen, read-only)
- [ ] Credential Injector (outbound-only, per-destination)
- [ ] Decision Recorder (signed events → EventLog)
- [ ] Escalation Router (critical → CEO card, hold-pending)
- [ ] Classification logic (non-critical/critical/denied) — shared with Module 14
- [ ] MCP Security Gateway integration (tool scan) — ADOPT from AGT
- [ ] Kill-switch trigger path (max-severity → ThorManager)
- [ ] Cook-adapter contract + Claude Code mapping (first cook)
- [ ] Adversarial test suite (denied-action canaries, egress-bypass attempts, fail-closed-under-load)

## 14. Dependencies & Sequencing
**Depends on:**
- **Module 1 (Wall)** — the Leash's in-room proxy lives on the door the Wall enforces; without the one-door network lock, the Leash can be bypassed. **Hard dependency.**
- **AGT** installed + the adapter built.
- **ThorManager** (events, cards, kill-switch) — can be partially **stubbed** for Module-2 isolated testing.
- **EventLog** — for recording decisions.

**Blocks:** Module 14 (Development-Governance Engine) leans on the Leash's classification + events. All SDLC build/qa stages run *governed*, i.e. with the Leash live.

**Build-order note:** This module replaces the build-order stub gate ("always approve") with real pre-action governance. **Milestone:** a cook in a Wall room is denied an out-of-scope action *before* it executes, the denial is a signed event, and a forbidden bypass attempt is dropped.

## 15. Test / Acceptance Criteria (evidence-based)
- **AC-1** A tool call to an out-of-scope path is denied *before* the write happens (verified: the file is never modified).
- **AC-2** The denial reaches the cook with a structured reason (verified by the cook's received error).
- **AC-3** Every decision (allow/deny/escalate) appears as a signed event in the EventLog (verified by reading the log, not the Leash's self-report).
- **AC-4** With the AGT adapter down, all actions are denied (fail-closed verified by negative test).
- **AC-5** A raw-HTTP bypass attempt (not via structured tools) is blocked by Layer B (verified by adversarial test).
- **AC-6** Credentials never appear inside the container (verified by inspecting room env/FS); approved outbound calls still succeed (creds injected).
- **AC-7** A dependency-add escalates to a CEO card and is held until decided (verified end-to-end).
- **AC-8** A second, different cook (not Claude Code) is governed by the same Leash via its Cook-adapter (verified — proves cook-agnostic).
- **AC-9** A malicious tool definition triggers the kill-switch and the room is terminated (verified).
- **AC-10** Under load (N actions/sec), no action is ever allowed without a recorded decision (verified: decisions == actions; no unaudited allows; timeouts → deny).
- **AC-11** The per-room policy cannot be modified from inside the room (verified by attempted edit failing).
- **AC-12** An AGT version bump does not break THOR: only the adapter's tests touch AGT; THOR-vocabulary callers are unchanged (verified by upgrade test).

**Headline milestone:** AC-1 + AC-4 + AC-5 together — a real out-of-scope or bypass action is stopped *before* it executes, and the system *denies* rather than allows when the governor is unavailable. That proves the leash governs and fails safe.

---

*End of THOR Module 2 — The Leash PRD v1.0. Next module: 3 — The THOR Manager (the single governance brain + room lifecycle authority that the Leash reports to and the Scheduler/CTO instruct).*
