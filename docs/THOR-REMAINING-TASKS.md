# THOR ENTERPRISE — REMAINING TASKS (T3 → release), detailed for Claude Code

Done: T0 run target (C2) · T1 Wall proven · T2 Manager sole-writer (H6+H7+M1). Single ledger is solid.
Each task below: GAP · REFERENCES to read · the WIRING (seam only) · the LOGIC/FLOW it restores ·
the PROOF (LANE 2 test) · PLAN-FIRST? Follow the master-prompt per-task loop for every one.

────────────────────────────────────────────────────────────────────────
T3 — CTO + LEASH (C1)  [PLAN-FIRST — the first moat task; show the plan]
GAP: the cook's actions don't route through the Leash; BuildStage writes files directly. The P3
     promise ("every action judged before it executes") is not real in product.
READ: leash/proxy.py, leash/policy.py (DO NOT change — §7b), sdlc/stages.py (BuildStage), the
     CTO-scaling decision (per-room cheap Leash vs shared CTO), Integration PRD seam S4 + FLOW B,
     and _reference/ cto.js (the original decide-before + brain-inject) to port doctrine.
WIRE: route every cook write/action in BuildStage THROUGH InRoomProxy.check_action BEFORE it
     executes; the proxy is the cook's only exit; deny/escalate recorded via the Manager (T2 sink);
     fail-closed if the governor is unreachable. Wire the shared CTO for plan + escalation only
     (cheap mechanical per-room checks stay in the Leash). Skill inject-before (drift-3 first half).
LOGIC/FLOW restored: FLOW B — a real out-of-scope write is DENIED before the file exists.
PROOF (LANE 2): test_flow_B_out_of_scope_blocked — a real cook write outside scope never touches
     disk; allow path lets in-scope writes through; governor-down → deny; every decision an event.
INVARIANT: decide-before + fail-closed. The moat gets harder.

