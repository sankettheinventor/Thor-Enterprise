"""
Production hardening: the HTTP surfaces require a bearer token on MUTATING endpoints when
THOR_API_TOKEN is configured (and stay open in dev/test when it is not). Docker-free, un-deferred.
"""
from fastapi.testclient import TestClient


def test_is_authorized_logic(monkeypatch):
    import thor_http_auth as a
    monkeypatch.delenv("THOR_API_TOKEN", raising=False)
    assert a.is_authorized(None) is True                 # disabled when no token configured
    monkeypatch.setenv("THOR_API_TOKEN", "s3cret")
    assert a.is_authorized(None) is False                 # configured → header required
    assert a.is_authorized("Bearer wrong") is False
    assert a.is_authorized("Bearer s3cret") is True


def test_manager_mutating_endpoint_requires_token(monkeypatch):
    monkeypatch.setenv("THOR_API_TOKEN", "s3cret")
    import manager.api as mapi
    client = TestClient(mapi.app)
    # an unauthenticated MUTATING call is rejected at the transport (401) — before any DB work
    r = client.post("/events/append", json={"event_type": "x", "payload": {}})
    assert r.status_code == 401, r.text
    # a wrong token is also rejected
    r2 = client.post("/events/append", json={"event_type": "x", "payload": {}},
                     headers={"Authorization": "Bearer nope"})
    assert r2.status_code == 401, r2.text


def test_dashboard_approve_requires_token(monkeypatch):
    monkeypatch.setenv("THOR_API_TOKEN", "s3cret")
    import dashboard.dashboard_api as dapi
    client = TestClient(dapi.app)
    # /approve is the most security-critical mutating endpoint — it MUST be gated
    r = client.post("/approve", json={"card_id": "c", "signature": "x", "signer_pub": "y"})
    assert r.status_code == 401, r.text
