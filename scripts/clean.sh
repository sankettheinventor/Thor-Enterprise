#!/usr/bin/env bash
# Reap all THOR room containers + truncate the ledger to genesis. Idempotent, safe to re-run.
set -uo pipefail
cd "$(dirname "$0")/.."
.venv/bin/python - <<'PY'
import docker
from manager import db, pg
try:
    cli = docker.from_env(); cli.ping()
except Exception as e:
    print("clean: docker unavailable:", e); raise SystemExit(0)
reaped = []
for c in cli.containers.list(all=True, filters={"label": "thor.room=1"}):
    try:
        c.remove(force=True); reaped.append(c.name)
    except Exception as e:
        print("clean: reap-fail", c.name, e)
print(f"clean: reaped {len(reaped)} THOR room(s): {reaped}")
try:
    pg.start(cli)
    conn = db.connect(); db.init_schema(conn)
    with conn.cursor() as cur:
        cur.execute("TRUNCATE eventlog, rooms, cards, features")
    conn.commit()
    print("clean: ledger truncated -> genesis (0 events)")
except Exception as e:
    print("clean: postgres unavailable:", e)
PY
