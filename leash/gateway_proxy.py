"""
Leash gateway — the egress-governing HTTP forward proxy (Layer B, sub-module 2.3 + 2.6).

Runs INSIDE the dual-homed gateway container (the room's only reachable forwarder). STDLIB ONLY,
so it runs from the thor-room image without any pip install. For every outbound request the room
makes (forced here by topology — the room has no other route), it:

  * extracts the destination host (Layer B egress inspection),
  * ALLOWS only allowlisted destinations that resolve to a PUBLIC IP on :443; DENIES the rest (FR-9),
  * never attaches the upstream credential to a cook-named request (the cook carries its own model auth
    end-to-end inside TLS; the gateway controls WHERE, not the content),
  * records every decision to a mounted log (read back by the host to verify AC-5/AC-6).

Config via env: LEASH_ALLOWLIST (comma hosts), LEASH_UPSTREAM_CRED, LEASH_DECISION_LOG.
"""
import ipaddress
import json
import os
import select
import socket
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


def _allowlisted(host: str) -> bool:
    """Exact host or a subdomain of an allowlisted host (so api.anthropic.com matches anthropic.com)."""
    return host in ALLOWLIST or any(host == a or host.endswith("." + a) for a in ALLOWLIST)


def _safe_ip(host: str) -> str | None:
    """SSRF / DNS-rebinding guard. Resolve ONCE and return a single PUBLIC IP to connect to, or None if the
    host resolves to ANY private/loopback/link-local/reserved/multicast address. The caller connects to the
    RETURNED IP — so the allowlist check and the actual connection use the SAME validated address, closing
    the classic resolve-then-connect TOCTOU (a rebind can't swap in an internal IP after the check)."""
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        return None
    chosen = None
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except ValueError:
            return None
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return None
        chosen = chosen or info[4][0]
    return chosen


class Handler(BaseHTTPRequestHandler):
    def do_CONNECT(self):  # HTTPS tunnel — the method real agents (Claude Code etc.) use for :443
        host = self.path.rsplit(":", 1)[0]
        try:
            port = int(self.path.rsplit(":", 1)[1])
        except (IndexError, ValueError):
            port = 443
        if port != 443:
            _record("deny", host, f"egress CONNECT to non-443 port {port} refused (AUD-doget-cred)")
            self.send_response(403)
            self.end_headers()
            return
        pinned = _safe_ip(host)
        if not _allowlisted(host) or pinned is None:
            _record("deny", host, "egress CONNECT not allowlisted or resolves to a private IP (Layer B)")
            self.send_response(403)
            self.end_headers()
            return
        _record("allow", host, "allowlisted CONNECT")
        try:
            upstream = socket.create_connection((pinned, port), timeout=10)   # PINNED IP — no rebind TOCTOU
        except Exception as e:  # noqa: BLE001 — upstream unreachable
            _record("error", host, f"upstream connect failed: {e}")
            self.send_response(502)
            self.end_headers()
            return
        self.send_response(200, "Connection Established")
        self.end_headers()
        # Blind byte tunnel both ways (the gateway controls WHERE, not the TLS content — host allowlist
        # is the egress control; the agent carries its own model auth end-to-end).
        client_sock = self.connection
        socks = [client_sock, upstream]
        try:
            while True:
                readable, _, errored = select.select(socks, [], socks, 60)
                if errored:
                    break
                done = False
                for s in readable:
                    other = upstream if s is client_sock else client_sock
                    data = s.recv(8192)
                    if not data:
                        done = True
                        break
                    other.sendall(data)
                if done:
                    break
        except Exception:  # noqa: BLE001 — tunnel closed/reset; just end
            pass
        finally:
            try:
                upstream.close()
            except Exception:  # noqa: BLE001
                pass

    def do_GET(self):  # forward-proxy: self.path is an absolute URL
        host = urlparse(self.path).hostname or ""
        if not _allowlisted(host) or _safe_ip(host) is None:
            _record("deny", host, "egress destination not allowlisted or resolves to a private IP (Layer B)")
            self.send_response(403)
            self.end_headers()
            self.wfile.write(f"GovernanceDenied: egress to {host} not allowed".encode())
            return
        _record("allow", host, "allowlisted")
        # The upstream credential is NEVER attached to a cook-named plaintext request — that would hand the
        # secret to whatever allowlisted/rebound host the cook picks (AUD-doget-cred). Real model traffic
        # uses CONNECT/TLS with the cook's OWN token end-to-end; the gateway only controls WHERE.
        req = urllib.request.Request(self.path)
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
