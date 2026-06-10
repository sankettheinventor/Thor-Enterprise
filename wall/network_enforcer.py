"""
Sub-module 1.3 — Network Enforcer. The heart of P4 (the one-door rule).

⚠️ BUILD-ORDER PHASING (flagged per Rule 9 — no silent drift):

  PRD §5.1 describes the END-STATE one-door model: the room is on a custom network with no
  default route, and host-side iptables DROP everything not destined for the in-room Leash
  proxy (:8001). That proxy is part of Module 2 (the Leash).

  Per the LOCKED build order (SESSION.md Rule 3, Bible §15, and the approved starter code),
  the Wall ships on DAY ONE *fully network-sealed*: `network_disabled=True` — the container
  has NO network at all. This trivially satisfies AC-2 in its "sealed shut" form (no route to
  the internet, the model API, or other rooms). The `:8001`-only routing UPGRADES this to the
  full one-door form when the Leash (Module 2) lands.

  So: day one = sealed shut. Module 2 = exactly one door. Same guarantee, tightening in two
  documented steps — not a divergence.
"""
from __future__ import annotations

# Day-one stance: no network. See module docstring.
SEALED_SHUT = True


def network_kwargs(room_id: str) -> dict:
    """
    Return the docker-run network kwargs for a room.

    Day one: `network_disabled=True` (FR-3/FR-4/FR-5 in "sealed shut" form). When the Leash
    (M2) arrives this returns instead a custom locked network whose only egress is :8001.
    """
    if SEALED_SHUT:
        return {"network_disabled": True}
    # --- Module 2 upgrade (NOT active yet) -------------------------------------------------
    # return {"network": f"thor-room-net-{room_id}"}   # custom net; iptables drop != :8001
    raise NotImplementedError("one-door (:8001) network arrives with Module 2 / the Leash")


def assert_sealed(container) -> bool:
    """
    Verify a running container really has no general network route (defence-in-depth for AC-2,
    sealed-shut form). Reads back the container's network settings from Docker ground-truth —
    we trust reality, not the request we sent.
    """
    container.reload()
    networks = container.attrs.get("NetworkSettings", {}).get("Networks", {}) or {}
    # With network_disabled=True there are no attached networks with an IP.
    for net in networks.values():
        if net.get("IPAddress"):
            return False
    return True


# ============================================================================
# Phase 2b — the one-door egress lock (replaces sealed-shut for GOVERNED rooms).
# ============================================================================
#
# Realization decision (2026-06-06, flagged per Rule 9): PRD §5.1 describes an in-room proxy on
# :8001 + host iptables dropping non-:8001 egress. Host iptables needs root/sudo (an interactive
# password we cannot supply non-interactively) and is brittle on WSL2. We enforce the SAME
# invariant — "the room's only egress is the governed door" — purely via Docker network TOPOLOGY:
#
#   thor-room-net   : `--internal` network (NO route to the internet)
#   thor-egress-net : normal bridge network (HAS internet)
#   the room        : attached ONLY to thor-room-net -> cannot reach the internet at all
#   the leash gateway: dual-homed on BOTH nets -> the ONLY peer the room can reach with a path
#                      outward; it runs the egress-governing proxy on :8001
#
# A raw packet from the room to the internet has no route (dropped by Docker); the only reachable
# forwarder is the governed gateway. This is P4 by topology instead of by iptables — no sudo.

ROOM_NET = "thor-room-net"
EGRESS_NET = "thor-egress-net"
GATEWAY_NAME = "thor-leash-gateway"   # the dual-homed gateway (must match leash.gateway.GATEWAY_NAME)
GATEWAY_PORT = 8001


def egress_proxy_env() -> dict:
    """Env that forces a one-door room's HTTP(S) egress through the governed gateway — the ONLY door.
    The room has no other route (internal net), so even an agent that ignores these vars cannot reach
    the internet; setting them makes well-behaved clients (curl, Claude Code, ...) use the door cleanly."""
    proxy = f"http://{GATEWAY_NAME}:{GATEWAY_PORT}"
    return {"HTTP_PROXY": proxy, "HTTPS_PROXY": proxy,
            "http_proxy": proxy, "https_proxy": proxy, "NO_PROXY": "localhost,127.0.0.1"}


def ensure_networks(client) -> None:
    """Create the internal room network + the egress network if absent. Idempotent."""
    existing = {n.name for n in client.networks.list()}
    if ROOM_NET not in existing:
        client.networks.create(ROOM_NET, driver="bridge", internal=True)
    if EGRESS_NET not in existing:
        client.networks.create(EGRESS_NET, driver="bridge", internal=False)


def one_door_room_kwargs() -> dict:
    """docker-run kwargs for a GOVERNED room: attached only to the internal (no-internet) net."""
    return {"network": ROOM_NET}


def assert_no_internet(container) -> bool:
    """Confirm the room is on the internal net ONLY (no path to the outside). AC-5 ground-truth."""
    container.reload()
    nets = container.attrs.get("NetworkSettings", {}).get("Networks", {}) or {}
    return set(nets.keys()) == {ROOM_NET}
