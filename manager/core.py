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
import os
import time
import uuid

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from wall import provisioner
from wall.identity_stamper import IdentityStamper, _unb64

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
    def __init__(self, conn, stamper: IdentityStamper | None = None,
                 audit=None, identity=None) -> None:
        self.conn = conn
        self.stamper = stamper or IdentityStamper()
        # T10 — the Strangler made real: THOR speaks ONLY the AuditPort/IdentityPort vocabulary, so the
        # audit + identity vendor each swaps behind ONE adapter file (default = THOR's own chain + Ed25519).
        from adapters.audit_adapter import ChainAudit
        from adapters.identity_adapter import MeshIdentity
        self.eventlog = audit or ChainAudit(EventLogWriter(conn, self.stamper))   # swappable AuditPort
        self.identity = identity or MeshIdentity(self.stamper)                    # swappable IdentityPort
        self._eventlog_writable = True   # toggled to demonstrate fail-closed (AC-7)
        self.sentinel = None             # attached at boot; the Coordinator escalates caught lies to it
        self.authorized_signers: set[str] = set()   # T7: only these Ed25519 keys may sign cards (COMMANDERS)
        self.user_roles: dict[str, str] = {}         # RBAC: pubkey -> role (commander/operator/viewer)
        self._challenges: dict[str, str] = {}        # T7: one-time per-card nonces (replay defence)

    def attach_sentinel(self, sentinel) -> None:
        """Wire the Sentinel so a caught lie (divergence) escalates to meta-governance (T5)."""
        self.sentinel = sentinel

    # ---- T7: human-signs authority — registered operator/device keys + one-time card nonces ----
    def register_operator(self, pub_b64: str) -> None:
        """Register an authorized signer. Use at BOOT (from THOR_OPERATOR_PUBKEYS) or to bootstrap the
        FIRST operator. After one operator exists, a NEW key must be added via `register_operator_signed`
        — a transport token alone must NOT mint signing authority (AUD-register-authority). A bare operator
        registration is a COMMANDER (the merge-signing authority); RBAC users come in via `register_user`."""
        self.authorized_signers.add(pub_b64)
        self.user_roles[pub_b64] = "commander"

    def register_user(self, user_id: str, role: str, pub_b64: str) -> None:
        """RBAC: bind an Ed25519 key to a role. ONLY a COMMANDER's key enters `authorized_signers`, so only
        a commander can ever sign a merge — an operator/viewer key is a known identity with NO merge
        authority, even though its holder's TOKEN can drive the build flow (transport authZ is separate).
        Used at boot from THOR_USERS; an operator/viewer key registered here is removed from the signer set
        if it was somehow present (defence-in-depth against a mis-seeded roster)."""
        if pub_b64:
            self.user_roles[pub_b64] = role
            if role == "commander":
                self.authorized_signers.add(pub_b64)
            else:
                self.authorized_signers.discard(pub_b64)

    def register_operator_signed(self, new_pub_b64: str, signature_b64: str, by_pub_b64: str) -> dict:
        """Add a new operator key ONLY if an existing operator co-signed it (Ed25519 over the new key)."""
        if not self.authorized_signers or by_pub_b64 not in self.authorized_signers:
            return {"registered": False, "reason": "co-signer is not a registered operator"}
        if not self.identity.verify_signature(by_pub_b64, new_pub_b64, signature_b64)["valid"]:
            return {"registered": False, "reason": "invalid co-signature over the new key"}
        self.authorized_signers.add(new_pub_b64)
        self._record("operator.registered", {"new_pub": new_pub_b64, "by": by_pub_b64})
        return {"registered": True}

    def is_authorized_signer(self, pub_b64: str) -> bool:
        if self.authorized_signers:
            return pub_b64 in self.authorized_signers           # only registered keys may sign
        # No operator registered: accept any ONLY in dev/test (no API token). PRODUCTION (token set) is
        # fail-CLOSED — an unconfigured signer set must never accept an arbitrary key (AUD-register-authority).
        return not os.environ.get("THOR_API_TOKEN")

    def issue_challenge(self, card_id: str) -> str:
        """Issue a one-time nonce bound to this card; a signature must carry it, and it is consumed on
        use — so a captured signature cannot be replayed."""
        nonce = uuid.uuid4().hex
        self._challenges[card_id] = nonce
        return nonce

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
            {"decision_id": action.get("decision_id"),   # H7: preserve the Leash's decision_id
             "room_id": action.get("room_id"),
             "action": {"type": action.get("type"), "name": action.get("name"),
                        "target": action.get("target")},
             "decision": verdict.decision, "reason": verdict.reason,
             "classification": verdict.classification},
            actor="leash", room_id=action.get("room_id"),
        )

    def record_threat(self, threat: dict) -> dict:
        """Record a detected attack signature (the Threat Detector's output) to the tamper-evident ledger
        so an operator can reconstruct the incident (security invariant #7: audit for incident response)."""
        return self._record("threat.detected", threat, actor="threat-detector")

    # ---- 3.2 Lifecycle Coordinator (drives the Wall) ----
    def provision_room(self, feature_id: str, task_type: str = "build", branch: str | None = None,
                       network_mode: str = "sealed", **wall_kw) -> dict:
        if self.sentinel is not None and getattr(self.sentinel, "halted", False):
            raise RuntimeError("HALTED — the Sentinel is not accepting new work (a governor failed)")
        branch = branch or f"feature/{feature_id}"
        with self.conn.cursor() as cur:  # FR-20 one-branch-one-room
            cur.execute("SELECT room_id FROM rooms WHERE branch=%s AND status='working'", (branch,))
            if cur.fetchone():
                raise ValueError(f"one-branch-one-room: {branch} already owned")
        room = provisioner.provision_room(task_type=task_type, network_mode=network_mode,
                                          feature_slice={"feature_id": feature_id}, **wall_kw)
        # FR-5 verify the Wall's identity token before trusting/registering the room
        if not self.identity.verify_identity(room["identity_token"], room["room_id"])["valid"]:
            provisioner.destroy_room(room["room_id"], room.get("_mount_plan"))
            raise ValueError("identity verification failed — room refused")
        self._record("room.provisioned",
                     {"room_id": room["room_id"], "container": room["container"],
                      "task_type": task_type, "feature_id": feature_id, "branch": branch,
                      "status": "working", "identity_token": room["identity_token"],
                      "address": room.get("address")},   # M10: routable address into the registry
                     room_id=room["room_id"], feature_id=feature_id)
        room["_branch"] = branch
        return room

    def destroy_room(self, room_id: str, mount_plan=None) -> dict:
        provisioner.destroy_room(room_id, mount_plan)
        self._record("room.destroyed", {"room_id": room_id, "status": "destroyed",
                                        "branch_preserved": True}, room_id=room_id)
        return {"room_id": room_id, "status": "destroyed", "branch_preserved": True}

    def verify_room_identity(self, room_id: str, token: str) -> bool:  # FR-5 / AC-8
        return self.identity.verify_identity(token, room_id)["valid"]

    # ---- crash-resume of in-flight work (AC-8): run at boot, AFTER rebuild_from_log ----
    _INFLIGHT_STATES = ("building", "in_qa")

    def _working_room_ids(self, feature_id: str) -> list[str]:
        with self.conn.cursor() as cur:
            cur.execute("SELECT room_id FROM rooms WHERE feature_id=%s AND status='working'", (feature_id,))
            return [r[0] for r in cur.fetchall()]

    def recover_in_flight(self) -> dict:
        """Crash-resume. The control plane has JUST started, so nothing is actively building yet — any
        feature whose projected status is mid-flight (`building`/`in_qa`) is an interrupted build from before
        the crash. Re-queue it to `ready` (the scheduler re-dispatches; the verdict re-judges from reality,
        so no false `done` can slip through), and mark its orphaned `working` room destroyed (branch
        preserved) so a fresh room can be provisioned (FR-20 one-branch-one-room). Idempotent; never touches
        `awaiting_signature` (work done, human pending) or `done`. Projection rebuild runs first."""
        recovered = []
        for f in self.list_features():
            if (f.get("status") or "backlog") not in self._INFLIGHT_STATES:
                continue
            fid = f["feature_id"]
            for room_id in self._working_room_ids(fid):
                # The container (if any) died with the crash; record the projection-level teardown so the
                # branch is freed for a fresh room. (Best-effort docker reap is the provisioner's job.)
                self._record("room.destroyed",
                             {"room_id": room_id, "status": "destroyed", "branch_preserved": True,
                              "reason": "crash-recovery"}, room_id=room_id, feature_id=fid)
            self.set_feature_status(fid, "ready")
            self._record("feature.recovered", {"feature_id": fid, "from": f.get("status")}, feature_id=fid)
            recovered.append({"feature_id": fid, "from": f.get("status")})
        return {"recovered": recovered}

    # ---- 3.5 Card & Signature Authority (the three signature points) ----
    def raise_card(self, type_: str, feature_id: str, payload: dict, held: bool = False) -> str:
        card_id = "card-" + uuid.uuid4().hex[:8]
        status = "held" if held else "open"
        self._record("card.raised", {"card_id": card_id, "type": type_, "feature_id": feature_id,
                                     "payload": payload, "status": status}, feature_id=feature_id)
        hook = getattr(self, "on_card_raised", None)   # optional push-notify hook (the plane sets it)
        if hook:
            try:
                hook(card_id, type_, feature_id, status)
            except Exception:  # noqa: BLE001 — a notification must NEVER break governance
                pass
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
    def card_material(card_id: str, payload: dict, nonce: str | None = None) -> str:
        """What a human signs: card-id bound to the payload hash (D5), and (T7) a one-time nonce."""
        base = f"{card_id}|{hashlib.sha256(_canon(payload).encode()).hexdigest()}"
        return f"{base}|{nonce}" if nonce else base

    def _sig_rejected(self, card_id: str, reason: str, signer_pub_b64: str = "") -> dict:
        """Record a rejected signature attempt (spoofing/replay signal the Threat Detector scores) and
        return the standard failure dict."""
        self._record("signature.rejected", {"card_id": card_id, "reason": reason,
                                             "signer": (signer_pub_b64 or "")[:12]})
        return {"verified": False, "reason": reason}

    def approve(self, card_id: str, signature_b64: str, signer_pub_b64: str,
                nonce: str | None = None) -> dict:
        card = self._get_card(card_id)
        if not card or card["status"] in ("approved", "rejected"):
            return self._sig_rejected(card_id, "card not open", signer_pub_b64)   # replay on a decided card
        if not self.is_authorized_signer(signer_pub_b64):
            return self._sig_rejected(card_id, "unauthorized signer — not a registered operator key", signer_pub_b64)
        # BUG-3: the one-time nonce is MANDATORY — an absent nonce no longer skips the replay lock.
        # A captured/pre-signed no-nonce signature must be rejected; the card stays open. (fail-closed)
        if nonce is None or self._challenges.get(card_id) != nonce:
            return self._sig_rejected(card_id, "missing or replayed challenge — card stays open", signer_pub_b64)
        material = self.card_material(card_id, card["payload"], nonce)
        if not self.identity.verify_signature(signer_pub_b64, material, signature_b64)["valid"]:
            return self._sig_rejected(card_id, "signature invalid — card stays open", signer_pub_b64)  # AC-5
        self._challenges.pop(card_id, None)                            # consume the nonce (replay defence)
        self._record("card.approved", {"card_id": card_id, "decided_by": signer_pub_b64[:12],
                                      "signature": signature_b64}, feature_id=card["feature_id"])
        return {"verified": True, "action_taken": "approved"}

    def reject_card(self, card_id: str, signature_b64: str, signer_pub_b64: str,
                    nonce: str | None = None, reason: str = "") -> dict:
        """Decline a card with the SAME signed-authority guarantees as approve (registered signer +
        mandatory one-time nonce — a captured reject can't be replayed). Records card.rejected."""
        card = self._get_card(card_id)
        if not card or card["status"] in ("approved", "rejected"):
            return {"verified": False, "reason": "card not open"}
        if not self.is_authorized_signer(signer_pub_b64):
            return {"verified": False, "reason": "unauthorized signer — not a registered operator key"}
        if nonce is None or self._challenges.get(card_id) != nonce:
            return {"verified": False, "reason": "missing or replayed challenge — card stays open"}
        material = self.card_material(card_id, card["payload"], nonce)
        if not self.identity.verify_signature(signer_pub_b64, material, signature_b64)["valid"]:
            return {"verified": False, "reason": "signature invalid — card stays open"}
        self._challenges.pop(card_id, None)
        self._record("card.rejected", {"card_id": card_id, "decided_by": signer_pub_b64[:12],
                                      "reason": reason}, feature_id=card["feature_id"])
        return {"verified": True, "action_taken": "rejected"}

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

    def all_bugs(self) -> list[dict]:
        """Every bug found across the line (QA + checker), newest first — the cockpit 'new bugs' feed."""
        with self.conn.cursor() as cur:
            cur.execute("SELECT bug_id,feature_id,severity,description,source,status,found_at FROM bugs "
                        "ORDER BY found_at DESC")
            return [{"bug_id": r[0], "feature_id": r[1], "severity": r[2], "description": r[3],
                     "source": r[4], "status": r[5]} for r in cur.fetchall()]

    # ---- feature catalog (Kind C) — directed by the PM Surface (Module 8), event-sourced ----
    def add_feature(self, feature_id: str, title: str, context: str = "", priority: int = 3,
                    est_tokens: int = 1000) -> str:
        self._record("feature.added", {"feature_id": feature_id, "title": title, "context": context,
                                      "priority": priority, "est_tokens": est_tokens,
                                      "status": "backlog"}, feature_id=feature_id)
        return feature_id

    def set_feature_status(self, feature_id: str, status: str) -> None:
        self._record("feature.status", {"feature_id": feature_id, "status": status}, feature_id=feature_id)

    def set_feature_priority(self, feature_id: str, priority: int) -> None:
        self._record("feature.priority", {"feature_id": feature_id, "priority": int(priority)},
                     feature_id=feature_id)

    def remove_feature(self, feature_id: str) -> None:
        """Remove a feature from the catalog (event-sourced — the ledger keeps the full history)."""
        self._record("feature.removed", {"feature_id": feature_id}, feature_id=feature_id)

    def list_features(self) -> list[dict]:
        with self.conn.cursor() as cur:
            cur.execute("SELECT feature_id,title,priority,status,est_tokens,context FROM features "
                        "ORDER BY priority NULLS LAST, feature_id")
            out = []
            for r in cur.fetchall():
                feat = {"feature_id": r[0], "title": r[1], "priority": r[2], "status": r[3], "est_tokens": r[4]}
                if r[5]:                                  # Genesis stores the rich plan (tasks/QA/etc.) in context
                    try:
                        c = json.loads(r[5])
                        for k in ("summary", "acceptance_criteria", "tasks", "qa_cases", "depends_on"):
                            if c.get(k):
                                feat[k] = c[k]
                    except (ValueError, TypeError):
                        pass
                out.append(feat)
            return out

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
                    "address,identity_token,created_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                    "ON CONFLICT (room_id) DO UPDATE SET status=EXCLUDED.status, "
                    "address=EXCLUDED.address",
                    (p["room_id"], p.get("container"), p["task_type"], p["feature_id"],
                     p["branch"], p["status"], p.get("address"), p.get("identity_token"), time.time()))
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
            elif event_type == "card.rejected":
                cur.execute("UPDATE cards SET status='rejected', decided_by=%s, decided_at=%s "
                            "WHERE card_id=%s", (p["decided_by"], time.time(), p["card_id"]))
            elif event_type == "feature.added":
                cur.execute("INSERT INTO features (feature_id,title,context,priority,status,est_tokens)"
                            " VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT (feature_id) DO UPDATE SET "
                            "title=EXCLUDED.title, priority=EXCLUDED.priority",
                            (p["feature_id"], p.get("title"), p.get("context"), p.get("priority"),
                             p.get("status", "backlog"), p.get("est_tokens", 1000)))
            elif event_type == "feature.status":
                cur.execute("UPDATE features SET status=%s WHERE feature_id=%s",
                            (p["status"], p["feature_id"]))
            elif event_type == "feature.priority":
                cur.execute("UPDATE features SET priority=%s WHERE feature_id=%s",
                            (p["priority"], p["feature_id"]))
            elif event_type == "feature.removed":
                cur.execute("DELETE FROM features WHERE feature_id=%s", (p["feature_id"],))
        self.conn.commit()

    def rebuild_from_log(self) -> None:
        """FR-13: clear the projections and rebuild them purely by replaying the EventLog. The hash-chain
        is VERIFIED first — a boot/replay on a tampered ledger fails CLOSED rather than rebuilding forged
        state (the chain integrity guarantee is now enforced on the load-bearing replay path, not just in
        smokes)."""
        if not self.eventlog.verify_chain():
            raise RuntimeError("ledger hash-chain verification FAILED — refusing to replay a tampered ledger")
        with self.conn.cursor() as cur:
            cur.execute("TRUNCATE rooms, cards, features")
        self.conn.commit()
        for e in self.eventlog.all_events():
            self._project(e["event_type"], json.loads(e["payload"]))

    def state_summary(self) -> dict:
        """The projected current state (registry + open cards) — for the Dashboard and AC-3 diff."""
        s: dict = {"rooms": {}, "cards": {}}
        with self.conn.cursor() as cur:
            cur.execute("SELECT room_id,task_type,feature_id,branch,status,address FROM rooms "
                        "ORDER BY room_id")
            for r in cur.fetchall():
                s["rooms"][r[0]] = {"task_type": r[1], "feature_id": r[2], "branch": r[3],
                                    "status": r[4], "address": r[5]}   # M10: routable address per room
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
    def run_verdict(self, feature_id: str, branch: str, repo: str) -> dict:
        """
        C4 — the HONEST Verdict Coordinator. Derives claim / contract / commit_window from TRUSTED
        state — the recorded assign_task slice (PM/Contract), the ledger window, the Leash decision
        records — NEVER from the actor. Then drives the (unchanged) GovernanceEngine. On a caught lie
        (divergence) it runs the dishonesty loop: record the incident, escalate to the Sentinel, and
        return a legible 'you avoided/misreported X' message for the cook. The moat gets harder.
        """
        from govengine import reality, skill_verifier
        from govengine.engine import GovernanceEngine, VerdictContext

        events = self.eventlog.all_events()
        room_id = self._room_for_feature(feature_id, events)
        window = self._trusted_window(feature_id, events)
        contract = self._trusted_contract(feature_id, events)
        claim = self._trusted_claim(feature_id, room_id, window, events)

        # H2: real per-skill verdicts from artifacts — R1 is computed, never defaulted True.
        try:
            changed = reality.changed_files(repo, branch, "main")
        except reality.RealityError:
            changed = set()
        test_files = [f for f in (contract.get("test_file"), contract.get("regression_file")) if f]
        skill_ok, skill_results = skill_verifier.verify(repo, changed, test_files)

        ctx = VerdictContext(feature_id, branch, repo, contract=contract, claim=claim, manager=self,
                             commit_window=window, skill_results_ok=skill_ok)
        result = GovernanceEngine(self).run_verdict(ctx)
        result["room_id"] = room_id
        result["skill_results"] = skill_results

        if result["divergence"]["found"]:                      # a lie/avoidance was caught
            result["cook_feedback"] = self._dishonesty_loop(feature_id, room_id, result["divergence"]["signals"])
        return result

    # ---- trusted-state derivations for the Coordinator (the actor supplies NONE of these) ----
    def _room_for_feature(self, feature_id: str, events: list[dict]) -> str | None:
        # The verdict is about the BUILD: target the build room (where the cook worked), not a QA/checker
        # room that shares the feature_id — else the trusted claim is read against the wrong room.
        build_rid = last_rid = None
        for e in events:
            if e["event_type"] == "room.provisioned" and e.get("feature_id") == feature_id:
                p = json.loads(e["payload"])
                last_rid = p.get("room_id")
                if p.get("task_type") == "build":
                    build_rid = p.get("room_id")
        return build_rid or last_rid

    def _trusted_window(self, feature_id: str, events: list[dict]) -> tuple[int, int]:
        seqs = [e["seq"] for e in events if e.get("feature_id") == feature_id]
        lo = min(seqs) if seqs else 0
        hi = max(e["seq"] for e in events) if events else 0
        return (lo, hi)

    def _trusted_contract(self, feature_id: str, events: list[dict]) -> dict:
        """Read the spec from the recorded assign_task slice (trusted) — never an actor-curated scope."""
        slice_ = None
        for e in events:
            if e["event_type"] == "contract.assign_task":
                fs = json.loads(e["payload"]).get("feature_slice", {})
                if fs.get("feature_id") == feature_id:
                    slice_ = fs
        if not slice_:
            return {"scope": {"files": []}, "contracts": [], "test_file": None, "regression_file": None}
        cdict = slice_.get("contract", {})
        open_bugs = [b for b in self.list_bugs(feature_id) if b["status"] == "open"]
        contracts = [{"name": a, "status": "open" if open_bugs else "done"}
                     for a in cdict.get("acceptance_criteria", [])]
        return {"scope": slice_.get("scope", {"files": []}), "contracts": contracts,
                "test_file": cdict.get("test_file"), "regression_file": cdict.get("regression_file"),
                "protected_files": []}

    def _trusted_claim(self, feature_id: str, room_id: str | None,
                       window: tuple[int, int], events: list[dict]) -> dict:
        """Reconstruct the agent's effective claim from TRUSTED records (Option A): files_touched =
        the Leash's recorded allowed writes; tests_passed = a claim_done knock exists. The actor can
        never hand over a blank/curated claim to disable the lie-detector."""
        lo, hi = window
        files_touched, knocked = [], False
        for e in events:
            if not (lo <= e["seq"] <= hi):
                continue
            if e["event_type"] == "action.decided":
                p = json.loads(e["payload"])
                if p.get("decision") == "allow" and (room_id is None or p.get("room_id") == room_id):
                    tgt = (p.get("action") or {}).get("target")
                    if tgt:
                        files_touched.append(tgt)
            elif e["event_type"] == "contract.claim_done":
                if json.loads(e["payload"]).get("feature_id") == feature_id:
                    knocked = True
        return {"files_touched": sorted(set(files_touched)), "tests_passed": knocked}

    def _dishonesty_loop(self, feature_id: str, room_id: str | None, signals: list[str]) -> dict:
        """A caught lie: record the incident (CEO cockpit shows it), escalate to the Sentinel, and
        tell the cook exactly what was avoided/misreported (the correction loop)."""
        container = room_id or "unknown"
        self._record("dishonesty.caught",
                     {"feature_id": feature_id, "room_id": container, "container": container,
                      "signals": signals, "count": 1}, actor="govengine",
                     room_id=room_id, feature_id=feature_id)
        if self.sentinel is not None:                          # → Sentinel (meta-governance)
            self.sentinel.receive_urgent(
                {"detail": f"dishonesty caught in {container}: {'; '.join(signals)}",
                 "scope": f"room:{container}", "room_id": container,
                 "confirmed_critical": False, "source": "govengine"})
        message = ("BLOCKED — your claim does not match reality. This was avoided or misreported: "
                   + "; ".join(signals) + ". Fix it honestly and resubmit — this is on the record.")
        self._record("cook.feedback", {"feature_id": feature_id, "room_id": container,
                     "message": message}, actor="govengine", room_id=room_id, feature_id=feature_id)
        return {"status": "rejected_dishonesty", "room_id": container, "signals": signals,
                "message": message}

    def direct_merge(self, repo: str, branch: str, feature_id: str, signature_ref: str) -> dict:
        """Execute the merge through the Gitea adapter — THOR decides, Gitea executes (S9). The adapter
        refuses without a Signature-3 ref; on success record feature.merged + flip the feature to done."""
        from adapters import gitea_adapter
        pr = gitea_adapter.open_pr(repo, branch, {"feature_id": feature_id})
        res = gitea_adapter.merge(repo, pr["pr_id"], signature_ref)
        if res.get("merged"):
            self._record("feature.merged", {"feature_id": feature_id, "branch": branch,
                         "sha": res.get("sha")}, feature_id=feature_id)
            self.set_feature_status(feature_id, "done")
        return res
