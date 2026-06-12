"""
Sub-module 2.5 — Policy Loader + the THOR-native policy engine.

The per-room governance policy (Kind B) — scope, forbidden patterns, language lock — is loaded
FROZEN and read-only (FR-10, AC-11). `evaluate()` is THOR's own policy engine: it decides
allow / deny / escalate with a classification (non_critical / critical / denied).

⚠️ This is the STUB that Microsoft AGT plugs into at Module 12 (decision: keep Rule 5). The
AGT adapter calls `evaluate()` today; at M12 the adapter instead calls AGT's Agent OS — and
ONLY the adapter changes (the Strangler seam). The semantics here are deliberately simple
(scope/forbidden/manifest), the real richness arrives with AGT + Module 14.
"""
from __future__ import annotations

import fnmatch
import hashlib
import json
from dataclasses import dataclass

# Files whose change is a dependency/stack decision → escalate to a human (FR-13, FR-15).
CRITICAL_MANIFESTS = (
    "package.json", "package-lock.json", "requirements.txt", "pyproject.toml",
    "go.mod", "Cargo.toml", "Gemfile", "pom.xml", "build.gradle",
)


@dataclass(frozen=True)
class FrozenPolicy:
    """
    Immutable per-room policy. `frozen=True` + tuple fields mean it cannot be mutated in place
    — the cook (or anything inside the room) cannot relax its own rules (AC-11 / P1).
    """
    room_id: str
    scope_files: tuple[str, ...]        # allowed path prefixes / globs, e.g. ("src/", "tests/**")
    forbidden_patterns: tuple[str, ...]  # always-denied globs/prefixes, e.g. ("infra/", "**/secrets*")
    language_lock: str | None = None
    frozen_at: float = 0.0

    @property
    def policy_hash(self) -> str:
        raw = json.dumps(
            {
                "room_id": self.room_id,
                "scope_files": list(self.scope_files),
                "forbidden_patterns": list(self.forbidden_patterns),
                "language_lock": self.language_lock,
            },
            sort_keys=True,
        ).encode()
        return hashlib.sha256(raw).hexdigest()


@dataclass
class Verdict:
    decision: str          # "allow" | "deny" | "escalate"
    reason: str
    classification: str    # "non_critical" | "critical" | "denied"


def _matches(path: str, patterns: tuple[str, ...]) -> bool:
    """A path matches if it equals/under a dir-prefix entry, or matches a glob entry."""
    for pat in patterns:
        if fnmatch.fnmatch(path, pat):
            return True
        base = pat.rstrip("/")
        if path == base or path.startswith(base + "/"):
            return True
    return False


def _is_unsafe_path(target: str) -> bool:
    """BUG-1: a path is unsafe if it is absolute or contains a parent-dir ('..') segment. Such a path
    can TEXTUALLY satisfy a startswith() scope check ('src/../../x' startswith 'src/') yet escape the
    worktree once os.path.join'd. We reject it BEFORE any scope match so traversal can never be
    'within scope'. Checked on segments (both separators) so '..' / '/etc' / '..\\x' are all caught."""
    if not target:
        return False
    if target.startswith("/") or target.startswith("\\"):
        return True
    return ".." in target.replace("\\", "/").split("/")


def evaluate(policy: FrozenPolicy, action: dict) -> Verdict:
    """
    Pre-action decision (P3). Order matters: forbidden wins, then manifest→escalate, then scope.
    Fail-closed for anything we cannot understand (deny, never allow).
    """
    if action.get("type") not in ("tool_call", "model_call", "egress"):
        return Verdict("deny", f"unrecognized action type: {action.get('type')!r}", "denied")

    target = action.get("target") or ""

    # A WRITE action whose path could not be resolved (inspector returned no target) FAILS CLOSED — an
    # unparseable write must never fall through to the allow at the end (AUD-policy-empty-target).
    _WRITE_OPS = ("write_file", "edit_file", "delete_file", "append_file", "create_file", "patch_file")
    if not target and action.get("name") in _WRITE_OPS:
        return Verdict("deny", f"write with no resolvable path, denied: {action.get('name')!r}", "denied")

    # 0) path-traversal / absolute path → deny BEFORE any scope reasoning (BUG-1, sandbox escape).
    #    A raw-string scope match can be fooled by 'src/../../x'; reject the escape outright.
    if _is_unsafe_path(target):
        return Verdict("deny", f"unsafe path (traversal/absolute), denied: {target}", "denied")

    # 1) forbidden wins (deny-precedence — PRD §10 "conflicting policies: deny-wins")
    if _matches(target, policy.forbidden_patterns):
        return Verdict("deny", f"path matches a forbidden pattern: {target}", "denied")

    # 2) dependency/stack change → escalate to a human (critical) — FR-13/FR-15
    basename = target.rsplit("/", 1)[-1]
    if basename in CRITICAL_MANIFESTS:
        return Verdict("escalate", f"dependency-manifest change needs approval: {target}", "critical")

    # 3) scope check — out-of-scope writes are denied before they execute (AC-1)
    if target and not _matches(target, policy.scope_files):
        return Verdict("deny", f"path outside approved scope: {target}", "denied")

    return Verdict("allow", "within approved scope", "non_critical")
