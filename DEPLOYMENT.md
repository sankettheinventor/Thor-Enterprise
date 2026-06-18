# THOR Enterprise — Deployment

Two deployment shapes are provided. **Honest status** is given for each — what is verified vs. authored.

## A) Single host (Docker) — `docker-compose.prod.yml`  ✅ verified

The control plane runs as a container; Postgres as a service; sealed ROOM containers are created as
siblings via the host Docker socket. The control-plane **image builds**, **boots against an external
Postgres**, **serves on `0.0.0.0`**, and **enforces bearer auth** — all verified by `docker run`
(see the campaign log; compose itself needs the Docker Compose v2 plugin, absent in the build env, so
the equivalent `docker run` was used to verify).

```sh
export THOR_API_TOKEN=$(openssl rand -hex 32)        # REQUIRED
export THOR_PG_PASSWORD=$(openssl rand -hex 16)       # recommended
docker compose -f docker-compose.prod.yml up -d --build
# Dashboard: http://127.0.0.1:7080/   Manager health: http://127.0.0.1:7100/health
# Every MUTATING call needs:  -H "Authorization: Bearer $THOR_API_TOKEN"
```

Config (all via env / secret store — nothing hardcoded):
- `THOR_API_TOKEN` — single bearer token for mutating endpoints (unset ⇒ auth disabled; set in prod *unless* using `THOR_USERS`).
- `THOR_USERS` — **RBAC** (multiple users on one host): JSON `[{"id","role":"viewer|operator|commander","token","pubkey"}]`. Gates the mutating surface by role and the data reads at viewer+; only a commander's key may sign a merge. When set, a valid per-user token is required even without `THOR_API_TOKEN`. See `docs/THREAT-MODEL.md` → RBAC.
- `THOR_OPERATOR_PUBKEYS` — boot-registered commander signing keys (comma-separated Ed25519 b64) when not using `THOR_USERS`.
- `THOR_PG_DSN` — full Postgres DSN (else built from `THOR_PG_*`).
- `THOR_SELFAUDIT_PASSWORD` / `THOR_SELFAUDIT_DSN` — read-only self-audit role.
- `THOR_BIND_HOST` — `0.0.0.0` in containers (set for you in the compose/k8s manifests).

## B) Kubernetes — `k8s/thor-enterprise.yaml`  ⚠️ authored + YAML-validated, NOT cluster-verified

Deploys the governance surfaces + Postgres + Secret + probes + resource limits. See `k8s/README.md`.
**Validate on your cluster** (`kubectl apply --dry-run=server`) before relying on it — no cluster was
available in the build environment to run it for real.

### The one large remaining piece: rooms on Kubernetes
The control plane provisions **sealed rooms via the Docker SDK**. On a single Docker host that is the
mounted socket (shape A). **On Kubernetes rooms must become Pods** via a `KubernetesProvisioner` behind
the existing `wall/provisioner.py` seam (`THOR_PROVISIONER=docker|k8s`) — this is the deferred
compose↔k8s parity work (`wall` AC-9). Until it lands, k8s runs the surfaces but build rooms run on the
single-host Docker deployment. Full plan in `k8s/README.md`.

## Production checklist (what is done vs. still needed)
- [x] Auth on mutating HTTP endpoints — single token (`THOR_API_TOKEN`) **or** per-user **RBAC** (`THOR_USERS`: viewer/operator/commander), enforced on every served surface; sensitive reads gated at viewer+ under RBAC
- [x] No hardcoded DB host/passwords (all env / secret-store driven)
- [x] Containerized control plane (image builds + boots against external Postgres + binds 0.0.0.0)
- [x] Health endpoints for liveness/readiness probes; resource requests/limits in k8s
- [x] Single-writer enforced (Manager is sole EventLog writer; `replicas: 1`)
- [x] **TLS / ingress** — Caddy terminates `:443` in `docker-compose.prod.yml` (auto-cert; persisted in `caddy_data`)
- [x] **Real in-room cook agent** + one-door egress — `BuildStage → CookRunner`, per-feature one-door gateway (C1/C2); **parallel cooks** isolated per feature. *Live frontier (Claude Code) run still needs an operator-supplied `CLAUDE_CODE_OAUTH_TOKEN` — deferred, not faked.*
- [ ] **Postgres HA / backups**, observability (metrics/tracing), crash-recovery **resume of in-flight work** (projection rebuild-from-ledger is done; resuming an interrupted build is not), load tests
- [ ] **CI gate** — `make qa`/`make prove`/`make launch` are green but not yet wired as an automated pipeline (`.github/workflows`)
- [ ] **k8s-native room provisioner** (Pods) — **de-scoped** for the single-host product target; surfaces run on k8s but build rooms stay on the Docker host
- [ ] **Non-Python mechanical verification** — JS/HTML/SQL work **escalates to a human** (fail-closed/safe) rather than being machine-verified
```
