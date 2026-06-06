# THOR Module 11 — The Self-Audit Model (Zero-Cost Qwen Inspector)

**Module PRD + FRD.** Read alongside the Bible (§11.2 the Self-Audit Model, §11.4 system-trust-not-agent-trust, §18 Toras as the v2 evolution, P9), the System Design & Flow doc (§5.4 health/SelfAudit sequences, §10 who-writes-what), and Module 10 (the Sentinel, which it escalates to).

> Saved from `THOR-Module11-SelfAudit-PRD.pdf` (v1.0) on 2026-06-06, transcribed faithfully. Build to this PRD; flag drift (Rule 9).

- **Module:** 11 — The Self-Audit Model · **Pillar:** 2 (Governance — the understanding layer of health) · **Kind:** BUILD (a small local-model service; the precursor to the Toras runtime checker)
- **Build order:** Eleventh — after the Sentinel; the two form the health stack.
- **One-line purpose:** Run a cheap, always-on, read-only local model that continuously asks "is THOR doing its job correctly?" — writing reports, audits, and the system meta-trust score to the database at near-zero cost, and escalating anything severe to the Sentinel.
- **Version:** 1.0

---

## 1. Overview
Where the Sentinel (M10) asks "are you alive?", the Self-Audit Model asks "are you doing your job correctly?" — it brings **understanding** to health-watching without bringing **cost**. The Sentinel is mechanical reflexes (binary, can halt); the Self-Audit Model is the continuous, intelligent observer that reads what actually happened and reasons about whether the system is performing properly. With the Human (judgment), they are the three health layers.

Defining properties (Bible §11.2): a small, cheap, always-on local model (Qwen class) in its own container; **zero token cost** (self-hosted — marginal cost is compute already paid for); **read-only** (inspects everything, changes nothing); **output → the database** (reports, findings, meta-trust score; queryable, never agent memory); **reports + escalates, never enforces directly** (flags normally; raises URGENT to the Sentinel, which decides whether to halt — a cheap, fallible model must never hold a stop button).

It is the **v1 of Toras** (Bible §18): the zero-cost observer that observes and reports grows, in v2, into a runtime checker that observes, understands, and corrects. It is also where the **system meta-trust score** lives (Bible §11.4): THOR scores the *system's* reliability, not individual agents.

## 2. Sub-modules
- **11.1 Inspector Loop** — the always-on read-only loop: reads the EventLog, room states, verdicts, outcomes, and assesses whether the system is behaving correctly.
- **11.2 Local Model Host** — runs the small model (Qwen class) in its own container; prompting + inference at zero token cost.
- **11.3 Report Generator** — structured reports (what happened, what looks wrong, patterns over time) → DB.
- **11.4 Meta-Trust Scorer** — system reliability score from component failure / required-output-miss rates (system-trust, not agent-trust) → DB.
- **11.5 Anomaly Detector** — flags correctness drift, recurring failures, suspicious patterns the mechanical Sentinel wouldn't catch.
- **11.6 URGENT Escalator** — for clear/severe findings, raises URGENT to the Sentinel (which decides). The only path by which this observer influences enforcement.
- **11.7 Retro & Benchmark Runner** — run retrospectives + periodically the golden benchmark suite, cheaply, over existing data.
- **11.8 Read-Only Guard** — enforces read-only access; it writes only its own report/score tables, never code/state/rules/EventLog.

