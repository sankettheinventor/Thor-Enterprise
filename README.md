# THOR Enterprise

**A governed agentic development platform.** THOR lets AI write software *while a human stays in command* — every agent is isolated, every action is governed, every "done" is judged against reality, everything is auditable, and the governance verifies *itself*.

> The industry is racing to remove the human ("ship while you sleep"). THOR makes the opposite bet: an accountable human in command, with the tooling to direct, watch, and **cryptographically sign** the decisions that matter — over a system engineered so an AI agent *cannot* quietly fake its work.

---

## Why THOR exists

An LLM agent that builds code is fast, occasionally brilliant, and **structurally untrustworthy** — it will confidently claim a feature is finished, tests pass, and nothing else was touched, when none of that is true. Most "autonomous coding" tools trust that self-report. THOR refuses to.

Instead THOR treats the agent as a powerful-but-unreliable worker and wraps it in five guarantees:

1. **Isolation** — each agent runs in a sealed, throwaway container with exactly the files it was given and (at most) one governed door to the outside.
2. **Governance** — every tool call and model call is judged *before* it executes; out-of-scope or forbidden actions are denied, not undone-after-the-fact.
3. **Verdict against reality** — "done" is decided by an engine that reads the *real* git history, *runs the real tests*, and compares them to what the agent *claimed*. A lie diverges from reality and is caught.
4. **Human command** — a person directs the work on a kanban and signs three decisions (plan, re-work, merge) with a real Ed25519 signature, from a desktop cockpit or a phone.
5. **Self-verifying governance** — a meta-layer continuously proves the governor itself is alive, loaded, untampered, and *still catching* — and an always-on, zero-cost inspector reasons about whether the system is behaving correctly.

That combination — *the un-fakeable verdict plus the human-in-command experience* — is THOR's moat.

---

## Architecture — 17 modules across five layers

| Layer | Modules | What it guarantees |
|---|---|---|
| **1 · Isolation** | **Wall** | Sealed, hardened, identity-stamped throwaway rooms; one governed egress door |
| **2 · Governance** | **Leash** · **Manager** · **Scheduler** · **Contract** | Pre-action policy checks; one event-sourced brain (tamper-evident, signed, hash-chained); dependency-wave scheduling; a frozen six-message seam between brain and room |
| **2 · The moat** | **GovernanceEngine** | The un-fakeable verdict + claim-vs-reality lie-detector |
| **3 · SDLC + human command** | **SDLC Stages** · **PM Surface** | Genesis → Build → independent QA → Verdict → merge, behind three signature gates; the operator's kanban / approval / audit cockpit |
| **4 · Mobile / Remote** | **Mobile** | The same command from a phone — end-to-end-encrypted, signed approvals, no inbound attack surface |
| **Meta-governance** | **Sentinel** · **Self-Audit Model** | Mechanical reflexes that detect *and halt* on a broken governor; a zero-cost read-only model that reasons about correctness and escalates |
| **Foundation** | **Audit / Identity / Gitea Adapters** | The adopted substrate (tamper-evident audit, cryptographic identity, git/PR/CI) behind thin, swappable Strangler seams |

*(17 modules are delivered as 12 packages; the foundation adapters group three substrates.)*

### The life of a feature

```
human intent ─▶ catalog (kanban)
                  │  Sig 1: "approve the plan"
                  ▼
            Scheduler picks a ready feature
                  ▼
   Wall provisions a sealed room ── identity-stamped, network-locked
                  ▼
   Build stage (the "cook") writes code  ── every action judged by the Leash
                  ▼
   Independent QA room re-tests it adversarially
                  │  Sig 2 (only if re-work is needed)
                  ▼
   GovernanceEngine verdict: reads REAL git + RUNS the tests,
   compares to the agent's CLAIM → done / not_done / escalate
                  │  Sig 3: "approve the merge"  (verified Ed25519)
                  ▼
   Gitea adapter executes the merge (THOR decides, git executes)
                  ▼
   Every step is a signed, hash-chained event in the one ledger
```

Throughout: the **Sentinel** proves the governor is healthy and can halt it; the **Self-Audit** model watches for correctness drift at near-zero cost; the human can intervene from desktop or phone.

---

## Design principles (the locked rules)

- **Build ungoverned, prove later.** THOR's own construction is ordinary software — we do not apply THOR's governance to building THOR. Build → smoke-check → defer formal proving.
- **Real evidence only.** No faked results, no fabricated test passes, no invented bugs. Every claim in this repo is demonstrated against a real Postgres, real Docker, real cryptography, or real git — or it is explicitly labelled a stand-in.
- **Adopt deeply, behind thin seams (Strangler-fig).** Commodity substrates (a tamper-evident audit chain, cryptographic identity, a git host) are *adopted*, each behind a THOR-owned adapter that is the only code importing it — so the moat is never welded to a dependency.
- **Score the system, not the agent.** THOR rejects per-agent trust-scoring (agents are inherently inconsistent); it scores the *system's* own reliability instead.
- **Fail-closed.** If the audit can't record, governed work doesn't proceed; if identity can't verify, nothing is trusted; if the governor can't prove itself, it stops.

