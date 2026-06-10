# THOR Enterprise on Kubernetes

`thor-enterprise.yaml` deploys the **control plane** (Manager/Dashboard/Sentinel/Self-Audit, one Pod)
+ **Postgres** (StatefulSet + PVC) + a **Secret** for `THOR_API_TOKEN` and the DB password, with
liveness/readiness probes and resource requests/limits.

## Status (honest)

- ✅ **Authored + YAML-validated** (parses as valid Kubernetes objects).
- ⚠️ **NOT cluster-verified** in this build environment (no cluster/kubectl/helm available here). Validate
  on your cluster with `kubectl apply --dry-run=server -f k8s/thor-enterprise.yaml` before relying on it.

## Apply

```sh
# real secrets (do NOT use the placeholders in the manifest)
kubectl create namespace thor
kubectl -n thor create secret generic thor-secrets \
  --from-literal=THOR_API_TOKEN=$(openssl rand -hex 32) \
  --from-literal=POSTGRES_PASSWORD=$(openssl rand -hex 16)
# build + push the control-plane image to a registry your cluster can pull, then set the image ref
kubectl apply -f k8s/thor-enterprise.yaml
```

## The one big remaining piece: room provisioning on k8s

The control plane provisions **sealed ROOM containers** via the Docker SDK (`wall/provisioner.py` +
`wall/lifecycle.py`). That works on a single Docker host (see `docker-compose.prod.yml`, which mounts
the Docker socket). **On Kubernetes there is no Docker socket** — rooms must become **Pods** created
through the Kubernetes API. This is the deferred "compose ↔ k8s parity" work (wall **AC-9**, currently
skipped). The clean path (the codebase is already shaped for it):

1. Add a `KubernetesProvisioner` behind the same interface `wall/provisioner.py` exposes
   (`provision_room` / `destroy_room`), creating a sealed Pod (no egress NetworkPolicy, read-only
   rootfs, the task slice as a projected volume, the worktree as a PVC) instead of a container.
2. Select the provisioner by env (`THOR_PROVISIONER=docker|k8s`) — a Strangler swap, no logic change
   elsewhere (the Manager/Leash/Sentinel already talk to the provisioner only through that seam).
3. Grant the control-plane ServiceAccount RBAC to create/delete Pods in a dedicated `thor-rooms`
   namespace; the Sentinel halt then deletes Pods by label (the label-kill path is already built).

Until that adapter lands, this manifest runs the **governance surfaces** on k8s but cannot provision
build rooms there — run rooms on the single-host Docker deployment, or wire the provisioner above.

## Also for production
- **Ingress + TLS** in front of the Service (the app speaks plain HTTP; terminate TLS at the ingress).
- **Do NOT scale the control plane beyond `replicas: 1`** — the Manager is the single EventLog writer.
- **Postgres**: this is a single-replica StatefulSet; for HA use a managed Postgres or an operator.
- **Secrets**: replace the placeholder Secret with Sealed Secrets / External Secrets / Vault.
