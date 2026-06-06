# THOR Module 10 — The Sentinel (Meta-Governance / Self-Verifying Governance)

**Module PRD + FRD.** Read alongside the Bible (P9 Self-Verifying Governance, §11.1 the Sentinel, §11.4 system-trust-not-agent-trust, §20 grounding in the original watchdog), the System Design & Flow doc (§5.4 health sequences, §8 error/recovery), and all prior modules — the Sentinel watches every one of them.

> Saved from `THOR-Module10-Sentinel-PRD.pdf` (v1.0) on 2026-06-06, transcribed faithfully. Build to this PRD; flag drift (Rule 9).

- **Module:** 10 — The Sentinel · **Pillar:** 2 (Governance — meta-governance) · **Kind:** ADOPT (AGT Agent SRE + Runtime, behind the THOR adapter) + BUILD (the canary + THOR-specific efficacy checks)
- **Build order:** Tenth — after the system it watches exists; it verifies all of it.
- **One-line purpose:** Continuously prove that THOR itself is alive, loaded, connected, untampered, and *still actually catching* — and fail-closed + halt the moment it cannot — so the governor is never silently broken.
- **Version:** 1.0

---

## 1. Overview
Every other module governs the agents. The Sentinel governs THOR. It answers the question the separated architecture forces: **who governs the governor?** If the Leash silently dies, agents run free while the operator believes they're caged. A governance system that fails silently is worse than none, because it gives false confidence.

It is the embodiment of **P9 (Self-Verifying Governance):** every component must continuously prove it is alive, loaded, connected, and doing its job — and fail-closed + alarm when it cannot. The Sentinel is the mechanical, deterministic **reflexes** of the three-layer health model: Sentinel (can halt) → Self-Audit Qwen (understanding, reports + escalates, M17) → Human.

Grounded in what the original THOR proved works (Bible §20): synthetic monitoring (F086 — "responsive, not just process-alive"), a file-integrity crawler (CRAWLER_ALARM), boot self-tests, and the canary (F030). The original failure was only that all this lived tangled in one 6,000-line file. This module makes it a clean, first-class layer. It adopts AGT's SRE substrate (SLOs, circuit breakers, chaos) + Runtime (kill-switch) behind the THOR adapter, and builds the THOR-specific efficacy checks — above all the **canary**, the elegant base case that stops the infinite regress.

## 2. Sub-modules
- **10.1 Liveness Prober** — probes every component for alive AND responsive (answers correctly in time), not just "process up."
- **10.2 Loadedness Verifier** — confirms each stage's declared skills/brain actually loaded before work began.
- **10.3 Connectivity Checker** — verifies the REST channels between components are open and flowing.
- **10.4 Integrity Crawler** — hashes THOR's governance code/rules at boot and re-checks for drift/tampering (CRAWLER_ALARM).
- **10.5 Canary Engine** — fires planted must-fail actions on a schedule; if a canary ever passes, the detector is broken. The proof the detectors still detect.
- **10.6 Halt Authority** — the kill-switch / fail-closed trigger; halts the affected scope (a room, or the whole system). (ADOPT AGT Runtime.)
- **10.7 Boot Self-Test** — on startup, verifies the Sentinel's own integrity + that all components answer, before THOR accepts work.
- **10.8 Reconciler** — reconciles the room registry against actual containers; reaps orphans; Shadow-AI discovery.
- **10.9 Alarm & Escalation** — raises alarms (Dashboard, operator, EventLog); receives URGENT escalations from the Self-Audit model (M17) and decides whether to halt.

