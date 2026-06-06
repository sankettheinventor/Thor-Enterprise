# THOR Module 7 — The SDLC Stages (Genesis / Project Checker / Build / QA)

**Module PRD + FRD.** Read alongside the Bible (§10 the Hybrid Agentic SDLC, §10.2 stage anatomy, §10.3 the stages, §10.4 QA mandate, the three signature points), the System Design & Flow doc (§4 the phased flow), and Modules 1–6.

> Saved from `THOR-Module7-SDLC-PRD.pdf` (v1.0) on 2026-06-06, transcribed faithfully. Build to this PRD; flag drift (Rule 9).

- **Module:** 7 — The SDLC Stages · **Pillar:** spans 1–3 (the typed stage-containers are the connective tissue of the lifecycle) · **Kind:** BUILD — the moat surface (the stages + their skill-composition; runs inside adopted Wall + Leash)
- **Build order:** Seventh — after the orchestration core (1–5) and the verdict engine (6); the stages produce the work the engine judges.
- **One-line purpose:** Turn THOR from a "room system" into a governed software lifecycle — typed stage-containers (Plan / Check / Build / Test), each with its own brain and skills, moving work through Genesis → Build → QA → Verdict with a human signature at each gate.
- **Version:** 1.0

---

## 1. Overview
Where THOR stops being "containers running agents" and becomes a **Hybrid Agentic SDLC** (Bible §10): containers are not generic boxes differing only by task text — they are **typed lifecycle stages**, each with its own brain, skills, and mandate. Docker provides the stages (nodes); THOR is the lifecycle moving work through them and governing every transition (edges). LangGraph-shaped: nodes = stage-containers, edges = governed transitions, state = the feature.

Four stage types, all on the same universal anatomy, all inside the Wall (M1) under the Leash (M2), all judged by the Engine (M6):
- **Genesis (Plan)** — once, at first setup: interview the human, draft the vision + feature catalog. Human approves (Signature 1).
- **Project Checker (Plan, existing codebases)** — read-only full-codebase analysis that shows the human the truth about their code (the install "aha moment"). Changes nothing.
- **Build (Dev)** — many, parallel: build one feature, skills composed by task-type.
- **QA (Test)** — fresh per feature: an *independent* adversarial tester that did not write the code. Bugs → DB, failures → CEO ticket (Signature 2).

The defining strength (Bible §10.4): each stage is **structure + swappable skills**, so any stage improves by *adding a skill* — isolated, composable, non-breaking. The opposite of the original THOR's fNNN sediment.

## 2. Sub-modules
- **7.1 Stage Anatomy Framework** — the shared 5-part skeleton every stage implements: Input → Brain+Skills → Mandate → Edge-check → Output.
- **7.2 Skill Composer** — given `task_type` + `capability_tags`, composes the brain: floor skills (always-on) + specialty skills (per capability). Instructs the Wall which skills to load.
- **7.3 Genesis Stage** — planning brain (PM + CTO + UX-strategy); interviews the human (Dashboard relay); produces vision.md, state, metrics, outcomes, the feature catalog (acceptance criteria + capability tags).
- **7.4 Project Checker Stage** — read-only codebase analysis; mounts the codebase read-only; emits findings (bad code, attack surface, dead code, patch-hacks, unwired code) to the DB; changes nothing.
- **7.5 Build Stage** — building brain composed by task-type; builds one feature within scope under the live Leash; produces a branch + claim_done.
- **7.6 QA Stage** — independent tester brain composed by task-type; verifies planned criteria + reads the actual code to write NEW tests + tries to break it; bugs → DB, failures → CEO ticket.
- **7.7 Stage Transition Controller** — governs the edges: what's checked before work leaves a stage, what passes on, what loops back. Enforces SDLC order (Genesis-first; Build → QA → Verdict; QA-fail → ticket → Build).
- **7.8 Findings & Ticket Bridge** — routes QA findings as structured bugs to the DB (via the Manager) and QA failures as CEO cards that, when signed (Signature 2), become re-work tickets fed back to the Scheduler.

