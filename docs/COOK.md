# The Cook — Claude Code in the room, governed by the Leash

THOR's cook (the AI that writes the code) is **Claude Code running inside the sealed room**. THOR does
not call an LLM API itself and needs **no `ANTHROPIC_API_KEY`** — Claude Code authenticates with the
operator's Claude subscription via a long-lived token. Every action the cook takes is gated by the
**Leash** before it happens.

## How governance is wired (and PROVEN)

- Room image: `wall/image/Dockerfile.claude` (base `node:20`, + `@anthropic-ai/claude-code`, + the
  Leash hook, + an unprivileged `cook` user).
- The Leash is a Claude Code **`PreToolUse` hook** (`leash/claude_code_hook.py`): before every
  `Write` / `Edit` / `MultiEdit` / `NotebookEdit` / `Bash`, Claude Code calls the hook, which evaluates
  the target path against the room's frozen policy using the **same `leash.policy` engine as FLOW B**
  (so it inherits the BUG-1 traversal guard). **Allow → exit 0; block → exit 2 + the reason the model
  then sees.** Fail-closed: unreadable input / missing policy / any error → block.
- It is wired via **managed settings** (`/etc/claude-code/managed-settings.json`) — the highest-
  precedence Claude Code settings — and the hook + settings are **root-owned**, so the unprivileged
  cook **cannot disable its own governor**.

**Verified (no API key / no network needed for the governance layer):**
- `test_claude_code_hook.py` (6 tests): in-scope allow, out-of-scope deny, traversal deny, multi-edit
  per-path, missing-slice fail-closed, CLI exit 0/2.
- In the built room image: Claude Code `2.1.170` present; an out-of-scope write → `THOR Leash DENY …
  forbidden pattern` (exit 2); a traversal → `… unsafe path (traversal)` (exit 2); a cook attempt to
  rewrite `managed-settings.json` → `Permission denied`.

## Running the cook LIVE (what it additionally needs)

1. **Auth (no API key):** on a logged-in machine run `claude setup-token`, then pass the result to the
   room as `CLAUDE_CODE_OAUTH_TOKEN` (env / secret store). The room is launched roughly as:
   ```sh
   claude -p "<task from /task/feature.json>" --permission-mode acceptEdits --output-format json
   ```
   (The PreToolUse hook is the real gate; `acceptEdits` just stops interactive prompts in the
   unattended room — the Leash still blocks anything out of policy.)
2. **One-door egress:** the room is `network_disabled` by default. Claude Code needs HTTPS (443) egress
   to Claude's hosts to function: `api.anthropic.com`, `claude.ai`, `platform.claude.com`,
   `downloads.claude.ai`, `raw.githubusercontent.com`. This is the **one-door egress** (`wall/
   network_enforcer.one_door_room_kwargs`, currently `NotImplementedError`) restricted to that
   allowlist — the named prerequisite to take the live cook end-to-end. Until it lands, the governance
   (hook) is proven but the live Claude Code run cannot reach the model from a fully-sealed room.

## Still TODO for the live cook (honest)
- Build the **one-door egress** (allowlist to Claude's hosts) so a sealed room can run Claude Code.
- A small **cook-runner** in the Manager that launches `claude -p` in the room with the slice + token,
  then collects `claim_done`.
- **Bash-command-level** governance in the hook (currently file-write tools are scope-checked; Bash is
  allowed — a sealed room limits blast radius, but parsing redirects/egress is a follow-up).
- Verify the exact `managed-settings.json` path + `PreToolUse` field names against your Claude Code
  version (built/tested against `2.1.170`).
