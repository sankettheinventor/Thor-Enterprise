"""
Audit follow-on — the cockpit self-setup wizard (pure code, no AI): requirement check, image build state,
and the "Connect Claude once, reused everywhere" token store. Fast lane (no Docker/Postgres needed —
check() degrades gracefully when Docker is absent).
"""
from fastapi.testclient import TestClient


def test_setup_check_shape():
    from dashboard import setup
    c = setup.check()
    assert set(c) >= {"docker", "images", "claude", "ready", "build"}
    assert isinstance(c["images"], list) and all({"tag", "present", "desc"} <= set(i) for i in c["images"])
    assert isinstance(c["ready"], bool)


def test_setup_check_endpoint():
    import dashboard.dashboard_api as dapi
    r = TestClient(dapi.app).get("/setup/check")
    body = r.json()
    assert r.status_code == 200 and "ready" in body and "claude_source" in body


def test_consent_is_required_and_round_trips(tmp_path, monkeypatch):
    """THOR must not use a frontier-model login until the user explicitly consents."""
    from dashboard import setup
    monkeypatch.setattr(setup, "_THOR_DIR", tmp_path)
    monkeypatch.setattr(setup, "_CONSENT_FILE", tmp_path / "consent.json")
    assert setup.consent()["authorized"] is False
    assert setup.grant_consent("bogus-model")["ok"] is False        # only known providers
    assert setup.grant_consent("claude")["ok"] is True
    assert setup.consent() == {"authorized": True, "model": "claude"}
    setup.revoke_consent()
    assert setup.consent()["authorized"] is False


def test_build_loop_is_gated_on_consent(monkeypatch):
    """The live build loop must NOT spend the user's subscription without consent."""
    from sdlc import build_driver
    from dashboard import setup
    monkeypatch.setattr(setup, "consent", lambda: {"authorized": False, "model": None})
    assert build_driver._ai_consented() is False
    monkeypatch.setattr(setup, "consent", lambda: {"authorized": True, "model": "claude"})
    assert build_driver._ai_consented() is True


def test_claude_source_reports_existing_login(tmp_path, monkeypatch):
    """The wizard must distinguish 'reusing your existing login (nothing to do)' from 'needs a paste'."""
    from dashboard import setup
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    monkeypatch.setattr(setup, "_TOKEN_FILE", tmp_path / "no_thor_token")
    monkeypatch.setattr("os.path.expanduser", lambda p: p.replace("~", str(tmp_path)))
    monkeypatch.setattr("glob.glob", lambda p: [])
    assert setup.claude_source() == "none"                       # nothing anywhere -> paste fallback
    (tmp_path / ".claude").mkdir(parents=True)
    (tmp_path / ".claude" / ".credentials.json").write_text("{}")
    assert setup.claude_source() == "existing"                   # existing Claude login -> nothing to do


def test_connect_claude_rejects_junk_and_writes_token(tmp_path, monkeypatch):
    from dashboard import setup
    monkeypatch.setattr(setup, "_THOR_DIR", tmp_path)
    monkeypatch.setattr(setup, "_TOKEN_FILE", tmp_path / "claude_token")
    assert setup.connect_claude("short")["ok"] is False        # too short -> rejected
    setup.connect_claude("sk-ant-oat01-" + "x" * 40)
    assert (tmp_path / "claude_token").read_text().startswith("sk-ant-oat01-"), "token must be stored"


def test_discover_reads_the_thor_token_store(tmp_path, monkeypatch):
    """The cockpit 'Connect Claude' writes ~/.thor/claude_token; every room reuses it via discover."""
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr("os.path.expanduser", lambda p: p.replace("~", str(tmp_path)))
    (tmp_path / ".thor").mkdir()
    (tmp_path / ".thor" / "claude_token").write_text("sk-ant-oat01-REUSED-EVERYWHERE")
    from cook.runtime import discover_claude_oauth
    assert discover_claude_oauth() == "sk-ant-oat01-REUSED-EVERYWHERE"
