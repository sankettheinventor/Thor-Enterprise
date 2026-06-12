# THOR Enterprise — Readiness Report (Phase 2.5)

**The one question:** *Can a real company point THOR at their real repository and have an AI agent build a
real feature under governance, safely, today?*

**One-line verdict:** **Production-ready** to govern an AI coding agent building a **Python** feature in a
**single-host, single-commander** deployment — every build runs in a sealed/one-door room, every "done"
is proven against reality, every merge carries a human Ed25519 signature, and a lying or out-of-scope
agent is caught. **Not yet ready** for multi-tenant/RBAC teams, Kubernetes-scale room fleets, non-Python
coverage-of-diff, or a turnkey hosted product — and the **frontier-model** cook is wired but its *live*
run is gated on an OAuth token absent from this sandbox.

All evidence below is reproducible from a clean tree on WSL2 + Docker + Postgres. THOR does not govern its
own build; the moat only ever gets harder.

---

## 1 · The real cook, end-to-end, live (the flow C2 was missing)

A real agent now builds **inside** the room via `BuildStage → CookRunner`, and the GovEngine verdict
judges the result from reality. The control plane never cleans, retries, or supplements the cook's output.

- **One-door egress (C1)** — `tools/qa/prove_cook_onedoor.py`:
  a cook that declares model hosts gets a real `one_door` room (gateway started as its only forwarder).
  `example.com → 200`, `www.google.com → BLOCKED`, **no model-host secret in the room env**.
- **Real-cook build → verdict (C2)** — `tools/qa/prove_c2_realcook.py`, driven through the identical seam:
  - honest build → **`done`**
  - lying stub (claims done, ships `return 0`) → **`not_done`** — caught by **M1+M4 running the real test**
  - out-of-scope write → **`escalate`** — stakes-elevated to require a human signature (never an auto-`done`)

**Honest deferral (named):** the **frontier Claude Code** cook is the *same* `CookRuntime` seam; its *live*
run needs `CLAUDE_CODE_OAUTH_TOKEN` (`claude setup-token`), which is **not present in this CI sandbox**, so
the live frontier run is **deferred, not faked**. The wiring, egress, in-room hook, and verdict are all
proven above with a real (deterministic) agent; swapping in Claude Code is `THOR_COOK=claude-code` + the
token, no code change.

## 2 · The adversarial campaign against a real cook — none earns a false "done"

| Attack | Caught by | Evidence (live) |
|---|---|---|
| Fabricated claim / hollow test | M1 runs the real test; the fake-test discrimination gate guts bodies + re-runs | `prove_c2_realcook.py` (lie), `test_moat_adversarial.py`, `govengine/fake_test.py` |
| Out-of-scope write | **stakes elevation → escalate** (verdict; human signs) + in-room PreToolUse hook (Claude Code) + read-only root (M11) | `prove_c2_realcook.py` (escape), `test_flow_b_out_of_scope_blocked.py` |
| Killed governor (HALT) | Sentinel HALT fails **closed** — Docker-label kill + health verify + alarm | `test_flow_d_governor_halts.py`, `test_finding_bc_halt_failclosed` (9fe5c44) |
| Stale verdict (branch moved) | R9 freshness — merge refused, re-verdict forced | `test_flow_a_stale_verdict_refused` |
| Forged / replayed signature | Ed25519 + registered key + one-time card nonce | `test_flow_e_human_signs` (forged + replayed nonce both rejected) |
| Ledger tamper | SHA-256 hash-chain verify on every read | eventlog chain verify (`make prove`) |
| Chain under concurrency | Postgres `pg_advisory_xact_lock` single-writer | `tools/qa/prove_concurrent_writer` |

Full live campaign: `make prove` (the live lane — real rooms, real Postgres, real attacks: it provisions
rooms, attempts real violations, and passes only if every attack is caught). Gated lane: `make qa` — 59
passed from clean. The 8-attack launch campaign: `make launch`. The three Phase-2.5 proofs above run
green inline (`C1_COOK_ONEDOOR_OK`, `C2_REALCOOK_OK`, `C3_EXTERNAL_REPO_OK`).

## 3 · The external-project proof (C3) + exact manual setup

`tools/qa/prove_c3_external_repo.py` carried **one real change into a SEPARATE "Acme customer" repo**
(`src/greeter.py`) through the full flow: assign_task → real-cook build in the repo's worktree → verdict
`done` → CEO Ed25519 signature (registered key + one-time nonce) → **real git merge into the external
repo's `main`** (`greet` upgraded `hi → Hello, …!`; `feature.merged` in the ledger). **Zero code edits** —
THOR operates on any repo path via `worktree_host_path`.

**The manual setup a real enterprise user performs (no code, env only):**
1. `docker` + `postgres` reachable (the control plane boots Postgres in a container).
2. Pick the cook: `export THOR_COOK=claude-code` + `export CLAUDE_CODE_OAUTH_TOKEN=$(claude setup-token)`
   (or any agent via `THOR_COOK=generic` + `THOR_COOK_IMAGE`/`THOR_COOK_CMD`/`THOR_COOK_ENV_*`).
3. Point at the repo: the feature's `worktree_host_path` = the customer repo (a real git repo the uid-1000
   cook can write).
4. Register the operator (CEO) signing key once: `POST /operator/register`.
5. (Optional) `THOR_GIT_BACKEND=gitea` for live branches/PRs/merges behind the git adapter.
That is the entire footprint — no THOR source change to onboard a new project.

## 4 · The honest NOT-ready list (each with its register row)

| Not yet | Why | Register |
|---|---|---|
| **Frontier-model cook, LIVE** | Wiring/egress/verdict proven with a deterministic real cook; the *live* Claude Code run needs an OAuth token absent from the sandbox. | `C2-realcook` (deferral named) |
| **Multi-commander / RBAC** | One operator key; no per-user roles, no team auth. Single-commander only. | — (scope) |
| **Kubernetes room fleets** | Single-host Docker siblings only; k8s rooms deferred. Concurrency bounded by one host. | — (scope) |
| **Non-Python mechanical verification** | The anti-hollow coverage-of-diff gate is `.py`-only. Now handled **fail-closed**: a non-Python feature ESCALATES for a human signature (it can't earn an auto-`done`), but THOR still can't *mechanically* verify JS/HTML/SQL work — a human must. | `HH-nonpy-coverage` (escalates) |
| **Microsoft AGT backend** | The AGT **policy gate is real and consumed by the Leash**; AGT identity/health/compliance are **representative** stubs (no Azure creds). Real AGT plugs in behind the same Strangler seam at deploy (one-line construction change). | `L1`, `M9` (representative) |
| **Turnkey hosted product** | Operator-run control plane (RUNBOOK), not a managed SaaS; no billing/tenancy. | — (scope) |

## 5 · Verdict

**Production-ready for:** a single team, single commander, governing an AI agent (deterministic today;
frontier with a token) to build and merge **Python** features into **their own repository**, on one Docker
host, with every action judged before it runs, every "done" proven against reality, and every merge
human-signed.

**Not-yet-ready for:** multi-tenant/RBAC teams, Kubernetes-scale fleets, non-Python coverage enforcement,
a live frontier cook without an operator-supplied token, or a hosted SaaS. None of these are faked — each
is a named, tracked register row, and the moat holds for everything inside the ready envelope.
