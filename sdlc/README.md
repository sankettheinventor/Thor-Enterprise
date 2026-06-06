# Module 7 — The SDLC Stages (Genesis / Project Checker / Build / QA)

Turns THOR from a "room system" into a **governed software lifecycle**: typed stage-containers on one
universal anatomy (Input → Brain+Skills → Mandate → Edge-check → Output), moving a feature through
**Genesis → Build → QA → Verdict → Merge** with a human signature at each gate. Stages run as rooms
(Wall M1) under the Leash (M2), briefed via the Contract (M5), coordinated by the Manager (M3),
scheduled by the Scheduler (M4), and judged by the Engine (M6). Spec:
[`../docs/PRD-Module-7-SDLC.md`](../docs/PRD-Module-7-SDLC.md).

**Bootstrap fidelity:** real Wall rooms (Build/QA/Checker), real Manager cards/signatures/bugs, the real
Engine verdict, real read-only Checker mount. The cook and the QA agent's *intelligence* are deterministic
stand-ins (no LLM); the **structure** — independence, floor+specialty skills, governed transitions, the
three signatures — is real (Bible §10.4: structure + swappable skills).

## Files (→ PRD §2 sub-modules)
| File | Sub-module | Role |
|---|---|---|
| `skills.py` | 7.2 Skill Composer | floor (always-on) + specialty (by tags); deterministic |
| `anatomy.py` | 7.1 Stage Anatomy | the shared 5-part skeleton |
| `stages.py` | 7.3–7.6 | Genesis · Checker · Build · QA |
| `transitions.py` | 7.7 | SDLC order + the three signature gates + bounded loop |
| `bridge.py` | 7.8 | bugs → DB; QA-fail → card (Sig 2); capability gap → card; merge card (Sig 3) |

## Milestone (smoke `tools/smoke_sdlc.py`)
**AC-2 + AC-3** — an independent QA agent (a fresh room that did NOT write the code) reads the actual
implementation and catches an edge case the plan never specified. Demonstrated end-to-end against the
real Manager + Engine + Wall, with all three signature points enforced.

## Smoke (NOT run until asked)
```bash
python tools/smoke_sdlc.py   # Postgres + real Build/QA/Checker rooms; full Genesis→Build→QA→Verdict→merge
```
`tests/sdlc/` holds AC-1..AC-12 as deferred/skipped specs (never a false green).
