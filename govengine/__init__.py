"""
THOR Module 6 — the Development-Governance Engine (THE MOAT).

Decides whether a feature is *really* done — honestly and un-fakeably — by computing a verdict from
REALITY (git, tests, audit, contract), never the agent's word (P5/FR-1). Three things nobody
combines: the 8-probe verdict (all must pass), claim-vs-reality divergence (the lie-detector), and
a panel that trusts no single mechanism (conflict/high-stakes → escalate to a human, P6).

Read-only (FR-4), deterministic (FR-10), and fail-closed — it NEVER returns a false `done` (FR-15).
No LLM in the core verdict (FR-16). The verdict is mechanical.

Files → PRD §2 sub-modules:
    reality.py    6.2 Git Ground-Truth + 6.3 Test/CI + 6.5 Audit-Window (read-only reality)
    fake_test.py  fake-test-checker (FR-13) — defends M1 against hollow tests
    probes.py     6.1 Probe Runner — the 8 probes (M1–M5 mechanical, R1–R3 review)
    divergence.py 6.7 Divergence Detector — reality manifest vs the agent's untrusted claim
    panel.py      6.8 Panel Adjudicator — probes + divergence + stakes → done/not_done/escalate
    engine.py     orchestrator + 6.9 Verdict Recorder + canary + freshness + fail-closed
"""
