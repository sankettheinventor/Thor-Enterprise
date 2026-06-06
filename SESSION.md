# THOR Enterprise — SESSION HANDOFF (read me first)

**Purpose:** This file preserves all project state across a Windows reboot and across the
move from the Windows session (`C:\Users\sanke`) to the WSL session (`~/thor-enterprise`).
If you are a fresh Claude Code session, **read this entire file before doing anything.**

**Last updated:** 2026-06-06 (just after `wsl --install`, BEFORE the required reboot).

---

## ⚠️ CRITICAL OPERATING NOTE — THE USER IS NOT A CODER

- Give **every command exactly, copy-paste-ready, one step at a time** — no placeholders the user
  must fill in unless clearly marked, no "do X or Y", no assumed prior knowledge.
- After each command, **state plainly what they should see** so they can confirm success vs failure.
- **Never guess.** If a command could go wrong or depends on an unknown, ASK first (rule #9).
- Prefer a single correct command over several options. Walk, don't sprint.
- The user will **paste the Bible + System Design docs** themselves after reboot (do not transcribe).
- The Windows folder `C:\dev\Project\Thor Enterprise Project` exists ONLY to survive the reboot so we
  don't restart from zero. The **real build tree is WSL `~/thor-enterprise`** (locked decision).

---

## 0. WHERE WE ARE RIGHT NOW (current state)

- Project: **THOR Enterprise** — a Governed Agentic Development Platform. CEO/owner: Sanket Toraskar.
- **Dev setup COMPLETE (2026-06-06):** WSL2 **Ubuntu 26.04** (user `sanket`), **Docker Engine 29.1.3**
  (native, no-sudo, systemd), **Python 3.14.4**, **git 2.53.0**. Checkpoints A–D all passed.
- **Build tree live** at WSL `~/thor-enterprise` (git repo + `.venv`), with `docs/` + read-only
  `_reference/` copied in. Editor workflow chosen: **VS Code connected to WSL** (not yet opened).
- **Module 1 (Wall) PRD received** → `docs/PRD-Module-1-Wall.md`. **Module 1 SCAFFOLDED** (ungoverned,
  P7): `wall/` (all six sub-modules + `api.py` + `config.py`), `adapters/` (Gitea+AGT stubs),
  `tests/wall/` (AC-1..AC-12 deferred/skipped), `tools/arch_lint.py` (passes). Syntax-checked; arch-lint green.
- **Smoke-check PASSED (2026-06-06):** `tools/smoke_ac1_ac2.py` ran for REAL — image built, sealed room
  provisioned (`network_disabled=True`, `sealed:True`, Ed25519 token), in-room network attempt FAILED
  (`OSError [Errno 101] Network is unreachable`), cook made a real commit (host-verified SHA match
  `2f800762`), room destroyed, branch persisted. **HEADLINE AC-1 + AC-2 = PASS.** Deps installed in `.venv`.
  Caveats (no overclaim): the "cook" was git driven via `docker exec` (stand-in; autonomous agent-server is
  M2+); AC-2 is the sealed-shut form (`:8001` one-door is M2). This was a ONE-TIME demonstration, NOT the
  formal AC-1..AC-12 proving suite (still deferred, Rule 2; `tests/wall/` stays skipped).
- Also fixed during review: a liveness bug (ENTRYPOINT bash + `command="sleep infinity"` would exit) →
  now `command=["-c","sleep infinity"]`.
- **Module 2 (Leash) PRD received** → `docs/PRD-Module-2-Leash.md`. **Decisions (2026-06-06):**
  stub AGT / keep Rule 5 (THOR-native policy now, Microsoft AGT plugs into `adapters/agt_adapter.py`
  at M12); build **governance core first** (Phase 2a).
- **Module 2 Phase 2a BUILT + smoke PASSED (2026-06-06):** `leash/` (proxy 2.1, inspector 2.2,
  policy 2.5, decision 2.7, escalation 2.8, credentials 2.6) + upgraded AGT adapter. `tools/smoke_leash.py`
  ran for REAL: out-of-scope write DENIED before execute (file absent), fail-closed when governor down,
  escalate+hold on dependency add, 5 signed hash-chained events (`verify_chain=True`), frozen policy
  immutable. **HEADLINE (governs + fails safe + audits) = PASS.** Caveats: "cook" is a stand-in calling
  the proxy in-process; this is a demo, NOT the formal AC suite (deferred, `tests/leash/` skipped).
- **Module 2 Phase 2b COMPLETE + smoke PASSED (2026-06-06):** the one-door egress lock. Realized via
  Docker network TOPOLOGY (decision, flagged Rule 9): `thor-room-net` (`--internal`, no internet) +
  `thor-egress-net` + a dual-homed **leash gateway** (`leash/gateway_proxy.py`, stdlib) as the room's
  ONLY forwarder — same P4 invariant as the PRD's iptables recipe, but no sudo (host iptables needs an
  interactive password we can't supply) and robust on WSL. `tools/smoke_leash_2b.py` ran for REAL:
  direct-to-internet bypass BLOCKED (URLError, no route), proxied non-allowlisted host DENIED 403
  (Layer B), allowlisted upstream forwarded OK, upstream cred NEVER in room env, malicious tool →
  kill-switch terminated the room. Clean teardown (no orphan containers/networks). **AC-5 + AC-6 + AC-9
  = PASS.** Files: `leash/gateway_proxy.py`, `leash/gateway.py`, `leash/security.py`, `leash/inspector.py`
  (Layer B), `wall/network_enforcer.py` (one-door funcs), `wall/provisioner.py` (`network_mode="one_door"`).
  Deferred refinements (noted, not blocking): TLS-terminating/CONNECT egress inspection, real CEO-card
  escalation flow, AGT-upgrade test (AC-12) — all land with Module 12 / the dashboard.
- **Module 3 (THOR Manager) PRD received** → `docs/PRD-Module-3-Manager.md`. **Decision (2026-06-06):**
  REAL Postgres for [ThorDB] + the EventLog (per the user, not file-based). The Leash now records THROUGH
  the Manager (FR-2 single writer).
- **Module 3 BUILT + smoke PASSED (2026-06-06):** `manager/` (pg, db, eventlog, core, api). Backed by a
  real **postgres:16-alpine** container + **psycopg 3.3.4**. `tools/smoke_manager.py` ran for REAL
  (2 real rooms provisioned via the Wall): **ALL 11 criteria PASS** — headline **AC-2** (tamper-evident
  signed chain: editing a past row → `verify_chain=False`) + **AC-3** (kill Manager → replay log →
  `rebuilt_matches=True`); plus AC-1 (Leash→Manager single writer), AC-4/5 (signature gate + forged
  rejected), AC-7 (fail-closed), AC-8 (bad identity), AC-9 (one-branch-one-room), AC-10 (health),
  AC-11 (held card), AC-12 (idempotent). Clean teardown (rooms + Postgres removed).
  Fixed during the run: a real deadlock — `autocommit=False` left read-txns holding locks → `TRUNCATE`
  during replay blocked forever; now `autocommit=True` (single-writer chain serialized in-process).
  Stubbed pending later modules: 3.6 Verdict Coordinator (M6), 3.7 real Gitea merge (M12); AC-6 deferred.
- **Module 4 (Scheduler) PRD received** → `docs/PRD-Module-4-Scheduler.md`. **Choices (PRD-permitted, no
  conflict):** tiny custom DAG (no networkx) + stubbed CTO (`scheduler/cto_stub.py` — the only place a
  planning call happens; the Scheduler makes zero LLM calls).
- **Module 4 BUILT + smoke PASSED (2026-06-06):** `scheduler/` (graph, core, cto_stub, api).
  `tools/smoke_scheduler.py` ran for REAL — **ALL 12 ACs PASS** + real-Manager integration: headline
  **AC-1** (byte-identical schedule on re-run) + **AC-2** (zero planning calls while scheduling); plus
  AC-3 (deps respected), AC-4 (capacity cap+queue), AC-5 (dry-run zero provisioning), AC-6 (budget halt),
  AC-7 (same order cap3==cap10), AC-8 (re-work no dep re-run), AC-9 (Genesis-first), AC-11 (cycle rejected),
  AC-12 (replay). **Part B real Manager:** Scheduler dispatched 2 real rooms (CTO made the 2 planning
  calls, not the Scheduler); restarted Scheduler rebuilt running-state from the Manager registry and
  refused to double-dispatch (**AC-10**). Clean teardown. First-try pass (pure-logic module, low risk).
- **Module 5 (Task Handoff Contract) PRD received** → `docs/PRD-Module-5-Contract.md`. **Choices
  (PRD-permitted):** Pydantic schemas (`extra="forbid"`) + TWO transports (docker-exec v1 + in-process/REST
  v1.1) to actually demonstrate transport-swappability.
- **Module 5 BUILT + smoke PASSED (2026-06-06):** `contract/` (messages, slice_builder, transport, seam).
  `tools/smoke_contract.py` ran for REAL — **ALL 12 ACs PASS** + real-room/Manager integration: headline
  **AC-2** (real room `/task/feature.json` = one feature F047, no catalog) + **AC-4** (structural P5 —
  `claim_done` has NO verdict field; a room cannot issue `result_decision`); plus AC-1 (only six messages),
  AC-3 (slice read-only write fails), AC-5+AC-12 (same suite over in-process AND docker-exec — transport
  swap, no logic change), AC-6 (malformed rejected), AC-7 (amend authority), AC-8 (idempotent claim → one
  verdict), AC-9 (version mismatch), AC-10 (no creds/catalog leak), AC-11 (messages in EventLog). Clean
  teardown. First-try pass. The Leash/Manager already-informal seam is now formalized + frozen.
- **Module 6 (Development-Governance Engine) PRD received** → `docs/PRD-Module-6-GovEngine.md`. THE MOAT.
  **Fidelity:** real git ground-truth (local-git stub), real test EXECUTION (machine runs verifier/regression),
  real EventLog audit scan (R2/R3), contract from slice; R1 (CTO skills) stubbed; real Gitea CI = M12.
  No LLM in the verdict (FR-16). Added git helpers to `adapters/gitea_adapter.py` (commit_sha, diff_files, head_sha).
- **Module 6 BUILT + smoke PASSED (2026-06-06):** `govengine/` (reality, fake_test, probes, divergence,
  panel, engine, api). `tools/smoke_govengine.py` ran for REAL (real git repos + real test runs + Postgres) —
  **ALL 12 ACs + happy-path PASS.** Headline **AC-2** (fabricated claim caught by divergence) + **AC-8**
  (git unreadable → escalate, never false done) + **AC-12** (adversarial fake-test/fabricated-claim/gamed-gate
  suite cannot get a done). Plus AC-1 (M3 blocker), AC-3 (hollow fake test), AC-4 (conflict→escalate),
  AC-5 (read-only), AC-6 (deterministic), AC-7 (freshness), AC-9 (canary not_done), AC-10 (high-stakes→sig),
  AC-11 (12 verdict + 7 divergence signed events). Clean teardown.
  Fixed during the run: (1) an honest claim must list ALL touched files or divergence flags undisclosed
  changes (the engine caught my own incomplete test claim); (2) panel now always reports true stakes level.
- **THE BUILD-ORDER STUB GATE IS GONE.** "always approve" is replaced by real, un-fakeable judgment (per
  the PRD build-order note). The verdict engine's done is now the authoritative `result_decision` (M5).
- **Module 7 (SDLC Stages) PRD received** → `docs/PRD-Module-7-SDLC.md`. The moat surface — typed stages
  on one anatomy, skill composition (floor+specialty), governed transitions, three signature gates.
  Added a `bugs` table + `append_bug`/`list_bugs` to the Manager (M3) for QA/Checker findings.
- **Module 7 BUILT + smoke PASSED (2026-06-06):** `sdlc/` (skills, anatomy, stages, transitions, bridge,
  api). `tools/smoke_sdlc.py` ran the FULL lifecycle for REAL (Postgres + real Build/QA/Checker rooms +
  the M6 engine) — **ALL 12 ACs PASS, first run.** Headline **AC-2** (QA room ≠ Build room, fresh instance)
  + **AC-3** (independent QA wrote a NEW edge test `edge_discount_zeros`, caught a hidden ZeroDivisionError
  the plan never specified). Plus AC-1 (no skip-QA), AC-4 (bugs in DB), AC-5 (Sig1 gate), AC-6 (Sig2 ticket),
  AC-7 (checker read-only + findings), AC-8 (floor skills), AC-9 (new UX-audit stage no regression),
  AC-10 (capability-gap card, no silent skill add), AC-11 (bounded loop → escalate), AC-12 (three sigs:
  good feature → verdict done → Sig3 merge). Clean teardown. Cook + QA intelligence are deterministic
  stand-ins (no LLM); the structure (independence, skills, transitions, signatures) is real.
- **"IS IT DONE?" NOW HAS THREE WITNESSES:** the agent's claim (untrusted), the mechanical 8-probe verdict
  (M6), and the independent adversarial QA agent (M7). The full Genesis→Build→QA→Verdict→merge lifecycle runs.
- **Module 8 (PM Surface) PRD received** → `docs/PRD-Module-8-PMSurface.md`. The human cockpit. **Decision
  (flagged Rule 9):** PRD specifies a JS/TS React frontend, but this env has no Node + a SPA isn't
  smoke-testable → built the substantive **Python DashboardAPI + cockpit logic** (testable) + a minimal
  static `dashboard/cockpit.html`; the full React presentation layer is DEFERRED (pure UI over the same API).
  Extended the Manager (M3) `features` table (title/context/priority/est_tokens) + `add_feature`/
  `set_feature_status`/`list_features`/`list_checker_findings`.
- **Module 8 BUILT + smoke PASSED (2026-06-06):** `dashboard/` (legible, kanban, cost, audit, service,
  dashboard_api, cockpit.html). `tools/smoke_pmsurface.py` ran for REAL (Postgres + Manager + Scheduler +
  real Checker room) — **ALL 12 ACs PASS, first run.** Headline **AC-2** (verified Ed25519 sig drives a real
  merge; forged rejected) + **AC-3** (legible refusal in plain language) + **AC-6** (disconnected → signing
  disabled, never stale-as-live). Plus AC-1 (kanban + scheduler pickup), AC-4 (read-only logs, no room
  mutation), AC-5 (no authoritative state — a window not a brain), AC-7 (cost/caps/alert/dry-run),
  AC-8 (three signature cards held), AC-9 (audit feed + CSV/JSON export), AC-10 (checker findings match DB),
  AC-11 (operator actions recorded), AC-12 (one decision across heads — idempotent). Clean teardown.
- **THOR HAS A HUMAN FACE.** Direct → Watch → Decide → Audit, all read-and-sign over the one Manager.
- **Module 9 (Mobile / Remote) PRD received** → `docs/PRD-Module-9-Mobile.md`. The phone as a remote head.
  **Decisions (flagged Rule 9):** the postman/Cloudflare bridge is rebuilt CLEAN (`_reference` read-only,
  Rule 10); the mobile app UI is DEFERRED (no Node; not smoke-testable) — built the security-critical
  substance instead.
- **Module 9 BUILT + smoke PASSED (2026-06-06):** `mobile/` (crypto, relay, bridge, allowlist,
  phone_client). REAL E2EE = X25519 + ChaCha20-Poly1305 (cryptography lib). `tools/smoke_mobile.py` ran
  for REAL (Postgres + Manager + M8 DashboardService + E2EE bridge + phone stand-in) — **ALL 12 ACs PASS,
  first run.** Headline **AC-1** (merge signed from phone, Manager-verified, merges) + **AC-2** (relay
  zero-knowledge: ciphertext only, byte-flip forgery fails AEAD) + **AC-3** (no inbound port — dials out).
  Plus AC-4 (non-allowlisted rejected+logged), AC-5 (one-sentence legible), AC-6 (no double-resolve),
  AC-7 (disconnect disables signing), AC-8 (bound-sig replay rejected), AC-9 (device revocation),
  AC-10 (phone actions audited like desktop), AC-11 (no room reach/rule change), AC-12 (consistent card).
  Clean teardown.
- **PILLAR 4 COMPLETE — human command from desktop OR phone, over one Manager truth.** Pillars 1–4 all stood up.
- **Module 10 (Sentinel) PRD received** → `docs/PRD-Module-10-Sentinel.md`. Meta-governance (P9), the
  governor of the governor. **Decision (Rule 9/Rule 5):** AGT SRE + Runtime stay STUBBED until M12; the
  THOR-specific efficacy (canary, integrity, loadedness, reconcile, boot self-test, silent-heartbeat) built real.
- **Module 10 BUILT + smoke PASSED (2026-06-06):** `sentinel/` (integrity, canary, reconcile, core, api).
  `tools/smoke_sentinel.py` ran for REAL (Postgres + Manager + real Leash policy canary + a real shadow
  container) — **ALL 12 ACs PASS, first run.** Headline **AC-1** (dead leash → fail-closed) + **AC-2**
  (a passing canary on a broken policy → alarm+halt) + **AC-7** (Sentinel's own death caught by the
  silent-heartbeat base case). Plus AC-3 (hung≠responsive), AC-4 (rule-tamper CRAWLER_ALARM), AC-5
  (unloaded floor skill fail-closes), AC-6 (failed boot blocks startup), AC-8 (proportionate halt
  room-vs-system), AC-9 (Sentinel decides on Self-Audit URGENT; cheap model never halts directly),
  AC-10 (shadow discovered + orphan reaped via real Docker reconcile), AC-11 (maintenance scoped+bounded+auth),
  AC-12 (chaos pages every failure class). Clean teardown.
- **THE GOVERNOR IS ITSELF GOVERNED — THOR cannot be silently broken, down to the watcher.**
- **Module 11 (Self-Audit Model) PRD received** → `docs/PRD-Module-11-SelfAudit.md`. The "understanding eyes."
  **Decisions (Rule 9):** the local Qwen is a DETERMINISTIC stand-in behind a Toras-ready `InspectionModel`
  seam (no Ollama; zero frontier calls); read-only enforced FOR REAL by a Postgres `selfaudit` role.
- **Module 11 BUILT + smoke PASSED (2026-06-06):** `selfaudit/` (db, model_host, inspector, metatrust,
  escalate, core, api). `tools/smoke_selfaudit.py` ran for REAL (real read-only Postgres role + Manager
  EventLog + the real Sentinel) — **ALL 12 ACs PASS, first run.** Headline **AC-1** (zero token cost,
  frontier_calls=0) + **AC-3** (EventLog write DENIED by Postgres permissions — broad eyes, no hands) +
  **AC-4** (severe anomaly escalated URGENT to the Sentinel; SelfAudit has no enforce method). Plus AC-2
  (reports+meta-trust in DB), AC-5 (not-on-critical-path + absence alarmed), AC-6 (system-trust not
  agent-trust), AC-7 (false-positive → Sentinel note, no wrongful halt), AC-8 (retro/benchmark zero
  frontier), AC-9 (Sentinel watches it), AC-10 (findings persist across restart), AC-11 (resource-bounded),
  AC-12 (Toras-ready seam). Clean teardown.
- **THE THREE HEALTH LAYERS COMPLETE: Sentinel (reflexes) + Self-Audit (eyes) + Human (judgment).**
- **Module 12 (Foundation Adapters) PRD received** → `docs/PRD-Module-12-Adapters.md`. The Strangler substrate.
  **Decision (Rule 9/Rule 5):** real Microsoft AGT (Public Preview, Azure-dep) + a live Gitea server are the
  PRODUCTION backends; in this bootstrap env the three THOR-owned adapters are backed by the REAL equivalents
  already built — M3 hash-chain (audit), M1/M3 Ed25519 (identity), REAL local git (the PRD-sanctioned
  local-git backend) for Gitea. The SEAMS (the actual THOR work) are 100% real + arch-lint-enforced; the
  Substitution Harness proves the swap with a 2nd backend.
- **Module 12 BUILT + smoke PASSED (2026-06-06):** `adapters/` (contract, audit_adapter, identity_adapter,
  compliance, catalog_bridge, gitea_adapter completed, substitution). `tools/smoke_adapters.py` ran for REAL
  (real hash-chain tamper + real Ed25519 + real git merge + real room env inspect) — **ALL 12 ACs PASS.**
  Headline **AC-1** (arch-lint: no AGT/Gitea type leaks) + **AC-2** (force-edited past row → chain detects it)
  + **AC-7** (same THOR flow merges on local-git AND a GitHub stub — swap touches one file). Plus AC-3
  (SOC2 evidence traces to chain), AC-4 (identity verify/forge/revoke), AC-5 (3 signatures + replay reject),
  AC-6 (REAL git merge only after verified Sig 3 — peer handshake), AC-8 (version bump absorbed), AC-9/AC-10
  (fail-closed audit/identity), AC-11 (no creds in room env), AC-12 (no per-agent scoring).
  **One real bug caught + fixed (Rule 11):** ci_result compiled a file deleted relative to the branch →
  fixed to --diff-filter=AM (added/modified only). Clean teardown.
- **★★★ ALL 17 MODULES (12 PRDs) BUILT — EVERY SMOKE GREEN, EVERY TEARDOWN CLEAN, EVERY PRD PRESERVED. ★★★**
  THOR Enterprise structural build COMPLETE: isolation (Wall) → governance (Leash/Manager/Scheduler/Contract/
  GovEngine) → SDLC → human command (PM Surface + Mobile) → meta-governance (Sentinel + Self-Audit) →
  foundation adapters (Audit/Identity/Gitea, Strangler-swappable). 17 packages, 12 smokes, ~144 deferred AC tests.
- **WHAT REMAINS (not structural build):** the deferred FORMAL proving pass (Rule 2 — turn the ~144 skipped
  pytest ACs into gated tests); the production-backend swaps (real AGT pip + live Gitea server + Ollama/Qwen +
  React/mobile UIs) — each is a single-adapter/single-seam fill-in, by design. No new modules remain.

### Immediate next steps (ORIGINAL setup list — all DONE; kept for history)
1. **Reboot Windows** (if not already done).
2. After reboot, Ubuntu should auto-launch and ask for a **Unix username + password**.
   - If it does NOT auto-launch: open the **Ubuntu** app from Start, or run `wsl --install -d Ubuntu`.
   - **WRITE THE CHOSEN UBUNTU USERNAME INTO SECTION 6 BELOW** (it's currently UNKNOWN and blocks path rendering).
3. **Checkpoint A:** `wsl -l -v` → confirm Ubuntu is listed, **VERSION 2**, STATE Running.
4. **Checkpoint B:** in Ubuntu shell: `docker run hello-world` → confirm Docker works.
   - Uses native **Docker Engine (`docker.io`) inside Ubuntu**, systemd-managed (NOT Docker Desktop).
   - Setup: `sudo apt install -y docker.io` · `sudo systemctl enable --now docker` ·
     `sudo usermod -aG docker $USER` · then `wsl --shutdown` + reopen so the docker-group change applies.
5. **Checkpoint C:** in Ubuntu shell:
   `python3 --version` (want 3.11+) · `git --version` · `sudo apt update && sudo apt install -y python3-venv python3-pip`
6. **Checkpoint D:** create the real build tree IN WSL:
   ```bash
   mkdir -p ~/thor-enterprise && cd ~/thor-enterprise
   git init
   python3 -m venv .venv && source .venv/bin/activate
   ```
   then `pwd && ls -la && git status`.
7. **Reopen in VS Code connected to WSL** (`code .` from `~/thor-enterprise`) so the terminal + Claude Code run natively in Linux. (Open question — see Section 6.)
8. **Copy this handoff + docs into the WSL tree:** copy `C:\dev\Project\Thor Enterprise Project\*`
   into `~/thor-enterprise/` (so SESSION.md and docs/ live with the code).
9. **Copy the reference source:** copy `C:\dev\thor2 - Copy` → `~/thor-enterprise/_reference/` (read-only study material).
10. Only THEN, when the user pastes the **Module 1 (Wall) PRD**, start BUILDING the Wall (not proving it).

---

## 1. PROJECT IDENTITY

THOR is a platform that lets a human direct multiple AI coding agents to build software in
parallel, where every agent works in a sealed environment it cannot escape, every action is
judged *before* it happens against rules the agent cannot touch, and nothing reaches the real
codebase without a governance gate + a human signature.

Two source documents are the source of truth (place them in `docs/` — see Section 7):
- **THOR-Enterprise-Bible.md** — principles (P1–P9), 4 pillars, 17 modules, build order, decisions.
- **THOR-System-Design-Flow.md** — topology, ports, end-to-end flow, API sequences, data model.

---

## 2. THE 11 PROJECT RULES (these OVERRIDE default behavior — never violate)

1. **Build ungoverned (P7).** THOR is ordinary software during its own construction. Do NOT apply
   THOR's own governance/leash/verdict to THOR's own codebase. (Original THOR died from governing
   its own construction.)
2. **Build, don't prove.** Smoke-check as you go. Write AC tests into `tests/` but DO NOT gate
   progress on them. Confirm code runs; defer formal proving until THOR is whole. Keep moving.
3. **Strict build order:** Wall → Leash → Manager → Scheduler → Contract → GovEngine → SDLC →
   PMSurface → Mobile → Sentinel → SelfAudit → Adapters. No jumping to the moat. The Wall ships
   **network-sealed (`network_disabled`)**; the one-door rule arrives with the Leash (Module 2).
4. **Adapter discipline.** AGT only in `adapters/agt_adapter.py`; Gitea only in
   `adapters/gitea_adapter.py`. Nowhere else. Everything else speaks THOR vocabulary. Add an
   **architecture-lint** that FAILS the build if AGT/Gitea is imported outside its adapter.
5. **Stub externals (Modules 1–11).** Local-git stand-in for Gitea, always-allow+log stub for
   leash/AGT, minimal local Ed25519 signer for identity. Real AGT+Gitea wiring is **Module 12**.
6. **Environment: WSL2/Ubuntu ONLY.** Linux paths, bash, Docker via WSL integration. NEVER generate
   PowerShell or Windows-style paths in project code.
7. **Single source of truth.** ONLY the Manager writes the EventLog and owns the room registry.
   No other module keeps a competing room list or state store. Recording goes through the Manager.
8. **Structure mirrors the PRDs.** Folders/files match the module map and sub-module names
   (e.g. `wall/network_enforcer.py` = sub-module 1.3).
9. **Reference the PRD; flag drift.** Build against the PRD's FRs + checklist. If a requirement
   seems wrong, or you're about to make an architectural decision NOT in the PRD, STOP and ASK.
   Do not silently diverge or guess.
10. **Original THOR = read-only `_reference/`.** Mine doctrine, NEVER import from it, NEVER extend
    it, rebuild clean. (It failed by accretion in one 6,000-line file. Do not repeat.)
11. **Don't run anything without being asked; don't fake results.** No invented test passes,
    claims, or bugs. The user is emphatic: "do not run anything, dont show fake result, claims and bugs."

---

## 3. DECISIONS MADE (locked for this setup)

- **Project location:** WSL2 ext4 → `~/thor-enterprise` (Linux-native, fast Docker). NOT `/mnt/c`.
  - (The Windows folder `C:\dev\Project\Thor Enterprise Project` is only a durable handoff/docs vault.)
- **Toolchain:** was NOT set up → doing the one-time dev setup first (Section 0).
- **Reference source:** COPY `C:\dev\thor2 - Copy` → `~/thor-enterprise/_reference/` (read-only).
- **Docker delivery:** native **Docker Engine (`docker.io`) inside Ubuntu**, managed by systemd —
  NOT Docker Desktop (decided 2026-06-06 with the user; lighter, Linux-native, no Windows GUI app).
  The docs' "Docker Desktop + WSL Integration" instructions are superseded by this.

---

## 4. BUILD ORDER & MODULE MAP (skeleton to create in WSL, Section 5)

Strict order (do not jump ahead):
Wall(1) → Leash(2) → Manager(3) → Scheduler(4) → Contract(5) → GovEngine(6) → SDLC(7) →
PMSurface(8) → Mobile(9) → Sentinel(10) → SelfAudit(11) → Adapters(12).

**Day-one focus:** `wall/` — get a cook into a sealed container that makes a real commit.
Wall network = **sealed shut** (`network_disabled=True`) for now; one-door proxy arrives with Leash.

---

## 5. PROJECT SKELETON (create this under ~/thor-enterprise in WSL)

```
thor-enterprise/
├── README.md
├── docker-compose.yml          # local control plane (filled in as modules land)
├── pyproject.toml              # Python control-plane deps
├── .env.example                # config (never commit real secrets)
├── SESSION.md                  # this handoff (copied in)
├── docs/                       # Bible + System Design + setup docs
├── _reference/                 # read-only copy of original THOR (thor2). NEVER import.
│
├── wall/                       # Module 1 — the sealed container (BUILD FIRST)
│   ├── image/Dockerfile        # room OCI image (cook runtime, skill-loader)
│   ├── provisioner.py          # create container: mounts, limits, task_type
│   ├── network_enforcer.py     # sub-module 1.3 — one-door egress lock (stub until Leash/M2)
│   ├── mount_manager.py        # ro/rw mounts (incl. checker read-only)
│   ├── lifecycle.py            # create / health / destroy
│   └── identity_stamper.py     # Ed25519 room token (local signer stub)
│
├── leash/        # Module 2 — pre-action interception (AGT adapter lives in adapters/)
├── manager/      # Module 3 — single brain + EventLog writer + registry
├── scheduler/    # Module 4 — deterministic task-graph executor
├── contract/     # Module 5 — frozen six-message interface + slice
├── govengine/    # Module 6 — 8-probe verdict (THE MOAT)
├── sdlc/         # Module 7 — typed stages (genesis/checker/build/qa)
├── pmsurface/    # Module 8 — kanban/cards/audit (JS/TS web UI)
├── mobile/       # Module 9 — phone bridge (extend postman + Cloudflare)
├── sentinel/     # Module 10 — meta-governance health
├── selfaudit/    # Module 11 — zero-cost Qwen inspector
├── adapters/     # Module 12 — ONLY place AGT/Gitea are imported
│   ├── agt_adapter.py          # ONLY file importing AGT
│   └── gitea_adapter.py        # ONLY file importing Gitea
│
└── tests/                      # PROVING suite — written alongside, RUN at the end (deferred)
    └── wall/                   # AC-1..AC-12 for the Wall (deferred proving)
```

**Starter code already provided by the user** (reproduce when scaffolding the Wall):
- `wall/provisioner.py` — minimal provisioner: `build_image()`, `provision_room(task_type, feature_slice,
  worktree_host_path, cpu, mem)`, `destroy_room(room_id)`. Uses `docker` SDK. Key choices already set:
  `network_disabled=True`, task slice mounted READ-ONLY at `/task/feature.json`, worktree RW at `/work`,
  `user="cook"`, `cap_drop=["ALL"]`, `security_opt=["no-new-privileges"]`, mem/cpu caps, thor.* labels.
- `wall/image/Dockerfile` — `python:3.11-slim` + git + unprivileged `cook` user (uid 1000), WORKDIR `/work`,
  ENTRYPOINT `/bin/bash`. One image, four task_types.
(Both are reproduced verbatim in docs/Windows-Dev-Setup-and-Skeleton.md.)

---

## 6. OPEN QUESTIONS TO RESOLVE WITH THE USER (before/at build start)

- [x] **Ubuntu username = `sanket`** (resolved 2026-06-06). Home = `/home/sanket`; editor path =
      `\\wsl$\Ubuntu\home\sanket\thor-enterprise`. NOTE: the first `wsl --install` only installed the
      WSL *platform*; the Ubuntu *distro* was a separate `wsl --install -d Ubuntu` step done afterward.
- [ ] **Workflow:** reopen in VS Code connected to WSL (recommended), or drive WSL from a Windows
      PowerShell session via `wsl bash -c "..."`? (User to decide.)
- [x] **Module 1 (Wall) PRD RECEIVED** (2026-06-06). Saved verbatim to `docs/PRD-Module-1-Wall.md`
      (FR-1..FR-18, AC-1..AC-12, six sub-modules 1.1–1.6, one-door model, REST API §6.1). Building MAY
      now begin per the build-order law — **gate stubbed "always approve"; build ungoverned (P7); do NOT
      prove/gate progress; smoke-check only.** Headline day-one milestone = **AC-1 + AC-2**.

---

## 7. SOURCE DOCS (place the two .md files the user already has into docs/)

The user already possesses these as files (named exactly):
- `THOR-Enterprise-Bible.md`
- `THOR-System-Design-Flow.md`

**Action for next session:** ask the user to drop those two files into
`~/thor-enterprise/docs/` (or `C:\dev\Project\Thor Enterprise Project\docs\` pre-move).
A third doc, `docs/Windows-Dev-Setup-and-Skeleton.md`, has been written with the dev-setup
runbook + starter code, so it survives independently.

---

## 8. HOW THE NEXT SESSION SHOULD GREET THE USER

"Welcome back. Per SESSION.md we just finished `wsl --install` and were waiting on the reboot.
Did the reboot complete and did you set up the Ubuntu user? What username did you pick? Then
let's run Checkpoints A–D." — Then continue from Section 0 step 3.

*End of SESSION.md handoff.*
