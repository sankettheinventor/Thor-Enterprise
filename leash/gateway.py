"""
Control-plane helper to stand up the Phase 2b egress topology:

  * an internal room-net + an egress-net (via wall.network_enforcer.ensure_networks),
  * a mock UPSTREAM (an approved destination, e.g. "the model API") on the egress-net,
  * the dual-homed LEASH GATEWAY running leash/gateway_proxy.py — the room's only forwarder.

All three run from the existing thor-room image (python stdlib only — no extra build). The gateway
holds the upstream credential; the room never does (capability separation, P4 / AC-6).
"""
from __future__ import annotations

import os

import docker

from wall import config, network_enforcer

GATEWAY_NAME = "thor-leash-gateway"
UPSTREAM_NAME = "thor-upstream"
# Secrets NEVER live in source (security invariant #1). The optional upstream credential comes from the
# environment only — and the proxy no longer attaches it to any cook-named request (AUD-doget-cred), so it
# is vestigial unless a deployment configures a real upstream that needs it.
UPSTREAM_CRED = os.environ.get("LEASH_UPSTREAM_CRED", "")


def _rm(client, name):
    for c in client.containers.list(all=True, filters={"name": name}):
        c.remove(force=True)


def start_upstream(client: docker.DockerClient) -> str:
    """A trivial approved destination on the egress net (stands in for the model API / Gitea)."""
    _rm(client, UPSTREAM_NAME)
    client.containers.run(
        config.ROOM_IMAGE,
        command=["-c", "echo THOR-UPSTREAM-OK > /tmp/index.html && cd /tmp && "
                 "python3 -m http.server 8080"],   # 8080: unprivileged cook can't bind <1024
        name=UPSTREAM_NAME, detach=True, network=network_enforcer.EGRESS_NET,
        labels={"thor.leash": "upstream"},
    )
    return UPSTREAM_NAME


def start_gateway(client: docker.DockerClient, leash_host_path: str, decision_log_dir: str,
                  allowlist: tuple[str, ...], suffix: str = "") -> str:
    """
    Start the dual-homed gateway: created on this cook's room-net, then connected to the egress-net so it
    is the ONLY bridge between the sealed room and the outside. Runs leash/gateway_proxy.py on :8001.

    `suffix` (the request's room_id/feature_id) keys a PER-COOK gateway + room-net, so multiple real cooks
    run truly in parallel each behind its OWN door with its OWN allowlist — no shared singleton, no lock,
    no cross-wiring. Empty suffix -> the shared default names (backward compatible).
    """
    name = network_enforcer.gateway_name(suffix)
    _rm(client, name)
    network_enforcer.ensure_networks(client, suffix)   # this cook's room-net + the shared egress-net
    os.makedirs(decision_log_dir, exist_ok=True)
    container = client.containers.run(
        config.ROOM_IMAGE,
        command=["-c", "python3 /leash/gateway_proxy.py"],
        name=name, detach=True, network=network_enforcer.room_net(suffix),
        mounts=[
            docker.types.Mount("/leash", leash_host_path, type="bind", read_only=True),
            docker.types.Mount("/var/log/leash", decision_log_dir, type="bind", read_only=False),
        ],
        environment={
            "LEASH_ALLOWLIST": ",".join(allowlist),
            "LEASH_UPSTREAM_CRED": UPSTREAM_CRED,      # creds live HERE, never in the room
            "LEASH_DECISION_LOG": "/var/log/leash/decisions.jsonl",
        },
        labels={"thor.leash": "gateway", "thor.leash.suffix": network_enforcer._sanitize_suffix(suffix)},
    )
    # dual-home it: now also on the egress net (so it — and only it — can reach upstream/internet)
    client.networks.get(network_enforcer.EGRESS_NET).connect(container)
    _wait_ready(container)   # return only once the proxy is actually listening (race-free for parallel cooks)
    return name


def _wait_ready(container, timeout: int = 20) -> None:
    """Block until the gateway proxy is accepting connections on :8001 inside the container, or timeout.
    Without this the caller could provision a room and exec the cook before the proxy is listening — a race
    that is usually masked by room-provisioning latency for a single cook but bites under PARALLEL starts."""
    import time
    probe = ("import socket,sys\n"
             "s=socket.socket(); s.settimeout(1)\n"
             "sys.exit(0 if s.connect_ex(('127.0.0.1', %d))==0 else 1)" % network_enforcer.GATEWAY_PORT)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if container.exec_run(["python3", "-c", probe]).exit_code == 0:
                return
        except Exception:  # noqa: BLE001 — container still starting / docker hiccup → retry
            pass
        time.sleep(0.2)


def teardown(client: docker.DockerClient, remove_networks: bool = True, suffix: str = "") -> None:
    """Tear down THIS cook's gateway (and its per-cook room-net). The shared egress-net is removed only for
    the default (no-suffix) teardown — other parallel cooks may still be using it."""
    _rm(client, network_enforcer.gateway_name(suffix))
    if not network_enforcer._sanitize_suffix(suffix):
        _rm(client, UPSTREAM_NAME)
        if remove_networks:
            for net in (network_enforcer.ROOM_NET, network_enforcer.EGRESS_NET):
                try:
                    client.networks.get(net).remove()
                except docker.errors.APIError:
                    pass  # still has endpoints (e.g. a room mid-teardown) — leave it
    elif remove_networks:
        network_enforcer.remove_room_net(client, suffix)   # this cook's net only; egress-net is shared