## 3. Functional Requirements (FR)
- **FR-1** Run a small, self-hosted local model (Qwen class) in its own container, continuously and always-on.
- **FR-2** Incur zero token cost (self-hosted; marginal cost = compute already paid for); do not consume the frontier-model budget.
- **FR-3** Be READ-ONLY: inspect everything, change nothing in code/state/rules/EventLog; write only its own report/score tables.
- **FR-4** Continuously assess whether the system is doing its job correctly (not merely whether it's alive — that's the Sentinel's job).
- **FR-5** Write structured reports + findings to the DB; findings live in the DB, never agent memory.
- **FR-6** Compute the system meta-trust score from system-reliability signals (system-trust, NOT agent-trust).
- **FR-7** Report normally and be able to raise URGENT to the Sentinel for severe findings; SHALL NOT halt or enforce directly.
- **FR-8** URGENT escalations are advisory to the Sentinel, which decides whether to halt; a Self-Audit false-positive SHALL NOT by itself halt the system.
- **FR-9** Detect anomalies/correctness-drift requiring understanding (recurring failures, suspicious patterns).
- **FR-10** Generate run retrospectives + run a golden benchmark suite periodically — cheaply, over existing data.
- **FR-11** NOT be on the critical path: the system functions if the Self-Audit Model is down; its absence is noted by the Sentinel.
- **FR-12** Its findings are surfaced on the PM Surface (M8) — the correctness assessment + meta-trust score.
- **FR-13** Architected as the v1 of Toras: clean seams so observe→report can later become observe→understand→correct (v2) without re-architecting.
- **FR-14** Itself watched by the Sentinel (its liveness/responsiveness probed like any component) — not exempt from P9.
- **FR-15** Its model + prompts are improvable without changing its read-only, advisory, zero-cost character.
- **FR-16** Bound its own resource use so continuous inspection never starves the rooms (the paying work) of compute.

## 4. Technical Requirements
- **Model:** a small, self-hostable model (Qwen-coder / Qwen-general) run locally (Ollama or a lightweight inference server) in its own container.
- **Cost:** zero token cost; only compute, bounded so it never competes with rooms (FR-16).
- **Language:** Python service (`:7150`) wrapping the model host; read-only DB + EventLog access.
- **Access:** READ the EventLog, room states, verdicts, outcomes; WRITE only its own report/score tables — enforced by the Read-Only Guard + DB permissions (it physically cannot write elsewhere).
- **Inspection cadence:** continuous loop + event-triggered; not a heavy batch job.
- **Meta-trust:** a reliability score from system-level signals (required-output misses, component failures, verdict escalations) → DB → Dashboard.
- **Escalation:** POST URGENT to the Sentinel (`:7140`) for severe findings; otherwise write to the DB.
- **Toras-ready seams:** the inspection interface (read → assess → emit) is designed so a future Toras runtime plugs in deeper without changing the surrounding architecture.
- **Not on critical path:** the system's correctness does not depend on this model running.

## 5. The Logic
- **5.1 Understanding without cost** — the expensive models are the cooks (building code). Observing/reporting/auditing don't need a frontier model; a small local model handles "read this run's data and tell me what looks wrong." Self-hosted, it runs continuously at essentially no marginal cost. Separate the understanding (cheap, local, always-on) from the doing (expensive, frontier, per-task).
- **5.2 The complement to the Sentinel** — Sentinel = mechanical, binary, can halt ("is the leash responding? did the canary fire?"). Self-Audit = intelligent, continuous, read-only, reports ("are auth features failing QA suspiciously often? is the divergence rate climbing?"). One is reflexes; the other is watching eyes.
- **5.3 Reports + escalation, never enforcement (the safety boundary)** — the cheap model NEVER halts directly. A small model is cheap precisely because it's less reliable; giving it a stop button would be an unpredictable judge with enforcement power. Instead it reports + escalates URGENT to the Sentinel (the reliable enforcer). A false positive costs at most a Sentinel evaluation, never a wrongful halt. Pure upside.
- **5.4 The system meta-trust score** — THOR rejects scoring agents (inherently inconsistent). Instead it scores the *system's* reliability: how often the machinery fails to produce required output, how often verdicts escalate, how often components fail. A system should be consistent, so its failure rate is meaningful. Score the thing that should be reliable.
- **5.5 Read-only is the trust guarantee** — like the Project Checker, its trustworthiness is being unable to change anything. Read access to observe everything; write only to its own tables — enforced by DB permissions, so it physically cannot alter code/state/rules/EventLog. Broad eyes, no hands.
- **5.6 Cheap reports, retros, benchmarks** — generated by the cheap local model over data THOR already has (the EventLog), not new frontier runs. Continuous self-measurement at near-zero cost.
- **5.7 The v1 of Toras** — today observe→report; in v2, the same slot evolves into observe→understand→correct (semantic claim-vs-reality checking, correction proposals). Building with clean seams now means v2 is an evolution in place, not a rebuild.
- **5.8 Not a dependency** — the system does not depend on this model. If it's down, rooms build, the Leash governs, the Engine verdicts, the Sentinel enforces — only observability degrades (and the Sentinel notes its absence).

## 6. API Strategy
### 6.1 Endpoints the Self-Audit Model EXPOSES (`:7150`)
```
GET  /selfaudit/reports?range -> { reports:[ {timestamp, scope, findings[], assessment} ] }
GET  /selfaudit/meta_trust    -> { score, trend, contributing_signals[] }   # system-trust
GET  /selfaudit/anomalies     -> { anomalies:[ {pattern, severity, first_seen, occurrences} ] }
GET  /selfaudit/retro?run_id  -> { retrospective }
POST /selfaudit/benchmark/run -> { benchmark_results }   # cheap, over existing data
GET  /health                  -> { alive, responsive, model_loaded }   # probed by the Sentinel
```
### 6.2 Endpoints the Self-Audit Model CONSUMES (READ-ONLY)
- → ThorManager `:7100` GET `/audit/feed` (READ the EventLog)
- → ThorManager `:7100` GET `/state/summary` (READ rooms, feature states, verdicts)
- → GovernanceEngine READ verdict + divergence history
- → [ThorDB] READ outcomes; WRITE only its own report/score tables
- → Sentinel `:7140` POST `/sentinel/urgent { finding }` (escalate severe; Sentinel decides halt)
### 6.3 The discipline
The model READS everything and WRITES only its own reports/scores. It influences enforcement only by escalating URGENT to the Sentinel — never by acting. DB permissions enforce that it physically cannot write to code/state/rules/EventLog (FR-3). It is not on the critical path (FR-11).

## 7. Diagrams (described)
- **Figure 1** — The three health layers: Sentinel (reflexes — alive? can halt) | Self-Audit Model (eyes — correct? reports + escalates) | Human (judgment). The cheap model brings understanding without cost or enforcement power.
- **Figure 2** — Read-only, advisory: the model reads everything (EventLog, states, verdicts) but writes only its own reports + meta-trust score, and influences enforcement only by escalating URGENT to the Sentinel — broad eyes, no hands. DB permissions physically prevent writing to code/state/rules/EventLog.
- **Figure 3** — The v1 of Toras: today observe→report (cheap, read-only); v2 evolves the same slot into observe→understand→correct (semantic runtime, correcting drift early) — an evolution in place, not a rebuild.

## 8. Flows
- **8.1 Continuous inspection** — the Inspector Loop reads the EventLog + states; the model assesses correctness; the Report Generator writes findings; the Meta-Trust Scorer updates the score; the PM Surface shows the assessment + score (zero token cost throughout).
- **8.2 Anomaly → URGENT escalation** — the Anomaly Detector notices auth features failing QA at a suspicious rate / a climbing divergence rate; for a severe finding, the URGENT Escalator POSTs to the Sentinel; the Sentinel evaluates (halt if confirmed, else note). The cheap model did not halt — it escalated.
- **8.3 Cheap retro + benchmark** — after a run, the Retro Runner generates a retrospective from existing EventLog data (no frontier calls); periodically the benchmark suite runs cheaply; results → DB → Dashboard.
- **8.4 Self-Audit is down** — the container crashes; the Sentinel's liveness probe notes it; the system keeps running (rooms build, Leash governs, Engine verdicts, Sentinel enforces) — only observability degrades, with an alarm.
- **8.5 False positive** — the model flags something benign; it escalated URGENT (worst case) → the Sentinel evaluates and declines to halt → notes it. Cost: one Sentinel evaluation. No wrongful halt.

## 9. Use Cases / User Stories (story points)
- **US-1 (13)** a cheap always-on local model continuously assesses whether THOR is working correctly at zero token cost.
- **US-2 (8)** the cheap model reports + escalates but never halts directly (the safety boundary).
- **US-3 (8)** the operator sees a system meta-trust score (system-reliability, not agent-scoring).
- **US-4 (8)** read-only and physically cannot change anything (the trust guarantee).
- **US-5 (8)** detects correctness drift + recurring patterns the mechanical Sentinel can't.
- **US-6 (5)** retros + benchmarks generated cheaply over existing data.
- **US-7 (5)** the system runs fine if the Self-Audit is down (safely off the critical path).
- **US-8 (5)** the Sentinel receives its URGENT escalations and decides whether to halt.
- **US-9 (5)** findings live in the DB (queryable data), not agent memory.
- **US-10 (5)** architected as the v1 of Toras — v2 is an evolution in place, not a rebuild.
- **US-11 (3)** the Sentinel watches the Self-Audit's liveness too (P9).

**Total: ~73 points for Module 11.**

## 10. Error & Edge Cases
| Case | Trigger | Handling |
|---|---|---|
| Self-Audit down | container crash | Sentinel notes it; system keeps running (not on critical path); alarm that observability degraded |
| Cheap-model false positive | model error | Worst case = one URGENT → Sentinel evaluates, declines halt; no wrongful stop |
| Model tries to write outside its tables | bug/compromise | DB permissions deny; read-only guard blocks; physically can't alter code/state/rules/log |
| Inspection starves rooms of compute | resource contention | Bounded resource use (FR-16); rooms have priority |
| Model hallucinates a finding | small-model limitation | Findings are advisory; humans/Sentinel evaluate; never auto-acted-on |
| Meta-trust score misleading | bad signal weighting | Advisory + trend-based; refined over time; never an automatic gate |
| URGENT flood | many escalations | Sentinel rate-limits/evaluates; deduplicates; the cheap model can't force action |
| Benchmark run costs add up | frequent runs | Runs over existing data (no frontier calls); scheduled; near-zero cost |
| Model version drift | model update | Versioned; reports tagged with model version; quality monitored |
| Reads stale EventLog | lag | Observational; lateness degrades freshness of insight, not correctness of the system |
| Sentinel down when escalating | dependency gap | Finding still written to DB; surfaced to operator; escalation retried when Sentinel returns |
| Confused with the Sentinel's role | design ambiguity | Clear boundary: Sentinel = alive/halt; Self-Audit = correct/report |

## 11. Easy vs Difficult Parts
- **Easy:** running a small local model in a container; reading the EventLog + writing report/score rows; read-only enforcement via DB permissions.
- **Moderate:** the meta-trust scoring model (which signals, weighted how); anomaly/pattern detection; cheap retros + benchmarks.
- **Difficult / real risk:** (1) **Useful findings, not noise** — making the small model's assessments genuinely useful (catch real drift, not flag everything). (2) **Escalation calibration** — deciding what's "severe enough" to escalate URGENT without flooding the Sentinel. (3) **Toras-ready seams without over-engineering** — anticipating v2 just enough to avoid a rebuild, not so much that v1 is bloated.

## 12. Technical Difficulties
- **D1 — Finding usefulness.** Focus prompts on specific correctness questions (failure-rate anomalies, divergence trends, escalation patterns), not open-ended "anything wrong?"; tune over time; measure precision; suppress low-confidence noise.
- **D2 — Escalation threshold.** Severity scoring on findings; only high-severity, high-confidence findings escalate URGENT; everything else is a DB report; the Sentinel evaluates before acting.
- **D3 — Zero-cost discipline.** A genuinely small model; bounded resource caps so rooms are never starved; event-triggered + a gentle continuous loop; runs over existing data, never new frontier calls.
- **D4 — Read-only enforcement.** DB-level permissions (write only its own tables); the read-only guard; no API path to writes elsewhere; verified by negative tests.
- **D5 — Toras evolution path.** Define the inspection interface (read → assess → emit) cleanly now; keep observe→report separable from the future understand→correct logic; document the seam so Toras plugs in where the assessment happens.

## 13. What Needs To Be Built (checklist)
- [ ] Local Model Host (Qwen-class in a container; bounded compute)
- [ ] Inspector Loop (continuous + event-triggered read-only assessment)
- [ ] Report Generator (structured findings → DB)
- [ ] Meta-Trust Scorer (system-reliability score → DB) — system-trust, not agent-trust
- [ ] Anomaly Detector (correctness drift, recurring patterns)
- [ ] URGENT Escalator (severe findings → Sentinel; advisory only)
- [ ] Retro & Benchmark Runner (cheap, over existing data)
- [ ] Read-Only Guard + DB permissions (physically can't write elsewhere)
- [ ] PM Surface integration (show assessment + meta-trust score)
- [ ] Sentinel liveness integration (the observer is itself watched)
- [ ] Toras-ready inspection interface (clean observe→assess→emit seam)
- [ ] Finding-precision evaluation harness (measure usefulness, tune)

## 14. Dependencies & Sequencing
**Depends on:** Module 10 (Sentinel) — receives the Self-Audit's URGENT escalations and decides halts; watches its liveness (the two form the health stack). Module 3 (Manager) + EventLog — the read source. A self-hostable small model (Qwen) + an inference host.

**Blocks / depended on by:** Module 8 (PM Surface) — shows the meta-trust score + assessment. Toras (v2, deferred) — this is its v1 slot. Nothing on the critical build path depends on it (it's an observer, FR-11) — which is the point.

**Build-order note:** Build after the Sentinel (so escalation has a target) and once there's an EventLog of real activity to inspect. Deliberately off the critical path. **Milestone:** the model runs continuously at zero token cost, writes a correctness report + meta-trust score to the DB, escalates a seeded severe anomaly to the Sentinel (which decides), and a negative test confirms it cannot write anything but its own tables.

## 15. Test / Acceptance Criteria (evidence-based)
- **AC-1** The model runs continuously and incurs zero token cost (no frontier-model API calls; only local inference).
- **AC-2** It writes correctness reports + a meta-trust score to the DB.
- **AC-3** It is read-only: an attempt to write to code/state/rules/EventLog is denied (DB permissions block it).
- **AC-4** A seeded severe anomaly is escalated URGENT to the Sentinel; the cheap model does NOT halt directly.
- **AC-5** The system continues to function with the Self-Audit Model down; its absence is alarmed.
- **AC-6** The meta-trust score reflects system reliability (system-level signals), not per-agent scoring.
- **AC-7** A false-positive escalation results in at most a Sentinel evaluation, never a wrongful halt.
- **AC-8** Retrospectives + benchmarks run over existing data without frontier-model calls.
- **AC-9** The Sentinel probes the Self-Audit model's liveness (it is itself watched).
- **AC-10** Findings live in the DB, not agent memory (queryable, persistent across restarts).
- **AC-11** Inspection respects resource bounds and never starves rooms of compute.
- **AC-12** The inspection interface has a clean observe→assess→emit seam documented for the Toras v2 evolution.

**Headline milestone:** AC-1 + AC-3 + AC-4 together — a continuous, zero-cost, read-only inspector that catches a real correctness anomaly and escalates it to the Sentinel without ever being able to act on the system itself. That proves the "understanding eyes" layer: intelligent self-audit with none of the cost or the risk of letting a cheap model enforce.

---

*End of THOR Module 11 — The Self-Audit Model PRD v1.0. The three health layers (Sentinel + Self-Audit + Human) are now fully specified. Next module: 12 — the foundation adapters (Audit Trail / Identity / Gitea), the adopted-behind-adapters substrate that the moat sits on.*
