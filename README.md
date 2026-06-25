<div align="center">

![THOR Enterprise](docs/assets/thor-banner.svg)

# ⚡ THOR Enterprise

### A governance cage for AI coding agents.

**Let an AI build features in your real repo — safely. Every action is checked *before* it runs, every "done" is proven against reality, and nothing merges without *your* signature.**

`single-host` · `any language` · `your Claude/ChatGPT/Kimi plan — no API bill` · `tamper-evident audit ledger`

</div>

---

## What it is, in one breath

You point THOR at your git repo and describe a feature. An AI "cook" builds it **inside a sealed container** it can't escape. A **decide-before guard** vets every file write as it happens. When the cook says "done," THOR doesn't believe it — it **runs the tests sealed and judges the real git diff** with 8 probes. Only a genuinely-passing result becomes a **merge card** that *you* sign with your key. A lying or out-of-scope agent is caught and **never auto-merges**.

It's the cage that lets you use a powerful, untrusted AI builder without trusting it.

---

## 🚀 Quick start (Windows, premium first-run)

You install **nothing** by hand. One line, then click **Allow** a couple of times.

```powershell
# in PowerShell
irm https://raw.githubusercontent.com/sankettheinventor/Thor-Enterprise/main/install.ps1 | iex
```

What it does (all with your permission — Windows shows its own prompts):

1. Installs **Docker** (`winget`) and **WSL2 + Ubuntu** — you click *Allow*.
2. Clones THOR and **builds the engine + the AI room image** (progress shown).
3. Opens the **cockpit** at **http://localhost:7080/**.
4. In the cockpit: a **Setup** panel finishes anything left, then asks **"May THOR use your AI subscription to build?"** → you click **Allow**.

> Want to look before you leap? `install.ps1 -Check` detects everything and installs *nothing*.

Already on Linux/WSL with the repo cloned? Just:

```bash
node bin/thor.js doctor      # checks + auto-builds anything missing
node bin/thor.js run ~/thor-projects/your-repo
```

---

## ✅ What you actually need

THOR sets up the rest itself. You provide three things:

| You need | Why | If missing |
|---|---|---|
| **Docker** | the engine everything runs inside | THOR installs it (winget + your *Allow*) |
| **A Claude login** (or ChatGPT/Codex, Kimi) | the AI builder — runs on **your** plan, no API key, no extra cost | already signed into Claude Code? **nothing to do.** Otherwise: one-time connect |
| **Your project** | a git repo with a `main` branch, in WSL (`~/...`, not `/mnt/c`) | `git init && git branch -M main` |

Run `thor doctor` any time — green ✓ for what's ready, a button for what's not.

---

## ▶️ Using it on your project

```bash
# 1. get your project into WSL as a git repo
git clone https://github.com/you/your-project.git ~/thor-projects/your-project
#    (or fresh: mkdir ~/thor-projects/x && cd $_ && git init && git add -A && git commit -m init && git branch -M main)

# 2. start THOR on it  (KEEP THIS TERMINAL OPEN — the plane runs as long as it does)
node bin/thor.js run ~/thor-projects/your-project
#    or:  npm run dev -- ~/thor-projects/your-project
#    or:  ./tools/thor-up.sh ~/thor-projects/your-project
```

Then open **http://localhost:7080/** and:

1. **Allow** THOR to use your AI login (one click, recorded to the audit ledger).
2. **✨ Plan Project** (AI drafts a feature catalog) — *or* **+ New task** for one feature.
3. Mark a feature **Ready** and watch it move: **Ready → Building → In QA → Awaiting Signature**.
4. When the merge card appears, click **Approve / Sign** → it merges into `main`. Done.

### Is it healthy? Where to look

| Where | Healthy looks like |
|---|---|
| Top banner | 🟢 **"THOR · SAFE — governance up"** |
| System health card | "Sentinel watching · fail-closed halt authority" |
| Nav tabs | Home / Decide / Work / Watch / Security **switch** when clicked |
| `curl localhost:7080/state/summary` | `"connected":true` |
| `curl localhost:7080/metrics` | `thor_connected 1`, `thor_sentinel_halted 0`, `thor_frontier_calls_total 0` |

---

## 🛡 How it keeps you safe (the moat)

Four guarantees, each enforced by real code — not policy, not trust:

