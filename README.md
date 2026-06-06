# Thor Enterprise Project

Governed Agentic Development Platform. Owner/CEO: Sanket Toraskar.

> **Status (2026-06-06): ★ ALL 17 MODULES (12 PRDs) BUILT — every smoke PASSED, every teardown clean. ★**
> Dev setup COMPLETE (WSL2 Ubuntu 26.04, Docker 29.1.3, Python 3.14, git). Build tree at WSL `~/thor-enterprise`.
> **Wall** (sealed room); **Leash** (pre-action governance + one-door egress + kill-switch); **Manager** on real
> Postgres (tamper-evident EventLog + crash-replay + signatures); **Scheduler** (deterministic zero-LLM waves);
> **Contract** (frozen six-message seam); **GovernanceEngine — THE MOAT** (un-fakeable verdict + claim-vs-reality
> lie-detector); **SDLC Stages** (Genesis→Build→QA→Verdict→merge, independent QA); **PM Surface** (cockpit —
> verified signature drives merge, legible refusal); **Mobile** (phone remote head — real E2EE X25519/ChaCha20,
> zero-knowledge relay, no inbound port); **Sentinel** (meta-governance — canary efficacy, integrity crawler,
> silent-heartbeat base case); **Self-Audit Model** (zero-cost read-only inspector — real Postgres RO role,
> system meta-trust, broad eyes/no hands); **Foundation Adapters** (Audit/Identity/Gitea behind Strangler seams —
> real hash-chain tamper-evidence, real Ed25519, real git merge as a peer handshake, swap proven by harness).
> 17 packages · 12 smokes (all green) · ~144 deferred AC tests. **Remaining (not new modules):** the formal
> proving pass (Rule 2) + production-backend swaps (real AGT/Gitea-server/Qwen/UIs — each a single-seam fill-in).
> **If you are resuming after a reboot or a new session: read [SESSION.md](SESSION.md) FIRST.**

## Layout of this folder (durable handoff vault on Windows)
- `SESSION.md` — full state handoff + next steps. **Read first.**
- `docs/` — source-of-truth documents:
  - `THOR-Enterprise-Bible.md` *(user to place here — already exists on their machine)*
  - `THOR-System-Design-Flow.md` *(user to place here — already exists on their machine)*
  - `Windows-Dev-Setup-and-Skeleton.md` — dev-setup runbook + project skeleton + starter code.

## Where the actual build tree lives
Per the locked decision, the Linux build tree (code, Docker, venv) is created in **WSL ext4 at
`~/thor-enterprise`** after the toolchain is verified (Docker via WSL2). This Windows folder is the
durable handoff + docs vault; it is copied into the WSL tree once WSL is ready. See SESSION.md §0.

## The one rule above all (P7)
THOR is built as **ordinary, ungoverned software**. We do not apply THOR's own governance to THOR's
own construction. Build first, smoke-check, defer formal proving. Strict module order (Wall first).
