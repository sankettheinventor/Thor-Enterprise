# Module 6 — The Development-Governance Engine (THE MOAT)

Decides whether a feature is *really* done — honestly and un-fakeably — by computing a verdict from
**reality** (git, tests, audit, contract), never the agent's word (P5). The 8-probe verdict (all must
pass) + claim-vs-reality divergence (the lie-detector) + a panel that escalates rather than guesses.
Read-only, deterministic, **fail-closed — never a false `done`**. Spec:
[`../docs/PRD-Module-6-GovEngine.md`](../docs/PRD-Module-6-GovEngine.md).

**Bootstrap fidelity:** real git ground-truth (local-git Gitea stub), **real test execution** (a machine
runs the verifier/regression — never the agent's "tests passed"), real EventLog audit scan (R2/R3),
contract from the slice. R1 (CTO skills) is a stubbed input (CTO is a later module); real Gitea CI is
Module 12 — until then M1/M4 use the PRD's sanctioned "fresh verification run." **No LLM in the verdict
(FR-16).**

## Files (→ PRD §2 sub-modules)
| File | Sub-module | Role |
|---|---|---|
| `reality.py` | 6.2/6.3/6.5 | git ground-truth, fresh test run, audit-window scan (read-only) |
| `fake_test.py` | — (FR-13) | fake-test-checker — defends M1 against hollow tests |
| `probes.py` | 6.1 Probe Runner | the 8 probes (M1–M5 mechanical, R1–R3 review) |
| `divergence.py` | 6.7 | reality manifest vs the agent's untrusted claim |
| `panel.py` | 6.8 | probes + divergence + stakes → done/not_done/escalate |
| `engine.py` | orchestrator + 6.9 | verdict, recorder, canary, freshness, fail-closed |

## Milestone (smoke `tools/smoke_govengine.py`)
**AC-2 + AC-8 + AC-12** — a fabricated claim is caught (divergence), the engine never returns a false
`done` even when its inputs fail (fail-closed), and an adversarial gaming suite cannot get a `done`.
Runs against **real git repos + real test execution + the real Manager EventLog**.

## Smoke (NOT run until asked)
```bash
python tools/smoke_govengine.py   # builds real git scenarios; Part B uses Postgres for audit/recording
```
`tests/govengine/` holds AC-1..AC-12 as deferred/skipped specs (never a false green).
