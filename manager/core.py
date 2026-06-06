"""
Sub-module 3.1/3.2/3.4/3.5/3.8/3.9 — the ThorManager coordinator.

Single brain: the only EventLog writer (delegated to EventLogWriter), the authoritative room
registry, the rules custodian, the three signature points, replay recovery, health. It DELEGATES
everything heavy: provisioning -> the Wall (M1); judging -> the Leash (M2); verdict -> M6 (stub);
merge -> Gitea (M12 stub). It only routes, records, owns state, and verifies signatures (P8).
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from wall import provisioner
from wall.identity_stamper import IdentityStamper, _b64, _unb64

from .eventlog import EventLogWriter, _canon


class FailClosed(Exception):
    """Raised when a governed action cannot be recorded — the Manager refuses to proceed (FR-15)."""


def _verify_sig(pub_b64: str, sig_b64: str, material: str) -> bool:
    try:
        Ed25519PublicKey.from_public_bytes(_unb64(pub_b64)).verify(_unb64(sig_b64), material.encode())
        return True
    except (InvalidSignature, ValueError):
        return False


class ThorManager:
    def __init__(self, conn, stamper: IdentityStamper | None = None) -> None:
        self.conn = conn
        self.stamper = stamper or IdentityStamper()
        self.eventlog = EventLogWriter(conn, self.stamper)
        self._eventlog_writable = True   # toggled to demonstrate fail-closed (AC-7)

    # ---- single-writer record path (FR-2) + fail-closed (FR-15) ----
    def set_eventlog_writable(self, ok: bool) -> None:
        self._eventlog_writable = ok

    def _record(self, event_type: str, payload: dict, actor: str = "manager",
                room_id: str | None = None, feature_id: str | None = None,
                client_id: str | None = None) -> dict:
        if not self._eventlog_writable:
            raise FailClosed("eventlog unwritable — refusing governed action (no unaudited actions)")
        try:
            ev = self.eventlog.append(event_type, payload, actor=actor, room_id=room_id,
                                      feature_id=feature_id, client_id=client_id)
        except Exception as e:  # store down → fail-closed (P2)
            raise FailClosed(f"eventlog write failed: {e}") from e
        if not ev.get("idempotent"):
            self._project(event_type, payload)
        return ev

    # ---- the Leash records THROUGH the Manager (FR-2: single writer) ----
    def record_decision(self, verdict, action: dict) -> dict:
        return self._record(
            "action.decided",
            {"room_id": action.get("room_id"),
             "action": {"type": action.get("type"), "name": action.get("name"),
                        "target": action.get("target")},
             "decision": verdict.decision, "reason": verdict.reason,
             "classification": verdict.classification},
            actor="leash", room_id=action.get("room_id"),
        )

    # ---- 3.2 Lifecycle Coordinator (drives the Wall) ----
    def provision_room(self, feature_id: str, task_type: str = "build", branch: str | None = None,
                       network_mode: str = "sealed", **wall_kw) -> dict:
        branch = branch or f"feature/{feature_id}"
        with self.conn.cursor() as cur:  # FR-20 one-branch-one-room
            cur.execute("SELECT room_id FROM rooms WHERE branch=%s AND status='working'", (branch,))
            if cur.fetchone():
                raise ValueError(f"one-branch-one-room: {branch} already owned")
        room = provisioner.provision_room(task_type=task_type, network_mode=network_mode,
                                          feature_slice={"feature_id": feature_id}, **wall_kw)
        # FR-5 verify the Wall's identity token before trusting/registering the room
        if not self.stamper.verify(room["identity_token"], expect_room_id=room["room_id"]):
            provisioner.destroy_room(room["room_id"], room.get("_mount_plan"))
            raise ValueError("identity verification failed — room refused")
        self._record("room.provisioned",
                     {"room_id": room["room_id"], "container": room["container"],
                      "task_type": task_type, "feature_id": feature_id, "branch": branch,
                      "status": "working", "identity_token": room["identity_token"]},
                     room_id=room["room_id"], feature_id=feature_id)
        room["_branch"] = branch
        return room

    def destroy_room(self, room_id: str, mount_plan=None) -> dict:
        provisioner.destroy_room(room_id, mount_plan)
        self._record("room.destroyed", {"room_id": room_id, "status": "destroyed",
                                        "branch_preserved": True}, room_id=room_id)
        return {"room_id": room_id, "status": "destroyed", "branch_preserved": True}

    def verify_room_identity(self, room_id: str, token: str) -> bool:  # FR-5 / AC-8
        return self.stamper.verify(token, expect_room_id=room_id)

    # ---- 3.5 Card & Signature Authority (the three signature points) ----
    def raise_card(self, type_: str, feature_id: str, payload: dict, held: bool = False) -> str:
        card_id = "card-" + uuid.uuid4().hex[:8]
        status = "held" if held else "open"
        self._record("card.raised", {"card_id": card_id, "type": type_, "feature_id": feature_id,
                                     "payload": payload, "status": status}, feature_id=feature_id)
        return card_id

    def _get_card(self, card_id: str) -> dict | None:
        with self.conn.cursor() as cur:
            cur.execute("SELECT card_id,type,feature_id,payload,status FROM cards WHERE card_id=%s",
                        (card_id,))
            r = cur.fetchone()
        if not r:
            return None
        return {"card_id": r[0], "type": r[1], "feature_id": r[2],
                "payload": json.loads(r[3]) if r[3] else {}, "status": r[4]}

    @staticmethod
    def card_material(card_id: str, payload: dict) -> str:
        """What a human signs: card-id bound to the payload hash (D5)."""
        return f"{card_id}|{hashlib.sha256(_canon(payload).encode()).hexdigest()}"

    def approve(self, card_id: str, signature_b64: str, signer_pub_b64: str) -> dict:
        card = self._get_card(card_id)
        if not card or card["status"] in ("approved", "rejected"):
            return {"verified": False, "reason": "card not open"}
        if not _verify_sig(signer_pub_b64, signature_b64, self.card_material(card_id, card["payload"])):
            return {"verified": False, "reason": "signature invalid — card stays open"}  # AC-5
        self._record("card.approved", {"card_id": card_id, "decided_by": signer_pub_b64[:12],
                                      "signature": signature_b64}, feature_id=card["feature_id"])
        return {"verified": True, "action_taken": "approved"}

    def is_card_approved(self, card_id: str) -> bool:
        c = self._get_card(card_id)
        return bool(c and c["status"] == "approved")

    # ---- bugs/findings sink (consumed by the SDLC QA + Checker stages, Module 7) ----
    def append_bug(self, feature_id: str, severity: str, description: str, source: str = "qa") -> str:
        bug_id = "bug-" + uuid.uuid4().hex[:8]
        with self.conn.cursor() as cur:
            cur.execute("INSERT INTO bugs (bug_id,feature_id,severity,description,source,status,found_at)"
                        " VALUES (%s,%s,%s,%s,%s,%s,%s)",
                        (bug_id, feature_id, severity, description, source, "open", time.time()))
        self._record("qa.finding", {"bug_id": bug_id, "feature_id": feature_id,
                                    "severity": severity, "source": source}, feature_id=feature_id)
        return bug_id

    def list_bugs(self, feature_id: str) -> list[dict]:
        with self.conn.cursor() as cur:
            cur.execute("SELECT bug_id,severity,description,source,status FROM bugs WHERE feature_id=%s",
                        (feature_id,))
            return [{"bug_id": r[0], "severity": r[1], "description": r[2], "source": r[3], "status": r[4]}
                    for r in cur.fetchall()]

    # ---- feature catalog (Kind C) — directed by the PM Surface (Module 8), event-sourced ----
    def add_feature(self, feature_id: str, title: str, context: str = "", priority: int = 3,
                    est_tokens: int = 1000) -> str:
        self._record("feature.added", {"feature_id": feature_id, "title": title, "context": context,
                                      "priority": priority, "est_tokens": est_tokens,
                                      "status": "backlog"}, feature_id=feature_id)
        return feature_id

    def set_feature_status(self, feature_id: str, status: str) -> None:
        self._record("feature.status", {"feature_id": feature_id, "status": status}, feature_id=feature_id)

    def list_features(self) -> list[dict]:
        with self.conn.cursor() as cur:
            cur.execute("SELECT feature_id,title,priority,status,est_tokens FROM features "
                        "ORDER BY priority NULLS LAST, feature_id")
            return [{"feature_id": r[0], "title": r[1], "priority": r[2], "status": r[3],
                     "est_tokens": r[4]} for r in cur.fetchall()]

    def list_checker_findings(self) -> list[dict]:
        with self.conn.cursor() as cur:
            cur.execute("SELECT bug_id,feature_id,description FROM bugs WHERE source='checker'")
            return [{"bug_id": r[0], "feature_id": r[1], "description": r[2]} for r in cur.fetchall()]

    # ---- 3.8 State Projector (event-sourcing) ----
    def _project(self, event_type: str, p: dict) -> None:
        with self.conn.cursor() as cur:
            if event_type == "room.provisioned":
                cur.execute(
                    "INSERT INTO rooms (room_id,container,task_type,feature_id,branch,status,"
                    "identity_token,created_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) "
                    "ON CONFLICT (room_id) DO UPDATE SET status=EXCLUDED.status",
                    (p["room_id"], p.get("container"), p["task_type"], p["feature_id"],
                     p["branch"], p["status"], p.get("identity_token"), time.time()))
            elif event_type == "room.destroyed":
                cur.execute("UPDATE rooms SET status='destroyed', destroyed_at=%s WHERE room_id=%s",
                            (time.time(), p["room_id"]))
            elif event_type == "card.raised":
                cur.execute(
                    "INSERT INTO cards (card_id,type,feature_id,payload,status,created_at) "
                    "VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT (card_id) DO NOTHING",
                    (p["card_id"], p["type"], p["feature_id"], json.dumps(p["payload"]),
                     p["status"], time.time()))
            elif event_type == "card.approved":
                cur.execute("UPDATE cards SET status='approved', decided_by=%s, signature=%s, "
                            "decided_at=%s WHERE card_id=%s",
                            (p["decided_by"], p["signature"], time.time(), p["card_id"]))
            elif event_type == "feature.added":
                cur.execute("INSERT INTO features (feature_id,title,context,priority,status,est_tokens)"
                            " VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT (feature_id) DO UPDATE SET "
                            "title=EXCLUDED.title, priority=EXCLUDED.priority",
                            (p["feature_id"], p.get("title"), p.get("context"), p.get("priority"),
                             p.get("status", "backlog"), p.get("est_tokens", 1000)))
            elif event_type == "feature.status":
                cur.execute("UPDATE features SET status=%s WHERE feature_id=%s",
                            (p["status"], p["feature_id"]))
        self.conn.commit()

    def rebuild_from_log(self) -> None:
        """FR-13: clear the projections and rebuild them purely by replaying the EventLog."""
        with self.conn.cursor() as cur:
            cur.execute("TRUNCATE rooms, cards, features")
        self.conn.commit()
        for e in self.eventlog.all_events():
            self._project(e["event_type"], json.loads(e["payload"]))

    def state_summary(self) -> dict:
        """The projected current state (registry + open cards) — for the Dashboard and AC-3 diff."""
        s: dict = {"rooms": {}, "cards": {}}
        with self.conn.cursor() as cur:
            cur.execute("SELECT room_id,task_type,feature_id,branch,status FROM rooms ORDER BY room_id")
            for r in cur.fetchall():
                s["rooms"][r[0]] = {"task_type": r[1], "feature_id": r[2], "branch": r[3], "status": r[4]}
            cur.execute("SELECT card_id,type,feature_id,status FROM cards ORDER BY card_id")
            for r in cur.fetchall():
                s["cards"][r[0]] = {"type": r[1], "feature_id": r[2], "status": r[3]}
        return s

    # ---- 3.9 Health Responder (FR-14 / AC-10) ----
    def health(self) -> dict:
        try:
            with self.conn.cursor() as cur:
                cur.execute("SELECT 1")
            db_ok = True
        except Exception:  # noqa: BLE001
            db_ok = False
        return {"alive": True, "responsive": True,
                "eventlog_writable": self._eventlog_writable and db_ok, "deps": {"postgres": db_ok}}

    # ---- 3.6 / 3.7 delegated coordinators (stubs pending M6 / M12) ----
    def run_verdict(self, feature_id: str, branch: str) -> dict:  # pragma: no cover - M6 stub
        raise NotImplementedError("Verdict Coordinator drives the GovernanceEngine — arrives with Module 6")

    def direct_merge(self, branch: str, signature_ref: str) -> dict:  # pragma: no cover - M12 stub
        raise NotImplementedError("Gitea Director performs the real merge — arrives with Module 12")
