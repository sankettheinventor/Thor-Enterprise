# THOR — Incident Runbook (on-call)

The pager links here. Each section is the remediation for one alert in
`deploy/monitoring/alerts.yml`. Keep steps concrete — a tired on-call at 3am should not have to
reverse-engineer the service. After any incident, run a blameless post-mortem and feed the learning back
into this file and the [GAP & RISK REGISTER](../GAP-AND-RISK-REGISTER.md).

**Service context.** THOR is a single-host control plane (4 FastAPI surfaces on :7080/:7100/:7140/:7150)
over one Postgres ledger, plus ephemeral Docker "rooms" where untrusted AI cooks build. Blast radius if it
goes down: no new governed builds and no merges can be signed — but **nothing already merged is affected**,
and the tamper-evident ledger is durable + backed up. It is not on a customer's request path.

---

## control-plane-down  (`THORControlPlaneDown`, page)
Prometheus can't scrape `/metrics` for >1m.
1. `docker compose -f docker-compose.prod.yml ps` — is `controlplane` up?
2. If crashed: `docker compose -f docker-compose.prod.yml logs --tail=200 controlplane` — look for the boot line `THOR control plane UP`. A clean tail with no "UP" = killed/OOM; a traceback = a real crash.
3. Restart: `docker compose -f docker-compose.prod.yml up -d controlplane`. Boot replays the ledger and re-queues any in-flight build (`recover_in_flight`) — a crash can never resurrect a false `done`.
4. Still down → check Postgres (next section) and host resources (`docker stats`, disk).

## ledger-disconnected  (`THORLedgerDisconnected`, page)
`thor_connected=0` — the Manager can't reach Postgres.
1. `docker compose -f docker-compose.prod.yml ps postgres` and `logs postgres`.
2. The plane self-heals a *dropped* link (`_LockedConn` reconnects). A persistent 0 means Postgres is down or unreachable.
3. Restart Postgres; the plane reconnects automatically. If Postgres data is lost/corrupt → **restore from backup** (see Rollback / DR below).

## sentinel-halted  (`THORSentinelHalted`, page)
A critical governor failed; the line is stopped (this is fail-closed and CORRECT — do not just un-halt).
1. `GET /threats` and the cockpit "Security" tab — what tripped it (ledger tamper? a governor unresponsive?).
2. If a genuine attack/tamper: preserve the ledger, investigate, do NOT clear until understood.
3. If a false halt (e.g. a surface was briefly unresponsive): confirm all surfaces healthy, then restart the plane to clear the halt and re-probe.

## threat-active  (`THORThreatActive`, page)
Named attack signatures over the window. Open `GET /threats` for the STRIDE-tagged signals (scope-probing /
exfiltration / signature-forgery / ledger-tamper). Ledger-tamper auto-escalates to HALT. Treat forgery/tamper
as a real incident: rotate the operator key, audit recent merges, preserve the ledger.

## dishonesty-caught  (`THORDishonestyCaught`, warn)
A cook's claim diverged from git reality and was caught (the moat working). Expected during adversarial runs.
Investigate only if it spikes unexpectedly on trusted work — check `GET /lies` for the container + signals.

## frontier-leak  (`THORFrontierCallLeak`, page)
`thor_frontier_calls_total>0` — the local-only Self-Audit reached an external model (zero-cost invariant
broken). Likely a misconfigured `selfaudit/model_host` or an unexpected egress. Pull the Self-Audit logs,
confirm the Ollama/deterministic backend, and check egress allowlists.

---

## Rollback / Disaster Recovery (tested)

**App rollback (fast, no data change).** Images are versioned + traceable to a commit.
```bash
# roll back to the previous known-good image tag (zero-downtime: compose recreates the one service)
THOR_IMAGE_TAG=<previous-tag> docker compose -f docker-compose.prod.yml up -d controlplane
docker compose -f docker-compose.prod.yml exec controlplane curl -fsS localhost:7080/metrics >/dev/null && echo "healthy"
```

**Data restore (DR).** The ledger is append-only + dumped on a schedule by the `pgbackup` service.
Restore is **tested in CI/live** by `tests/integration/test_backup_restore_rollback.py` (dump → wipe →
restore → `verify_chain` + row-count match). Manual procedure:
```bash
# 1) pick a dump
docker compose -f docker-compose.prod.yml exec pgbackup ls -1 /backups
# 2) restore into Postgres
docker compose -f docker-compose.prod.yml exec -T postgres psql -U postgres thor < /backups/<dump>.sql
# 3) verify the chain is intact AFTER restore (never trust a restore blindly)
docker compose -f docker-compose.prod.yml exec controlplane \
  python -c "from manager import db; from manager.core import ThorManager; \
  print('verify_chain', ThorManager(db.connect()).eventlog.verify_chain())"
```
A restore is only "done" when `verify_chain True` AND the row count matches the dump. The
hash-chain makes silent corruption detectable — a tampered/torn restore fails closed.

**Rule of thumb:** if you cannot answer *how do we know it broke* (alerts above) and *how do we roll back*
(this section), you are not ready — regardless of how green the tests look.