────────────────────────────────────────────────────────────────────────
T4 — PM + SCHEDULER + CONTRACT (M2, M3)  [mechanical]
GAP: scheduler dispatch + the six-message contract + PM scope/SDLC are smoke-only, not the live wire.
READ: scheduler/*, contract/seam.py + messages.py + transport.py, pm/* , Integration PRD seams S2,
     S6, and the DockerExec transport (the real room↔control wire).
WIRE: PM enforces scope/SDLC for real; scheduler dispatches real ready-feature waves (zero-LLM,
     deterministic) → CTO plan → Manager provision; the six-message contract is the live transport
     between control plane and rooms (read-only slice proven over real docker-exec, not in-proc).
PROOF (LANE 2): deterministic wave dispatch; contract P5 (read-only slice) over real docker-exec;
     PM refuses a no-spec feature.
INVARIANT: record-everything; deterministic (no LLM in scheduling).

────────────────────────────────────────────────────────────────────────
T5 — GOVENGINE / THE MOAT (C4, H1, H2, R9)  [PLAN-FIRST — the most important; show the plan]
GAP: no honest verdict caller — claim/contract/window are caller-supplied (claim={} disables the
     lie-detector); R1 defaults to pass (no real skill-verifier); fake-test is a static heuristic to
     strengthen; freshness not enforced before merge.
READ: govengine/engine.py, panel.py + divergence.py + probes.py + fake_test.py (DO NOT loosen — §7b),
     manager/core.py:249 (run_verdict stub), Integration PRD FLOW C + §7b + the moat-adversarial test,
     and _reference/ done-check.js + skill-verifier.js + fake-test-checker.js (port the proven model).
WIRE: build the HONEST Verdict Coordinator (manager.run_verdict) that DERIVES claim/contract/
     commit_window from trusted Manager+PM+Contract state, NEVER from the actor (C4); wire R1 to a
     real skill-verifier, stop defaulting to pass (H2); STRENGTHEN fake-test toward coverage-of-diff,
     modeled on the original's live anti-hallucination auditor (H1 — strengthen, don't replace);
     enforce is_fresh before merge (R9). DO NOT change panel/divergence — they're correct.
LOGIC/FLOW restored: FLOW C — a fabricated claim / hollow test / gamed gate CANNOT get a false done.
PROOF (LANE 2): test_moat_adversarial — fabricated claim, hollow-but-referencing test, gamed window,
     curated scope: NONE → done. Freshness: a stale verdict (branch moved) must re-run before merge.
INVARIANT: judge-from-reality. THE MOAT GETS HARDER, NEVER EASIER. If wiring would weaken it, STOP+ask.

────────────────────────────────────────────────────────────────────────
T6 — SDLC (H9)  [mechanical, but touches signatures — show the plan if unsure]
GAP: signature-gate setters aren't bound to verified Manager cards; merge isn't driven by a live verdict.
READ: sdlc/transitions.py (DO NOT change ordering — §7b), sdlc/bridge.py (the merge-card bridge is
     correct — drive it, don't rewrite), manager/core.py (is_card_approved, raise_card), Integration
     PRD FLOW A + seam S8/S9.
WIRE: bind sign_plan/authorize_ticket to VERIFIED Manager card approvals (H9); drive the bridge's
     merge-card from a live `done` verdict; wire lifecycle → merge through the Gitea adapter after Sig3.
LOGIC/FLOW restored: FLOW A end-to-end — plan(Sig1) → build → QA → verdict → merge-card → Sig3 → merge.
PROOF (LANE 2): no Build before Sig1; no merge before a verified Sig3; forged signature → card stays open.
INVARIANT: human-signs.

────────────────────────────────────────────────────────────────────────
T7 — DASHBOARD + MOBILE (M5, M6)  [PLAN-FIRST — the Sign button is authority]
GAP: dashboard HTTP read-only; Sign button deferred; mobile relay/push are stand-ins.
READ: dashboard/service.py + the harvested cockpit, mobile/* , Integration PRD FLOW A + FLOW E,
     the PM-Surface + Mobile module PRDs (layout: Direct/Watch/Decide/Audit).
WIRE: serve the dashboard for real; make the Sign button actually sign (real Ed25519 handler,
     Manager-verified, bound to card+payload+nonce); show real rooms/stages/cost/audit; mobile shares
     the same data + signature model. FLOW A must be VISIBLE end-to-end on the dashboard.
PROOF (LANE 2): test_flow_E_human_signs — sign from the dashboard → verified → action proceeds;
     forged/replayed signature → rejected; the operator sees a real feature go plan→signed-merge.
INVARIANT: human-signs (the product's face).

────────────────────────────────────────────────────────────────────────
T8 — SENTINEL (C3, R6)  [PLAN-FIRST]
GAP: halt() records an event but physically halts nothing; no real liveness probes; flap risk.
READ: sentinel/core.py + canary.py, wall/lifecycle.py (the real destroy/pause), manager kill path,
     Integration PRD FLOW D + edge R6/R7, _reference/ watchdog.js (synthetic monitoring + canary).
WIRE: halt() ACTUALLY halts — call Wall destroy/pause + block new work on confirmed critical failure;
     real liveness/responsiveness probes of the live :7100/:7080/:7150 surfaces; the canary; the
     silent-heartbeat base case; a brief re-probe before halting to avoid flap-thrash (R6).
LOGIC/FLOW restored: FLOW D — a killed governor is detected and the scope physically fail-closes.
PROOF (LANE 2): test_flow_D_governor_dies_halts (kill the Leash/CTO → actions denied + rooms halted);
     forced-pass canary → real halt; silent heartbeat detected; a flap does NOT thrash-halt.
INVARIANT: fail-closed + self-verifying. The cheap model never halts directly (Sentinel decides).

────────────────────────────────────────────────────────────────────────
T9 — SELF-AUDIT (M7)  [mechanical]
GAP: no real local model; model_loaded hardcoded; zero-cost unproven.
READ: selfaudit/* , Integration PRD seam S11, the Self-Audit module PRD.
WIRE: stand up a real local model (Ollama/Qwen) for the inspector; zero frontier calls; read-only DB
     role (already real); URGENT → Sentinel over the real path (Sentinel decides, model never halts).
PROOF (LANE 2): continuous read-only inspection at zero token cost (no frontier calls); a seeded
     anomaly escalates URGENT; a write attempt outside its tables is denied (read-only proven).
INVARIANT: read-only; advisory-only.

────────────────────────────────────────────────────────────────────────
T10 — ADAPTERS / STRANGLER (H5, H3, M8, M9)  [PLAN-FIRST — strategic]
GAP: audit/identity "adapters" are decorative (bypassed by the modules they claim to back); arch-lint
     is import-string-only; ci/compliance are representative.
READ: adapters/* , Integration PRD seam catalog, the Adapters module PRD, THOR-DRIFT-CHECK (Strangler).
DECIDE WITH ME: route Manager/Wall THROUGH audit_adapter/identity_adapter (make the Strangler REAL —
     the vendor-independence moat) OR drop the adapter pretense for those two. This is strategic
     (it protects vendor-independence vs the platform owners) — show the trade-off, decide together.
WIRE (per decision): strengthen arch-lint beyond import-strings (M8); ci_result + compliance improved
     or explicitly marked representative.
PROOF (LANE 2): the substitution harness proves a real swap for whatever adapters we keep.
INVARIANT: adopt-behind-adapters; the moat is portable.

────────────────────────────────────────────────────────────────────────
FINAL — FULL-SYSTEM PROVING + RELEASE
- The unified suite green from CLEAN (`make prove`): all integration seam/flow tests + the ~144 module
  ACs, over the live booted system. Evidence captured to docs/TEST-REPORT.md.
- The end-to-end live demo: `start` → dashboard shows FLOW A → a real feature goes plan→build(sealed
  room)→QA→verdict-from-reality→CEO signs→Gitea merges→room destroyed; out-of-scope BLOCKED; fabricated
  claim CANNOT pass; Sentinel HALTS on a killed governor.
- Define the ONE start command + RUNBOOK (decide the user-start experience WITH me — dev command now,
  packaged installer later). Tag the release.

## OPENHANDS SPLIT (held across all of the above)
- OpenHands = mechanical muscle: the test harness pieces (conftest fixtures, Makefile, integration-test
  scaffolding), un-skipping ACs, dashboard UI wiring, T4/T9 plumbing. Clear-right-answer work.
- HAND-WIRED with you, plan-first: T3 Leash, T5 Verdict Coordinator, T8 Sentinel, T10 Strangler decision.
  The moat is never wired by an autonomous agent.
