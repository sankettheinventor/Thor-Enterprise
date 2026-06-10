# THOR Enterprise — GAP & RISK REGISTER

**Date:** 2026-06-06 · **Method:** static read-only code audit (no code was run for this register) · **Scope:** all 12 module packages + cross-cutting wiring · **Evidence:** every claim cites `file:line` in the WSL tree `~/thor-enterprise`.

> This is the brutally-honest map the proving pass will work from. It deliberately *understates nothing*. The smokes are all green, but a green smoke proves only what the smoke wired — and almost every smoke wired the modules together **in-process** and exercised them against **deterministic stand-ins**. Where a guarantee holds only in a smoke, or only against a stub, this register says so.

---

## 0. Executive summary — the three things you must internalise

1. **THOR has never been assembled into a running system.** Every module ships a FastAPI `app`, but `uvicorn …:app` appears *only in docstrings*; `docker-compose.yml` has `services: {}` (empty); no product `__main__` boots a control plane; no module calls another module's HTTP API. **Every integration in the entire codebase happens in-process inside `tools/smoke_*.py`.** The "service mesh on ports :7100/:7080/:7140/…" described in the PRDs is documented shape, not running wiring. *(Evidence: `docker-compose.yml:10`; `sentinel/api.py:4` uvicorn-in-docstring; grep finds no `httpx`/`requests` cross-module calls.)*

2. **The components are mostly real and individually correct — but several headline guarantees are decorative or stand-in-only in product.** Real: the SHA-256+Ed25519 hash-chain, Docker room lifecycle, X25519/ChaCha20 E2EE, local-git ops, the read-only Postgres role, the verdict's real git reads and real subprocess test runs. Not real in product: the Leash never actually intercepts a cook's actions; the Sentinel's `halt()` kills nothing (appends a dict); the audit/identity "adapters" are bypassed by the modules they claim to back; the cook and QA "brains" are deterministic stand-ins.

3. **The moat (GovEngine) is genuinely un-fakeable against a lying *self-report* — but its strength today rests on three props that a real adversary or a real wiring would remove:** a regex-level fake-test check an LLM can evade, an `R1` probe hardcoded `True`, and a *trusted caller* for `claim`/`contract`/`commit_window` that **does not exist yet** (`manager.run_verdict` is `NotImplementedError`). A lazy/dishonest caller that passes `claim={}` silently disables the lie-detector.

**One-line verdict:** *A library of mostly-real, individually-smoked parts — not yet an assembled, wired, enforcing system. The proving pass is not just "turn ~144 skipped ACs green"; it must also wire the seams and re-test the guarantees that currently only hold in-process against stand-ins.*

---

## 1. Severity-ranked risk register

