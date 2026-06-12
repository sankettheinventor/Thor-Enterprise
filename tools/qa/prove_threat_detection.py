"""
RED-TEAM proof — THOR doesn't just BLOCK attacks, it KNOWS one is happening. We stage four real attack
patterns and confirm the Threat Detector names + scores each, records it to the tamper-evident ledger, and
escalates a CRITICAL signal (ledger tamper) to a Sentinel halt.

Run (from ~/thor-enterprise):  PYTHONPATH=. .venv/bin/python tools/qa/prove_threat_detection.py
"""
import json
import os
import tempfile
import time

import docker

from manager import db, pg
from manager.core import ThorManager
from sentinel.core import Sentinel
from sentinel.threat_detector import ThreatDetector

pg.start(docker.from_env())
conn = db.connect()
db.init_schema(conn)
with conn.cursor() as c:
    c.execute("TRUNCATE eventlog, rooms, cards, features")
conn.commit()
mgr = ThorManager(conn)
sentinel = Sentinel(mgr)
mgr.attach_sentinel(sentinel)


def _v(decision):
    return type("V", (), {"decision": decision, "reason": "out of scope", "classification": "denied"})()


# 1. SCOPE-PROBING — a cook hammering the boundary: 5 denied out-of-scope writes
for i in range(5):
    mgr.record_decision(_v("deny"), {"room_id": "room-1", "type": "tool_call", "name": "write_file",
                                     "target": f"infra/secret_{i}.tf"})

# 2. SIGNATURE-FORGERY — 3 forged approval attempts
card = mgr.raise_card("merge", "FX", {"feature_id": "FX"})
for _ in range(3):
    mgr.approve(card, "forged-signature", "ROGUE-OPERATOR-KEY")

# 3. EXFILTRATION — 6 blocked egress attempts in the gateway decision log
gw = os.path.join(tempfile.gettempdir(), "thor-leash", "decisions.jsonl")
os.makedirs(os.path.dirname(gw), exist_ok=True)
with open(gw, "w") as f:
    for i in range(6):
        f.write(json.dumps({"ts": time.time(), "type": "egress", "host": f"evil{i}.attacker.tld",
                            "decision": "deny"}) + "\n")

res = ThreatDetector(mgr, gateway_log=gw).run()
fired = {t["name"]: t for t in res["threats"]}
print("detected:")
for t in res["threats"]:
    print(f"  - {t['name']:22} sev={t['severity']:8} STRIDE={t['stride']:24} count={t['count']}")
assert "scope-probing" in fired, "must detect scope probing"
assert "signature-forgery" in fired, "must detect forged signatures"
assert "exfiltration-attempt" in fired, "must detect egress exfiltration"
assert any(e["event_type"] == "threat.detected" for e in mgr.eventlog.all_events()), "threats must be ledgered"

# 4. LEDGER-TAMPER — alter a past row; the chain breaks → CRITICAL → Sentinel halt
with conn.cursor() as c:
    c.execute("UPDATE eventlog SET payload=%s WHERE seq=(SELECT MIN(seq) FROM eventlog)", ('{"tampered":true}',))
conn.commit()
res2 = ThreatDetector(mgr, gateway_log=gw).run()
fired2 = {t["name"]: t for t in res2["threats"]}
print(f"after tamper: {sorted(fired2)}  sentinel.halted={sentinel.halted}")
assert "ledger-tamper" in fired2 and fired2["ledger-tamper"]["severity"] == "critical", "must detect tamper as critical"
assert sentinel.halted, "a critical threat (ledger tamper) must escalate to a Sentinel HALT"
print("THREAT_DETECTION_OK — attacks are named, scored, ledgered, and critical ones halt the system.")
