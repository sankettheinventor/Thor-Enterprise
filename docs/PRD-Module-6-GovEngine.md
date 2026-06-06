# THOR Module 6 — The Development-Governance Engine (The Core Moat)

**Module PRD + FRD.** Read alongside the Bible (§8 governance models, §9 the authority & verdict model, the 8 probes, P5 evidence-based done, P6 human signature), the System Design & Flow doc (§5.3 claim→verdict→merge), and Modules 1–5.

> Saved from `THOR-Module6-GovEngine-PRD.pdf` (v1.0) on 2026-06-06, transcribed faithfully. Build to this PRD; flag drift (Rule 9).

- **Module:** 6 — The Development-Governance Engine · **Pillar:** 2 (Governance) · **Kind:** BUILD — THE MOAT (port the proven doctrine from the original THOR's done-check / skill-verifier / evidence-ledger, rebuilt clean; never adopted, because nothing external provides it)
- **Build order:** Sixth — after the orchestration core (1–5); replaces the build-order stub gate's "always approve" with real, un-fakeable judgment.
- **One-line purpose:** Decide whether a feature is *really* done — honestly and un-fakeably — by computing a verdict from reality (git, tests, audit, contract) rather than the agent's word, and catching the gap between what the agent claimed and what actually happened.
- **Version:** 1.0

---

## 1. Overview
The module that makes THOR THOR. Everything else is infrastructure that exists somewhere; this is the part nobody has: a governor of **software-development correctness and honesty**, not just agent safety. AGT stops an agent misusing a tool; this stops an agent shipping work that is incomplete, out-of-contract, or dishonestly claimed done.

It answers the question the industry admits it can't reliably answer — *"is this feature actually done?"* — the only trustworthy way: by **ignoring the agent's self-report and computing a verdict from ground truth.** The agent can *claim* done (Module 5); this engine *decides* done.

Three things no competitor combines: **(1) the 8-probe verdict** — "done" from 8 independent read-only probes against reality; all 8 must pass. **(2) Claim-vs-reality divergence** — compares what the agent claimed against what actually happened; the gap is a measurable honesty signal — the lie-detector. **(3) A panel that trusts nothing blindly** — consensus across independent mechanisms; conflict/uncertainty escalates to a human signature (P6). The embodiment of P5 and THOR's "conscience, not cage" character.

## 2. Sub-modules
- **6.1 Probe Runner** — executes the 8 probes (M1–M5 mechanical, R1–R3 review), each read-only. Collects pass/fail + evidence.
- **6.2 Git Ground-Truth Reader** — actual commits, diffs, files, SHAs (via the Gitea adapter). Powers M2, M3.
- **6.3 Test/CI Verdict Reader** — reads CI results or (when needed) triggers a verification run. Powers M1, M4. Never trusts the agent's "tests passed."
- **6.4 Contract Checker** — diff satisfies the declared acceptance criteria; every contract `status:done`. Powers M3, M5.
- **6.5 Audit-Window Scanner** — scans the EventLog for the commit window: claim-gate/patch-detect hits (R2), security/backdoor/injection alarms (R3). Unique to THOR.
- **6.6 Skill-Result Reader** — CTO skill-check results (R1).
- **6.7 Divergence Detector** — builds the reality manifest (git/audit) vs the agent's claim; flags lies.
- **6.8 Panel Adjudicator** — 8 probes + divergence → `done` (all pass, no divergence, within policy), `not_done` (blockers), or `escalate` (conflict/uncertainty/high-stakes → human). Trusts no single mechanism.
- **6.9 Verdict Recorder** — returns the verdict to the Manager; recorded as a signed event; produces the blocker list.

## 3. Functional Requirements (FR)
- **FR-1** Compute "done" only from reality (git, tests/CI, audit, contract) — never the agent's self-report (P5).
- **FR-2** The verdict is `done` only if ALL 8 probes pass.
- **FR-3** The 8 probes: **M1** verifier exit 0; **M2** commit landed (real SHA via git-grep); **M3** diff matches the contracts' cited files; **M4** regression test exit 0; **M5** every contract `status:done`; **R1** CTO skills all passed; **R2** zero claim-gate/patch-detect hits in the commit window; **R3** zero security alarms in the window.
- **FR-4** Each probe is read-only; running the verdict changes nothing.
- **FR-5** On `not_done`, return the SPECIFIC failing probes as actionable blockers.
- **FR-6** Compute claim-vs-reality divergence; record the gap as an honesty signal (the lie-detector).
- **FR-7** Trust no single mechanism — including Gitea's CI; CI is one signal cross-checked against git/contract.
- **FR-8** On consensus (all pass, no divergence, within policy) the verdict MAY be `done`; on conflict/uncertainty → `escalate` (P6).
- **FR-9** High-stakes changes (protected files, dependencies, language changes) require a human signature even when all probes pass.
- **FR-10** Deterministic given the same reality inputs (replayable, auditable).
- **FR-11** Re-run/verify rather than trust prior verdicts when the branch changed (freshness; a stale verdict doesn't count).
- **FR-12** Produce a verdict on demand from the Manager (`POST /verdict`); return it for the Manager to record + act on.
- **FR-13** Detect "fake test" patterns: tests present but trivially passing / not exercising the feature (anti-gaming).
- **FR-14** Support the canary invariant: a deliberately-incomplete feature whose verdict MUST be `not_done`.
- **FR-15** Governed by the Sentinel (P9): if it cannot read its inputs or compute reliably, return `escalate`/`error` (fail-closed to human), never a false `done`.
- **FR-16** No agent/LLM logic in the core verdict (mechanical/deterministic); any LLM-assisted analysis is advisory, never the sole basis of a `done`.

## 4. Technical Requirements
- **Language:** Python. **Process:** a service on `:7130`; invoked by the Manager's Verdict Coordinator.
- **Inputs (all read-only):** Gitea adapter (commits/diffs/CI), EventLog (audit window), the feature contract (catalog/slice), CTO skill results.
- **Determinism:** pure function of reality inputs; no randomness; replayable.
- **Probe isolation:** each probe an independent pass/fail + evidence; the panel composes them.
- **Test execution:** prefers reading Gitea CI (M1/M4); can trigger a verification run in a fresh ephemeral context when CI is unavailable — but the cook never runs its own grading.
- **Fake-test detection:** static + behavioral heuristics (does the test assert on the contract? execute the new code? cover the changed lines?).
- **Performance:** seconds-to-minutes; heavy verification offloaded to CI.
- **Doctrine source:** port `done-check.js`, `skill-verifier.js`, `evidence-ledger.js`, `fake-test-checker.js`, `claim-rules.js` — rebuilt clean in Python, not lifted.

## 5. The Logic
- **5.1 Why reality, not the report** — every system that asks the agent "are you done?" inherits its biases/hallucinations. THOR refuses to ask; it looks at git (what truly changed), CI (whether tests truly pass), the audit log (how the agent behaved), the contract (what was required). The claim is collected only to compare against reality (divergence), never to be the verdict. The single idea the whole moat rests on.
- **5.2 The 8 probes (all must pass)** — mechanical M1–M5 (objective/binary) + review R1–R3 (behavioral). `done` requires all 8; any failure → `not_done` with that probe named. **R2 and R3 are the genuine moat** — they audit behaviour *during the work*, which neither CI nor a final-diff check can see.
- **5.3 Claim-vs-reality divergence (the lie-detector)** — build a reality manifest (git+audit) and compare to the agent's untrusted claim. Claimed 3 files, git shows 7 → undisclosed. Claimed a test passed with no CI trace → fabrication. Claimed done but R2 shows gate-gaming → dishonesty. Divergence is recorded as a measurable dishonesty signal (feeds anti-hallucination + Toras v2). "The gap between claim and reality is itself governed."
- **5.4 The panel adjudicator (trust nothing blindly)** — not "CI said pass, so done." M1 (CI) cross-checked against M2/M3 (git) against M5 (contract) against R1–R3 (behavior). Agree → clear verdict. Conflict (CI passes but diff doesn't touch contracted files; tests pass but R2 shows gaming) → `escalate`, never guess. High-stakes → human signature regardless.
- **5.5 Anti-gaming: fake-test detection** — a passing-but-hollow test (`assert true==true`, or not calling the new code) would fool M1. The fake-test-checker defends M1: does the test assert on the contract and exercise the changed lines? A hollow test fails → `not_done`.
- **5.6 The engine governs itself (P9 + canary)** — a broken verdict that always says `done` is catastrophic. So: (a) can't read git/CI/audit → `escalate`/`error`, never false `done` (FR-15); (b) the canary invariant — a deliberately-incomplete feature that MUST verdict `not_done` runs continuously; if it ever passes, the engine is broken → Sentinel alarms.
- **5.7 Why deterministic and read-only** — pure function of reality inputs (FR-10); changes nothing (FR-4). Gives replayability, trust, and safety (a verdict run can never corrupt the work it judges).

## 6. API Strategy
### 6.1 Endpoints the Engine EXPOSES (`:7130`)
```
POST /verdict
  req: { feature_id, branch, contract_ref, claim_context?, commit_window }
  res: { verdict:"done"|"not_done"|"escalate",
         probes: { M1..M5, R1..R3 : {pass:bool, evidence} },
         blockers: [ {probe, detail} ],            # when not_done
         divergence: { found:bool, signals:[...] },# the lie-detector output
         stakes: "normal"|"high",                  # high -> human signature required
         verdict_id, deterministic_hash }
POST /verdict/dry_explain { feature_id, branch } -> { what_would_be_checked, current_probe_status }
GET  /canary/status -> { canary_feature, expected:"not_done", actual, healthy:bool }
GET  /health -> { alive, responsive, can_read_git, can_read_ci, can_read_audit }
```
### 6.2 Endpoints the Engine CONSUMES (all read-only)
- → Gitea adapter `:7170` GET `/git/log?grep=FXXX` (M2)
- → Gitea adapter `:7170` GET `/git/diff?branch=...` (M3, reality manifest)
- → Gitea adapter `:7170` GET `/ci/result?branch=...` (M1, M4)
- → ThorManager `:7100` GET `/audit/window?range=...` (R2, R3)
- → CTO `:7120` GET `/skills/result?feature` (R1)
- → catalog/contract GET feature contract (M3, M5, contract check)

### 6.3 The discipline
The engine only READS. It returns a verdict to the Manager (which records it as a signed event and acts on it — drives `result_decision` via Module 5, raises the merge card for Signature 3). The engine never merges, never writes code, never marks anything done itself — it judges.

## 7. Diagrams (described)
- **Figure 1** — The 8-probe verdict: five mechanical (M1–M5) + three review (R1–R3), all read-only against reality; all 8 must pass for `done`. R2/R3 (behaviour during the work) are the genuine moat.
- **Figure 2** — Claim-vs-reality divergence: build a reality manifest from git+audit and compare to the agent's untrusted claim; the gap is a recorded honesty signal — the lie-detector.
- **Figure 3** — The panel adjudicator: probes + divergence + stakes combine; consensus → verdict; conflict or high-stakes → escalate to human signature; trusts no single mechanism, not even CI.

## 8. Flows
- **8.1 Happy path** — `POST /verdict` → all M1–M5 + R1–R3 pass → claim matches reality (no divergence) → stakes normal → `done` → Manager raises the merge card (Signature 3).
- **8.2 not_done** — M1 passes but M3 fails (contracted file untouched), M5 fails (contract still open) → `not_done`, blockers [M3, M5] → `result_decision: rejected{blockers}`; room fixes the specific gaps.
- **8.3 Caught lie** — agent claimed "added validation, tests pass"; M2 shows the commit but R2 shows a claim-gate hit and divergence shows the claimed validation file was never modified → `not_done` + divergence recorded → escalated (high concern).
- **8.4 Conflict → escalate** — CI (M1) passes but the diff (M3) doesn't match contracted files → mechanisms disagree → `escalate`; operator decides.
- **8.5 Fake test caught** — tests pass (M1 green) but the fake-test-checker finds the test never exercises the new code → M1 overridden to fail → `not_done`.
- **8.6 Canary heartbeat** — the canary (deliberately incomplete) is verdicted periodically; expected `not_done`; if it ever returns `done`, the engine is broken → Sentinel alarm + halt.

## 9. Use Cases / User Stories (story points)
- **US-1 (13)** "done" computed from reality, never the agent's word — completion can't be faked. *(The core moat — highest value.)*
- **US-2 (13)** catch the gap between claim and reality — dishonesty measurable and recorded. *(The lie-detector — the unique differentiator.)*
- **US-3 (8)** all 8 probes must pass; the specific failing probe is named on rejection.
- **US-4 (8)** behaviour during the work (R2/R3) is part of the verdict — honesty of getting there.
- **US-5 (8)** no single mechanism trusted alone; conflicts escalate to a human.
- **US-6 (8)** a passing-but-hollow fake test is caught.
- **US-7 (5)** high-stakes changes require a human signature even when all probes pass.
- **US-8 (5)** deterministic and read-only — replayable, auditable, can never corrupt the work.
- **US-9 (5)** a stale verdict doesn't count — freshness required.
- **US-10 (5)** fails closed to a human (never false done); a canary proves it still detects. *(P9.)*
- **US-11 (5)** every verdict + divergence a recorded signed event.

**Total: ~83 points for Module 6 — the largest, as befits the moat.**

## 10. Error & Edge Cases
| Case | Trigger | Handling |
|---|---|---|
| Can't read git | Gitea adapter down | Fail-closed: `escalate`/`error`, never false `done`; Sentinel alarm |
| Can't read CI | CI unavailable | Trigger a fresh verification run, or escalate; never trust agent's "passed" |
| CI passes, diff doesn't match | mechanisms conflict | `escalate` (don't guess); human decides |
| Hollow/fake test | gaming attempt | fake-test-checker overrides M1 to fail; `not_done` |
| Stale verdict reused | branch changed | Freshness check invalidates; re-run required |
| Divergence: claimed-but-absent | hallucination/lie | Recorded as dishonesty signal; `not_done`; escalate |
| Contract ambiguous | vague acceptance criteria | LLM-assisted semantic check is advisory only; ambiguity → escalate |
| Canary passes (should fail) | engine broken | Sentinel alarm + halt; no verdicts trusted until fixed |
| Audit window incomplete | EventLog gap | Cannot confirm R2/R3 → escalate (can't certify behavior) |
| Huge diff / timeout | very large feature | Bound the read; if can't complete reliably → escalate, don't false-pass |
| Probe disagreement (mechanical) | M2 SHA exists but M3 mismatch | `not_done` with the specific mismatch as blocker |
| Repeated not_done loops | agent can't satisfy | Bounded; after N attempts surface to operator |

## 11. Easy vs Difficult Parts
- **Easy:** reading git log/diff and CI; composing 8 pass/fail probes into all-must-pass; recording the verdict.
- **Moderate:** the audit-window scan (R2/R3); stakes-tiering; determinism + freshness.
- **Difficult / real risk:** (1) **Claim-vs-reality divergence done well** — accurate reality manifest + meaningful comparison without false-flagging honest mistakes or missing real fabrications. (2) **Fake-test detection** — whether a test actually exercises the feature (coverage, assertion, contract-mapping). (3) **The panel's conflict logic** — calibrating when mechanisms "conflict enough" to escalate vs an acceptable minor mismatch.

## 12. Technical Difficulties
- **D1 — Divergence accuracy.** Flag facts (claimed X, git shows Y), not intent; material divergence → escalate to human (who judges intent); record signals over time; never auto-punish, always surface.
- **D2 — Fake-test resistance.** Require tests to assert against the acceptance criteria and cover the changed lines; a test that doesn't execute new code fails; evolve heuristics (Toras v2).
- **D3 — Never a false done (the cardinal rule).** Fail-closed everywhere (can't verify → escalate); all-8-must-pass (no partial); canary proves detection; the most-tested module, with adversarial "try to get a false done" suites.
- **D4 — Calibrating escalation.** Deterministic clear-cases auto-resolve; only genuine conflict/high-stakes/divergence escalates; bias toward escalate-when-unsure.
- **D5 — Determinism with external inputs.** Pure function of a snapshot (commit SHA, CI run id, audit range); same snapshot → same verdict; freshness invalidates when the snapshot changes.

## 13. What Needs To Be Built (checklist)
- [ ] Probe Runner (orchestrates the 8 probes; pass/fail + evidence)
- [ ] Git Ground-Truth Reader (M2, M3, reality manifest) via Gitea adapter
- [ ] Test/CI Verdict Reader (M1, M4; read CI or trigger fresh verification)
- [ ] Contract Checker (M3, M5; diff vs acceptance criteria)
- [ ] Audit-Window Scanner (R2, R3; EventLog correlation) — the moat probes
- [ ] Skill-Result Reader (R1)
- [ ] Divergence Detector (reality manifest vs claim; honesty signals)
- [ ] Fake-test-checker (does the test exercise the feature?)
- [ ] Panel Adjudicator (probes + divergence + stakes → verdict; conflict → escalate)
- [ ] Verdict Recorder (return to Manager; signed event; blocker list)
- [ ] Canary invariant (deliberately-incomplete feature; must verdict not_done)
- [ ] Determinism + freshness layer (snapshot-keyed; invalidate stale)
- [ ] Adversarial test suite ("try to get a false done": fake tests, divergence, gamed gates)

## 14. Dependencies & Sequencing
**Depends on:** Gitea adapter (git ground-truth + CI). Module 3 (Manager) — invokes the engine, records the verdict, acts on it (result_decision, merge card). EventLog — for the R2/R3 audit-window scan. CTO — for R1 skill results. The feature contract (catalog/slice, Module 5) — for M3/M5/contract checking.

**Blocks / depended on by:** Module 5's `result_decision` — the engine's verdict *is* the authoritative "done." The merge — Signature 3 only on a `done` verdict. The QA stage (Module 13) — complements the verdict.

**Build-order note:** Build after the orchestration core (1–5). This is where the build-order stub gate ("always approve") is finally replaced by real, un-fakeable judgment. **Milestone:** a genuinely-incomplete feature is rejected with specific probe blockers, a fabricated claim is caught by divergence, and a hollow fake test fails the gate — none of which a self-reporting agent could slip past.

## 15. Test / Acceptance Criteria (evidence-based)
- **AC-1** A genuinely-incomplete feature (contracted file untouched) verdicts `not_done` with M3 named as the blocker.
- **AC-2** A feature where the agent claims work it didn't do is caught by divergence and does not verdict `done`.
- **AC-3** A passing-but-hollow test fails the fake-test-checker and yields `not_done`.
- **AC-4** With CI passing but the diff not matching the contracted files, the verdict is `escalate`, not `done`.
- **AC-5** Running the verdict changes nothing in the codebase or state (read-only).
- **AC-6** The same reality snapshot produces the identical verdict on replay (determinism).
- **AC-7** A stale verdict (branch changed since) does not count; a fresh run is required.
- **AC-8** With git/CI/audit unreadable, the engine returns `escalate`/`error`, never `done` (fail-closed — the cardinal rule).
- **AC-9** The canary (deliberately incomplete) always verdicts `not_done`; if forced to pass, the Sentinel alarms.
- **AC-10** A high-stakes change with all probes passing still requires a human signature.
- **AC-11** Every verdict + divergence result is recorded as a signed event.
- **AC-12** An adversarial suite attempting to obtain a false `done` (fake tests, fabricated claims, gamed gates) fails across all cases.

**Headline milestone:** AC-2 + AC-8 + AC-12 together — a fabricated claim is caught, the engine never returns a false `done` even when its inputs fail, and a determined attempt to game the gate cannot succeed. That is the moat, proven: completion is honest and un-fakeable.

---

*End of THOR Module 6 — The Development-Governance Engine PRD v1.0. This is the core differentiator; everything else serves it. Next module: 7 — The SDLC Stages (Genesis / Project Checker / Build / QA — the typed stage-containers that produce the work this engine judges).*
