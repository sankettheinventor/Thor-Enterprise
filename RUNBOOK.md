# THOR Enterprise — RUNBOOK

THOR is a governance cage for AI coding agents: a worker (any frontier agent) builds inside a sealed
room, and THOR mechanically proves — trusting no agent — that what it claims matches reality before a
human signs the merge.

## Prerequisites
- Docker + Docker Compose
- A strong API token: `export THOR_API_TOKEN=$(openssl rand -hex 32)`
- (optional) Node ≥18 if you install the launcher / build the React cockpit via npm

## Boot the control plane
```bash
# via the npm launcher (zero-dependency; see docs/NPM-SECURITY.md)
npm install -g thor-enterprise --ignore-scripts
thor up                       # docker compose up -d --build
thor status                   # service health
thor logs                     # follow logs
thor down                     # stop everything

# or directly
docker compose -f docker-compose.prod.yml up -d --build
```
Dashboard → `http://127.0.0.1:7080/`. Mutating calls require `Authorization: Bearer $THOR_API_TOKEN`.

## HTTPS for mobile push (required)
Web Push only works in a **secure context (HTTPS)**. The compose stack includes a **Caddy** TLS reverse
proxy (`Caddyfile`) that fronts the control plane on `:443`. Pick a mode with `THOR_SITE_ADDRESS` in `.env`:

| Mode | `THOR_SITE_ADDRESS` | Cert | Phone setup |
|---|---|---|---|
| **Production (a domain)** | `cockpit.yourco.com` | **Auto Let's Encrypt** (renewed) | nothing — publicly trusted |
| **LAN / IP (no domain)** | `https://192.168.1.50` | Caddy **internal CA** | install Caddy's root CA once (below) |
| **Local dev** | `localhost` | Caddy internal CA | desktop only |

```bash
echo "THOR_SITE_ADDRESS=cockpit.yourco.com" >> .env   # or https://<your-lan-ip>
thor up                                               # Caddy now serves https://<that address>/app/
```
**LAN — trust the internal CA on the phone** (one time, so the cert is green + push works):
```bash
# export Caddy's root CA from the running container, then AirDrop/email it to the phone and install+trust it:
docker compose -f docker-compose.prod.yml cp caddy:/data/caddy/pki/authorities/local/root.crt ./thor-root-ca.crt
# iOS: Settings → General → VPN & Device Management → install → Settings → General → About →
#      Certificate Trust Settings → enable. Android: Settings → Security → Install a certificate → CA.
```
For pure local dev on a laptop, [`mkcert`](https://github.com/FiloSottile/mkcert) is an easy alternative
(it installs a locally-trusted CA; point Caddy at the generated cert or just use `localhost`).

**Kubernetes:** terminate TLS at an Ingress with `cert-manager` (Let's Encrypt `ClusterIssuer`) routing to
the `dashboard` Service on `:7080` — same effect as Caddy. The `/stream` route must disable proxy buffering
(e.g. nginx-ingress: `nginx.org/proxy-buffering: "false"`).

## The end-to-end flow (what an operator does)
1. **Assign** a feature (cockpit *Direct* tab, or `POST /task`). The CTO plans the room's frozen scope.
2. **Build** — the worker (pluggable: Claude Code / any agent, `THOR_COOK`) builds INSIDE a sealed
   room; every write is gated by the Leash (decide-before). Out-of-scope writes never reach disk.
3. **QA** — an independent adversary in a fresh room fuzzes edge inputs; bugs become CEO tickets (Sig-2).
4. **Verdict** — the GovEngine runs THOR's OWN tests + checks the real git diff vs a claim derived from
   trusted state. A fabricated claim, hollow test, or hidden change → `not_done` (no false done).
5. **Sign** — when the verdict is `done`, the *Decide* tab shows a card. You sign with your Ed25519 key
   **in the browser** (it never leaves the device); the Manager verifies + consumes a one-time nonce.
6. **Merge** — only on a verified Signature-3 AND a FRESH verdict, THOR merges (local-git or live Gitea
   via `THOR_GIT_BACKEND=gitea`). The room is destroyed; the branch persists; everything is in the ledger.

## Backends (swap at deploy; seams are proven)
- **Git host:** `THOR_GIT_BACKEND=local` (default) or `gitea` (set `GITEA_URL/TOKEN/OWNER`).
- **Self-audit model:** local Ollama/Qwen if present (zero frontier cost), else the deterministic inspector.
- **Identity/audit/AGT:** Strangler ports; real Microsoft AGT plugs in behind the adapter (no creds in dev).

## Operate
- **Halt / recover:** a failed governor → the Sentinel halts new work (fail-closed); a `room:` fault kills
  one room. On restart, crash-replay rebuilds exact state from the ledger; orphan rooms are reaped, and any
  build interrupted by the crash is **re-queued to `ready`** (the verdict re-judges from reality on
  re-dispatch — no false `done`).
- **Audit:** `GET /audit/export` for the signed, hash-chained ledger; `GET /lies` for caught fabrications.
- **Metrics:** scrape `GET /metrics` (Prometheus text) — ledger size, active rooms, features-by-status,
  lies caught, active threats, `thor_frontier_calls_total` (must stay 0 — zero token cost). Open like
  liveness (a scraper carries no token).
- **RBAC (multi-user):** set `THOR_USERS` = JSON `[{"id","role":"viewer|operator|commander","token","pubkey"}]`.
  Roles: viewer reads, operator runs the flow, only a commander signs merges. Without it, the single
  `THOR_API_TOKEN` posture applies.

## Backups & restore (the ledger is the source of truth)
The `pgbackup` service runs scheduled `pg_dump` into the `thor_pgbackups` volume (retention via
`THOR_BACKUP_KEEP_DAYS/WEEKS/MONTHS`; schedule via `THOR_BACKUP_SCHEDULE`, default `@daily`).
```bash
# list backups
docker compose -f docker-compose.prod.yml exec pgbackup ls -lh /backups/daily
# restore a dump (stop the control plane first so nothing writes during restore)
docker compose -f docker-compose.prod.yml stop controlplane
gunzip -c /path/to/thor-<timestamp>.sql.gz | \
  docker compose -f docker-compose.prod.yml exec -T postgres psql -U postgres -d thor
docker compose -f docker-compose.prod.yml start controlplane   # rebuild_from_log replays the ledger
```

## Verify the build (the trust bar)
```bash
make prove     # full suite from clean over real Docker rooms + Postgres
make launch    # the 8-attack adversarial campaign — no attack may earn a false "done"
```

## Security
- No secret is committed; all secrets come from `.env` (gitignored) — see `.env.example`.
- npm install hardening (zero-dep launcher, no install scripts, pinned UI deps) — see `docs/NPM-SECURITY.md`.
- The worker's egress is one-door + allowlisted; a malicious dependency cannot phone home.

## Troubleshooting
- *Dashboard unreachable through the published port:* ensure `THOR_BIND_HOST=0.0.0.0` (set in compose/k8s).
- *Gitea merge fails:* confirm `GITEA_TOKEN` is set and the `gitea` service is healthy (`thor status`).
- *Rooms won't start:* the control plane needs the host Docker socket mounted (see `docker-compose.prod.yml`).
