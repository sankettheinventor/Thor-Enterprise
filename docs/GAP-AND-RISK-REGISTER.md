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
| **C1** | 🔴 CRITICAL | **Leash pre-action governance is wired into NOTHING in product.** `InRoomProxy` is never constructed outside smokes; the SDLC BuildStage writes files directly and never calls `check_action`. Out-of-scope / forbidden writes are **not actually intercepted** in any product path. | The entire P3 "every action judged before it executes" promise | `leash/proxy.py` only built in `tools/smoke_leash.py:77`, `smoke_manager.py:84`; `sdlc/stages.py:115-130` writes via `_git`/`open`, no leash call |
| ~~**C2**~~ | ✅ **CLOSED** (Task 0, 2026-06-07) | **Run target wired.** One control-plane process constructs the roles as peers sharing one ledger (manual boot order) and serves the four surfaces `:7100/:7080/:7140/:7150`; the dashboard renders live state. Proven by a cold-start + separate-process HTTP probe of all four ports. *(Decision flow — decide-before, dispatch, verdict, merge, real halt, Sign button — still wired in T1–T10.)* | — | wired: `tools/start_thor.py:65` `boot()` (role peers), `:121` `serve()` (4 uvicorn servers), `:109` (cockpit mount); `docker-compose.yml` (Postgres); `docs/RUNBOOK.md` (one start command) |
| **C3** | 🔴 CRITICAL | **Sentinel `halt()` does not halt.** It appends `{scope,reason}` to a list and maybe writes one event; it never calls Wall `destroy`/`pause` or Manager kill. Meta-governance can *detect* but cannot *enforce*. | Every "fail-closed halt" AC (M10 AC-1/2/8) is cosmetic in product | `sentinel/core.py:90-98`; real killers `wall/lifecycle.py:68-80`, `manager/core.py:96-100` are unreferenced by Sentinel |
| **C4** | 🔴 CRITICAL | **The verdict has no honest product caller, and its "reality inputs" are caller-supplied.** `manager.run_verdict` raises `NotImplementedError`. The engine trusts caller-provided `claim`, `contract`, `commit_window`. `claim={}` short-circuits divergence → lie-detector off. | The moat can be disabled by the (not-yet-existing) caller | `manager/core.py:249-250`; `govengine/engine.py:26-36`; `divergence.py:24-25` |
| **H1** | 🟠 HIGH | **Fake-test detector is a defeatable regex.** Only catches literal `assert True`/`assert 1`. A hollow test that references the module and asserts something trivially true (`assert callable(login)`) passes → M1 green on a test that exercises nothing. | A competent LLM cook earns a false "done" | `govengine/fake_test.py:29-39` |
| **H2** | 🟠 HIGH | **`R1` (CTO skills passed) is hardcoded `True`.** A verdict probe that checks nothing; every "done" is partly built on it. | False confidence; regresses when real CTO lands | `govengine/engine.py:35`, `probes.py:61-63` |
| **H3** | 🟠 HIGH | **"CI" = `python -m py_compile`.** `gitea_adapter.ci_result` only compiles changed `.py`. Lint/runtime/test failures and non-Python projects pass. GovEngine avoids it *today* but the System-Design doc wires the verdict's M1/M4 to `ci/result`. | If ci_result is ever trusted by the verdict, it regresses to syntax-only | `adapters/gitea_adapter.py:98-109`; `THOR-System-Design-Flow.md:222` |
| **H4** | 🟠 HIGH | **Cook & QA are deterministic stand-ins; QA adversary is zeros-only.** Build copies `feature["code_files"]` verbatim; QA only catches functions that throw on all-zero args. Off-by-one, auth bypass, logic/string bugs pass. | Real cook output + real bugs sail through the SDLC gate | `sdlc/stages.py:122-123`, `:189-201`; `QAStage.passed` `:165` |
| **H5** | 🟠 HIGH | **The M12 audit/identity "adapters" are decorative.** Manager uses its inline `EventLogWriter`; Wall/Leash/Manager import `wall.identity_stamper` directly. `audit_adapter`/`identity_adapter` are imported only by `tools/smoke_adapters.py`. Swapping to real AGT requires rewiring Manager/Wall, **not** a one-file adapter change. The Strangler claim holds only for `gitea_adapter`. | The "fully swappable substrate" headline is false for audit+identity | `manager/eventlog.py:15`; `manager/core.py:20`; `ChainAudit`/`MeshIdentity` importers = `smoke_adapters.py:26,29` only |
| **H6** | 🟠 HIGH | **"Manager is the sole writer" is not enforced.** Five product modules call `manager.eventlog.append(...)` directly, bypassing `_record`'s `_eventlog_writable` fail-closed gate and `_project`. | Fail-closed audit gate is bypassable; projections can drift | `govengine/engine.py:90,95`; `sentinel/core.py:95,110`; `dashboard/service.py:91,113`; `mobile/bridge.py:32,51`; `contract/seam.py:49` |
| **H7** | 🟠 HIGH | **Split-brain audit chains.** The Leash writes its *own* signed JSONL chain (`.thor/eventlog.jsonl`), not the Manager's Postgres EventLog. The "Leash records through the Manager" claim is true only in one smoke. | Two divergent ledgers; compliance/audit story breaks | `leash/decision.py:34`; product proxy uses it at `leash/proxy.py:49`; Manager sink only in `smoke_manager.py:142` |
| **H8** | 🟠 HIGH | **The one-door egress lock is never active in product.** Default product rooms are `network_mode="sealed"` (no network). The real one-door topology + gateway is exercised only by `smoke_leash_2b.py`. Host iptables/firewall path was deliberately skipped (needs root). | Governed-egress (the "exactly one door" guarantee) is unproven in product | `manager/core.py:76`; `wall/network_enforcer.py:58-70`; one_door caller only `smoke_leash_2b.py:71` |
| **H9** | 🟠 HIGH | **SDLC signature gates are plain setters, not bound to verified cards; merge is never driven by the lifecycle.** `sign_plan`/`authorize_ticket` are direct setters called by hand in the smoke; `raise_merge_card` never calls `gitea_adapter.merge`. | The three-signature HCD enforcement is ordering-only, not signature-verified, end-to-end | `sdlc/transitions.py:27-31`; `sdlc/bridge.py:31-33`; merge only in `smoke_adapters.py` |
| **M1** | 🟡 MED | Crash-replay (`rebuild_from_log`) has no product caller — a real restart would not replay. | Durability/recovery AC is smoke-only | `manager/core.py:217-223`; caller `smoke_manager.py:127` |
| **M2** | 🟡 MED | Scheduler is entirely smoke-only; no product module imports it; `run()` mutates only in-memory status. | Dispatch/wave orchestration unwired | grep: `from scheduler` only in `scheduler/api.py` + `tools/` |
| **M3** | 🟡 MED | Contract six-message seam is not the live wire format; in-process transport *fakes* the read-only negative (`return False`); event recording optional. | "Frozen seam" / P5 holds only in `smoke_contract.py` | `transport.py:48`; `seam.py:48`; no product importer |
| **M4** | 🟡 MED | Single-writer is a `threading.Lock`, not a DB lock; two Manager processes race `SELECT max(seq)`→`INSERT`. | Concurrency on the real backend | `manager/eventlog.py:33,40,63` |
| **M5** | 🟡 MED | Dashboard: cockpit **Sign button has no handler**; HTTP API never served/bound; `health_system()` hardcoded green; cost = estimate-as-spend. | The operator-facing surface is non-functional/unproven | `cockpit.html:46`; `dashboard_api.py:14,17`; `service.py:85-87,76-80` |
| **M6** | 🟡 MED | Mobile: relay = Python list, push (APNs/FCM) absent, device keystore in-process, "no inbound port" is vacuously true (nothing could listen). | Phone "infra" guarantees are stand-in-only | `mobile/relay.py:13-34`; `bridge.py:23,35-37`; `phone_client.py:27-28` |
| **M7** | 🟡 MED | Self-Audit has no Qwen/Ollama/inference host; `DeterministicInspector` only; `model_loaded` hardcoded `True`; `frontier_calls==0` is trivially true. | "Zero-cost local model" unproven (no model) | `selfaudit/model_host.py:24-51`; `core.py:87` |
| **M8** | 🟡 MED | `arch_lint` matches only literal `import agt/gitea` strings; a duck-typed/object-passed external leaks past it; it also exempts `tests/`+`docs/`. | The seam guarantee (AC-1) is weaker than it looks | `tools/arch_lint.py` FORBIDDEN regex |
| **M9** | 🟡 MED | Compliance mapper is a 6-entry hardcoded dict; events outside those six yield no evidence. | Compliance export is representative, not real | `adapters/compliance.py:16-26` |
| **M10** | 🟡 MED | `rooms.address` column defined but never projected/captured → routing registry incomplete for multi-room. | Real distributed routing | `manager/db.py:32`; `_project` `core.py:186-192` |
| **M11** | 🟡 MED | Room root FS is `read_only=False`; "hardening tightened later (D2)" deferred. | Container hardening | `wall/provisioner.py:106` |
| **M12** | 🟡 MED | **All ~144 acceptance tests are `@pytest.mark.skip`.** Proving is entirely deferred; smokes are one-time scripts, not regression gates that run in CI. | No standing safety net | `tests/**/test_acceptance.py` (every file) |
| **L1** | ⚪ BY-DESIGN | AGT entirely stubbed (`agt_adapter` has zero product callers; `is_component_healthy→True`, `agent_identity→"stub-identity"`). | Known per Rule 5 (real AGT = M12 prod swap) | `adapters/agt_adapter.py:61-67` |
| **L2** | ⚪ BY-DESIGN | React/mobile UIs deferred; `cockpit.html` is a 56-line static page; no Gitea server (local-git). | Known per Rule 9 decisions | `dashboard/__init__.py:17`; `mobile/__init__.py:17` |

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
