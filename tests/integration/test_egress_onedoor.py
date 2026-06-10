"""
One-door egress: the governed gateway allowlists destinations (HTTP and HTTPS-CONNECT); a one-door
room's proxy points at the gateway; each agent declares its own egress allowlist. Docker-free unit
coverage of the decision logic + wiring (the full sealed-room→gateway→internet path is proven live).
"""
import leash.gateway_proxy as gp
from cook.runtime import ClaudeCodeRuntime, GenericCommandRuntime
from wall.network_enforcer import GATEWAY_NAME, GATEWAY_PORT, egress_proxy_env


def test_allowlist_exact_and_subdomain(monkeypatch):
    monkeypatch.setattr(gp, "ALLOWLIST", {"anthropic.com", "claude.ai"})
    assert gp._allowlisted("anthropic.com")              # exact
    assert gp._allowlisted("api.anthropic.com")          # subdomain
    assert gp._allowlisted("claude.ai")
    assert not gp._allowlisted("evil.com")               # not listed
    assert not gp._allowlisted("notanthropic.com")       # suffix without a dot is NOT a subdomain


def test_egress_proxy_env_routes_through_the_gateway():
    e = egress_proxy_env()
    expect = f"http://{GATEWAY_NAME}:{GATEWAY_PORT}"
    assert e["HTTPS_PROXY"] == expect and e["https_proxy"] == expect
    assert e["NO_PROXY"].startswith("localhost")


def test_claude_runtime_allowlists_only_anthropic_hosts(monkeypatch):
    monkeypatch.delenv("THOR_COOK_EGRESS", raising=False)
    al = ClaudeCodeRuntime().egress_allowlist()
    assert "api.anthropic.com" in al and "claude.ai" in al
    assert "api.openai.com" not in al


def test_any_agent_declares_its_own_egress(monkeypatch):
    monkeypatch.setenv("THOR_COOK_EGRESS", "api.openai.com, gpt.example")
    assert GenericCommandRuntime().egress_allowlist() == ("api.openai.com", "gpt.example")
