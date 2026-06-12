"""
Native push: the full Web Push pipeline encrypts the alert (aes128gcm) and delivers it to a device
endpoint with a VAPID-signed Authorization. We point the subscription at a LOCAL receiver standing in for
FCM/APNs — the receiver gets ciphertext it cannot read (only the device can), proving the real crypto +
delivery without a physical phone. Docker-free gate test; skips if pywebpush is absent.
"""
import http.server
import os
import tempfile
import threading
from pathlib import Path

import pytest

pytest.importorskip("pywebpush")


def test_push_encrypts_and_delivers_to_device():
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
    from py_vapid.utils import b64urlencode

    from dashboard import push

    d = tempfile.mkdtemp(prefix="push-")
    push._KEY = Path(d) / "vapid.pem"
    push._SUBS = Path(d) / "subs.json"

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

    srv = http.server.HTTPServer(("127.0.0.1", 0), Receiver)  # port 0 = any free port
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        assert len(push.public_key()) > 80, "VAPID application key looks wrong"
        priv = ec.generate_private_key(ec.SECP256R1())
        p256dh = b64urlencode(priv.public_key().public_bytes(Encoding.X962, PublicFormat.UncompressedPoint))
        os.environ["THOR_PUSH_ALLOW_LOCAL"] = "1"   # this test points at a LOCAL mock receiver by design
        sub = {"endpoint": f"http://127.0.0.1:{port}/p",
               "keys": {"p256dh": p256dh, "auth": b64urlencode(os.urandom(16))}}
        assert push.subscribe(sub) == 1
        assert push.send("THOR", "A card needs your signature", "/app/")["sent"] == 1
        assert received.get("ce") in ("aes128gcm", "aesgcm"), "payload must be Web-Push encrypted"
        assert len(received.get("body", b"")) > 0, "device must receive ciphertext"
        assert received.get("auth", "").lower().startswith("vapid"), "must carry a VAPID Authorization"
    finally:
        srv.shutdown()
