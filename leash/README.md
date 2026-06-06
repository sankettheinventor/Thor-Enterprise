# Module 2 — The Leash

Live, pre-action behavioural governor: every tool/model call is forced through the in-room proxy,
judged **allow/deny/escalate before it executes**, **fail-closed**. Spec:
[`../docs/PRD-Module-2-Leash.md`](../docs/PRD-Module-2-Leash.md).

**Decisions (2026-06-06):** stub AGT, keep Rule 5 (THOR-native policy now; Microsoft AGT plugs in
at M12 — only the adapter changes) · build the **governance core first** (Phase 2a).

## Phase 2a — built now (files → PRD §2 sub-modules)
| File | Sub-module | Role |
|---|---|---|
| `proxy.py` | 2.1 In-Room Proxy | enforce verdict; side effect ONLY on `allow` (pre-action) |
| `inspector.py` | 2.2 Layer A (MCP) | normalize a tool call → THOR action |
| `policy.py` | 2.5 Policy Loader + engine | frozen Kind-B policy + `evaluate()` (the AGT stub) |
| `decision.py` | 2.7 Decision Recorder | signed, hash-chained EventLog (ThorManager stub) |
| `escalation.py` | 2.8 Escalation Router | hold `critical` actions (no auto-allow) |
| `credentials.py` | 2.6 Credential Injector | interface only (outbound creds = Phase 2b) |
| `../adapters/agt_adapter.py` | 2.4 AGT Adapter | the only AGT seam; calls `leash.policy` today |

Phase 2a milestone (smoke `tools/smoke_leash.py`): **AC-1, AC-2, AC-3, AC-4, AC-11** (+ partial AC-7).

## Phase 2b — deferred
The **one-door network egress lock** (flips `wall/network_enforcer.py` from sealed-shut to `:8001`-only)
→ AC-5 raw-egress block, AC-6 credential injection, AC-8 second cook, AC-9 kill-switch, AC-10 load test.

## Smoke (NOT run until asked)
```bash
python tools/smoke_leash.py   # in the WSL venv, from ~/thor-enterprise
```
`tests/leash/` holds AC-1..AC-12 as deferred/skipped specs (never a false green).