## 3. Functional Requirements (FR)
- **FR-1** Every stage implements the universal anatomy, so stages are uniform and new stages slot in without breaking.
- **FR-2** Each stage runs inside the Wall (M1) under the Leash (M2); no stage runs ungoverned.
- **FR-3** The Skill Composer composes each stage's brain from floor skills (always-on) + specialty skills (selected by capability tags).
- **FR-4** Genesis runs once, produces the vision + catalog (each feature with acceptance criteria + capability tags), and SHALL NOT proceed to any Build until the human approves the plan (Signature 1).
- **FR-5** Project Checker mounts the codebase READ-ONLY, analyzes, emits findings, and changes NOTHING (the trust guarantee).
- **FR-6** Build builds exactly one feature within scope, governed live by the Leash, producing a branch + claim_done.
- **FR-7** QA is a fresh container per feature, run by an agent that did NOT write the code (independence), destroyed after.
- **FR-8** QA (a) verifies the planned acceptance criteria, (b) reads the actual code and writes NEW tests for implementation-introduced edge cases, (c) attempts to break the feature.
- **FR-9** QA findings are emitted as structured bugs to the DB via the Manager — never held in agent memory.
- **FR-10** QA failures raise a CEO card; only on human authorization (Signature 2) does a re-work ticket loop back to Build.
- **FR-11** The Stage Transition Controller enforces SDLC order: Genesis-first; Build → QA → Verdict; QA-fail → ticket → Build; no skipping the verdict gate.
- **FR-12** Work SHALL NOT reach the merge/verdict (M6) directly from Build; it passes through QA first.
- **FR-13** Each stage receives only its appropriate input (Genesis: project intent; Checker: read-only codebase; Build: one feature-slice; QA: the build branch + planned criteria + read access).
- **FR-14** New stage types are addable by implementing the anatomy + a skill set, WITHOUT modifying existing stages.
- **FR-15** The three signature points are enforced at the stage edges: Sig 1 (Genesis→Build), Sig 2 (QA-fail→ticket), Sig 3 (Verdict→merge, owned by Manager/Engine).
- **FR-16** Floor skills (security, code-review, testing-discipline, error-handling) load in every Build and QA stage regardless of task-type.
- **FR-17** Specialty skill composition is governed: tags proposed at Genesis, ratified by the human in plan approval, composed deterministically (the agent does not pick its own skills).
- **FR-18** Mid-build discovery of a needed capability raises a CEO card (not silently add skills); on approval the tag is added and the stage recomposed.

## 4. Technical Requirements
- **Language:** Python (stage orchestration); the cook is any agent (cook-agnostic).
- **Stage = config + skills, not separate images:** all stages run the same Wall OCI image (M1 FR-15); `task_type` + composed skills select behavior.
- **Skill format:** loadable bundles (prompt/context/tooling) the Skill Composer assembles and the Wall loads. Floor + specialty.
- **Genesis interaction:** the planning agent converses with the human via a Dashboard relay.
- **Project Checker:** read-only mount (Wall enforces); analysis tooling in the checker skill bundle; findings to the DB.
- **QA independence:** a fresh container, different agent instance, that did not produce the code; gets branch + criteria + read access, not the build agent's context.
- **Transitions:** event-driven via the Manager. No stage self-promotes.
- **Skill catalog source:** floor fixed; specialty from a registry (Bernstein-style catalog).