| # | Sev | Risk | Where it bites | Evidence |
|---|---|---|---|---|
| ~~**C1**~~ | ✅ **CLOSED** (Task 3, 2026-06-08) | **Leash wired into the cook path.** BuildStage now routes every cook write THROUGH `InRoomProxy.handle_tool_call` BEFORE it executes: the CTO sets plan-owned scope at task-start (deny-all if undeclared), the room is sealed with a FrozenPolicy loaded HOST-SIDE (never into the room), allow→written / deny→never created / manifest→escalated+held, every decision recorded via the Manager (one ledger), fail-closed if the governor is down. | — | wired: `sdlc/stages.py` BuildStage.run (proxy + `agt_adapter.load_policy`); `scheduler/cto_stub.py` (plan-owned `scope_files`, deny-all default). Proven: `tests/integration/test_flow_b_out_of_scope_blocked.py` (in-scope allowed, out-of-scope/forbidden never on disk, manifest held, governor-down denied, every decision in the ledger) + Leash ACs `tests/leash` AC-1/2/3/4/7/11. §7b `policy.py`/`proxy.py`/adapter/inspector untouched |
| ~~**C2**~~ | ✅ **CLOSED** (Task 0, 2026-06-07) | **Run target wired.** One control-plane process constructs the roles as peers sharing one ledger (manual boot order) and serves the four surfaces `:7100/:7080/:7140/:7150`; the dashboard renders live state. Proven by a cold-start + separate-process HTTP probe of all four ports. *(Decision flow — decide-before, dispatch, verdict, merge, real halt, Sign button — still wired in T1–T10.)* | — | wired: `tools/start_thor.py:65` `boot()` (role peers), `:121` `serve()` (4 uvicorn servers), `:109` (cockpit mount); `docker-compose.yml` (Postgres); `docs/RUNBOOK.md` (one start command) |
| ~~**C3**~~ | ✅ **CLOSED** (Task 8, 2026-06-08) | **`halt()` physically enforces.** A confirmed halt now destroys the affected rooms (`manager.destroy_room`) and — for a systemic fault — sets `halted` so `manager.provision_room` REFUSES all new work; proportionate (a `room:`/non-systemic component halts the smallest scope, a systemic one halts everything). Plus: a passing canary (blind detector) halts, the boot watches the live surfaces, and `probe_all` re-probes once before halting (R6 anti-flap). The cheap Self-Audit model never halts directly. | — | `sentinel/core.py` (`halt`/`_destroy_rooms`/`evaluate_canaries`/`reap_orphans`/re-probe), `manager.provision_room` (halt-block), `tools/start_thor.py` (live-surface probes). Proven: `tests/integration/test_flow_d_governor_halts.py` (rooms killed + work blocked; flap no-thrash; proportionate; broken-canary halt) + `tests/sentinel` AC-1..12 |
| ~~**C4**~~ | ✅ **CLOSED** (Task 5, 2026-06-08) | **Honest Verdict Coordinator.** `manager.run_verdict(feature_id, branch, repo)` DERIVES claim/contract/commit_window from TRUSTED state — the recorded assign_task slice (PM/Contract), the ledger window, the Leash `action.decided{allow}` records + the claim_done knock — NEVER the actor, so `claim={}` can't be injected. A caught lie runs the dishonesty loop: record `dishonesty.caught` (per container) → escalate to the Sentinel → legible cook feedback → CEO cockpit honesty meter. §7b panel/divergence untouched. | — | `manager/core.py` `run_verdict` + `_trusted_*`/`_dishonesty_loop`. Proven: `tests/integration/test_moat_adversarial.py` (honest→done; fabricated/hollow/out-of-band→caught+loop) |
| ~~**H1**~~ | ✅ **CLOSED** (Task 5; **STRENGTHENED Phase-2**) | **Coverage-of-diff + DISCRIMINATION.** `fake_test.is_hollow` keeps the static checks, runs the test under `coverage` (must EXECUTE the contracted function bodies), AND now runs a **discrimination gate**: it guts the feature's function bodies and re-runs the test — a genuine test goes RED, a fake test that merely covers + asserts-something-always-true (e.g. `assert isinstance(r, object)`) still passes → flagged hollow → M1 fail. Catches the deepest fakery a frontier agent can write; trusts no model; PYTHONDONTWRITEBYTECODE keeps the verdict read-only (AC-5); the worktree is restored. | — | `govengine/fake_test.py` (`_discriminates`/`_gut_function_bodies`). Proven: `tests/govengine/test_fake_test_discrimination.py`; 16 live govengine+moat ACs still green |
| ~~**H2**~~ | ✅ **CLOSED** (Task 5, 2026-06-08) | **Real skill-verifier.** R1 reads `skill_results_ok` COMPUTED by `govengine/skill_verifier.py` (ported predicates: literal-asserts / no-skip / network-timeout / no-silent-catch over the feature's changed + test files) — never defaulted True. | — | `govengine/skill_verifier.py` wired in `manager.run_verdict`. Proven: skill verdicts gate R1 in the moat tests |
| ~~**H3**~~ | ☑️ **REPRESENTATIVE** (acknowledged, Task 10) | `gitea_adapter.ci_result` is now explicitly documented as a representative syntax smoke that the **verdict never trusts** — GovEngine M1/M4 run the REAL tests in a fresh subprocess (`reality.run_test`). A real CI (lint/test/build matrix) plugs in behind the same `GitPort.ci_result` at deploy. No regression risk: the verdict path does not call it. | — | `adapters/gitea_adapter.py ci_result` (docstring) |
| ~~**H4**~~ | ✅ **CLOSED** (Phase-2 P1+P2) | **Cook half (P1):** BuildStage no longer copies `code_files` verbatim — the cook is a pluggable, UNTRUSTED `cook.CookAgent` (deterministic `ScriptedCook` for the gate; a REAL frontier cook via `CookRuntime`/`CookRunner` in the room for production); every action routes through the InRoomProxy; an escape is denied before disk (`test_cook_buildstage`). **Anti-fake-test:** `fake_test._discriminates` guts the code + re-runs — a test that asserts nothing (can't go RED) is flagged hollow. **QA half (P2):** the QA adversary now fuzzes a MATRIX of edge inputs (not just zeros) and flags REAL-bug crashes (IndexError/ZeroDiv/…), EXCLUDING TypeError/ValueError — so a NON-zeros bug (IndexError on `[]`) is caught while clean numeric code is never false-flagged (`test_qa_adversarial`). Bug→CEO-ticket loop already wired (`raise_qa_fail_card`, Sig-2). | — | `sdlc/stages.py` BuildStage + `QAStage._adversarial`; `govengine/fake_test.py`. Proven: `test_cook_buildstage`, `test_qa_adversarial`, `test_fake_test_discrimination`, 12 SDLC ACs |
| ~~**H5**~~ | ✅ **CLOSED** (Task 10, 2026-06-08, *Full Strangler — your call*) | **Audit + identity routed THROUGH their ports.** The Manager's audit substrate IS the `AuditPort` (`self.eventlog = audit or ChainAudit(EventLogWriter(...))`) and all identity verification goes through the `IdentityPort` (`self.identity.verify_identity`/`verify_signature`). Swapping the audit OR identity vendor is now a one-line construction change — proven by the substitution harness driving the SAME THOR flow against a different `AuditPort` (V2InMemoryAudit) and `IdentityPort` (StubMeshIdentity). The "fully swappable substrate" headline is now TRUE for all four substrates. | — | `manager/core.py` (audit/identity params + routed verify), `adapters/audit_adapter.py` (ChainAudit drop-in), `adapters/substitution.py` (prove_audit_swap/prove_identity_swap). Proven: `tests/adapters` AC-1..12 (AC-7 substitution) |
| ~~**H6**~~ | ✅ **CLOSED** (Task 2, 2026-06-07) | **Sole-writer enforced.** All bypass sites now route through `Manager._record` (the `_eventlog_writable` fail-closed gate + `_project`). The Task-2 read found **two more** beyond the original five — `leash/escalation.py:24`, `leash/security.py:51` — now also routed (10 sites total). | — | routed: `govengine/engine.py:90,95`; `sentinel/core.py:95,110`; `dashboard/service.py:91,113`; `mobile/bridge.py:32,51`; `contract/seam.py:49`; leash `decision.py`→`Manager.record_decision`, `escalation.py:24`+`security.py:51`→`recorder.record_event`→`_record`. Proven: `tests/integration/test_seam_s12_no_bypass_writers.py` (static, gates every run) + `tests/manager/test_acceptance.py::test_ac1` |
| ~~**H7**~~ | ✅ **CLOSED** (Task 2, 2026-06-07) | **Single ledger.** The Leash's local signed JSONL chain is retired; `DecisionRecorder` sinks THROUGH the Manager (`record_decision`/`record_event`), preserving the `decision_id`. | — | `leash/decision.py` (local `EventLog` removed; `DecisionRecorder(manager)`); `manager/core.py:63` carries `decision_id`. Proven: `tests/integration/test_seam_s5_leash_records_through_manager.py` (one ledger, decision_id preserved, no `.thor/eventlog.jsonl`) |
| ~~**H8**~~ | ✅ **CLOSED** (Phase-2 P3) | The one-door egress is live-proven end-to-end (HTTPS `CONNECT` allowlist; FINDING-D fixed: `start_gateway` ensures its networks). The **egress ACs are no longer skipped**: **AC-5** (raw-HTTP egress to a non-allowlisted host BLOCKED; only the allowlisted door reachable), **AC-6** (the upstream credential lives in the gateway, NEVER in the room env), **AC-8** (a *different* cook governed by the same Leash) all prove LIVE, plus `test_flow_onedoor_egress`. (Product rooms still default to `sealed`; `one_door` is the opt-in for rooms needing network — the gateway is the sole forwarder.) | — | `leash/gateway.py`, `gateway_proxy.py`; `tests/leash/test_acceptance.py` AC-5/6/8; `tests/integration/test_flow_onedoor_egress.py` |
| ~~**H9**~~ | ✅ **CLOSED** (Task 6, 2026-06-08) | **Signature gates bound + lifecycle→merge wired (+ R9).** `TransitionController(manager)` flips `sign_plan`/`authorize_ticket` ONLY on a verified Manager card (`is_card_approved`); a `done` verdict drives `bridge.raise_merge_card`; `manager.direct_merge` merges through the Gitea adapter ONLY on a verified Signature 3 AND a FRESH verdict (R9 — `is_fresh`), records `feature.merged`, flips the feature done, and destroys the room. §7b transition ordering + bridge untouched. | — | wired: `sdlc/transitions.py` (card binding), `sdlc/merge_driver.py`, `manager.direct_merge`. Proven: `tests/integration/test_flow_a_merge.py` (no merge before Sig 3; forged sig → card stays open; stale → refused; valid Sig 3 → real merge + feature.merged + room destroyed) + `tests/sdlc` AC-1/5/6/12 |
| ~~**M1**~~ | ✅ **CLOSED** (Task 2, 2026-06-07) | Crash-replay has a real caller: every boot replays the durable ledger to rebuild projections. | — | `tools/start_thor.py:134` calls `manager.rebuild_from_log()` on boot. Proven: `tests/manager/test_acceptance.py::test_ac3_replay_rebuilds_exact_state` (identical state) |
| ~~**M2**~~ | ✅ **CLOSED** (Task 4, 2026-06-08) | **Live dispatch wire.** `scheduler/dispatch.py make_dispatcher` binds the deterministic Scheduler → PM admission gate → CTO plan → Manager provision; `Scheduler.run` dispatches a real ready-wave into real sealed rooms (zero-LLM in scheduling). The new PM module refuses a no-spec feature before any room is provisioned. *(An always-on boot scheduling loop is FLOW-A orchestration, later.)* | — | wired: `scheduler/dispatch.py`, `pm/gate.py`. Proven: `tests/scheduler` AC-1..12 (incl. AC-10 restart-no-double-dispatch over a real room) + `tests/integration/test_seam_s2_dispatch_and_pm_gate.py` (deterministic dispatch provisions real rooms; PM refuses no-spec → no room) |
| ~~**M3**~~ | ✅ **CLOSED** (Task 4, 2026-06-08) | **Six-message contract proven over the live wire.** The read-only slice negative is verified over a REAL room via `DockerExecTransport` (a real write to `/task/feature.json` fails — not the in-proc fake), the identical conformance suite passes over both transports, and every seam message is recorded via the Manager (T2). | — | Proven: `tests/contract` AC-1..12 — AC-3 read-only slice over docker-exec, AC-5/AC-12 same suite both transports (real room), AC-11 every message a `contract.*` event. §7b seam/messages/transport logic untouched |
| ~~**M4**~~ | ✅ **CLOSED** (Phase-2 P0) | The append now runs the whole `max(seq)`→`INSERT` inside ONE transaction guarded by a Postgres **advisory lock** (`pg_advisory_xact_lock`, key `_CHAIN_LOCK_KEY`), serializing the chain across **processes**, not just threads (the in-process `threading.Lock` stays as a cheap first gate). PROVEN: 8 concurrent PROCESSES × 60 appends → 480 contiguous seqs, no dup, `verify_chain=True`; with the DB lock removed the same load forks (`UniqueViolation` on `eventlog_pkey`). Chain logic unchanged (§7b). | — | `manager/eventlog.py:18-21,44-72`; proof `tools/qa/prove_concurrent_writer.py` |
| ~~**M5**~~ | ✅ **CLOSED** (Task 7, 2026-06-08) | **Sign button is real authority.** The cockpit signs in-browser with the operator's Ed25519 key (@noble/ed25519, key never leaves the device) over a one-time per-card nonce; the Manager accepts ONLY a registered operator key and rejects forged/replayed/unregistered signatures. A verified merge-card sign drives the REAL merge (T6 direct_merge) only if the verdict is fresh (R9). `/operator/register` + `/cards/{id}/challenge` + `/approve` wired. | — | `dashboard/cockpit.html` (Sign + @noble module), `dashboard/dashboard_api.py`, `dashboard/service.py`, `manager.register_operator/issue_challenge/approve`. Proven: `tests/integration/test_flow_e_human_signs.py` + `tests/dashboard` AC-1..12 |
| ~~**M6**~~ | ✅ **CLOSED** (Task 7, 2026-06-08) | **Phone rides the same signed path.** Mobile approvals go through the SAME `service.approve` (operator-key + nonce) over an E2EE relay (ciphertext only — `{nonce,ct,sender_pub}`), with a device-key allowlist + revocation and no inbound port. The relay/push transport stays an in-memory stand-in (real APNs/FCM is deployment). | — | `mobile/bridge.py` (register/revoke → authorized signers), `phone_client.py`, `crypto.py`. Proven: `tests/mobile` AC-1..12 |
| ~~**M7**~~ | ✅ **CLOSED** (Task 9, 2026-06-08) | **Local-model seam real + honest.** A real local Ollama/Qwen inspector (`OllamaInspector`) is wired behind the SAME `InspectionModel` seam and auto-selected when a local Ollama is reachable (`select_model`); else the deterministic v1 (a real, local, zero-cost analyzer) runs — `frontier_calls` stays 0 either way (Ollama is LOCAL, not a frontier API; zero frontier libs imported). `model_loaded` now reflects REALITY (the chosen inspector's availability), not a hardcode. The read-only Postgres role physically denies writes outside its own tables; HIGH findings escalate URGENT → the Sentinel decides (the model never halts). *(Phase-2 P6: Ollama is now INSTALLED + RUNNING `qwen2.5:3b` in this env — `select_model()` picks `OllamaInspector`, `loaded=True`; the 12 self-audit ACs pass LIVE on the real model (68s) with `frontier_calls=0`. The deterministic v1 remains the automatic fallback when Ollama is absent.)* | — | `selfaudit/model_host.py` (OllamaInspector + select_model + loaded), `core.py` health, `tools/start_thor.py`. Proven LIVE: `tests/selfaudit` AC-1..12 on Qwen |
| ~~**M8**~~ | ✅ **CLOSED** (Task 10, 2026-06-08) | **arch-lint strengthened beyond import-strings.** Adds a POSITIVE check that the audit + identity ports are actually CONSUMED by the Manager (`ChainAudit` + `self.eventlog = audit or`, `self.identity.verify_identity`) — so a regression back to decorative adapters (the H5 failure mode) FAILS the lint, not just a raw `import agt/gitea`. | — | `tools/arch_lint.py` `_strangler_wired()`. Proven: `tests/adapters` AC-1 |
| ~~**M9**~~ | ☑️ **REPRESENTATIVE** (acknowledged, Task 10) | Compliance mapper is a faithful **representative** 6-framework mapping that derives evidence FROM the tamper-evident chain (traceable, not invented); explicitly documented as representative — real AGT Agent Compliance plugs in behind the same export at deploy. Likewise **H3** `ci_result` is now explicitly a representative syntax smoke that the verdict never trusts (M1/M4 run real subprocess tests). | — | `adapters/compliance.py` (docstring), `adapters/gitea_adapter.py ci_result` (docstring) |
| ~~**M10**~~ | ✅ **CLOSED** (Phase-2 P0.5) | The provisioner now returns a routable `address` (`room_id:agent_port`; `None` for a sealed room); the Manager records it in `room.provisioned`, `_project` writes `rooms.address`, and `state_summary` exposes it — so the registry can route to a room (incl. a remote one). | — | `wall/provisioner.py` (return); `manager/core.py` provision_room+`_project`+state_summary; proof `tools/qa/prove_room_hardening.py` |
| ~~**M11**~~ | ✅ **CLOSED** (Phase-2 P0.5) | Room root FS is now `read_only=True`; the ONLY writable set is `/work` (the worktree, rw bind), `/tmp` (tmpfs), and a **cook-owned** `/home/cook` tmpfs (`uid=1000`, so HOME-based tool config/cache works). PROVEN LIVE: writes to `/`, `/etc`, `/usr` fail (`Read-only file system`); `/work`+`/tmp`+`~` writable; a real build (write + git commit) still succeeds. | — | `wall/provisioner.py:106-110`; proof `tools/qa/prove_room_hardening.py` |
| **M12** | 🟡 MED | **All ~144 acceptance tests are `@pytest.mark.skip`.** Proving is entirely deferred; smokes are one-time scripts, not regression gates that run in CI. | No standing safety net | `tests/**/test_acceptance.py` (every file) |
| **L1** | ☑️ **REPRESENTATIVE** (Phase-2 P4) | The AGT adapter's **policy gate (`check_action`/`load_policy`) IS real and consumed by the Leash** (`InRoomProxy(agt_adapter, …)`, decide-before on every cook action). The AGT-specific **identity/health/compliance** (`is_component_healthy→True`, `agent_identity→"stub-identity"`) are representative stubs — **no Azure AGT creds in this env**, so the deterministic backend stays ACTIVE. The Strangler seam is the deliverable and is **substitution-proven** (H5: the SAME THOR flow runs against a swapped `AuditPort`/`IdentityPort`); real Microsoft AGT plugs in behind the same adapter at deploy (one-line construction change), arch-lint enforces no AGT-type leak elsewhere. NEVER commit Azure creds (→ `.env`). | — | `adapters/agt_adapter.py`; seam proven `adapters/substitution.py`, `tests/adapters` AC-1..12; arch-lint `tools/arch_lint.py` |
| **L2** | 🟡 **Gitea CLOSED (P5)** · React pending (P7) | **Gitea (P5): DONE** — `GiteaServerBackend(GitPort)` talks to a LIVE Gitea server (real branches/PRs/merges via the Gitea API, stdlib `urllib`, no new dep); selected by `THOR_GIT_BACKEND=gitea`; compose `gitea` service added. PROVEN LIVE: a feature opens a PR in Gitea, the merge is REFUSED without Sig-3 and SUCCEEDS with it (real merge commit landed, Gitea reports `merged:True`); the verdict still runs its OWN tests (never trusts Gitea CI — H3). **React UI (P7): DONE** — a real Vite+React cockpit (`ui/`) over the SAME DashboardAPI with the SAME Ed25519 sign/nonce authority ported byte-for-byte from `cockpit.html` (operator key stays in the browser; `@noble/ed25519`). Builds clean (`vite build`, 39 modules). PROVEN cross-language: the browser-produced signature is ACCEPTED by the Python Manager, replay + forgery REJECTED (`test_react_sign_authority`). Fail-closed: signing disabled on disconnect. (Mobile push still deferred.) | — | `adapters/gitea_adapter.py`; `docker-compose.prod.yml`; `ui/` (React); proofs `tools/qa/prove_gitea_live.py`, `tests/integration/test_gitea_live.py`, `tests/integration/test_react_sign_authority.py` |

---

## 2. "Smoke passed against a stub that won't hold against the real backend" (your specific ask)

Consolidated — every place a green result depends on a stand-in, not the real mechanism:

| Smoke / AC that is green | Why it passes today | What breaks it against the real backend |
|---|---|---|
| Leash AC-1..12 (governance) | A smoke directly calls `evaluate()` / builds an `InRoomProxy` | No product code intercepts a real cook's actions; a real cook writing out-of-scope is **not** stopped (C1) |
| SDLC "QA catches the bug" | The bug is hand-tuned to throw on zeros; cook writes honest code | A real cook + a non-zeros bug → QA `passed=True` on broken code (H4) |
| GovEngine "fake test rejected" | `TEST_FAKE` is literal `assert True` | A hollow-but-referencing test passes the regex → false done (H1) |
| GovEngine "all probes pass → done" | `R1` hardcoded `True`; `claim`/`contract`/`window` supplied honestly by the smoke | A lazy/dishonest caller disables divergence / narrows the window (C4, H2) |
| Adapters AC-6 "real merge after Sig 3" | Real local-git merge, but Sig 3 is a smoke-made signature; lifecycle never drives it | Real Gitea + real lifecycle binding absent (H9) |
| Adapters AC-2/3 "audit tamper / compliance" | Real chain — but via `ChainAudit`, which **no product module uses** | Manager uses inline chain; adapter swap ≠ one file (H5) |
| Adapters AC-1 "no external type leaks" | `arch_lint` greps import strings | Duck-typed/object leak passes the lint (M8) |
| Sentinel AC-1/2/8 "fail-closed halt" | `halt()` appends a dict; smoke asserts the dict | Nothing is actually halted in a real deployment (C3) |
| Sentinel AC-3 "hung component detected" | Smoke registers `lambda: raise` | No real HTTP/exec health probe of a live service exists |
| Self-Audit AC-1 "zero token cost" | No model is ever called | A real Qwen path is unimplemented/unproven (M7) |
| Mobile AC-2/3 "relay zero-knowledge / no inbound port" | Crypto is real; relay/tunnel are in-process objects | No Cloudflare worker, no tunnel, no push; vacuously true (M6) |
| Dashboard AC-* (sign/merge/cost) | `DashboardService` methods called in-process | HTTP API never served; cockpit Sign button inert (M5) |
| Manager AC-3 "crash-replay" | Smoke calls `rebuild_from_log` | No product restart path calls it (M1) |
| Contract P5 "read-only slice" | In-process transport returns `False` for writes | Only the Docker-exec transport actually tests the mount (M3) |

---

## 3. Per-module detail (with file:line evidence)

### Module 1 — Wall  *(the most real module)*
- **(a) Real:** `provision_room` runs a real hardened container (caps dropped, no-new-privileges, unprivileged `cook`, cpu/mem caps) `wall/provisioner.py:91-113`; sealed-shut network with ground-truth readback `network_enforcer.py:32-51`; Ed25519 stamper real `identity_stamper.py:51-89`; lifecycle real Docker ops `lifecycle.py:39-111`.
- **(b) Wired seams:** Manager→`provision_room` **YES** `manager/core.py:82`; Manager→`stamper.verify` room-trust **YES end-to-end** `manager/core.py:85-87` (the one genuinely end-to-end Leash-adjacent guarantee).
- **(c) Fail-closed (real):** forged/stale token → room destroyed `core.py:85-87`; sealed readback shows a route → `status:error` `provisioner.py:116-126`.
- **(d) Won't-hold:** one-door egress reachable only from `smoke_leash_2b.py` (H8); host firewall path skipped `network_enforcer.py:58-70`; `health()` HTTP fakes with `exec_run("true")` `lifecycle.py:53-56`, `agent_server`/`leash_proxy` hardcoded `False`; root FS writable `provisioner.py:106` (M11); single local signing key stands in for AGT Mesh, revocation is an in-memory set `identity_adapter.py:32`.

### Module 2 — Leash  *(real logic, unwired enforcement — see C1)*
- **(a) Real:** `policy.evaluate` deny-precedence + fail-closed-on-unknown `policy.py:71-94`; `FrozenPolicy` immutable `:27-37`; `InRoomProxy` logic `proxy.py:29-71`; decision recorder signed chain `decision.py:31-101`; kill-switch mechanism `security.py:42-55`.
- **(b) Wired:** `policy.evaluate`→Sentinel canary **YES** `sentinel/canary.py:15`. **NOT wired:** the interceptor (C1), kill-switch (smoke-only `smoke_leash_2b.py:127`), egress gateway (smoke-only).
- **(c) Fail-closed (real but unreached in product):** no policy→deny `agt_adapter.py:47-49`; governor down→deny `proxy.py:43-45`; can't record→forbid `proxy.py:49-51`; unknown action→deny `policy.py:76-77`.
- **(d) Won't-hold:** AGT absent (`check_action`→`evaluate`, `is_component_healthy→True`, `agent_identity→stub`) `agt_adapter.py:50,62,67`; credential injector is a no-op `credentials.py:20-27`; decision sink is local JSONL not Manager (H7); all AC tests skipped.

### Module 3 — Manager  *(strong core, leaky invariants)*
- **(a) Real:** hash-chain `eventlog.py:24-55`, Ed25519 sign `:56`, `verify_chain` `:78-91`, idempotency `:42-46`, Postgres `db.py`, projections `core.py:184-215`, card signature authority `:128-136`.
- **(b) Stub:** `run_verdict`/`direct_merge` → `NotImplementedError` `core.py:249-253` (C4). FastAPI `:7100` defined, never served.
- **(c) Fail-closed (real):** eventlog-unwritable→`FailClosed` `core.py:51-52`; forged card→stays open `:132-133`. **Bypassable** by direct `eventlog.append` callers (H6).
- **(d) Won't-hold:** sole-writer not enforced (H6); split-brain audit (H7); crash-replay no product caller (M1); `rooms.address` unprojected (M10); threading.Lock not DB lock (M4).

### Module 4 — Scheduler  *(smoke-only)*
- Real DAG/wave/budget logic `graph.py:35-81`, `core.py:42-92`; **but no product module imports it** (M2); CTO is a counter stub `cto_stub.py:13-23`; `run()` mutates in-memory only.

### Module 5 — Contract  *(defined, not live)*
- Real six-message Pydantic schema `messages.py:18-92`, seam logic `seam.py:52-104`, real DockerExecTransport `transport.py:51-75`. **But** `Seam` constructed only in `smoke_contract.py` (M3); in-process transport fakes the read-only negative `transport.py:48`; event recording optional `seam.py:48`.

### Module 6 — GovernanceEngine (THE MOAT) — see §4 for the adversarial detail
- **(a) Real probes:** M1 runs `python3 <test>` real subprocess `reality.py:46-59`; M2 `git log --grep` real `gitea_adapter.py:56-62`; M3 real git diff vs caller-supplied scope `probes.py:44-49`; M4 real regression subprocess. **Stub-fed:** M5 reads caller `contract["contracts"][].status`; **R1 hardcoded True** `engine.py:35`; R2/R3 scan only caller `commit_window`.
- **Good news:** govengine does **not** use the weak `ci_result`; its tests are real subprocess runs.
- **(c) Fail-closed (real):** reality unreadable→`escalate` `engine.py:52-63`; divergence→never `done` `panel.py:42-44`; high-stakes all-pass→`escalate` `:56-58`.

### Module 7 — SDLC Stages
- **(a) Real:** stage anatomy `anatomy.py:14-50`; skill composer `skills.py:46-54`; Checker real dir-hash `stages.py:31-41`; Build real git commit `:115-130`; QA real subprocess `:144-176`; transition gates + bounded loop `transitions.py:19-63`.
- **(b/d) Stubs:** Genesis is pass-through `stages.py:51-60`; cook copies `code_files` (H4); QA adversary zeros-only `:189`; signature gates plain setters (H9); merge never driven (H9). Pipeline orchestrated only in `smoke_sdlc.py:97-152`.

### Module 8 — PM Surface (Dashboard)
- **(a) Real:** `DashboardService` logic, kanban/cost/audit/legible pure fns, Ed25519 approval via Manager `service.py:106`.
- **(d) Stub/unwired:** `dashboard_api.py` never served/`bind()`ed; **cockpit Sign button has no handler** `cockpit.html:46`; `health_system()` hardcoded green `service.py:85-87`; cost = estimate-as-spend `:76-80`; service constructed only by smokes (M5).

### Module 9 — Mobile
- **(a) Real:** X25519+ChaCha20 E2EE `crypto.py:11-45`; Ed25519 device signing; allowlist `allowlist.py:8-12`; revocation dict `bridge.py:27-32`.
- **(d) Stub:** relay = Python lists `relay.py:13-34`; no APNs/FCM; keystore in-process `phone_client.py:27-28`; "no inbound port" vacuous; assembled only by `smoke_mobile.py` (M6).

### Module 10 — Sentinel
- **(a) Real:** probe logic, integrity sha256, canary→real `leash.policy`, reconciler→real Docker API.
- **(d) Stub:** **`halt()` no-op** (C3); liveness probes in-process lambdas; connectivity is a dict echo `core.py:75-79`; `accepts_work` read only by the unlaunched API.

### Module 11 — Self-Audit
- **(a) Real:** read-only Postgres role `db.py:31-47` (genuinely enforced); inspector/metatrust pure logic; advisory-only escalation.
- **(d) Stub:** no Qwen/inference host (M7); `model_loaded`/`frontier_calls` trivially green; URGENT→Sentinel wired only in `smoke_selfaudit.py:57-58`.

### Module 12 — Foundation Adapters
- **Real & wired:** `gitea_adapter` local-git ops `:19-73,111-125` (used by GovEngine `reality.py:16` + SDLC `stages.py:22`).
- **Decorative (H5):** `audit_adapter`/`identity_adapter` wrap the same code the product already calls directly; importers are only `smoke_adapters.py`. `agt_adapter`, `compliance`, `catalog_bridge`, `substitution`, `contract` — zero product importers.
- **Stub:** `ci_result`=py_compile (H3); PR/issue in-memory dicts `:87-96`; compliance 6-entry dict (M9); `arch_lint` import-string-only (M8).

---

## 4. The moat — focused adversarial assessment (can a false "done" get through?)

**Blocked by real code today (survives a lying LLM cook):**
- Fabricated "I changed X" → divergence vs real git diff → `escalate` (`divergence.py:30-31`).
- "tests passed" lie → M1 runs the real test; `claim.tests_passed and not verifier_passed` → `escalate` (`divergence.py:39-40`).
- Empty/absent test → exit 1 → `not_done` (`reality.py:48-52`).
- Skipping the contracted file → M2/M3 missing → conflict-escalate (`panel.py:48-51`).
- Reality unreadable → fail-closed `escalate` (`engine.py:61-62`).

**NOT blocked — gets a false "done" against a real adversary (these are the proving-pass targets):**
1. **Hollow-but-referencing test** (`assert callable(login)`) defeats the regex fake-test check → M1 green on a test that exercises nothing. *Biggest single gap.* `fake_test.py:29-39`
2. **`R1` hardcoded `True`** — a probe that can never fail. `engine.py:35`
3. **Caller controls the lie-detector's inputs** — `claim={}` ⇒ no divergence ever; narrow `commit_window` ⇒ R2/R3 scan nothing; curated `contract.scope.files` ⇒ M3/M5 satisfied by construction. No honest product caller exists (`run_verdict` is `NotImplementedError`). `engine.py:26-36`, `divergence.py:24-25`, `reality.py:71-73`
4. **SDLC QA gate is independently weak** — a non-zeros logic bug passes QA (`stages.py:165,189`); the only backstop is M6's defeatable fake-test check.
5. **Freshness is advisory** — nothing in product calls `is_fresh` before acting on a verdict. `engine.py:99`

**Implication:** the adversarial GovEngine work in the proving pass should (a) replace the regex fake-test check with execution-based coverage/mutation evidence, (b) implement `R1` against real CTO skill results, (c) build the *honest Verdict Coordinator* (`run_verdict`) that derives `claim`/`contract`/`commit_window` from trusted Manager/Contract state rather than accepting them from the actor, and (d) enforce freshness before merge.

---

## 5. Implications for the proving pass (for your review — no work started)

Your plan was: Wall→up the stack, ~144 ACs→gated tests, integration tests across seams, adversarial GovEngine. This register suggests the pass must do **three kinds of work**, not one:

1. **Prove (turn ACs green as gated tests).** Un-skip `tests/**/test_acceptance.py`, port the smoke assertions into real pytest gates that run in CI (M12). Wall first (it's the most real), then Manager, then up.
2. **Wire (close the "smoke-only" gaps) — this is new scope the green smokes hid.** Several ACs cannot become honest gated tests without first wiring the seam they assert:
   - Stand up an actual run target (compose services or an in-proc supervisor) so the APIs and `bind()` paths are exercised (C2).
   - Put the Leash interceptor in the real cook action path (C1) and bind SDLC signature gates to verified Manager cards (H9).
   - Make Sentinel `halt()` actually call Wall/Manager kill (C3).
   - Decide audit/identity: either route Manager/Wall *through* `audit_adapter`/`identity_adapter` (make the Strangler real) or drop the adapter pretense (H5); unify the Leash chain into the Manager (H7); enforce sole-writer (H6).
   - Build the honest Verdict Coordinator (C4).
3. **Harden the moat adversarially.** The §4 list 1–5 — especially execution-based fake-test detection and removing caller-trust on `claim`/`window`/`contract`.

**Suggested dependency order for proving + wiring (bottom-up):**
Wall → Manager (sole-writer + replay + adapter decision) → Leash (interceptor wiring) → Contract/Scheduler → GovEngine (coordinator + adversarial) → SDLC (gate binding + merge) → Dashboard/Mobile (serve + cockpit) → Sentinel (real halt + probes) → Self-Audit → Adapters (Strangler real-or-removed).

---

*Prepared by static audit on 2026-06-06. No code was executed for this register. Every risk above is reproducible from the cited `file:line`. Nothing here has been fixed — this is the map, per your instruction.*
