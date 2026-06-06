"""
Sub-module 2.2 — MCP-Aware Inspector (Layer A) [+ Layer B placeholder].

Layer A understands the structured tool-call protocol: it turns a raw tool call into a normal
THOR action shape `{type, name, target, args, room_id}` the policy engine can reason about
(FR-8). For file tools, `target` is the path the policy checks against.

Layer B (egress / raw HTTP / DNS) is Phase 2b — it needs the one-door network lock to exist.
"""
from __future__ import annotations

# Tools whose first concern is a filesystem path (so `target` = the path).
_PATH_TOOLS = ("write_file", "read_file", "edit_file", "delete_file", "append_file")


def inspect_tool_call(tool_call: dict) -> dict:
    """
    Normalize a structured tool call into a THOR action (Layer A). Cook-agnostic: a Cook-adapter
    maps any agent's protocol into this same shape, so the Leash logic never depends on the cook.
    """
    name = tool_call.get("name")
    args = tool_call.get("args", {}) or {}
    target = ""
    if name in _PATH_TOOLS:
        target = args.get("path", "") or ""
    return {
        "type": "tool_call",
        "name": name,
        "target": target,
        "args": args,
        "room_id": tool_call.get("room_id"),
    }


def inspect_egress(url: str) -> dict:
    """
    Layer B — normalize a raw outbound request into a THOR egress action. `target` is the
    destination host the policy/allowlist checks against. The enforcement runs in the gateway
    (leash/gateway_proxy.py), which lives on the room's only egress path (network topology).
    """
    from urllib.parse import urlparse

    host = urlparse(url).hostname or ""
    return {"type": "egress", "name": "http_request", "target": host, "args": {"url": url}}