---

## Tech stack

- **Python 3.14** control plane · **FastAPI** + **Pydantic** service shapes
- **Docker** engine (native, rootless-friendly) for sealed rooms and Postgres
- **PostgreSQL 16** — the event-sourced, hash-chained ledger
- **cryptography** — Ed25519 (signatures + identity), X25519 + ChaCha20-Poly1305 (mobile E2EE)
- **git** — real branches/commits/merges as the SDLC backbone
- Deterministic stand-ins occupy the seams where a frontier LLM, Microsoft AGT, a Gitea server, a local Qwen inspector, and the web/mobile UIs will plug in.

---

## Repository layout

```
wall/        Module 1  — sealed room provisioning, network lock, identity stamping
leash/       Module 2  — pre-action governance policy + egress gateway + kill-switch
manager/     Module 3  — the one brain: event-sourced, signed, hash-chained ledger
scheduler/   Module 4  — dependency-wave scheduling + budget caps
contract/    Module 5  — the frozen six-message brain↔room seam
govengine/   Module 6  — THE MOAT: the verdict + claim-vs-reality lie-detector
sdlc/        Module 7  — Genesis → Build → QA → Verdict → merge, with signature gates
dashboard/   Module 8  — PM Surface: kanban, approval cards, audit, legible refusal
mobile/      Module 9  — phone remote head: E2EE relay, signed approvals, allowlist
sentinel/    Module 10 — meta-governance reflexes: liveness, canary, integrity, halt
selfaudit/   Module 11 — zero-cost read-only inspector + system meta-trust score
adapters/    Module 12 — audit / identity / gitea behind swappable Strangler seams
tools/       one-time smoke demonstrations + the architecture lint
tests/       acceptance-criteria suites (deferred until the proving pass)
docs/        the PRD suite (one per module) + the gap & risk register
```

---

## Status — honest, as of 2026-06-06

**Structural build complete: all 17 modules are built, and each passes a one-time smoke** demonstrating its acceptance criteria against a *real* Postgres, real Docker rooms, real Ed25519/X25519 cryptography, and real git.

This is a **pre-proving snapshot**, and the README will not pretend otherwise:

- The components are individually real and individually verified — **but they have not yet been assembled into a single running service mesh.** Every cross-module integration today happens in-process inside the smoke scripts.
- Several real-world backends are represented by **deterministic stand-ins behind swappable seams**: Microsoft AGT (governance/audit/identity), a Gitea server, a local LLM cook/QA, the local Qwen inspector, and the React/mobile UIs.
- A complete, **brutally honest audit** of exactly what is wired end-to-end vs. stand-in — including where a green smoke would not hold against a real backend, and where the verdict could still be gamed — lives in **[`docs/GAP-AND-RISK-REGISTER.md`](docs/GAP-AND-RISK-REGISTER.md)**. Read it before trusting any single guarantee.

### What's next — the proving pass

1. **Prove** — turn the ~144 deferred acceptance tests into gated CI tests (Wall first, then up the dependency stack).
2. **Wire** — assemble the modules into a runnable system; put the Leash interceptor in the real action path; make the Sentinel's halt actually halt; build the honest verdict coordinator.
3. **Harden the moat** — adversarial tests: can a fabricated claim, a hollow test, or a gamed gate *ever* earn a false "done"? Replace heuristics with execution-based evidence.

---

## Reproducing the smokes

Each module has a self-contained smoke under `tools/` that stands up its real dependencies, demonstrates every acceptance criterion with observed output, and tears everything down. Requires Docker + a Python 3.14 virtualenv with `requirements.txt`.

```bash
# from the repo root, inside the venv
python tools/smoke_wall.py        # sealed room, identity, lifecycle
python tools/smoke_manager.py     # tamper-evident ledger, crash-replay, fail-closed
python tools/smoke_govengine.py   # the verdict + claim-vs-reality lie-detector
# ... one per module; see tools/
python tools/arch_lint.py         # fails if AGT/Gitea is imported outside adapters/
```

---

## A note on honesty

This project was built to a strict rule: **never show a fake result, claim, or bug.** The gap register exists because the same rule applies to the project's own description — a governed AI platform that overstated its own readiness would be self-refuting. What's real is labelled real; what's a stand-in is labelled a stand-in.

---

## Author

**Sanket Toraskar** — owner / architect. Built module-by-module from a written PRD suite (see `docs/`).

> Developers resuming work: read **[`SESSION.md`](SESSION.md)** first — it carries the full build state and the next steps.

*This repository is a snapshot for version safety and review. License: all rights reserved (to be finalised).*
