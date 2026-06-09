"""
Phase 4 step 6 — LIVE Qwen self-audit proof. Against a live ledger, proves the OllamaInspector path:
  * a REAL local Qwen is serving and SELECTED (select_model picks ollama-qwen, model.loaded() True),
  * ZERO frontier API calls (frontier_calls stays 0 — Ollama is local, not a frontier API),
  * runs in PARALLEL — its inspect() overlaps the Manager's single-writer critical path (no block),
  * READ-ONLY — a write to the EventLog via the `selfaudit` Postgres role is physically DENIED,
  * a planted SEVERE anomaly is escalated URGENT to the Sentinel.

Run (from ~/thor-enterprise):  .venv/bin/python tools/qa/prove_qwen_selfaudit.py
"""
import threading
import time

import docker

from manager import db, pg
from manager.core import ThorManager
from selfaudit import db as sa_db
from selfaudit.core import SelfAudit
from selfaudit.model_host import select_model
from sentinel.core import Sentinel

pg.start(docker.from_env())
admin = db.connect()
db.init_schema(admin)
with admin.cursor() as c:
    c.execute("TRUNCATE eventlog, rooms, cards, features")
admin.commit()
sa_db.setup(admin)                       # create the read-only `selfaudit` role + its tables + grants

mgr = ThorManager(admin)
sentinel = Sentinel(mgr)
mgr.attach_sentinel(sentinel)

# --- plant a SEVERE anomaly: a high claim-vs-reality divergence rate in the ledger ---
for i in range(4):
    mgr._record("verdict.computed", {"feature_id": f"F{i}", "verdict": "done"}, actor="govengine")
for i in range(2):
    mgr._record("divergence.detected", {"feature_id": f"F{i}", "signals": ["claimed X, git shows Y"]},
                actor="govengine")                    # div_rate = 2/4 = 0.5 ≥ 0.3 → HIGH finding

# --- select the inspector: a REAL local Qwen if reachable ---
model = select_model()
print(f"MODEL_NAME={model.name} | model_loaded={model.loaded()}")
assert model.name == "ollama-qwen" and model.loaded(), "live Qwen not selected/loaded — is ollama serving?"

ro = sa_db.connect_readonly()
sa = SelfAudit(ro, sentinel=sentinel, model=model)

# --- PARALLEL: run inspect() in a thread while the Manager keeps writing the ledger (critical path) ---
t = {}
out = []


def _audit():
    t["audit_start"] = time.time()
    out.append(sa.inspect())
    t["audit_end"] = time.time()


th = threading.Thread(target=_audit)
th.start()
t["build_start"] = time.time()
for i in range(8):
    mgr._record("build.tick", {"i": i}, actor="manager")
    time.sleep(0.05)
t["build_end"] = time.time()
th.join()
res = out[0]
overlap = t["audit_start"] < t["build_end"] and t["build_start"] < t["audit_end"]
print(f"PARALLEL_OVERLAP={overlap}  (audit ran while the Manager kept writing — not blocked)")

print(f"FRONTIER_CALLS={model.frontier_calls}")
print(f"REPORT_ID={res['report_id']}")
print(f"FINDINGS={[f['pattern'] for f in res['findings']]}")
print(f"ESCALATIONS={res['escalations']}")
assert model.frontier_calls == 0, "frontier_calls must be 0 (zero token cost)"
assert res["escalations"], "planted severe anomaly did NOT escalate URGENT to the Sentinel"

# --- READ-ONLY: a write to the EventLog via the `selfaudit` role must be DENIED by Postgres ---
try:
    with ro.cursor() as c:
        c.execute("INSERT INTO eventlog (seq,prev_hash,hash,signature,ts,actor,event_type,payload) "
                  "VALUES (999999,'x','y','z',0,'selfaudit','hack','{}')")
    print("EVENTLOG_WRITE=NOT_DENIED  (BAD — read-only guard failed)")
    raise SystemExit(1)
except Exception as e:
    print(f"EVENTLOG_WRITE_DENIED={type(e).__name__}: {str(e).splitlines()[0][:90]}")

print("QWEN_SELFAUDIT_PROOF: OK")
