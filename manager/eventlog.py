"""
Sub-module 3.3 — EventLog Writer. The ONLY writer of the append-only, signed, hash-chained log
(FR-2, FR-8). Tamper-evident (AC-2), idempotent (AC-12), single serialized write path (D1).

Each row's `hash` covers seq + prev_hash + ts + actor + event_type + room_id + feature_id +
the exact canonical payload TEXT, and is Ed25519-signed (wall.identity_stamper). Altering any
column of any past row breaks `verify_chain()`.
"""
from __future__ import annotations

import hashlib
import json
import threading

from wall.identity_stamper import IdentityStamper

GENESIS = "GENESIS"


def _canon(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _material(seq, prev, ts, actor, event_type, room_id, feature_id, payload_text) -> bytes:
    # A single deterministic string over every field — exact round-trip, no JSON re-encode ambiguity.
    return f"{seq}|{prev}|{ts!r}|{actor}|{event_type}|{room_id}|{feature_id}|{payload_text}".encode()


class EventLogWriter:
    def __init__(self, conn, stamper: IdentityStamper | None = None) -> None:
        self.conn = conn
        self.stamper = stamper or IdentityStamper()
        self._lock = threading.Lock()  # serialize the single write path (chain integrity)

    def append(self, event_type: str, payload: dict, actor: str = "manager",
               room_id: str | None = None, feature_id: str | None = None,
               client_id: str | None = None) -> dict:
        import time

        with self._lock:
            with self.conn.cursor() as cur:
                if client_id:  # idempotency: a retry returns the existing row, no new chain entry
                    cur.execute("SELECT seq, hash FROM eventlog WHERE client_id=%s", (client_id,))
                    row = cur.fetchone()
                    if row:
                        return {"seq": row[0], "hash": row[1], "idempotent": True}
                cur.execute("SELECT seq, hash FROM eventlog ORDER BY seq DESC LIMIT 1")
                last = cur.fetchone()
                seq = (last[0] + 1) if last else 0
                prev = last[1] if last else GENESIS
                ts = time.time()
                payload_text = _canon(payload)
                digest = hashlib.sha256(
                    _material(seq, prev, ts, actor, event_type, room_id, feature_id, payload_text)
                ).hexdigest()
                signature = self.stamper.sign_blob(digest.encode())
                cur.execute(
                    "INSERT INTO eventlog (seq,prev_hash,hash,signature,ts,actor,event_type,"
                    "room_id,feature_id,payload,client_id) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (seq, prev, digest, signature, ts, actor, event_type, room_id, feature_id,
                     payload_text, client_id),
                )
            self.conn.commit()
            return {"seq": seq, "hash": digest}

    def all_events(self) -> list[dict]:
        cols = ["seq", "prev_hash", "hash", "signature", "ts", "actor", "event_type",
                "room_id", "feature_id", "payload"]
        with self.conn.cursor() as cur:
            cur.execute(f"SELECT {','.join(cols)} FROM eventlog ORDER BY seq")
            return [dict(zip(cols, r)) for r in cur.fetchall()]

    def count(self) -> int:
        with self.conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM eventlog")
            return cur.fetchone()[0]

    def verify_chain(self) -> bool:
        """Recompute every hash + signature + prev-link from the stored rows. True iff intact."""
        prev = GENESIS
        for e in self.all_events():
            digest = hashlib.sha256(
                _material(e["seq"], e["prev_hash"], e["ts"], e["actor"], e["event_type"],
                          e["room_id"], e["feature_id"], e["payload"])
            ).hexdigest()
            if digest != e["hash"] or e["prev_hash"] != prev:
                return False
            if not self.stamper.verify_blob(digest.encode(), e["signature"]):
                return False
            prev = e["hash"]
        return True
