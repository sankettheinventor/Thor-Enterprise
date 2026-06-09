# THOR — RUNBOOK (how to start the control plane)

The wiring phase brings THOR up as ONE control-plane process on the WSL host, with Postgres as its
ledger. This is the single documented start experience for now (a packaged one-command launcher is a
later decision to make together — see `THOR-WIRING-MANUAL.md` Part D).

## Start THOR (dev, one command)

From the repo root, inside the Python venv:

```bash
make start        # = python tools/start_thor.py
```

See it work end to end (one real feature: plan → sealed-room build → QA → verdict → CEO-signed merge,
with an out-of-scope write blocked, a lie caught, and a dead governor halted), then the booted
dashboard reflecting it:

```bash
make demo
```

Reproduce the full proof from a clean state (the trust bar — all integration flows + module ACs over
real Docker + Postgres):

```bash
make prove
```

That cold-starts everything:
- ensures Postgres is up (uses the `thor-postgres` container — auto-bootstrapped if not already
  running; `docker compose up -d postgres` is the declarative equivalent),
- constructs the THOR roles as peers sharing one ledger (CTO · Manager · PM · GovEngine · Sentinel ·
  Self-Audit),
- serves the four HTTP surfaces and prints an "up" banner with the URLs.

Then open the **Dashboard** to see THOR live:

```
http://127.0.0.1:7080/
```

Press **Ctrl-C** to stop.

## The surfaces

| Role | URL |
|---|---|
| Manager (room mechanism + ledger) | http://127.0.0.1:7100 |
| Dashboard (operator cockpit) | http://127.0.0.1:7080/ |
| Sentinel (meta-governance/health) | http://127.0.0.1:7140 |
| Self-Audit (correctness eyes) | http://127.0.0.1:7150 |

## What works at this checkpoint (Task 0)

Task 0 is the **run target** — it makes THOR *stand up and be visible*, not yet *act*:
- ✅ the control plane boots; the four surfaces respond; the dashboard renders **live state** (rooms,
  cards, ledger feed) read from the real Postgres ledger.
- ⏳ **deferred (later tasks):** the cook action loop + decide-before (T3), scheduler dispatch (T4), the
  verdict coordinator (T5), the merge chain (T6), the **click-to-Sign** button (T7), real halt (T8),
  the local Self-Audit model (T9). Your signing authority is unchanged — only the on-screen click is
  deferred until there is a verdict/merge for it to act on.

## Postgres only (alternative)

```bash
docker compose up -d postgres     # bring up just the ledger
python tools/start_thor.py        # the supervisor finds it already reachable
```
