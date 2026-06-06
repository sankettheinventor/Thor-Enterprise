"""
Leash gateway — the egress-governing HTTP forward proxy (Layer B, sub-module 2.3 + 2.6).

Runs INSIDE the dual-homed gateway container (the room's only reachable forwarder). STDLIB ONLY,
so it runs from the thor-room image without any pip install. For every outbound request the room
makes (forced here by topology — the room has no other route), it:

  * extracts the destination host (Layer B egress inspection),
  * ALLOWS only allowlisted destinations; DENIES the rest with a governance reason (FR-9),
  * injects credentials for approved destinations (FR-3/FR-12) — creds live HERE, never in the room,
  * records every decision to a mounted log (read back by the host to verify AC-5/AC-6).

Config via env: LEASH_ALLOWLIST (comma hosts), LEASH_UPSTREAM_CRED, LEASH_DECISION_LOG.
"""
import json
import os
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

ALLOWLIST = {h for h in os.environ.get("LEASH_ALLOWLIST", "").split(",") if h}
DECISION_LOG = os.environ.get("LEASH_DECISION_LOG", "/var/log/leash/decisions.jsonl")
UPSTREAM_CRED = os.environ.get("LEASH_UPSTREAM_CRED")  # held by the gateway; NEVER in the room


def _record(decision: str, host: str, reason: str) -> None:
    os.makedirs(os.path.dirname(DECISION_LOG) or ".", exist_ok=True)
    with open(DECISION_LOG, "a") as f:
        f.write(json.dumps({"ts": time.time(), "type": "egress", "host": host,
                            "decision": decision, "reason": reason}) + "\n")


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # forward-proxy: self.path is an absolute URL
        host = urlparse(self.path).hostname or ""
        if host not in ALLOWLIST:
            _record("deny", host, "egress destination not allowlisted (Layer B)")
            self.send_response(403)
            self.end_headers()
            self.wfile.write(f"GovernanceDenied: egress to {host} not allowed".encode())
            return
        _record("allow", host, "allowlisted")
        req = urllib.request.Request(self.path)
        if UPSTREAM_CRED:
            req.add_header("Authorization", f"Bearer {UPSTREAM_CRED}")  # injected by gateway, not room
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                body = r.read()
            self.send_response(200)
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:  # noqa: BLE001 - report upstream failure verbatim
            self.send_response(502)
            self.end_headers()
            self.wfile.write(str(e).encode())

    def log_message(self, *_a):  # silence default stderr logging
        pass


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8001), Handler).serve_forever()