## 5. The Logic
- **5.1 Typed stages dissolve the Docker-vs-THOR confusion** — Docker provides the stage; THOR is the lifecycle moving a feature through stages and governing each transition. A Build container and a QA container are the same Wall image with different skills and mandates. Stages are nodes, THOR is the graph.
- **5.2 The universal anatomy** — every stage implements Input, Brain+Skills, Mandate, Edge-check, Output. Uniformity = extensibility (FR-14): a new stage is the anatomy + a skill set slotted into the graph; no existing stage changes.
- **5.3 Skill composition: floor + specialty** — floor (security, code-review, testing-discipline, error-handling) loads in every Build/QA always; the dangerous-to-miss competencies are floors, so the scariest selection failure is eliminated. Specialty is composed per feature from capability tags (low cost if wrong, because floor protects the critical cases). Governed: tags proposed at Genesis, ratified by the human, composed deterministically; the agent never picks its own skills (P1).
- **5.4 Genesis: the plan comes first, the human signs it** — the planning brain interviews the human and drafts the catalog; the human approves the plan (Signature 1) before any Build runs. The agent proposes the roadmap; the human disposes.
- **5.5 Project Checker: the read-only aha moment** — for an existing codebase, THOR's first act is to honestly tell the human what's there in a read-only container that provably changes nothing. Findings feed the Genesis catalog.
- **5.6 QA: the independent adversary (the second witness)** — a *different agent, different brain, fresh container, that did not write the code* — adversarial by design, no ego in passing. (a) verifies planned criteria, (b) reads the actual code and writes NEW tests for edge cases the implementation introduced, (c) tries to break it. "Is it really done?" now has three independent witnesses: the agent's claim (untrusted), the mechanical 8-probe verdict (M6), and the adversarial QA agent.
- **5.7 Transitions are governed edges, not self-promotion** — the Stage Transition Controller governs every edge: claim_done → QA; QA-pass → verdict; QA-fail → ticket card; verdict + Sig 3 → merge. Work cannot skip QA to reach the verdict (FR-12), cannot reach Build before the plan is signed (FR-4).

## 6. API Strategy
Stages don't expose their own service ports — they run as rooms (Wall) briefed via the Task Handoff Contract (M5). This module's APIs are the stage orchestration surface + the transition events.
### 6.1 Stage orchestration (control-plane, consumed by Scheduler/Manager)
```
POST /stage/compose_skills { task_type, capability_tags[] } -> { floor[], specialty[], bundle_ref }
POST /stage/genesis/start  { project_intent }             -> { genesis_room_id }
POST /stage/checker/start  { repo (read-only) }           -> { checker_room_id }
POST /stage/transition     { feature_id, from, to, evidence } -> { allowed:bool, next }
GET  /stage/state          { feature_id } -> { current_stage, history[] }
```
### 6.2 Transition events (via the Manager's event bus)
```
claim_done(feature_id)        -> Transition Controller provisions QA
qa.pass(feature_id)           -> trigger verdict (Module 6)
qa.fail(feature_id, bugs[])   -> raise CEO ticket card (Signature 2)
ticket.authorized(feature_id) -> Scheduler re-dispatches to Build
verdict.done + Signature 3    -> Manager directs merge
```
### 6.3 Findings & tickets
```
QA      -> Manager POST /bugs/append { feature_id, severity, description, source:"qa" }  (-> DB)
QA-fail -> Manager raises card -> human Signature 2 -> ticket -> Scheduler
Checker -> Manager POST /findings/append { repo, findings[] }  (-> DB, shown on Dashboard)
```
### 6.4 The discipline
Stages are briefed and judged through the existing seams: Task Handoff Contract (M5) for task in / result out; the Leash (M2) for per-action governance; the Verdict Engine (M6) for "done." This module adds stage typing, skill composition, and transition governance — it does not invent a new room interface.

## 7. Diagrams (described)
- **Figure 1** — The Hybrid Agentic SDLC pipeline: Genesis (or Project Checker) → Build → QA → Verdict → Merge, with the three human signature points at the gates and the QA-fail loop-back.
- **Figure 2** — The universal stage anatomy: Input → Brain+Skills → Mandate → Edge-check → Output. One skeleton for all stages; new stages slot in without breaking existing ones.
- **Figure 3** — Skill composition: floor skills (always-on, the critical baseline) + specialty skills (selected by capability tags, ratified by the human) — dangerous-to-miss competencies are floors, so selection errors are never catastrophic.

