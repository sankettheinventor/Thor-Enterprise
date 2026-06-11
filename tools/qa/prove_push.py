"""
Native push proof — the full Web Push pipeline works: a VAPID key, a device subscription, and a SEND that
ENCRYPTS the alert (aes128gcm) and delivers it to the device endpoint with a VAPID-signed Authorization.
We point the subscription at a LOCAL receiver (standing in for FCM/APNs), so this proves the real crypto +
delivery without a physical phone. The receiver can't decrypt — only the device can — which is the point.

Run (from ~/thor-enterprise):  PYTHONPATH=. .venv/bin/python tools/qa/prove_push.py
"""
import http.server
import os
import threading

os.environ["THOR_VAPID_KEY"] = "/tmp/thor_vapid_test.pem"
os.environ["THOR_PUSH_SUBS"] = "/tmp/thor_push_subs_test.json"
for f in (os.environ["THOR_VAPID_KEY"], os.environ["THOR_PUSH_SUBS"]):
    if os.path.exists(f):
        os.remove(f)

from cryptography.hazmat.primitives.asymmetric import ec  # noqa: E402 — env set above first (intentional)
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat  # noqa: E402
from py_vapid.utils import b64urlencode  # noqa: E402

from dashboard import push  # noqa: E402

received = {}


class Receiver(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        received["body"] = self.rfile.read(n)
        received["ce"] = self.headers.get("Content-Encoding")
        received["auth"] = self.headers.get("Authorization")
        self.send_response(201)
        self.end_headers()

    def log_message(self, *a):
        pass


PORT = 7095
srv = http.server.HTTPServer(("127.0.0.1", PORT), Receiver)
threading.Thread(target=srv.serve_forever, daemon=True).start()

pk = push.public_key()
print("VAPID application key length:", len(pk))
assert len(pk) > 80, "VAPID public key looks wrong"

# a stand-in "device": a real P-256 keypair + a 16-byte auth secret (what a browser sends on subscribe)
priv = ec.generate_private_key(ec.SECP256R1())
p256dh = b64urlencode(priv.public_key().public_bytes(Encoding.X962, PublicFormat.UncompressedPoint))
sub = {"endpoint": f"http://127.0.0.1:{PORT}/push", "keys": {"p256dh": p256dh, "auth": b64urlencode(os.urandom(16))}}

print("subscribers after subscribe:", push.subscribe(sub))
res = push.send("THOR", "A card needs your signature — feature LOGIN", "/app/")
print("send result:", res)

print("device endpoint received: encoding=%s, ciphertext_bytes=%s, vapid_signed=%s"
      % (received.get("ce"), len(received.get("body", b"")), bool(received.get("auth"))))

assert res["sent"] == 1, "the push must be sent to the 1 subscriber"
assert received.get("ce") in ("aes128gcm", "aesgcm"), "payload must be Web-Push encrypted"
assert len(received.get("body", b"")) > 0, "the device must receive ciphertext"
assert received.get("auth", "").lower().startswith("vapid"), "must carry a VAPID-signed Authorization"
print("PUSH_PIPELINE_OK")