## 3. Functional Requirements (FR)
- **FR-1** Continuously verify every governance + execution component is alive AND responsive (not merely process-up). (P9)
- **FR-2** Verify each stage's declared skills/brain actually loaded before that stage did governed work.
- **FR-3** Verify connectivity of the REST channels between components.
- **FR-4** Hash THOR's governance code/rules at boot and continuously detect tampering/drift.
- **FR-5** Run canaries: planted must-fail actions that MUST be denied/caught; if a canary passes, alarm + halt the affected scope.
- **FR-6** On a confirmed critical failure (dead leash, passing canary, tampered rule, unwritable EventLog), fail-closed: halt the affected scope. (P2, P9)
- **FR-7** Run a boot self-test verifying own integrity + all components answering, BEFORE THOR accepts work; a failed boot self-test prevents startup.
- **FR-8** Reconcile the registry against actual containers, reaping orphans and discovering shadow rooms/agents.
- **FR-9** Receive URGENT escalations from the Self-Audit model (M17) and decide whether to halt (it reports; the Sentinel enforces).
- **FR-10** Raise alarms to Dashboard + operator + EventLog on any failure, distinguishing severity (degraded vs critical).
- **FR-11** Silent success is forbidden: always distinguish "passed because it was checked" from "passed because the checker was dead."
- **FR-12** The Sentinel is subject to the discipline it enforces; its own liveness is provable via the canary base case.
- **FR-13** The canary heartbeat is designed so its *absence* is itself an alarm condition (no infinite "who watches the watcher" regress).
- **FR-14** Adopt AGT's SRE + Runtime via the THOR adapter; THOR-specific efficacy (canaries) is built.
- **FR-15** Support maintenance mode: a deliberate, human-authorized window to silence specific alarms during chaos tests — without ever silencing real-failure detection outside that window.
- **FR-16** Compute and expose the system meta-trust signal inputs (component failure rates) — system-trust, not agent-trust.
- **FR-17** Halt with the minimum necessary scope (a single failed room, not the whole system, when the failure is local) — fail-closed but proportionate.

## 4. Technical Requirements
- **Language:** Python; runs as a service on `:7140`.
- **Adopted substrate:** AGT Agent SRE (SLO, circuit breakers, chaos) + Agent Runtime (kill-switch) — via the THOR AGT adapter (the only AGT import).
- **Probing:** active HTTP `/health` probes on a schedule (F086 — "responsive, not just up"); plus event-driven failure detection.
- **Integrity:** cryptographic hashing of governance code/rules at boot; periodic re-hash; compare to baseline.
- **Canary:** planted must-fail conditions (an action that must be denied; a deliberately-incomplete feature that must verdict not_done — shared with Module 6); scheduled firing; pass = broken detector.
- **Halt:** the kill-switch path (AGT Runtime) + the Manager's fail-closed; proportionate scoping (room vs system).
- **Reconcile:** periodic registry-vs-actual reconciliation (Docker/K8s); orphan reaping; shadow-agent discovery.
- **Self-liveness:** the canary base case — a heartbeat whose absence an external watch/operator treats as the alarm; no additional watcher needed.

## 5. The Logic
- **5.1 Who governs the governor** — the danger is the worst kind: not a loud crash, but a silent failure that leaves the operator falsely confident. The Sentinel's job is to make every such failure loud and fail-closed.
- **5.2 Alive AND responsive** — a process can be running but hung (F086). A naive check passes a hung leash. The Liveness Prober checks responsiveness: a correct, timely answer to an active probe. Closes the "looks alive, actually dead" gap.
- **5.3 The five things it verifies** — liveness, loadedness, connectivity, integrity, efficacy (the canary). Each maps to a class of silent failure; together they make "is THOR actually working?" a continuously-answered question.
- **5.4 The canary: efficacy + regress-stopper (two roles)** — **efficacy:** a planted condition that must trigger a guard; if it ever passes, the guard is broken → alarm + halt. **The regress-stopper:** a heartbeat whose silence is itself the alarm. One detector whose absence means failure is the elegant base case that ends the infinite regress.
- **5.5 Fail-closed, proportionately** — on a confirmed critical failure, halt with the minimum necessary scope. A hung room → halt that room. A tampered global rule / dead leash → halt broadly. Fail-closed, but proportionate.
- **5.6 Separation makes this safe** — a monolith hides internal failures; a separated system where every piece self-reports turns each failure into a visible, catchable signal. Separation + self-verification is *more* governable than a monolith.
- **5.7 The Sentinel governs itself too** — a boot self-test before THOR accepts work; regression tests on its own checks; its own liveness provable via the canary base case. It is the one component allowed to be the bottom of the trust stack, because its failure mode (the canary going silent) is itself detectable.
- **5.8 Maintenance mode** — a human-authorized window that silences specific alarms during an intentional chaos test, without ever silencing real-failure detection outside that window. Lets THOR prove its meta-governance works without crying wolf.