## 8. Flows
- **8.1 Fresh project (Genesis)** — Genesis interviews the human; drafts vision + catalog → DB; Manager raises the plan-approval card; human signs (Sig 1) → only now can Build be scheduled; Genesis room destroyed.
- **8.2 Existing project (Project Checker)** — read-only mount; analyze; findings → DB; Dashboard shows the findings (aha moment); changed nothing; findings inform the Genesis catalog.
- **8.3 Build a feature** — Scheduler dispatches; Skill Composer composes floor + specialty; Manager provisions a Build room; assign_task delivers the slice; cook builds under the Leash; produces a branch; emits claim_done.
- **8.4 QA the feature** — claim_done → Transition Controller provisions a fresh QA room; QA verifies criteria + reads code + writes new tests + tries to break it; pass → verdict; fail → bugs to DB + CEO ticket card.
- **8.5 QA-fail loop-back** — QA finds a real failure → CEO card; operator authorizes the re-work ticket (Sig 2); Scheduler re-dispatches to Build (done deps not re-run); QA room destroyed.
- **8.6 Adding a new stage** — a UX-audit stage is needed post-merge; implement the anatomy + a UX-audit skill set; register it in the transition graph; no existing stage changes (proves FR-14).

## 9. Use Cases / User Stories (story points)
- **US-1 (13)** typed SDLC stages with governed transitions — THOR is a lifecycle, not just rooms. *(The core reframe.)*
- **US-2 (8)** "is it done?" has three independent witnesses (claim, mechanical verdict, adversarial QA).
- **US-3 (8)** structure + swappable skills; new stages slot in without breaking — improves without destabilizing.
- **US-4 (8)** floor skills load in every Build/QA — dangerous-to-miss competencies never absent.
- **US-5 (8)** the operator approves the plan before any build runs (Sig 1, HCD at planning).
- **US-6 (8)** on install THOR shows the truth about the existing codebase, having changed nothing (the aha moment).
- **US-7 (8)** QA is a fresh independent agent that didn't write the code — no bias toward passing.
- **US-8 (5)** QA failures become tickets only when the operator authorizes them (Sig 2; bounded loop).
- **US-9 (5)** QA findings live in the DB not agent memory — system stays light, findings are queryable.
- **US-10 (5)** work cannot skip QA to reach the verdict.
- **US-11 (5)** specialty skills proposed at Genesis, ratified by the human, composed deterministically.
- **US-12 (3)** a mid-build capability gap raises a card rather than a silent skill add.

**Total: ~84 points for Module 7.**

## 10. Error & Edge Cases
| Case | Trigger | Handling |
|---|---|---|
| Build reaches verdict skipping QA | order violation | Transition Controller refuses; QA mandatory (FR-12) |
| QA agent = build agent | independence broken | Provisioner ensures a fresh, different instance |
| QA writes to code under test | should be read-only-ish | QA gets read access + its own test space; production code change is out of scope |
| Floor skill fails to load | bundle error | Sentinel detects (loadedness, P9); stage fail-closes |
| Capability tag missing for a real need | planning gap | Mid-build CEO card; human adds tag; recompose (FR-18) |
| Checker tries to modify codebase | impossible by mount | Read-only mount denies; flagged critical if attempted |
| Genesis never approved | operator absent | No Build scheduled; the system waits (no auto-proceed past Sig 1) |
| QA-fail ticket never authorized | operator absent | Feature held; card pending; no silent loop-back |
| Infinite Build↔QA loop | feature keeps failing | Bounded: after N cycles surface to operator |
| New stage breaks an old one | bad integration | Anatomy + transition-graph isolation prevents it; integration test per new stage |
| Genesis produces a vague catalog | weak criteria | The verdict engine struggles → escalate; human reviews the plan |
| Skill registry unavailable | specialty missing | Floor still loads (critical safety holds); specialty degraded → flag |

## 11. Easy vs Difficult Parts
- **Easy:** the stage anatomy framework; Genesis as a guided planning conversation; routing QA findings to the DB.
- **Moderate:** skill composition (floor + specialty assembly + loading); transition governance; Project Checker analysis tooling.
- **Difficult / real risk:** (1) **QA writing genuinely good NEW tests** — the QA stage's value is reading real code to find edge cases the plan didn't foresee; depends on top-1% QA skills. (2) **Skill composition that actually improves output** — more skills ≠ better; avoiding context bloat is a tuning problem. (3) **Bounding the Build↔QA loop without cutting real fixes** — calibrating "N cycles then escalate."

