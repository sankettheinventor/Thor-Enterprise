"""
The Cook is PLUGGABLE — bring your own agent.

THOR governs the WALLS, never the agent: a sealed room (no network except the one-door), the worktree
as the only writable mount, the GovEngine **verdict-from-reality** (judges the real git diff + test
runs vs the claim), and a **human-signed merge**. Those hold for ANY cook — Claude Code, Aider, a
home-grown script, an agent THOR has never heard of — because they govern the agent's OUTPUT and its
BLAST RADIUS, not its identity. So the user picks the agent; THOR does not depend on it.

A `CookRuntime` is just a DESCRIPTION of how to launch a chosen agent inside a room (image + command +
env). It carries NO governance — governance is the walls. Select with `THOR_COOK` (default
"claude-code"). Add ANY agent with ZERO THOR code via the "generic" runtime (THOR_COOK=generic +
THOR_COOK_IMAGE + THOR_COOK_CMD), or register a new CookRuntime subclass.

(The actual launch — provision a room with `image()`, run `command()` in it, collect claim_done — is the
Manager-side cook-runner; it is the live integration that also needs the one-door egress. See docs/COOK.md.)
"""
from __future__ import annotations

import os
import shlex
from abc import ABC, abstractmethod


def task_prompt(feature_slice: dict) -> str:
    """The task handed to whatever agent runs. Agent-agnostic; the FULL slice is mounted at
    /task/feature.json (read-only) and the worktree is /work (the only writable mount)."""
    fid = feature_slice.get("feature_id", "?")
    acs = feature_slice.get("acceptance_criteria") or []
    scope = feature_slice.get("scope_files") or (feature_slice.get("scope") or {}).get("files") or []
    return (f"Implement feature {fid}. Write ONLY within these paths: {list(scope)}. "
            f"Acceptance criteria: {list(acs)}. The full task slice is at /task/feature.json (read-only); "
            f"the repository worktree is /work (the only writable location). Add a real test. Do not "
            f"touch anything outside the listed scope — out-of-scope writes are blocked by THOR.")


class CookRuntime(ABC):
    """How to launch ONE agent inside a THOR room. Carries NO governance — the walls do the enforcing."""

    name: str = "abstract"

    @abstractmethod
    def image(self) -> str:
        """The Docker image: a THOR room (sealed, /task read-only, /work read-write) with the agent in it."""

    @abstractmethod
    def command(self, feature_slice: dict) -> list[str]:
        """The command that runs the agent NON-interactively to build the feature, then exits."""

    def env(self) -> dict:
        """Agent credentials/config to inject (from the host env / a secret store). THOR never stores keys."""
        return {}

    def egress_allowlist(self) -> tuple[str, ...]:
        """The ONLY hosts this agent may reach (its model/auth endpoints). The one-door gateway denies
        everything else. Default: from THOR_COOK_EGRESS (comma-separated); empty = fully sealed."""
        return tuple(h.strip() for h in os.environ.get("THOR_COOK_EGRESS", "").split(",") if h.strip())

    def preflight(self) -> list[str]:
        """Config problems to surface BEFORE provisioning a room (e.g. a missing credential). Empty = ready.
        The runner refuses to launch when this is non-empty, so a misconfigured cook fails fast and clearly
        instead of dying opaquely inside the sealed room."""
        return []

    def describe(self, feature_slice: dict) -> dict:
        return {"cook": self.name, "image": self.image(), "command": self.command(feature_slice),
                "env_keys": sorted(self.env().keys()), "egress_allowlist": list(self.egress_allowlist())}


class ClaudeCodeRuntime(CookRuntime):
    """Claude Code as the cook (NO API key — auth via CLAUDE_CODE_OAUTH_TOKEN from `claude setup-token`).
    Its room image additionally carries the Leash PreToolUse hook as agent-specific defence-in-depth, but
    the ENFORCEMENT is still the walls + verdict (true for every runtime)."""

    name = "claude-code"

    def image(self) -> str:
        return os.environ.get("THOR_COOK_IMAGE", "thor-room-claude:latest")

    def command(self, feature_slice: dict) -> list[str]:
        return ["claude", "-p", task_prompt(feature_slice),
                "--permission-mode", "acceptEdits", "--output-format", "json"]

    def env(self) -> dict:
        tok = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN")
        return {"CLAUDE_CODE_OAUTH_TOKEN": tok} if tok else {}

    def egress_allowlist(self) -> tuple[str, ...]:
        # Claude Code's required hosts (the one-door gateway denies all else). Override with THOR_COOK_EGRESS.
        env = super().egress_allowlist()
        return env or ("api.anthropic.com", "claude.ai", "console.anthropic.com", "statsig.anthropic.com")

    def preflight(self) -> list[str]:
        """Fail fast on a misconfigured frontier deploy: the live Claude Code cook authenticates with an
        operator-supplied OAuth token (`claude setup-token`). Without it the cook would launch and only fail
        opaquely inside the sealed room — so surface the exact fix here, before provisioning."""
        if not os.environ.get("CLAUDE_CODE_OAUTH_TOKEN"):
            return ["CLAUDE_CODE_OAUTH_TOKEN is not set — run `claude setup-token` and export it "
                    "(the frontier cook authenticates with it; THOR injects no model key)"]
        return []


class GenericCommandRuntime(CookRuntime):
    """Bring ANY agent with NO THOR code: set THOR_COOK_IMAGE + THOR_COOK_CMD. In THOR_COOK_CMD, the token
    `{task}` is replaced by the task prompt (else it is appended). Inject the agent's own secrets via
    THOR_COOK_ENV_* (e.g. THOR_COOK_ENV_OPENAI_API_KEY). The walls + verdict govern it identically."""

    name = "generic"

    def image(self) -> str:
        img = os.environ.get("THOR_COOK_IMAGE")
        if not img:
            raise ValueError("THOR_COOK=generic requires THOR_COOK_IMAGE (the agent's room image)")
        return img

    def command(self, feature_slice: dict) -> list[str]:
        raw = os.environ.get("THOR_COOK_CMD")
        if not raw:
            raise ValueError("THOR_COOK=generic requires THOR_COOK_CMD (how to launch the agent)")
        task = task_prompt(feature_slice)
        parts = shlex.split(raw)
        if "{task}" in raw:
            return [task if p == "{task}" else p for p in parts]
        return parts + [task]

    def env(self) -> dict:
        return {k[len("THOR_COOK_ENV_"):]: v for k, v in os.environ.items()
                if k.startswith("THOR_COOK_ENV_")}


_RUNTIMES: dict[str, type[CookRuntime]] = {
    "claude-code": ClaudeCodeRuntime,
    "generic": GenericCommandRuntime,
}


def register_runtime(name: str, cls: type[CookRuntime]) -> None:
    """Register a new agent runtime (so a third party can add one without editing THOR)."""
    _RUNTIMES[name] = cls


def known_runtimes() -> list[str]:
    return sorted(_RUNTIMES)


def select_runtime(name: str | None = None) -> CookRuntime:
    """Pick the cook the user configured (THOR_COOK, default 'claude-code'). The choice is the user's;
    THOR governs whichever agent runs identically (the walls + verdict)."""
    name = (name or os.environ.get("THOR_COOK", "claude-code")).strip()
    cls = _RUNTIMES.get(name)
    if cls is None:
        raise ValueError(f"unknown THOR_COOK={name!r}; known: {known_runtimes()} "
                         f"(or register a CookRuntime). Bring any agent with THOR_COOK=generic.")
    return cls()
