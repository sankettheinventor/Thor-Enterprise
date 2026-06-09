"""
The Sentinel core: 10.1 Liveness Prober (alive AND responsive) · 10.2 Loadedness · 10.3 Connectivity ·
10.6 Halt Authority (proportionate) · 10.7 Boot Self-Test · 10.9 Alarm & Escalation + maintenance +
the canary base-case heartbeat. Mechanical and deterministic — the reflexes (no LLM, no verdicts).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .integrity import IntegrityCrawler

# Components whose failure is SYSTEMIC (halt broadly); others are local (halt the smallest scope).
_SYSTEMIC = {"leash", "manager", "govengine", "eventlog"}


@dataclass
class Component:
    name: str
    critical: bool
    health_fn: Callable[[], dict]   # () -> {"alive":bool, "responsive":bool}; may raise (= hung)


class Sentinel:
    def __init__(self, manager=None) -> None:
        self.manager = manager
        self.components: dict[str, Component] = {}
        self.integrity = IntegrityCrawler()
        self.alarms: list[dict] = []
        self.halts: list[dict] = []
        self.failures: dict[str, int] = {}      # per-component failure counts (meta-trust inputs, FR-16)
        self._heartbeat = 0
        self._maintenance: dict | None = None
        self.accepts_work = False
        self.halted = False            # C3: set on a systemic halt → the Manager blocks all new work

    def register(self, name: str, critical: bool, health_fn: Callable[[], dict]) -> None:
        self.components[name] = Component(name, critical, health_fn)

    # ---- 10.1 Liveness Prober: alive AND responsive (not just process-up) (FR-1 / AC-1 / AC-3) ----
    def probe(self, name: str) -> dict:
        comp = self.components[name]
        try:
            h = comp.health_fn()
            alive = bool(h.get("alive", True))
            responsive = bool(h.get("responsive", False))
        except Exception:                         # up but hung / timed out → not responsive (AC-3)
            alive, responsive = True, False
        healthy = alive and responsive
        if not healthy:
            self.failures[name] = self.failures.get(name, 0) + 1
        return {"name": name, "alive": alive, "responsive": responsive,
                "healthy": healthy, "critical": comp.critical}

    def probe_all(self) -> list[dict]:
        results = [self.probe(n) for n in self.components]
        for r in results:
            if not r["healthy"]:
                self.alarm("critical" if r["critical"] else "degraded",
                           f"{r['name']} unhealthy (alive={r['alive']} responsive={r['responsive']})",
                           name=r["name"])
                if r["critical"]:                 # fail-closed, proportionate (FR-6 / FR-17 / AC-1)
                    if self.probe(r["name"])["healthy"]:   # R6 anti-flap: re-probe once; a blip recovers
                        continue
                    scope = "system" if r["name"] in _SYSTEMIC else f"component:{r['name']}"
                    self.halt(scope, f"{r['name']} unresponsive (confirmed on re-probe)")
        return results

    # ---- 10.2 Loadedness (FR-2 / AC-5) ----
    def verify_loadedness(self, declared_floor, loaded_skills) -> dict:
        missing = [s for s in declared_floor if s not in loaded_skills]
        if missing:
            self.alarm("critical", f"floor skills not loaded: {missing}")
            return {"ok": False, "missing": missing, "fail_closed": True}
        return {"ok": True, "missing": []}

    # ---- 10.3 Connectivity (FR-3) ----
    def verify_connectivity(self, channels: dict[str, bool]) -> dict:
        broken = [k for k, ok in channels.items() if not ok]
        if broken:
            self.alarm("critical", f"channels broken: {broken}")
        return {"ok": not broken, "broken": broken}

    # ---- 10.4 Integrity (FR-4 / AC-4) ----
    def check_integrity(self, items: dict[str, bytes]) -> dict:
        res = self.integrity.check(items)
        if not res["ok"]:
            self.alarm("critical", f"CRAWLER_ALARM: governance rules tampered {res['tampered']}")
            self.halt("system", "rule tampering")
        return res

    # ---- 10.6 Halt Authority — fail-closed, proportionate (FR-6 / FR-17 / AC-8) ----
    def halt(self, scope: str, reason: str) -> dict:
        """C3 — a HALT physically ENFORCES: it destroys the affected rooms and (for a systemic fault)
        blocks all new work. The branch/work persists in git; only the live container dies (fail-closed).
        Proportionate (AC-8): `room:X`/a non-systemic component halts the smallest scope; a systemic
        component (leash/manager/govengine/eventlog) or `system` halts everything."""
        only: set[str] | None = None
        systemic = scope == "system" or scope.removeprefix("component:") in _SYSTEMIC
        if scope.startswith("room:"):
            only, systemic = {scope.split(":", 1)[1]}, False
        if systemic:
            self.halted = True                 # the Manager refuses new provisions while halted
            self.accepts_work = False
        rooms_halted = self._destroy_rooms(only)
        rec = {"scope": scope, "reason": reason, "systemic": systemic, "rooms_halted": rooms_halted}
        self.halts.append(rec)
        if self.manager is not None:
            try:
                self.manager._record("sentinel.halt", rec, actor="sentinel")
            except Exception:  # noqa: BLE001
                pass
        return rec

    def _destroy_rooms(self, only: set[str] | None) -> list[str]:
        """Physically destroy the working rooms in scope (all if only=None). Returns the ids killed."""
        if self.manager is None:
            return []
        try:
            rooms = self.manager.state_summary()["rooms"]
        except Exception:  # noqa: BLE001
            return []
        killed = []
        for rid, r in rooms.items():
            if r.get("status") != "working" or (only is not None and rid not in only):
                continue
            try:
                self.manager.destroy_room(rid)
                killed.append(rid)
            except Exception:  # noqa: BLE001 — already gone; the branch persists regardless
                pass
        return killed

    # ---- 10.5 Canary verdicts: a PASSING planted-failure means a BROKEN detector → halt (AC-2) ----
    def evaluate_canaries(self, canaries: list[dict]) -> dict:
        """Given the canary results (from sentinel.canary fired at the REAL Leash/Engine), HALT if any
        passed — a planted must-fail that got through means the detector is blind (a systemic failure)."""
        broken = [c for c in canaries if not c.get("healthy")]
        for c in broken:
            self.alarm("critical",
                       f"CANARY BROKEN: {c['name']} expected {c.get('expected')} got {c.get('result')}")
            self.halt("system", f"detector blind: {c['name']}")
        return {"canaries": canaries, "broken": [c["name"] for c in broken], "all_healthy": not broken}

    # ---- 10.8 Shadow/orphan reaper (AC-10) — reconcile Docker reality vs the owned set ----
    def reap_orphans(self, known_room_ids: set[str] | None = None) -> list[str]:
        from wall.lifecycle import LifecycleController
        known = known_room_ids
        if known is None and self.manager is not None:
            known = set(self.manager.state_summary()["rooms"].keys())
        reaped = LifecycleController().reap_orphans(known or set())
        if reaped:
            self.alarm("degraded", f"reaped {len(reaped)} orphan container(s): {reaped}")
        return reaped

    # ---- 10.9 Alarm (respects a maintenance window; FR-10 / FR-15) ----
    def alarm(self, severity: str, message: str, name: str | None = None) -> dict:
        key = name or message
        m = self._maintenance
        if m and m["ticks"] > 0 and any(a in key for a in m["alarms"]):
            return {"suppressed": True, "reason": "maintenance window"}
        rec = {"severity": severity, "message": message}
        self.alarms.append(rec)
        if self.manager is not None:
            try:
                self.manager._record("sentinel.alarm", rec, actor="sentinel")
            except Exception:  # noqa: BLE001
                pass
        return rec

    # ---- 10.7 Boot Self-Test (FR-7 / AC-6) ----
    def boot_self_test(self, integrity_items: dict[str, bytes] | None = None) -> bool:
        if integrity_items is not None and not self.check_integrity(integrity_items)["ok"]:
            self.accepts_work = False
            return False
        for n in self.components:
            if not self.probe(n)["healthy"]:
                self.alarm("critical", f"boot self-test: {n} not answering")
                self.accepts_work = False         # a system that can't verify itself never starts
                return False
        self.accepts_work = True
        return True

    # ---- the canary base case: a heartbeat whose SILENCE is itself the alarm (FR-12/13 / AC-7) ----
    def heartbeat(self) -> int:
        self._heartbeat += 1
        return self._heartbeat

    def heartbeat_alive(self, last_seen: int) -> bool:
        """External base-case check: if the heartbeat hasn't advanced, the Sentinel is dead (silence = alarm)."""
        return self._heartbeat > last_seen

    # ---- maintenance mode (human-authorized, bounded, auto-closing; FR-15 / AC-11) ----
    def set_maintenance(self, alarms, ticks: int, human_authority: bool) -> dict:
        if not human_authority:
            return {"ok": False, "reason": "maintenance requires human authority"}
        self._maintenance = {"alarms": set(alarms), "ticks": ticks}
        return {"ok": True}

    def tick(self) -> None:
        if self._maintenance:
            self._maintenance["ticks"] -= 1
            if self._maintenance["ticks"] <= 0:
                self._maintenance = None          # auto-close — never silences outside the window

    # ---- 10.9 URGENT from the Self-Audit model (M17) — the cheap model escalates, Sentinel enforces (FR-9/AC-9) ----
    def receive_urgent(self, finding: dict) -> dict:
        if finding.get("confirmed_critical"):
            self.halt(finding.get("scope", "system"), "self-audit confirmed critical failure")
            return {"decision": "halt"}
        self.alarm("degraded", f"self-audit note: {finding.get('detail', '')}")
        return {"decision": "note"}

    # ---- status + meta-trust inputs (FR-16 — system-trust, not agent-trust) ----
    def status(self) -> dict:
        comps = {n: self.probe(n) for n in self.components}
        overall = "healthy" if all(c["healthy"] for c in comps.values()) and not self.halts else \
            ("halt" if self.halts else "degraded")
        return {"components": comps, "overall": overall, "alarms": len(self.alarms),
                "meta_trust_inputs": dict(self.failures)}
