"""
Threat Detector (sub-module 10.7) — "how do we KNOW an attack is happening?"

The cage already DENIES attacks: out-of-scope writes (Leash), non-allowlisted egress (gateway), forged or
replayed signatures (Manager), a tampered ledger (hash-chain), a lying cook (verdict). Each denial is a
single, low-context event. This engine reads that tamper-evident stream over a sliding window and turns it
into NAMED, SCORED, STRIDE-tagged THREAT SIGNALS — so an operator sees "a cook is probing the cage / an
exfiltration attempt is underway / a forged signature was tried", not just scattered denials.

Detection is defense-in-DEPTH, never the enforcement: the attack is already blocked by the time it is
counted here. A crossed threshold records `threat.detected` (incident-response audit, invariant #7) and a
CRITICAL signal escalates to the Sentinel (halt). Signatures are an allow-list of KNOWN attack shapes; new
shapes are added explicitly (positive detection, not a guess).
"""
from __future__ import annotations

import json
import os
import tempfile
import time


class ThreatDetector:
    def __init__(self, manager, *, gateway_log: str | None = None) -> None:
        self.manager = manager
        self.gateway_log = gateway_log or os.path.join(tempfile.gettempdir(), "thor-leash", "decisions.jsonl")

    # --- helpers -----------------------------------------------------------
    @staticmethod
    def _ts(e) -> float:
        try:
            return float(e.get("ts") or 0)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _payload(e) -> dict:
        try:
            return json.loads(e["payload"])
        except (KeyError, ValueError, TypeError):
            return {}

    def _egress_denies(self, lo: float) -> list[dict]:
        out: list[dict] = []
        try:
            with open(self.gateway_log, encoding="utf-8") as f:
                for line in f:
                    try:
                        d = json.loads(line)
                    except ValueError:
                        continue
                    if d.get("decision") == "deny" and float(d.get("ts") or 0) >= lo:
                        out.append(d)
        except OSError:
            pass
        return out

    @staticmethod
    def _threat(name, severity, stride, detail, count, threshold, samples=None) -> dict:
        return {"name": name, "severity": severity, "stride": stride, "detail": detail,
                "count": count, "threshold": threshold,
                "samples": [s for s in (samples or []) if s][:5]}

    # --- the scan ----------------------------------------------------------
    def scan(self, *, window_secs: int = 300, now: float | None = None) -> list[dict]:
        """Return the list of attack signatures currently firing over the window (read-only)."""
        now = now if now is not None else time.time()
        lo = now - window_secs
        events = [e for e in self.manager.eventlog.all_events() if self._ts(e) >= lo]

        denies = [e for e in events if e["event_type"] == "action.decided"
                  and self._payload(e).get("decision") == "deny"]
        forged = [e for e in events if e["event_type"] == "signature.rejected"]
        dishonesty = [e for e in events if e["event_type"] == "dishonesty.caught"]
        alarms = [e for e in events if e["event_type"] in ("security.alarm", "sentinel.kill")]
        egress = self._egress_denies(lo)
        chain_ok = self.manager.eventlog.verify_chain()

        threats: list[dict] = []
        if not chain_ok:   # Tampering — the audit ledger itself was altered (the worst signal)
            threats.append(self._threat(
                "ledger-tamper", "critical", "Tampering",
                "the hash-chain failed verification — the append-only audit ledger has been altered", 1, 1))
        if len(denies) >= 5:   # Elevation of Privilege — a cook hammering the scope boundary
            threats.append(self._threat(
                "scope-probing", "high", "Elevation of Privilege",
                f"{len(denies)} out-of-scope/denied actions in {window_secs}s — a cook is probing the cage",
                len(denies), 5,
                samples=[self._payload(e).get("action", {}).get("target") for e in denies]))
        if len(egress) >= 5:   # Information Disclosure — repeated tries to reach non-allowlisted hosts
            threats.append(self._threat(
                "exfiltration-attempt", "high", "Information Disclosure",
                f"{len(egress)} blocked egress attempts — repeated tries to reach non-allowlisted hosts",
                len(egress), 5, samples=[d.get("host") for d in egress]))
        if len(forged) >= 3:   # Spoofing — forged / replayed approval signatures
            threats.append(self._threat(
                "signature-forgery", "high", "Spoofing",
                f"{len(forged)} rejected signatures — forged or replayed approval attempts",
                len(forged), 3, samples=[self._payload(e).get("reason") for e in forged]))
        if dishonesty:   # Tampering — a cook fabricated a claim/test/result and was caught
            threats.append(self._threat(
                "dishonest-cook", "high", "Tampering",
                f"{len(dishonesty)} caught lie(s) — the cook fabricated a claim/test/result",
                len(dishonesty), 1))
        if alarms:   # a governor/canary already fired — surface it as a threat too
            threats.append(self._threat(
                "governor-alarm", "high", "Denial of Service",
                f"{len(alarms)} security alarm(s)/kill(s) from the governors in the window",
                len(alarms), 1))
        return threats

    # --- act on it ---------------------------------------------------------
    def run(self, *, window_secs: int = 300) -> dict:
        """Scan, record each NEW firing signature to the ledger, and escalate CRITICAL ones to the Sentinel.
        Dedups by signature name over the window so a persistent attack isn't re-recorded every cycle."""
        now = time.time()
        threats = self.scan(window_secs=window_secs, now=now)
        already = {self._payload(e).get("name") for e in self.manager.eventlog.all_events()
                   if e["event_type"] == "threat.detected" and self._ts(e) >= now - window_secs}
        recorded = []
        for t in threats:
            if t["name"] not in already:
                try:
                    self.manager.record_threat(t)
                    recorded.append(t["name"])
                except Exception:  # noqa: BLE001 — recording is best-effort; detection already happened
                    pass
            sentinel = getattr(self.manager, "sentinel", None)
            if t["severity"] == "critical" and sentinel is not None:
                try:
                    sentinel.halt("system", f"threat:{t['name']} — {t['detail']}")
                except Exception:  # noqa: BLE001
                    pass
        return {"scanned_window_secs": window_secs, "threats": threats, "newly_recorded": recorded}
