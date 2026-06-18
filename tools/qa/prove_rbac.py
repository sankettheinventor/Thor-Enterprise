"""
RBAC proof — three roles on ONE host, two separated layers (authN ≠ authZ), docker-free + Postgres-free.

LAYER 1 — TRANSPORT (per-user token gates the mutating surface by ROLE), via the real DashboardAPI:
  * viewer   : reads OK, every mutation 403.
  * operator : runs the SDLC flow (POST /features) OK, but the authority surface (POST /approve) 403.
  * commander: everything, including the authority surface.
  * no/bad token: 401. And with RBAC OFF (THOR_USERS unset) the surface falls back to open (so dev/test
    and `make qa`/`make prove`, which send no token, keep passing).

LAYER 2 — AUTHORITY (a merge is minted ONLY by a COMMANDER Ed25519 signature; no token can do it), via the
real Manager: a commander key is an authorized signer; an operator/viewer key is NOT — `approve` would
reject it as an unauthorized signer. This is the gate `Manager.approve` actually consults.

Run (from ~/thor-enterprise):  PYTHONPATH=. .venv/bin/python tools/qa/prove_rbac.py
"""
import json
import os

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from wall.identity_stamper import _b64


def _keypair():
    priv = Ed25519PrivateKey.generate()
    return priv, _b64(priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw))


cmd_priv, cmd_pub = _keypair()
op_priv, op_pub = _keypair()
view_priv, view_pub = _keypair()

USERS = [
    {"id": "carol", "role": "commander", "token": "tok-commander", "pubkey": cmd_pub},
    {"id": "olivia", "role": "operator", "token": "tok-operator", "pubkey": op_pub},
    {"id": "vince", "role": "viewer", "token": "tok-viewer", "pubkey": view_pub},
]


# ---------- LAYER 1: transport role gates via the real DashboardAPI ----------
class StubService:
    """Minimal window so the auth-passing handlers have something to call (the auth check fires first)."""

    class _Mgr:
        eventlog = type("E", (), {"count": staticmethod(lambda: 0)})()

    manager = _Mgr()

    def kanban(self):
        return {"columns": {}}

    def add_feature(self, *a, **k):
        return "F-stub"

    def approve(self, *a, **k):
        return {"verified": True, "stub": True}


os.environ["THOR_USERS"] = json.dumps(USERS)
from fastapi.testclient import TestClient  # noqa: E402 — import after env is set
from dashboard import dashboard_api  # noqa: E402

dashboard_api.bind(StubService())
client = TestClient(dashboard_api.app)


def hdr(tok):
    return {"Authorization": f"Bearer {tok}"}


# reads are open to any authenticated role (and even unauthenticated) — viewer reads fine
assert client.get("/kanban", headers=hdr("tok-viewer")).status_code == 200, "viewer must read"
# viewer CANNOT mutate
r = client.post("/features", json={"title": "x"}, headers=hdr("tok-viewer"))
assert r.status_code == 403, f"viewer must NOT queue features, got {r.status_code}"
# operator CAN run the flow...
r = client.post("/features", json={"title": "x"}, headers=hdr("tok-operator"))
assert r.status_code == 200, f"operator must queue features, got {r.status_code}"
# ...but operator CANNOT reach the authority surface (approve = sign a merge)
r = client.post("/approve", json={"card_id": "c", "signature": "s", "signer_pub": "p"},
                headers=hdr("tok-operator"))
assert r.status_code == 403, f"operator must NOT approve merges, got {r.status_code}"
# commander CAN reach the authority surface
r = client.post("/approve", json={"card_id": "c", "signature": "s", "signer_pub": "p"},
                headers=hdr("tok-commander"))
assert r.status_code == 200, f"commander must reach approve, got {r.status_code}"
# bad / missing token → 401
assert client.post("/features", json={"title": "x"}, headers=hdr("nope")).status_code == 401, "bad token → 401"
assert client.post("/features", json={"title": "x"}).status_code == 401, "no token → 401"
print("LAYER1 transport role gates: viewer<operator<commander enforced; 401 on bad/missing token  OK")

# RBAC OFF → fall back to OPEN (so `make qa`/`make prove` send no token and still pass)
os.environ.pop("THOR_USERS", None)
assert client.post("/features", json={"title": "x"}).status_code == 200, "RBAC off → open posture (no token)"
print("LAYER1 fallback: RBAC off (THOR_USERS unset) → legacy open posture, dev/test unaffected  OK")


# ---------- LAYER 2: merge authority is commander-only, via the real Manager ----------
from manager.core import ThorManager  # noqa: E402

mgr = ThorManager(None)   # in-memory authority state only (register_user/is_authorized_signer touch no DB)
mgr.register_user("carol", "commander", cmd_pub)
mgr.register_user("olivia", "operator", op_pub)
mgr.register_user("vince", "viewer", view_pub)

assert mgr.is_authorized_signer(cmd_pub) is True, "a commander key MUST be allowed to sign a merge"
assert mgr.is_authorized_signer(op_pub) is False, "an operator key must NOT be allowed to sign a merge"
assert mgr.is_authorized_signer(view_pub) is False, "a viewer key must NOT be allowed to sign a merge"
assert op_pub not in mgr.authorized_signers and view_pub not in mgr.authorized_signers, \
    "only commander keys may enter the signer set"
assert mgr.user_roles[op_pub] == "operator" and mgr.user_roles[cmd_pub] == "commander", "roles recorded"
print("LAYER2 authority: only the COMMANDER Ed25519 key may sign a merge; operator/viewer keys cannot  OK")

print("\nRBAC_OK")
