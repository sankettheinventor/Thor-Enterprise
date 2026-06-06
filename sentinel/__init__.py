"""
THOR Module 10 — the Sentinel (meta-governance / self-verifying governance).

Every other module governs the agents; the Sentinel governs THOR (P9). It continuously proves THOR
is alive AND responsive, loaded, connected, untampered, and STILL CATCHING — and fail-closes + halts
the moment it cannot, so the governor is never SILENTLY broken. The mechanical, deterministic reflexes
of the three-layer health model (Sentinel → Self-Audit Qwen (M17) → Human).

Five verifications + the canary's double duty (efficacy check + the regress-stopping heartbeat).

Files → PRD §2 sub-modules:
    integrity.py  10.4 Integrity Crawler (hash governance code/rules; detect tamper)
    canary.py     10.5 Canary Engine (planted must-fail actions; pass = broken detector)
    reconcile.py  10.8 Reconciler (registry vs actual containers; orphans + shadow agents)
    core.py       10.1/10.2/10.3 probes · 10.6 Halt Authority · 10.7 Boot Self-Test · 10.9 Alarm +
                  the canary base-case heartbeat + maintenance mode

Decision (Rule 9 / Rule 5): AGT SRE + Runtime (kill-switch) stay STUBBED behind the adapter until M12;
the THOR-specific efficacy (canary), integrity, loadedness, reconcile, boot self-test, and the
silent-heartbeat base case are built for real — that is the meta-governance moat.
"""
