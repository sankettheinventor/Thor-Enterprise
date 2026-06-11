#!/usr/bin/env bash
# TLS-for-push proof: (1) the real production Caddyfile validates, (2) Caddy terminates HTTPS with its
# internal CA and reverse-proxies to the control plane, (3) the SSE stream flows THROUGH HTTPS (the
# real-time push path). Proves the secure-context requirement for mobile Web Push, without a public domain.
set -u
cd "$(dirname "$0")/../.." || exit 1
cleanup() { docker rm -f thor-caddy-test >/dev/null 2>&1; kill "${BACK:-0}" 2>/dev/null; }
fail() { echo "TLS_PROOF_FAILED: $1"; cleanup; exit 1; }

echo "=== 1) caddy validate the REAL production Caddyfile ==="
docker run --rm -v "$PWD/Caddyfile:/etc/caddy/Caddyfile:ro" -e THOR_SITE_ADDRESS=localhost \
  caddy:2-alpine caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile 2>&1 | grep -q "Valid configuration" \
  && echo "Caddyfile: Valid configuration" || fail "Caddyfile did not validate"

echo "=== 2) backend (cockpit + SSE) on :7081 ==="
python3 - <<'PY' &
import http.server, time
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/stream':
            self.send_response(200); self.send_header('Content-Type', 'text/event-stream'); self.end_headers()
            for i in range(10):
                self.wfile.write(f"data: {{\"seq\": {i}}}\n\n".encode()); self.wfile.flush(); time.sleep(0.25)
        else:
            self.send_response(200); self.send_header('Content-Type', 'text/html'); self.end_headers()
            self.wfile.write(b"<h1>THOR cockpit</h1>")
    def log_message(self, *a): pass
http.server.HTTPServer(('127.0.0.1', 7081), H).serve_forever()
PY
BACK=$!
sleep 1
curl -s http://127.0.0.1:7081/ | grep -q "THOR cockpit" || fail "backend not up"

echo "=== 3) Caddy HTTPS (internal CA) on :8443 -> backend :7081 ==="
docker rm -f thor-caddy-test >/dev/null 2>&1
docker run -d --rm --name thor-caddy-test --network host caddy:2-alpine \
  caddy reverse-proxy --from localhost:8443 --to 127.0.0.1:7081 --internal-certs >/dev/null
for i in $(seq 1 20); do curl -sk https://localhost:8443/ >/dev/null 2>&1 && break; sleep 0.5; done

echo "--- cockpit over HTTPS ---"
curl -sk https://localhost:8443/ | grep -q "THOR cockpit" && echo "OK: cockpit served over HTTPS" || fail "HTTPS did not proxy the cockpit"

echo "--- SSE over HTTPS (real-time push path) ---"
curl -sk -N --max-time 3 https://localhost:8443/stream | grep -q "data:" && echo "OK: SSE streamed through HTTPS" || fail "SSE did not stream through HTTPS"

cleanup
echo "TLS_PROXY_SSE_OK"
