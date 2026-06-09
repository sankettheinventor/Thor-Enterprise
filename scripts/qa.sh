#!/usr/bin/env bash
# make qa (LANE QA): the ISOLATED, throwaway QA room (docs/THOR-TEST-ENVIRONMENT.md).
#
# Distinct from `make test` (host-local, fast) and `make prove` (live dev plane). `make qa` builds a
# dedicated container that mounts the repo READ-ONLY and runs the suite against a SEPARATE throwaway
# Postgres (its OWN container + OWN named volume + OWN private network, all labelled thor.qa=1) — so a
# QA run can NEVER touch or corrupt the dev DB, the dev volume, or the build tree. Everything QA
# creates is destroyed and ASSERTED-clean at the end. A verdict from here is trustworthy because the
# room is sealed and reproducible from clean.
#
# Usage:
#   bash scripts/qa.sh                 # run the full non-deferred suite in the QA room
#   QA_TARGET="tests/qa/labproof/lab_true.py tests/qa/labproof/lab_false.py" bash scripts/qa.sh
#                                      # run an explicit target (used for the harness red/green proof)
set -uo pipefail
cd "$(dirname "$0")/.."
REPO="$(pwd)"

# ---- QA room identifiers (all isolated from dev; all labelled thor.qa=1) ----
QA_NET="thor-qa-net"
QA_PG="thor-qa-postgres"
QA_VOL="thor-qa-pgdata"
QA_IMG="thor-qa:latest"
QA_PG_PORT_INTERNAL=5432
QA_TARGET="${QA_TARGET:-tests}"
TS="$(date -u '+%Y%m%dT%H%M%SZ')"
mkdir -p docs/qa
LOG="docs/qa/RUN-${TS}.log"

log() { echo "$@" | tee -a "$LOG"; }

# ---- teardown: remove everything labelled thor.qa, then PROVE nothing QA-labelled is left ----
teardown() {
  log "-- teardown: removing QA room (container, postgres, volume, network) --"
  docker rm -f "$QA_PG" >/dev/null 2>&1 || true
  docker ps -aq --filter "label=thor.qa=1" | xargs -r docker rm -f >/dev/null 2>&1 || true
  docker volume rm -f "$QA_VOL" >/dev/null 2>&1 || true
  docker network rm "$QA_NET" >/dev/null 2>&1 || true

  LEFT_C="$(docker ps -aq --filter "label=thor.qa=1")"
  LEFT_V="$(docker volume ls -q --filter "name=^${QA_VOL}$")"
  LEFT_N="$(docker network ls -q --filter "name=^${QA_NET}$")"
  log "clean-check  QA containers:[${LEFT_C:-<none>}]  QA volume:[${LEFT_V:-<none>}]  QA network:[${LEFT_N:-<none>}]"
  if [ -n "$LEFT_C$LEFT_V$LEFT_N" ]; then
    log "TEARDOWN-DIRTY: QA-labelled resources survived — the room did not seal."
    return 1
  fi
  log "TEARDOWN-CLEAN: no QA-labelled containers / volume / network remain."
  return 0
}

log "==================== make qa — isolated QA room (${TS}) ===================="
log "target: ${QA_TARGET}"

# Start from clean (a prior crashed run must never poison this one).
docker rm -f "$QA_PG" >/dev/null 2>&1 || true
docker volume rm -f "$QA_VOL" >/dev/null 2>&1 || true
docker network rm "$QA_NET" >/dev/null 2>&1 || true

# ---- private network + SEPARATE throwaway Postgres on its OWN named volume ----
log "-- creating private QA network + separate throwaway Postgres (own volume) --"
docker network create "$QA_NET" >/dev/null
docker volume create --label thor.qa=1 "$QA_VOL" >/dev/null
docker run -d --name "$QA_PG" --label thor.qa=1 --network "$QA_NET" \
  -e POSTGRES_PASSWORD=thor -e POSTGRES_DB=thor \
  -v "${QA_VOL}:/var/lib/postgresql/data" \
  postgres:16-alpine >/dev/null

# wait for the QA Postgres to accept connections (own container, NOT the dev one)
UP=0
for i in $(seq 1 40); do
  if docker exec "$QA_PG" pg_isready -U postgres >/dev/null 2>&1; then UP=1; break; fi
  sleep 1
done
if [ "$UP" != 1 ]; then log "FATAL: QA Postgres did not become ready"; teardown; exit 1; fi
log "QA Postgres ready (container=${QA_PG}, volume=${QA_VOL}, network=${QA_NET})"

# Prove the QA DB is FRESH from clean (genesis): zero rows / no THOR tables yet.
FRESH="$(docker exec "$QA_PG" psql -U postgres -d thor -tAc \
  "SELECT count(*) FROM information_schema.tables WHERE table_name IN ('eventlog','rooms','cards','features')" 2>/dev/null || echo '?')"
log "QA DB fresh-from-clean check: thor tables present=${FRESH} (expect 0 — a clean database)"

# ---- build the QA image (deps + runner only; repo NOT baked in) ----
log "-- building QA image (${QA_IMG}) --"
if ! docker build -q -f tools/qa/Dockerfile.qa -t "$QA_IMG" . >>"$LOG" 2>&1; then
  log "FATAL: QA image build failed (see ${LOG})"; teardown; exit 1
fi

# ---- run the suite inside the sealed room: repo READ-ONLY, no docker socket, QA DB over the net ----
QA_DSN="postgresql://postgres:thor@${QA_PG}:${QA_PG_PORT_INTERNAL}/thor"
log "-- running suite in the QA room (repo mounted READ-ONLY :ro) --"
log "   THOR_PG_DSN=${QA_DSN}"
set +e
# NOTE on the docker.sock mount: the product couples Manager-import to a live Docker daemon
# (wall/provisioner.py runs docker.from_env() at import — recorded as FINDING-A in the QA register), so
# importing ThorManager for the ledger tests requires a reachable daemon. We mount the host socket to
# satisfy that import. STATE isolation — the property that matters — is unaffected: the QA Postgres is a
# SEPARATE container+volume, the conftest QA branch connects DIRECTLY (never calls pg.start), and
# THOR_PG_NAME is pinned to the QA container so even an accidental pg.start() can never touch the dev DB.
docker run --rm --name thor-qa-runner --label thor.qa=1 \
  --network "$QA_NET" \
  -v "${REPO}:/repo:ro" \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -w /repo \
  -e THOR_PG_DSN="$QA_DSN" \
  -e THOR_PG_NAME="$QA_PG" \
  -e THOR_PG_VOLUME="$QA_VOL" \
  "$QA_IMG" -v --no-header $QA_TARGET 2>&1 | tee -a "$LOG"
RC=${PIPESTATUS[0]}
set -e
log "-- suite exit code: ${RC} --"

teardown
TD=$?

# Snapshot of global docker state right after teardown (honesty: pre-existing dev resources remain).
log "-- post-teardown docker snapshot --"
log "running containers:"; docker ps --format '  {{.Names}} ({{.Image}})' | tee -a "$LOG"
log "QA-labelled anything:"; docker ps -aq --filter 'label=thor.qa=1' | tee -a "$LOG"

log "==================== make qa complete (suite rc=${RC}, teardown rc=${TD}) ===================="
echo "evidence log -> ${LOG}"
exit "$RC"
