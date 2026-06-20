"""
Boot auth-guard — a NETWORK-EXPOSED plane must never start with auth OFF. Localhost dev stays open for
convenience; a 0.0.0.0 bind (the compose/k8s posture) requires THOR_API_TOKEN or THOR_USERS (RBAC), with an
explicit THOR_ALLOW_OPEN=1 escape hatch. Docker-free.
"""
import pytest

from tools.start_thor import _auth_guard

_KEYS = ("THOR_BIND_HOST", "THOR_API_TOKEN", "THOR_USERS", "THOR_ALLOW_OPEN")


def _env(monkeypatch, **kw):
    for k in _KEYS:
        monkeypatch.delenv(k, raising=False)
    for k, v in kw.items():
        monkeypatch.setenv(k, v)


def test_localhost_with_no_auth_boots(monkeypatch):
    _env(monkeypatch, THOR_BIND_HOST="127.0.0.1")
    _auth_guard()                                   # no raise — dev convenience


def test_exposed_with_no_auth_is_refused(monkeypatch):
    _env(monkeypatch, THOR_BIND_HOST="0.0.0.0")
    with pytest.raises(SystemExit):
        _auth_guard()


def test_exposed_with_token_boots(monkeypatch):
    _env(monkeypatch, THOR_BIND_HOST="0.0.0.0", THOR_API_TOKEN="strong-secret")
    _auth_guard()


def test_exposed_with_rbac_users_boots(monkeypatch):
    _env(monkeypatch, THOR_BIND_HOST="0.0.0.0",
         THOR_USERS='[{"id":"a","role":"commander","token":"t"}]')
    _auth_guard()


def test_explicit_allow_open_overrides(monkeypatch):
    _env(monkeypatch, THOR_BIND_HOST="0.0.0.0", THOR_ALLOW_OPEN="1")
    _auth_guard()
