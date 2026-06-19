"""
RBAC — three roles on one host, the two separated layers (authN ≠ authZ). Docker-free + Postgres-free, so
it runs in the fast `make qa` lane as a permanent regression guard. Live walk-through: tools/qa/prove_rbac.py.

  LAYER 1 (transport): a per-user token gates the mutating surface by ROLE (viewer<operator<commander).
  LAYER 2 (authority): a merge is minted only by a COMMANDER Ed25519 signature — no token, and no
                       operator/viewer key, can ever sign one.
"""
import json
import os

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from fastapi.testclient import TestClient

from wall.identity_stamper import _b64


def _pub():
    priv = Ed25519PrivateKey.generate()
    return _b64(priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw))


CMD, OP, VIEW = _pub(), _pub(), _pub()
USERS = [
    {"id": "carol", "role": "commander", "token": "tok-commander", "pubkey": CMD},
    {"id": "olivia", "role": "operator", "token": "tok-operator", "pubkey": OP},
    {"id": "vince", "role": "viewer", "token": "tok-viewer", "pubkey": VIEW},
]


class _StubService:
    class _Mgr:
        eventlog = type("E", (), {"count": staticmethod(lambda: 0)})()

    manager = _Mgr()

    def kanban(self):
        return {"columns": {}}

    def threats(self):
        return {"threats": []}

    def health_system(self):
        return {"ok": True}

    def metrics(self):
        from dashboard.service import DashboardService
        return DashboardService.metrics(self)   # the real (fully defensive) metric builder

    def add_feature(self, *a, **k):
        return "F-stub"

    def approve(self, *a, **k):
        return {"verified": True, "stub": True}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("THOR_USERS", json.dumps(USERS))
    from dashboard import dashboard_api
    dashboard_api.bind(_StubService())
    return TestClient(dashboard_api.app)


def _h(tok):
    return {"Authorization": f"Bearer {tok}"}


def test_viewer_reads_but_cannot_mutate(client):
    assert client.get("/kanban", headers=_h("tok-viewer")).status_code == 200
    assert client.post("/features", json={"title": "x"}, headers=_h("tok-viewer")).status_code == 403


def test_operator_runs_flow_but_cannot_approve(client):
    assert client.post("/features", json={"title": "x"}, headers=_h("tok-operator")).status_code == 200
    r = client.post("/approve", json={"card_id": "c", "signature": "s", "signer_pub": "p"},
                    headers=_h("tok-operator"))
    assert r.status_code == 403


def test_commander_reaches_authority_surface(client):
    r = client.post("/approve", json={"card_id": "c", "signature": "s", "signer_pub": "p"},
                    headers=_h("tok-commander"))
    assert r.status_code == 200


def test_bad_or_missing_token_is_401(client):
    assert client.post("/features", json={"title": "x"}, headers=_h("nope")).status_code == 401
    assert client.post("/features", json={"title": "x"}).status_code == 401


def test_sensitive_reads_require_viewer_when_rbac_on(client):
    """FINDING B: with RBAC on, the audit/threat/cost feeds require at least a viewer token (not world-
    readable); liveness stays open so probes still work."""
    assert client.get("/threats").status_code == 401          # no token → blocked
    assert client.get("/threats", headers=_h("tok-viewer")).status_code == 200   # viewer may read
    assert client.get("/health/system").status_code in (200, 500)  # liveness stays open (no 401)


def test_metrics_is_open_prometheus_even_under_rbac(client):
    """Observability: /metrics is Prometheus text and stays open (a scraper carries no token), and degrades
    gracefully (the stub lacks most sources, so counters default rather than 500)."""
    r = client.get("/metrics")
    assert r.status_code == 200
    assert "thor_frontier_calls_total" in r.text and "# TYPE" in r.text


def test_manager_api_is_role_gated_and_not_failopen(monkeypatch):
    """FINDING A: the Manager surface (:7100) must enforce the SAME roles and must NOT fall open when RBAC
    is configured via THOR_USERS without the legacy THOR_API_TOKEN."""
    monkeypatch.setenv("THOR_USERS", json.dumps(USERS))
    monkeypatch.delenv("THOR_API_TOKEN", raising=False)
    from manager import api as manager_api
    c = TestClient(manager_api.app)
    body = {"feature_id": "F1"}
    assert c.post("/rooms/provision", json=body).status_code == 401            # no creds → NOT open anymore
    assert c.post("/rooms/provision", json=body, headers=_h("tok-viewer")).status_code == 403   # viewer too low
    # raw ledger write is commander-grade
    ev = {"event_type": "x", "payload": {}}
    assert c.post("/events/append", json=ev, headers=_h("tok-operator")).status_code == 403
    assert c.post("/events/append", json=ev).status_code == 401


def test_rbac_off_falls_back_to_open(monkeypatch):
    """THOR_USERS unset → legacy open posture, so `make qa`/`make prove` (no token) keep passing."""
    monkeypatch.delenv("THOR_USERS", raising=False)
    monkeypatch.delenv("THOR_API_TOKEN", raising=False)
    from dashboard import dashboard_api
    dashboard_api.bind(_StubService())
    c = TestClient(dashboard_api.app)
    assert c.post("/features", json={"title": "x"}).status_code == 200


def test_merge_authority_is_commander_only():
    """LAYER 2: only a commander key may sign a merge — the exact gate Manager.approve consults."""
    from manager.core import ThorManager
    mgr = ThorManager(None)
    mgr.register_user("carol", "commander", CMD)
    mgr.register_user("olivia", "operator", OP)
    mgr.register_user("vince", "viewer", VIEW)
    assert mgr.is_authorized_signer(CMD) is True
    assert mgr.is_authorized_signer(OP) is False
    assert mgr.is_authorized_signer(VIEW) is False
    assert OP not in mgr.authorized_signers and VIEW not in mgr.authorized_signers


def test_operator_key_demoted_out_of_signer_set():
    """Defence-in-depth: registering a key as operator REMOVES any stale commander authority it had.
    A second commander stays registered so the signer set is non-empty (the real check fires, not the
    empty-set dev fallback)."""
    from manager.core import ThorManager
    mgr = ThorManager(None)
    other_commander = _pub()
    mgr.register_user("dana", "commander", other_commander)
    mgr.register_operator(CMD)            # legacy bootstrap → commander/signer
    assert mgr.is_authorized_signer(CMD) is True
    mgr.register_user("carol", "operator", CMD)   # same key now demoted to operator
    assert mgr.is_authorized_signer(CMD) is False
    assert mgr.is_authorized_signer(other_commander) is True   # the real commander still signs