## 12. Technical Difficulties
- **D1 — QA test quality.** Invest in top-1% QA skill bundles (edge-case generation, adversarial thinking, contract-mapping); QA reads the actual diff; measure catch rate and improve.
- **D2 — Skill composition value.** Floor minimal and essential; specialty targeted by tags; measure output quality per composition; prune skills that don't help.
- **D3 — Independence enforcement.** Fresh container, fresh agent instance, no build-agent context — only the branch + criteria + read access; verified by the provisioner.
- **D4 — Extensibility without regression.** Anatomy + transition-graph isolation; each new stage ships with an integration test asserting existing flows are unaffected.
- **D5 — Genesis catalog quality.** Genesis skills push for testable criteria; the human reviews the plan (Sig 1); poor criteria surface as verdict escalations.

## 13. What Needs To Be Built (checklist)
- [ ] Stage Anatomy Framework (the shared 5-part skeleton)
- [ ] Skill Composer (floor + specialty; tag-driven; deterministic; loads into the cook)
- [ ] Genesis stage (planning brain; human interview; catalog production)
- [ ] Project Checker stage (read-only analysis; findings → DB)
- [ ] Build stage (task-type skills; one feature; under the Leash)
- [ ] QA stage (independent; verify + write-new-tests + break; bugs → DB)
- [ ] Stage Transition Controller (governed edges; SDLC order enforcement)
- [ ] Findings & Ticket Bridge (bugs → DB; QA-fail → card → Sig 2 → ticket → Scheduler)
- [ ] Floor skill bundles (security, code-review, testing-discipline, error-handling)
- [ ] Specialty skill registry (capability-tag → skill bundle; swappable)
- [ ] New-stage integration harness (proves extensibility without regression)
- [ ] The three-signature-point enforcement at the edges

## 14. Dependencies & Sequencing
**Depends on:** Modules 1–5 (stages run as rooms, governed, coordinated, scheduled, briefed/judged — hard deps). Module 6 (Verdict Engine — QA-pass triggers the verdict). The catalog (Kind C) — Genesis produces it; Build/QA consume slices.

**Blocks / depended on by:** The PM Surface (M15) — surfaces stage states, the catalog, cards/signatures, Checker findings. The end-to-end product experience — the SDLC stages are what the operator watches and signs.

**Build-order note:** Build after the orchestration core + verdict engine. Start with Build + QA (the core loop), then Genesis, then Project Checker. **Milestone:** a feature flows Genesis(approved) → Build → QA(independent, finds a real edge case) → Verdict(M6) → merge(Sig 3), with the QA-fail loop-back working via a human-signed ticket.

## 15. Test / Acceptance Criteria (evidence-based)
- **AC-1** A feature flows through all stages in order; an attempt to reach the verdict without passing QA is refused.
- **AC-2** The QA agent is a fresh, different instance from the Build agent for the same feature (independence).
- **AC-3** QA reads the actual code and produces at least one NEW test not in the planned criteria, catching an implementation-specific edge case.
- **AC-4** QA findings appear as structured bugs in the DB, not in agent memory.
- **AC-5** No Build stage runs before the plan is signed (Signature 1).
- **AC-6** A QA failure does not loop back to Build until the operator authorizes a ticket (Signature 2).
- **AC-7** The Project Checker changes nothing in the codebase (read-only) yet produces findings to the DB.
- **AC-8** Floor skills are present in every Build and QA stage regardless of task-type.
- **AC-9** A new stage type can be added without modifying any existing stage, and existing flows still pass.
- **AC-10** A mid-build capability gap raises a CEO card rather than the agent silently adding a skill.
- **AC-11** The Build↔QA loop is bounded: after N failed cycles the feature surfaces to the operator.
- **AC-12** All three signature points are enforced at their edges (1: plan→build, 2: qa-fail→ticket, 3: verdict→merge).

**Headline milestone:** AC-2 + AC-3 together — an independent QA agent that did not write the code reads the actual implementation and catches an edge case the plan never specified. That proves the third witness adds real value beyond the mechanical verdict.

---

*End of THOR Module 7 — The SDLC Stages PRD v1.0. The moat surface (the lifecycle that produces and tests the work) is now specified. Next module: 8 — The PM Surface (kanban, approval cards, audit view, the three signature points — the human direction layer the operator actually touches).*