1. **Decide-before.** Every cook action (write/edit/command) routes through the **Leash** and is allowed or denied *before* it touches disk. Out-of-scope writes never happen.
2. **Sealed rooms.** The cook runs in a hardened Docker container — read-only root, dropped capabilities, no network except one governed "door" to its model. It cannot reach your host, your secrets, or other rooms.
3. **Done is proven, not claimed.** The verdict runs the tests in a **fresh sealed sandbox** and judges the **real git diff** with 8 probes + a fake-test detector (it guts the code and re-runs — a test that can't fail is rejected). A lie (claim ≠ reality) is caught and escalated.
4. **Human-signed merges.** A "done" raises a **merge card**. It merges only on *your* **Ed25519 signature** (your key never leaves your browser) against a **fresh** verdict. The AI structurally cannot approve its own work.

Underneath it all: a **SHA-256 hash-chained, signed event ledger** — every decision, verdict, signature, and *permission* is a tamper-evident record.

---

## 🔑 Your AI login & your consent

- **No API key, no extra cost.** THOR reuses your existing **Claude** subscription (auto-discovered from your Claude Code / desktop login), or ChatGPT/Codex / Kimi with your own key.
- **It asks first.** THOR will **not** spend your subscription until you explicitly **Allow** it in the cockpit. No consent → the build loop refuses to run. The grant is written to the audit ledger.
- **Your credentials are never committed.** The token lives in `~/.thor` (owner-only), outside any repo; `.gitignore` blocks every credential pattern. The repo holds your code — never your login.

---

## 🧰 Commands

```bash
thor doctor            # check the system + auto-build anything missing
thor run <repo>        # govern a project (live-watch in the cockpit)
thor up                # production boot via Docker Compose (detached; needs THOR_API_TOKEN)
thor status | logs | down

npm run dev -- <repo>  # = thor run
npm run qa             # fast test gate (docker-free)
npm run prove          # full live trust bar (real rooms + Postgres + attack campaign)
npm run build:ui       # build the React cockpit (PWA)
```

> `thor` = `node bin/thor.js`. The `npm run` scripts need a **Linux Node in WSL** (`nvm install --lts`) — Windows Node can't resolve WSL paths.

---

## 📋 Common scenarios

| Situation | What happens |
|---|---|
| Already signed into Claude Code | **Zero paste** — THOR reuses it. |
| Never signed in anywhere | One-time **Connect Claude** (paste a token once, reused forever). |
| You **don't** grant consent | THOR stays idle — it never touches your AI account. ✓ |
| A feature passes the verdict | Merge card → you **Sign** → merges to `main`. |
| A feature fails the verdict | Back to the queue; after 2 tries it's **blocked** for you. **Never auto-merged.** |
| The AI writes out of scope, or lies | Blocked before it lands / caught by the verdict → **escalated to you**. |
| Dashboard says "isn't running" | Usually the **plane process died** (WSL idle-shutdown) — restart it; keep the terminal open, or use `thor up` (detached). |
| You close everything and return | Data is safe (ledger + backups). Restart — it replays and re-checks any half-finished build from reality. |

---

## 📊 Honest status

**Production-ready within its envelope:** a single **team** (roles: viewer / operator / commander), governing AI agents that build and merge features **in any language** into **their own repo**, on one Docker host, with every action governed, every "done" proven, every merge signed. Verified by `make qa` (fast gate) + `make prove` (live, from clean).

**Not yet (named, tracked — not faked):** Postgres HA · distributed tracing · load/soak tests · a live frontier cook without an operator token *(the wiring + a real Claude build are proven)* · the Microsoft AGT real Azure backend · a hosted SaaS. Kubernetes room fleets are **de-scoped** (single-host is the target).

This honesty is a feature: THOR is built on **truth before green** — it never reports something as done that isn't.

---

## 🧱 Architecture (one view)

```
        YOU (cockpit / phone) ──sign──►  Manager ──► one hash-chained ledger (Postgres)
                                            │
   Scheduler ─► PM gate ─► CTO plan ─► provision SEALED ROOM (Docker)
                                            │            cook (Claude/…) builds /work only
                                       Leash (decide-before every action)
                                            │
                                   GovEngine VERDICT  ◄── runs tests SEALED, judges real git diff
                                            │   done? → merge card → YOUR signature → real merge
            Sentinel (halts on a caught governor failure) · Self-Audit (read-only, zero AI cost)
```

**Repo layout:** `wall/` (rooms) · `leash/` (decide-before + egress) · `manager/` (ledger) · `govengine/` (the verdict) · `sdlc/` (build/QA stages + the live loop) · `cook/` (pluggable AI runtimes) · `dashboard/` (cockpit + setup wizard) · `mobile/` (phone, E2EE) · `sentinel/` · `selfaudit/` · `adapters/` · `tools/` (launchers, `bin/thor.js`) · `tests/` (fast + live lanes).

---

## 🔬 Verify it yourself

```bash
make qa       # fast, docker-free — the every-commit gate (100+ tests)
make prove    # live — real Docker rooms + Postgres + the attack campaign (the trust bar)
```

CI (`docs/ci/ci.yml`) runs the fast lane + a **browser smoke test** (renders the cockpit under the real CSP) + a no-AI-co-author guard on every push.

---

## 📚 More docs

`RUNBOOK.md` (incident + ops) · `DEPLOYMENT.md` (prod compose) · `docs/PRD-Module-*.md` (per-module specs) · `docs/GAP-AND-RISK-REGISTER.md` (the brutally-honest status) · `docs/THREAT-MODEL.md`.

## 📜 License & author

Operator-run control plane. Built by **Sanket Toraskar** — human-controlled development, sole author. UNLICENSED / private.
