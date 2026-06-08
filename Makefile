# THOR Enterprise — two test lanes (docs/THOR-TEST-ENVIRONMENT.md).
# LANE 1 (test): fast, docker-free, gates every commit. LANE 2 (prove): live, from clean — the trust bar.
.PHONY: help test prove clean
PY := .venv/bin/python

help:
	@echo "make test  — LANE 1: fast, docker-free; gates every commit (deferred tests deselected)"
	@echo "make prove — LANE 2: boot a fresh plane + real Docker rooms + Postgres from clean; trust bar"
	@echo "make clean — reap THOR rooms + truncate the ledger to genesis"

test:
	$(PY) -m pytest -p no:cacheprovider

prove:
	bash scripts/prove.sh

clean:
	bash scripts/clean.sh
