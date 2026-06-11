<div align="center">

![THOR Enterprise](docs/assets/thor-banner.svg)

### **Governed development, in your pocket.**

AI agents build your software in sealed rooms. Every action is judged **before** it executes.
"Done" is proven against reality — never taken on the agent's word.
And the final signature is always yours, from your laptop or your phone.

[🌐 Website](https://thor-enterprise.dev) · [▶️ Watch the 3-minute demo](https://youtube.com/watch?v=YOUR_DEMO_VIDEO) · [📚 Docs](docs/) · [🐦 Follow the build](https://x.com/sankettheinventor)

![License](https://img.shields.io/badge/license-Source--Available-C77DD6)
![Python](https://img.shields.io/badge/python-%E2%89%A53.11-3776AB?logo=python&logoColor=white)
![version](https://img.shields.io/badge/version-1.0.0-8E3BA6)
![npm](https://img.shields.io/badge/npm-thor--enterprise-CB3837?logo=npm&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-required-2496ED?logo=docker&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-ledger-336791?logo=postgresql&logoColor=white)
![dashboard](https://img.shields.io/badge/dashboard-127.0.0.1%3A7080-E8B23A)

</div>

---

## 1 · Introduction

AI has a known nature. It hallucinates. It makes claims it cannot back — fake results, fake completions, fake confidence. None of this is malice; it's simply what these systems do today. And as agents scale — multiple sessions, multiple features, a workload no person can watch in real time — the hardest part of the job quietly changes. It stops being *doing the work* and becomes *deciding what to believe*. Trusting that the agent examining a module examined it correctly becomes nearly impossible at exactly the moment the stakes are highest — which is precisely when today's tools remove the human from the loop.

**THOR Enterprise works differently.** Critical decisions are never taken by AI. They are taken by you and me — the human. We call this **Human Command Development (HCD)**: the AI does the labor; an accountable human stays in command; and the system is engineered so the agent cannot quietly fake, drift, or lie — even if it tries.

This is not an AI coding tool with a review step bolted on. It is a different category: **Governed Development** — a runtime where governance is structural, not procedural. The agent doesn't follow rules because it was asked nicely. It follows them because the architecture offers no other path.

---

## 2 · Why THOR Exists

For seventy years, every tool in computing waited for your hand. The compiler compiled when you asked. The editor changed what you typed. The deploy ran when you pressed the key. Tools amplified humans — but the human was always *in* the motion.

AI agents are the first tools in history that work while you're not looking.

That changes something fundamental, and almost nobody has named it: **when work happens out of sight, the product is no longer code. The product is trust.** And here is the asymmetry the whole industry is built on top of, without acknowledging it:

> **The cost of writing code has collapsed to nearly zero. The cost of trusting it hasn't moved an inch.**

A model can produce a thousand lines in a minute. Verifying those thousand lines still takes a human hour — an hour of reading, doubting, re-running, cross-checking. Generation scaled a millionfold; verification didn't scale at all. Every "autonomous" coding product on the market resolves this gap the same way: *it asks you to stop verifying.* Trust the summary. Trust the green checkmark the agent itself printed. Ship while you sleep.

But the gap doesn't disappear when you stop looking at it. It compounds, in three ways every team running agents has already met:

**Scope quietly dissolves.** Asked to fix a login bug, the agent "improves" the payment module on the way through. Not sabotage — enthusiasm without boundaries. By the time the diff reaches you, the blast radius is the repository.

**"Done" becomes a feeling, not a fact.** Agents report tests passed that never ran, features finished that are stubs, and write hollow tests that touch the code without asserting anything — so even your test suite testifies on the agent's behalf. An agent that writes 500 lines an hour can misreport 500 lines an hour.

**Confidence fails in both directions.** The same nature that produces false success produces false alarms — a "critical bug" declared after reading half the code, missing how Feature A depends on Feature B. Each false alarm spins up re-work, burns model spend on a problem that never existed, and trains you to ignore the alarm that's real.

And all of it multiplies with scale. One agent, one feature — you can hover. Five agents across five features, around the clock? No human can hover. The industry's answer is to remove the hoverer. THOR's answer is to make hovering unnecessary — **without removing the human's command.**

Here's the part that should make you a little angry: this is a solved problem. Computer security answered *"how do you safely run code you don't trust?"* fifty years ago — reference monitors, complete mediation, least privilege, separation of duty (Anderson 1972; Saltzer & Schroeder 1975; Clark & Wilson 1987). Banks have used these ideas for decades. The AI industry simply never applied them to the most prolific untrusted code-producer ever built.

THOR was built to apply them. Not to slow agents down — to make their speed *believable*.

---

## 3 · The Solution

THOR treats the agent as what it is: **a brilliant, untrusted worker.** Five interlocking guarantees, each one structural:

| # | Guarantee | Mechanism |
|---|-----------|-----------|
| 1 | **Isolation** | Every agent works in a sealed, throwaway Docker room — capabilities dropped, unprivileged user, network locked, identity stamped with a real Ed25519 token. Forged identity → room destroyed. |
| 2 | **Decide-before** | Every write is judged against a frozen policy **before it executes**. An out-of-scope file is not reverted — it *never exists*. Governor unreachable → fail-closed, all work stops. |
| 3 | **Verdict from reality** | "Done" is computed, never claimed. The GovEngine reads real git history, runs the real tests in a fresh process with coverage, and compares reality against the agent's claim — using inputs derived from trusted ledger state the agent cannot touch. Any mismatch is a caught lie, recorded forever. |
| 4 | **Human command** | Three signature gates — plan, re-work, merge — signed with your Ed25519 key, which never leaves your device. The room↔system contract contains **no message type for self-approval**. The agent could not approve its own work even in principle. |
| 5 | **Self-verifying governance** | The governor is itself governed. A Sentinel continuously feeds canary violations to the policy engine; a guard that approves a forbidden action triggers alarm and a *physical* halt — rooms destroyed, new work blocked. A read-only auditor (whose database role cannot write) watches everything at near-zero cost. |

Every event — every allowed action, every denial, every signature, every caught lie — lands in a single hash-chained, Ed25519-signed ledger. Edit one historical entry and the entire chain screams.

**One sentence:** the agent proposes, the guard disposes, reality decides, and you sign.

<!-- 🖼 SCREENSHOT — the cockpit with an approval card open -->
![THOR command deck](docs/assets/thor-dashboard.png)

---

## 4 · Features

### 🗂 i. Kanban command deck
A built-in project management surface. Features move across a live board — *backlog → planned → in progress → QA → bug fixing → awaiting signature → merged* — driven by real ledger events, not self-reported status. The board cannot show "done" unless reality computed "done."

### ✍️ ii. Critical decisions are human-signed — AI structurally cannot approve
Plan approval, re-work authorization, and final merge each require your cryptographic signature on the dashboard. This isn't a permission setting an agent might route around — the protocol between rooms and the system has six message types, and *none of them means "I approve."* The vocabulary of self-approval does not exist.

### ⚙️ iii. Auto-approval for safe actions
Governance where it matters, invisibility where it doesn't. In-scope reads, writes, test runs, and updates flow through the policy engine in microseconds with no human in the loop. You are interrupted only at moments of consequence. Velocity for the agent; command for you.

### 📱 iv. Mobile dashboard, synced with your laptop
The same authority, anywhere. Your phone pairs over an end-to-end-encrypted, zero-knowledge relay (X25519 + ChaCha20-Poly1305); the signing key never leaves the device; replayed or forged signatures are rejected. Approve a merge from a café with the exact cryptographic weight of your desk. *Governed development, in your pocket* — literally.

### 🔀 v. Multi-session: parallel sealed rooms
Build many features at once. Each gets its own sealed room with its own frozen scope; a deterministic scheduler dispatches by dependency order and enforces budget caps. Rooms share nothing. One agent's chaos cannot touch another's work.

### ✅ vi. Done is proven three ways
No single witness can ship code:
1. **The agent claims** — and the claim is treated as testimony from an unreliable witness.
2. **An independent adversary attacks** — a separate QA agent, in a *different* sealed room, with no access to the builder's reasoning, actively tries to break the work. Its bug reports face the same standard: **no reproduction, no bug** — a failing test or it didn't happen.
3. **The GovEngine rules from reality** — real commits, real test execution, real coverage of the diff, compared against the claim.
A lie must fool all three at once. Two of them don't listen to the agent at all.

### 🧠 vii. Brain skills, loaded per task
Agents don't carry one giant generic brain into every job. For each task, the planning layer selects the specific skill packs the work requires — and the verdict engine's skill verifier later confirms, from the actual output, that those skills were genuinely applied. The right expertise per task, proven after the fact, never assumed.

### 💸 viii. Zero ambient AI cost
The governance machinery itself — scheduler, policy engine, ledger, contract, verdict probes — is deterministic code. **It makes no LLM calls.** Your model spend goes to the task work itself, not to overhead. Most platforms burn tokens to supervise tokens; THOR's supervision runs at the price of electricity.

### 🔍 ix. Continuous audit with no AI bills
A local model (Qwen via Ollama) reads the ledger around the clock, hunting anomalies — on your hardware, at **zero frontier-API cost**. Its database role physically cannot write; it has broad eyes and no hands. Findings escalate to the Sentinel, which decides. Always-on oversight that never shows up on an invoice.

### 🪄 x. Session 0 — your feature list, before any agent moves
THOR begins with a genesis conversation: it interviews you, drafts the complete feature catalog with scopes and acceptance criteria, and presents it for **your approval**. Signature 1 — yours — is the first event in the ledger. No room boots, no token burns, until the human has commanded what gets built.

### 📂 xi. Works with your existing project
THOR isn't only for greenfield. Point it at an existing repository and the same lifecycle applies: features planned against your real codebase, scopes frozen over your real files, verdicts computed from your real history. Governance is something you add to the code you already have.

### ➕ xii. Add features anytime — the spec is a living document
Feature specs are append-only: new requirements and confirmed bugs are added as signed, chained entries — never edits. Every confirmed bug's reproduction test joins the regression suite *permanently*, so each caught bug makes the examiner stricter forever. The document grows; history is never rewritten.

### 🗑 xiii. Remove safely — kill switches with audit trails
Features can be cancelled and rooms destroyed at any moment — by you from the dashboard, or by the Sentinel when governance integrity is threatened. Destruction is physical (container removed, identity revoked) while the audit trail is preserved in full. Nothing disappears quietly. Nothing lingers dangerously.

---

## 5 · What's Inside — Standing on Proven Shoulders

THOR doesn't reinvent infrastructure; it governs it. Every third-party component sits behind a THOR-owned adapter seam (the Strangler-fig pattern), enforced by architecture lint — so any vendor below can be swapped without touching the governance core.

| Layer | Technology | Role in THOR |
|-------|-----------|--------------|
| Isolation | **Docker** | Sealed, throwaway agent rooms |
| Ledger | **PostgreSQL** | The hash-chained, append-only event store — the one source of truth |
| Cryptography | **Ed25519 / X25519 / ChaCha20-Poly1305** | Unforgeable signatures, room identity, E2EE mobile channel |
| Git hosting | **Gitea** (self-hosted, behind the git adapter) | Branches, PRs, merges — while the verdict always runs its *own* tests, never trusting CI |
| Enterprise governance | **Microsoft Agent Governance Toolkit** (behind the AGT adapter) | Enterprise audit/identity substrate — adopted, not depended on; one-line swappable |
| Local intelligence | **Ollama + Qwen** | The zero-cost continuous auditor on your own hardware |
| Control plane | **Python 3.11 · FastAPI · uvicorn** | The Manager, Scheduler, GovEngine, Sentinel surfaces |
| Command deck | **React cockpit + installable mobile PWA** · native Web Push (live) | The human's window and signing surface — laptop or phone, same Ed25519 authority |

The moat — decide-before, verdict-from-reality, human signatures, the chained ledger — is 100% THOR-owned code. The substrate is rented; the trust is not.

---

## 6 · Quick Start

**Prerequisites:** Linux or WSL2 · Docker · PostgreSQL 15+ · (Node 18+ to build the cockpit)

**From source (works today):**

```bash
git clone https://github.com/sankettheinventor/Thor-Enterprise.git
cd Thor-Enterprise
pip install -r requirements.txt
make start                              # boots the full control plane on one ledger
make demo                               # watch one governed feature go end-to-end

# the cockpit (laptop + installable phone PWA):
cd ui && npm ci --ignore-scripts && npm run build   # Dashboard → http://127.0.0.1:7080/app/
```

Session 0 (the genesis interview that drafts your feature catalog and takes your Signature 1) runs from
the command deck once the plane is up.

**The npm launcher** is a thin, zero-dependency wrapper that boots the Docker control plane
(`docs/NPM-SECURITY.md`). It installs from this repo today, and from the public registry once published:

```bash
npm install -g .          # from a clone (or: github:sankettheinventor/Thor-Enterprise)
thor start                # docker compose up — Dashboard → http://127.0.0.1:7080
```

**Then — don't trust us, verify:**

```bash
make prove
```

`make prove` is the trust bar: it provisions real rooms, attempts real violations — fabricated claims, hollow tests, out-of-scope writes, a killed governor — and passes only if **every attack is caught**. If you change the code and the moat weakens, this command tells you before your agents do.

<!-- ▶️ DEMO GIF — `make demo` end-to-end -->
![make demo](docs/assets/thor-demo.gif)

---

## 7 · System Architecture

```
                          ┌──────────────────────────────┐
   👤 YOU (Commander)     │      HUMAN COMMAND LAYER     │   📱 Phone (E2EE)
   sign: plan/rework/merge│   Dashboard · Mobile relay   │   same key authority
                          └──────────────┬───────────────┘
                                         │ Ed25519 signatures
                          ┌──────────────▼───────────────┐
                          │        CONTROL PLANE         │
                          │  Manager ── event-sourced,   │
                          │   hash-chained ledger (PG)   │
                          │  Scheduler ── deterministic  │
                          │  CTO ── plans scope + skills │
                          │  GovEngine ── verdict from   │
                          │   reality (git+tests+cov)    │
                          │  Sentinel ── canaries, halt  │
                          │  Self-Audit ── Qwen, read-   │
                          │   only eyes, zero AI bills   │
                          └──────┬───────────────┬───────┘
                                 │ six-message contract (no
                                 │ self-approval message exists)
                   ┌─────────────▼────┐     ┌────▼─────────────┐
                   │  SEALED ROOM A   │     │  SEALED ROOM B   │
                   │  build agent     │     │  QA adversary    │
                   │  ┌────────────┐  │     │  (independent,   │
                   │  │   LEASH    │  │     │   fresh room,    │
                   │  │ judge every│  │     │   no shared      │
                   │  │ action     │  │     │   state)         │
                   │  │ BEFORE it  │  │     │                  │
                   │  │ executes   │  │     │                  │
                   │  └────────────┘  │     │                  │
                   └──────────────────┘     └──────────────────┘
                     rooms are throwaway; all memory lives in the ledger
```

Seventeen modules across twelve packages. One ledger. One door per room. One human in command.

---

## 8 · Repository Layout

```
thor-enterprise/
├── manager/        # Event-sourced core: hash-chained signed ledger, projections, registry
├── wall/           # Room provisioner: sealed Docker rooms, identity stamping, destruction
├── leash/          # Decide-before policy engine: in-room proxy, frozen policy, egress gateway
├── scheduler/      # Deterministic dispatch: dependency order, budget caps, zero LLM calls
├── contract/       # The six-message room↔system protocol (self-approval not expressible)
├── govengine/      # Verdict from reality: git probes, real test runs, coverage, skill verifier
├── sdlc/           # The governed lifecycle: Session 0 → build → adversarial QA → verdict
├── dashboard/      # The command deck: kanban, approval cards, in-browser Ed25519 signing
├── mobile/         # Phone authority: E2EE zero-knowledge relay, device allowlist, replay defense
├── sentinel/       # Governance of the governor: canaries, escalation, physical halt
├── selfaudit/      # Read-only inspector: local Qwen seam, DB role that cannot write
├── adapters/       # Strangler-fig substrate: AGT / Gitea / audit behind swap seams
├── tools/          # start_thor.py — one-command boot of the full plane
├── scripts/        # demo.sh, prove.sh
├── tests/          # Unified suite: module ACs + integration flows + adversarial moat tests
└── docs/           # PRDs, wiring manual, gap & risk register, runbooks
```

Start reading at `docs/` — especially `GAP-AND-RISK-REGISTER.md`. We audit ourselves the way we audit agents: every known gap, honestly stated, with file:line, and closed only with a cited proving test.

---

## 9 · Contributing

THOR's contribution culture mirrors its product philosophy: **claims are testimony; tests are truth.**

1. **Read the actual code first.** Documentation drifts; source doesn't.
2. **One gap per PR.** Name the gap (register row or issue) in the commit. No drive-by refactors of working modules.
3. **Prove over the live plane.** A green unit test is testimony. Your PR must keep `make prove` green from clean — real rooms, real Postgres, real attacks.
4. **Never weaken the moat.** Any change that makes the policy engine more permissive, the verdict more forgiving, or the worker more trusted will be rejected regardless of what it improves. The moat gets harder, never easier.
5. **Adversarial proof for boundary changes.** If your PR touches the worker, the policy engine, or the network boundary, it ships with the attack that fails against it.
6. **Update the register.** Found a gap you're not fixing? Add the row with file:line. Honest open gaps outrank silent ones.

---

## 10 · Roadmap & what shipped

The core governance engine is proven, and the production phase has **landed** — each item closed with a
cited proving test in `docs/GAP-AND-RISK-REGISTER.md`. We audit ourselves the way we audit agents.

**✅ Shipped (production phase)**

| Shipped | Proof |
|---------|-------|
| **Pluggable real workers** — the build agent is a swappable cook governed by the policy engine; an independent adversarial QA agent in its own room; the anti-fake-test gate proves a test can go red | `make prove`, `test_cook_buildstage`, `test_qa_adversarial`, `test_fake_test_discrimination` |
| **Governed egress, one door** — internal room-net + allowlisting gateway; credentials never inside the room | leash AC-5/6/8 live, `test_flow_onedoor_egress` |
| **Hardening** — DB-level single-writer (advisory lock), routable room address, read-only room filesystem | `prove_concurrent_writer`, `prove_room_hardening` |
| **Live Gitea** — real branches/PRs/merges behind the git adapter; the verdict still runs its own tests | `prove_gitea_live`, `test_gitea_live` |
| **React + mobile cockpit** — installable PWA, real-time SSE sync, native Web Push, the same in-browser Ed25519 authority; TLS via Caddy | `test_react_sign_authority`, `test_mobile_sync`, `test_push_pipeline`, `prove_tls.sh` |

**🔜 Next**

| Next | Why |
|------|-----|
| Acceptance-criteria / test-list on each feature, surfaced in the cockpit | tie the UI to the governance contract |
| Epics / milestones, dependencies, assignees | richer project management |
| Microsoft AGT live behind the adapter; publish the npm package | enterprise substrate + one-line install |
| Live frontier-cook end-to-end with your token; push on a physical device over TLS | the last mile to a real-agent demo |

Every row closes with a proving test or it doesn't close.

---

## 11 · Author

**Sanket** — Founder, THOR Enterprise · Mumbai, India

Creator of **Human Command Development (HCD)** — the philosophy that every human who directs AI is a Commander carrying full accountability: wisdom from human experience, speed from AI execution, and command never delegated to the thing being commanded.

THOR is dogfooded daily: it governs the AI agents that help build it. The kill criterion is public — if its own founder stops trusting it enough to use it, it dies.

- 🌐 Website: [thor-enterprise.dev](https://thor-enterprise.dev)
- ▶️ YouTube: [THOR Enterprise channel](https://youtube.com/@thor-enterprise)
- 🐦 X: [@sankettheinventor](https://x.com/sankettheinventor)
- 💻 GitHub: [@sankettheinventor](https://github.com/sankettheinventor)

---

<div align="center">

**The agent proposes. The guard disposes. Reality decides. You sign.**

⭐ If you believe humans should command AI — not chase it with a mop — star this repo.

</div>
