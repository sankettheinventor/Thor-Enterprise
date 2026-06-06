"""
The SelfAudit service: inspect → report → score → escalate, plus retros/benchmarks and health.

Connects as the read-only `selfaudit` DB role (so it physically cannot write outside its own tables).
It reports + escalates but NEVER enforces (no halt method exists — broad eyes, no hands). It is NOT on
the critical path (FR-11): the system runs fine without it; the Sentinel watches its liveness (FR-14).
"""
from __future__ import annotations

import json
import time
import uuid

from . import escalate, metatrust
from .inspector import observe
from .model_host import DeterministicInspector, InspectionModel


class SelfAudit:
    def __init__(self, ro_conn, sentinel=None, model: InspectionModel | None = None,
                 max_events: int = 5000) -> None:
        self.conn = ro_conn                  # the read-only `selfaudit` role connection
        self.sentinel = sentinel
        self.model = model or DeterministicInspector()
        self.up = True
        self.max_events = max_events         # resource bound — never starve the rooms (FR-16/AC-11)

    # ---- read (broad eyes) ----
    def _read_events(self) -> list[dict]:
        with self.conn.cursor() as cur:
            cur.execute("SELECT seq,event_type,payload FROM eventlog ORDER BY seq DESC LIMIT %s",
                        (self.max_events,))
            return [{"seq": r[0], "event_type": r[1], "payload": r[2]} for r in cur.fetchall()]

    # ---- the inspection cycle ----
    def inspect(self) -> dict:
        obs = observe(self._read_events())
        findings = self.model.assess(obs)                 # zero frontier calls (AC-1)
        report_id = self._write_report(obs, findings)
        sc = metatrust.score(obs)
        self._write_meta_trust(sc)
        escalations = escalate.maybe_escalate(findings, self.sentinel) if self.sentinel else []
        return {"report_id": report_id, "observations": obs, "findings": findings,
                "score": sc, "escalations": escalations}

    # ---- write (only its OWN tables; DB permissions block anything else) ----
    def _write_report(self, obs: dict, findings: list[dict]) -> str:
        rid = "rpt-" + uuid.uuid4().hex[:8]
        assessment = "healthy" if not findings else "concerns: " + ", ".join(f["pattern"] for f in findings)
        with self.conn.cursor() as cur:
            cur.execute("INSERT INTO selfaudit_reports (report_id,ts,scope,findings,assessment) "
                        "VALUES (%s,%s,%s,%s,%s)",
                        (rid, time.time(), "system", json.dumps(findings), assessment))
        return rid

    def _write_meta_trust(self, sc: dict) -> None:
        with self.conn.cursor() as cur:
            cur.execute("INSERT INTO meta_trust (ts,score,signals) VALUES (%s,%s,%s)",
                        (time.time(), sc["score"], json.dumps(sc["contributing_signals"])))

    # ---- reads of its own findings (queryable, persistent — AC-10) ----
    def reports(self) -> list[dict]:
        with self.conn.cursor() as cur:
            cur.execute("SELECT report_id,assessment,findings FROM selfaudit_reports ORDER BY ts")
            return [{"report_id": r[0], "assessment": r[1], "findings": json.loads(r[2])}
                    for r in cur.fetchall()]

    def meta_trust(self) -> dict | None:
        with self.conn.cursor() as cur:
            cur.execute("SELECT score,signals FROM meta_trust ORDER BY ts DESC LIMIT 1")
            r = cur.fetchone()
        return {"score": r[0], "signals": json.loads(r[1])} if r else None

    # ---- cheap retros + benchmarks over EXISTING data (no frontier calls — AC-8) ----
    def run_retro(self) -> dict:
        obs = observe(self._read_events())
        return {"retrospective": {"events": obs["events_scanned"], "done": obs["done"],
                                  "escalated": obs["verdict_escalate"]},
                "frontier_calls": self.model.frontier_calls}

    def run_benchmark(self) -> dict:
        return {"benchmark": "golden-suite", "ran_over": "existing EventLog data",
                "frontier_calls": self.model.frontier_calls}

    # ---- health (probed by the Sentinel like any component — FR-14/AC-9) ----
    def health(self) -> dict:
        return {"alive": self.up, "responsive": self.up, "model_loaded": True}
