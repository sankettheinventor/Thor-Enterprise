#!/usr/bin/env bash
# make demo — the live end-to-end story over the BOOTED control plane: boot a fresh plane, run one real
# feature through the whole spine (real Docker rooms, real git, real Ed25519, real halt), then show the
# booted dashboard reflecting it. Deterministic teardown.
set -uo pipefail
cd "$(dirname "$0")/.."
PY=.venv/bin/python

echo "==================== THOR Enterprise — live end-to-end demo ===================="
pkill -f "[s]tart_thor.py" 2>/dev/null || true
sleep 1
bash scripts/clean.sh >/dev/null 2>&1

$PY tools/start_thor.py > .thor/demo-plane.log 2>&1 &
PLANE=$!
for i in $(seq 1 60); do curl -s -m1 http://127.0.0.1:7100/health >/dev/null 2>&1 && break; sleep 1; done
echo "control plane booted — dashboard at http://127.0.0.1:7080/"
echo ""

$PY tools/demo_flow_a.py
RC=$?

echo ""
echo "==================== the booted dashboard now REFLECTS the run ===================="
echo "  /lies (CEO honesty meter): $(curl -s -m3 http://127.0.0.1:7080/lies)"
echo "  /audit feed (last events):  $(curl -s -m3 'http://127.0.0.1:7080/audit/feed' | head -c 240)"

kill "$PLANE" 2>/dev/null || true
sleep 1
pkill -f "[s]tart_thor.py" 2>/dev/null || true
bash scripts/clean.sh >/dev/null 2>&1 || true
echo "==================== demo complete (rc=$RC) ===================="
exit "$RC"
