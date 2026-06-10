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
- `THOR_API_TOKEN` — bearer token for mutating endpoints (unset ⇒ auth disabled; **always set in prod**).
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
- [x] Bearer auth on mutating HTTP endpoints (`THOR_API_TOKEN`)
- [x] No hardcoded DB host/passwords (all env / secret-store driven)
- [x] Containerized control plane (image builds + boots against external Postgres + binds 0.0.0.0)
- [x] Health endpoints for liveness/readiness probes; resource requests/limits in k8s
- [x] Single-writer enforced (Manager is sole EventLog writer; `replicas: 1`)
- [ ] **TLS / ingress** in front of the surfaces (terminate at an ingress/reverse proxy)
- [ ] **k8s-native room provisioner** (Pods instead of Docker containers) — the parity work
- [ ] **Real in-room cook agent** (LLM builder behind the Leash) + one-door egress lock
- [ ] **Postgres HA / backups**, observability (metrics/tracing), crash-recovery resume, load tests
```
