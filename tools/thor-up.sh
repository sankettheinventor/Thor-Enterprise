#!/usr/bin/env bash
# THOR — one-command launcher for governing a project.
#
#   ./tools/thor-up.sh <path-to-git-repo> [project-name]
#
# Starts the control plane pointed at your project. KEEP THIS TERMINAL OPEN — the plane lives as long as
# this process runs (closing it stops THOR). Open the cockpit at http://localhost:7080/ to watch + sign.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"        # the thor-enterprise checkout
PROJECT="${1:?usage: thor-up.sh <path-to-git-repo> [project-name]}"
NAME="${2:-$(basename "$PROJECT")}"

# --- preflight: the project must be a writable git repo with a main branch ---
PROJECT="$(cd "$PROJECT" && pwd)"
if [ ! -d "$PROJECT/.git" ]; then
  echo "ERROR: $PROJECT is not a git repo. Run:  git init && git add -A && git commit -m init && git branch -M main"
  exit 1
fi
git -C "$PROJECT" rev-parse --verify main >/dev/null 2>&1 || {
  echo "ERROR: $PROJECT has no 'main' branch. Run:  git -C '$PROJECT' branch -M main"; exit 1; }

# --- the cook reuses your EXISTING Claude login (no API key, no extra cost) ---
CREDS="$HOME/.claude/.credentials.json"
if [ ! -f "$CREDS" ] && ! ls /mnt/c/Users/*/.claude/.credentials.json >/dev/null 2>&1 \
   && [ -z "${CLAUDE_CODE_OAUTH_TOKEN:-}" ]; then
  echo "WARN: no Claude login found. Log into Claude Code first (so the cook can build), or set CLAUDE_CODE_OAUTH_TOKEN."
fi

export THOR_PROJECT_REPO="$PROJECT"
export THOR_COOK="${THOR_COOK:-claude-code}"
export THOR_VERIFY_IMAGE="${THOR_VERIFY_IMAGE:-thor-room-claude:latest}"   # polyglot: python + node
export THOR_PG_VOLUME="${THOR_PG_VOLUME:-thor-pgdata-$NAME}"                # per-project persistent ledger
export THOR_BUILD_CAPACITY="${THOR_BUILD_CAPACITY:-1}"

echo "THOR governing : $PROJECT"
echo "cook           : $THOR_COOK   verify image: $THOR_VERIFY_IMAGE   ledger volume: $THOR_PG_VOLUME"
echo "cockpit        : http://localhost:7080/   (keep this terminal open)"
echo "------------------------------------------------------------------------"
cd "$REPO_DIR"
exec ./.venv/bin/python tools/start_thor.py