## 6. API Strategy
### 6.1 Endpoints the Sentinel EXPOSES (`:7140`)
```
GET  /sentinel/status     -> { components:{name:{alive,responsive,loaded,connected}}, integrity:ok, canaries:[...], overall:"healthy|degraded|halt" }
GET  /sentinel/canaries   -> { canaries:[ {name, expected, last_fired, result, healthy} ] }
POST /sentinel/halt       { scope:"room:{id}"|"system", reason } -> { halted:scope }   # internal, on confirmed failure
POST /sentinel/maintenance { window, alarms[], human_authority } -> { mode:"on", until }  # human-authorized
GET  /sentinel/reconcile  -> { registry_vs_actual, orphans[], shadow_agents[] }
POST /sentinel/urgent     { finding } -> { decision:"halt"|"note" }   # from Self-Audit (M17)
GET  /health              -> { self_test:ok, heartbeat }   # the canary base case
```
### 6.2 Endpoints the Sentinel CONSUMES
- → every component GET `/health` (liveness + responsiveness probes)
- → AGT adapter SRE (SLO/circuit-breaker); Runtime (kill-switch) — via the adapter
- → Leash/Engine fire canary actions (must be denied / must verdict not_done)
- → Docker/K8s API list actual containers (reconcile vs registry)
- → ThorManager POST `/events/append` (alarms); POST `/rooms/{id}/kill` (halt a room)
- → Integrity baseline (hashes of governance code/rules)
### 6.3 The discipline
The Sentinel READS health and FIRES canaries; on confirmed failure it HALTS (proportionately) and ALARMS. It does no agent work, computes no verdicts, runs no LLMs — mechanical and deterministic (the reflexes). The understanding-level inspection is the Self-Audit model (M17), which escalates to the Sentinel.

## 7. Diagrams (described)
- **Figure 1** — The five verifications: liveness (alive AND responsive), loadedness, connectivity, integrity, efficacy (canary) — each guarding a class of silent failure; any failure → fail-closed + alarm (silent success forbidden).
- **Figure 2** — The canary's double duty: efficacy (a must-fail action that proves the detector still detects) and the regress-stopper (a heartbeat whose silence is itself the alarm) — ending "who watches the watcher" at an elegant base case.
- **Figure 3** — Fail-closed, proportionately: a local fault halts one room; a systemic fault (dead leash, tampered rule) halts broadly — stop rather than run unguarded, but no bigger than necessary.

## 8. Flows
- **8.1 Boot self-test** — own integrity OK? all components answering? rules-hash baseline recorded? Pass → THOR accepts work. Fail → startup blocked + alarm.
- **8.2 Continuous health** — probe every component (alive AND responsive) every N seconds; unresponsive → degraded alarm; if critical (leash) → fail-closed halt of the affected scope.
- **8.3 Canary fires** — fire a must-fail action; Leash denies it → healthy; Leash allows it → broken → alarm + halt + operator told the detector failed.
- **8.4 Integrity tamper** — re-hash governance rules; mismatch → CRAWLER_ALARM → halt → operator re-verifies before resuming.
- **8.5 Self-Audit escalation** — the Self-Audit model POSTs URGENT; the Sentinel evaluates and decides halt (confirmed) or note + alarm. The cheap model escalates; the Sentinel enforces.
- **8.6 Maintenance-mode chaos test** — operator authorizes a window; specific alarms silenced for that window only; THOR breaks a component; the Sentinel detects it and would-have-paged (logged); window closes; full alarming resumes.
- **8.7 Reconcile + shadow discovery** — list actual containers vs registry; orphans reaped; shadows alarmed as unregistered agents.

