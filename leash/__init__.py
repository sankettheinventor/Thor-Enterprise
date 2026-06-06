"""
THOR Module 2 — the Leash (cook-agnostic pre-action interception).

The live behavioural governor: every model/tool call is forced through the in-room proxy,
judged allow/deny/escalate BEFORE it executes, fail-closed (P2/P3/P4). The Leash is the
*mechanism*; judgment semantics will live in AGT (M12) / Module 14.

Phase 2a (built now — decision: governance-core-first):
    proxy.py      2.1 In-Room Proxy   — deny-before-execute enforcement
    inspector.py  2.2 Layer A (MCP)   — structured tool-call inspection (Layer B egress = Phase 2b)
    policy.py     2.5 Policy Loader + THOR-native policy engine (the stub AGT plugs into at M12)
    decision.py   2.7 Decision Recorder — signed, hash-chained EventLog (ThorManager EventLog stub)
    escalation.py 2.8 Escalation Router — hold critical actions (full CEO-card flow = Phase 2b/M3)
    credentials.py 2.6 Credential Injector — interface only (outbound creds = Phase 2b, needs egress)

Deferred to Phase 2b: the one-door network egress lock (AC-5), Layer B, kill-switch (AC-9),
real CEO cards. The AGT *engine* is stubbed by THOR-native policy until Module 12 (Rule 5).
"""
