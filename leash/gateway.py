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
                  allowlist: tuple[str, ...]) -> str:
    """
    Start the dual-homed gateway: created on room-net, then connected to egress-net so it is the
    ONLY bridge between the sealed room and the outside. Runs leash/gateway_proxy.py on :8001.
    """
    _rm(client, GATEWAY_NAME)
    network_enforcer.ensure_networks(client)   # FINDING-D: the gateway depends on the room/egress nets
    os.makedirs(decision_log_dir, exist_ok=True)
    container = client.containers.run(
        config.ROOM_IMAGE,
        command=["-c", "python3 /leash/gateway_proxy.py"],
        name=GATEWAY_NAME, detach=True, network=network_enforcer.ROOM_NET,
        mounts=[
            docker.types.Mount("/leash", leash_host_path, type="bind", read_only=True),
            docker.types.Mount("/var/log/leash", decision_log_dir, type="bind", read_only=False),
        ],
        environment={
            "LEASH_ALLOWLIST": ",".join(allowlist),
            "LEASH_UPSTREAM_CRED": UPSTREAM_CRED,      # creds live HERE, never in the room
            "LEASH_DECISION_LOG": "/var/log/leash/decisions.jsonl",
        },
        labels={"thor.leash": "gateway"},
    )
    # dual-home it: now also on the egress net (so it — and only it — can reach upstream/internet)
    client.networks.get(network_enforcer.EGRESS_NET).connect(container)
    return GATEWAY_NAME


def teardown(client: docker.DockerClient, remove_networks: bool = True) -> None:
    _rm(client, GATEWAY_NAME)
    _rm(client, UPSTREAM_NAME)
    if remove_networks:
        for net in (network_enforcer.ROOM_NET, network_enforcer.EGRESS_NET):
            try:
                client.networks.get(net).remove()
            except docker.errors.APIError:
                pass  # still has endpoints (e.g. a room mid-teardown) — leave it