## 9. Use Cases / User Stories (story points)
- **US-1 (13)** THOR continuously proves it is alive/loaded/connected/untampered/still-catching — fails closed when it can't. *(The core P9 value.)*
- **US-2 (13)** a canary fires must-fail actions and alarms if a detector ever lets one through. *(The efficacy moat.)*
- **US-3 (8)** "who watches the watcher" ends at a base case — a heartbeat whose silence is the alarm.
- **US-4 (8)** components checked for alive AND responsive — a hung-but-running component is caught.
- **US-5 (8)** on a confirmed critical failure, halt rather than run unguarded — proportionately.
- **US-6 (5)** governance code/rules hash-checked for tampering.
- **US-7 (5)** a stage's skills verified loaded before it does governed work.
- **US-8 (5)** receive URGENT escalations from the Self-Audit model and decide whether to halt.
- **US-9 (5)** a boot self-test must pass before THOR accepts work.
- **US-10 (5)** reconcile registry vs actual + discover shadow agents.
- **US-11 (5)** run maintenance-mode chaos tests to prove the governor pages correctly, without crying wolf.
- **US-12 (3)** see THOR's health status — never asked for blind trust.

**Total: ~83 points for Module 10.**

## 10. Error & Edge Cases
| Case | Trigger | Handling |
|---|---|---|
| Component hung (up but unresponsive) | infinite loop / deadlock | Responsiveness probe catches it; degraded → halt if critical |
| Canary passes (should fail) | detector broken | Alarm + halt that detector's scope; operator told the guard failed |
| Rule tampering | hash mismatch | CRAWLER_ALARM + halt; re-verify before resuming |
| Skill didn't load | bundle error | Loadedness fails; stage fail-closes |
| Sentinel itself crashes | the watcher dies | Canary heartbeat goes silent → that absence is the alarm (base case) |
| EventLog unwritable | store down | Manager fail-closes; Sentinel alarms; halt governed actions |
| False alarm (transient blip) | network flicker | Severity tiers + brief re-probe before halting |
| Over-broad halt | halting everything for a local fault | Proportionate scoping (FR-17) |
| Maintenance mode left on | forgot to close | Required expiry; auto-closes; never silences outside |
| Shadow agent found | rogue/unregistered room | Alarm; quarantine/terminate; investigate |
| Self-Audit URGENT is wrong | cheap-model false positive | Sentinel evaluates before halting; can note instead (the model doesn't halt directly) |
| Reconcile race | container mid-create | Tolerate in-flight states; re-check before reaping |

## 11. Easy vs Difficult Parts
- **Easy:** HTTP health probing; hash-based integrity crawling; registry-vs-actual reconciliation + orphan reaping.
- **Moderate:** alive-AND-responsive probes; proportionate halt scoping; maintenance mode (silence safely, with expiry).
- **Difficult / real risk:** (1) **The canary done right** — planted must-fail conditions that genuinely exercise the detectors, where a pass reliably means "broken detector." (2) **The regress base case** — the "silence is the alarm" heartbeat must be airtight (bottom of the trust stack). (3) **Avoiding alarm fatigue while never missing a real failure** — calibrating severity tiers and halt thresholds.

## 12. Technical Difficulties
- **D1 — Canary design.** Canaries mirror real governed actions (a real out-of-scope write that must be denied; the deliberately-incomplete feature shared with M6); a pass is a hard failure of that detector; canaries are themselves tested.
- **D2 — The base-case heartbeat.** A heartbeat whose absence is monitored by a dead-simple external check; intentionally minimal and robust — its only job is "am I still firing?"
- **D3 — Alive vs responsive.** Active probes requiring a correct, timely response (F086); a component that doesn't answer correctly in time is unhealthy regardless of process state.
- **D4 — Proportionate fail-closed.** Classify failures local (one room) vs systemic (leash/rules/log); halt the smallest scope that contains the failure.
- **D5 — Alarm calibration.** Severity tiers (degraded vs critical); brief re-probe before halting on transients; critical failures halt immediately; tune with real data.

## 13. What Needs To Be Built (checklist)
- [ ] Liveness Prober (alive AND responsive; AGT SRE-backed)
- [ ] Loadedness Verifier (skills/brain loaded before governed work)
- [ ] Connectivity Checker (REST channels open/flowing)
- [ ] Integrity Crawler (hash governance code/rules; detect tamper)
- [ ] Canary Engine (planted must-fail actions; pass = broken detector) — the efficacy core
- [ ] Halt Authority (AGT kill-switch + Manager fail-closed; proportionate scoping)
- [ ] Boot Self-Test (own integrity + components answering; block startup on fail)
- [ ] Reconciler (registry vs actual; orphan reap; shadow-agent discovery)
- [ ] Alarm & Escalation (Dashboard/operator/EventLog; severity tiers; receive Self-Audit URGENT)
- [ ] Canary base-case heartbeat (silence = alarm; the regress-stopper)
- [ ] Maintenance mode (human-authorized, expiring, scoped alarm silencing)
- [ ] Chaos-test harness (prove the Sentinel pages correctly — the F088 pattern)

## 14. Dependencies & Sequencing
**Depends on:** all components it watches (Modules 1–9) must exist. AGT adapter — for SRE + Runtime (kill-switch). Module 3 (Manager) — for alarms (events), the room registry (reconcile), and fail-closed coordination.

**Blocks / depended on by:** Module 17 (Self-Audit) — escalates URGENT to the Sentinel; the two form the health stack. The trustworthiness of the whole system — without the Sentinel, every clean separation is a potential silent-failure point.

**Build-order note:** Build after the system it watches exists. Grounded in the original watchdog's proven mechanisms (synthetic monitoring, crawler, boot self-test, canary), now as a clean layer. **Milestone:** a deliberately-killed leash is detected and the affected scope fail-closes; a canary forced to pass triggers an alarm + halt; and the Sentinel's own simulated death is caught by the silent-heartbeat base case.

## 15. Test / Acceptance Criteria (evidence-based)
- **AC-1** A killed (or hung) leash is detected as unresponsive and the affected scope fail-closes.
- **AC-2** A canary forced to pass (broken detector) triggers an alarm + halt of that detector's scope.
- **AC-3** A hung-but-running component (alive, not responsive) is detected as unhealthy.
- **AC-4** Tampering with a governance rule (hash mismatch) triggers CRAWLER_ALARM + halt.
- **AC-5** A stage whose declared skill failed to load is caught and fail-closes before doing governed work.
- **AC-6** A failed boot self-test prevents THOR from accepting work.
- **AC-7** The Sentinel's own simulated death is detected via the silent-heartbeat base case.
- **AC-8** A confirmed local fault halts only the affected room; a systemic fault halts broadly (proportionate, both ways).
- **AC-9** A Self-Audit URGENT escalation is evaluated by the Sentinel, which halts or notes (the cheap model never halts directly).
- **AC-10** A shadow (unregistered) container is discovered and alarmed; an orphan is reaped.
- **AC-11** Maintenance mode silences only the specified alarms for a bounded window, auto-closes, and never silences real-failure detection outside it.
- **AC-12** A chaos test confirms the Sentinel pages correctly for each failure class.

**Headline milestone:** AC-1 + AC-2 + AC-7 together — a dead governor is caught and fail-closed, a broken detector is caught by a passing canary, and the Sentinel's own death is caught by its silent heartbeat. That proves the meta-governance is real: THOR cannot be silently broken, all the way down to the watcher itself.

---

*End of THOR Module 10 — The Sentinel PRD v1.0. The reflexes of the three-layer health model are specified. Next module: 11 — The Self-Audit Model (the zero-cost Qwen inspector: continuous read-only correctness inspection that reports + URGENT-escalates to the Sentinel, and becomes Toras in v2).*
