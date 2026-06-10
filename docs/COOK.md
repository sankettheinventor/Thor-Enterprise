# The Cook — bring your own agent; THOR governs the walls

**THOR depends on the WALLS, never on the agent.** The cook (the AI that writes the code) is whatever
the *user* chooses — Claude Code, Aider, a home-grown script, an agent THOR has never heard of. THOR
seals it in a room and judges its output from reality; the same governance holds for every agent.
Claude Code is just *one* selectable runtime. An agent can "birth or die" with no change to THOR.

## What enforces governance (agent-agnostic, the same for every cook)

1. **Sealed room** — `network_disabled` except the one-door egress; the agent cannot exfiltrate or
   reach arbitrary hosts.
2. **Worktree is the only writable mount** (`/work`); the task slice is read-only at
   `/task/feature.json`. The agent's blast radius is the feature branch, nothing else.
3. **GovEngine verdict-from-reality** — judges the actual git diff + real test runs against the claim.
   This governs the agent's *output*, not its identity, so a lying / out-of-scope / unknown agent is
   caught here regardless of which tool produced the change.
4. **Human-signed merge** (Ed25519 + nonce) — nothing reaches `main` without the human.

None of the above knows or cares which agent ran. That is the point.

## Choosing / adding a cook (zero THOR code to add an agent)

Select with `THOR_COOK` (default `claude-code`). A `CookRuntime` is only a *description* of how to launch
the agent (image + command + env) — it carries no governance.

```sh
# Claude Code (default): auth via a subscription token, NOT an API key
export THOR_COOK=claude-code
export CLAUDE_CODE_OAUTH_TOKEN=$(claude setup-token)   # run on a logged-in machine

# ANY other agent — no THOR code change, just env:
export THOR_COOK=generic
export THOR_COOK_IMAGE=my-org/aider-room:latest        # a THOR room image with the agent installed
export THOR_COOK_CMD='aider --yes --message {task}'    # {task} is replaced by THOR's task prompt
export THOR_COOK_ENV_OPENAI_API_KEY=sk-...             # the agent's OWN secret, passed through
```

Or register a runtime in code: `cook.register_runtime("my-agent", MyAgentRuntime)`.

## The contract an agent must satisfy to be a THOR cook

Any agent works if it:
- runs **non-interactively** inside the room and **exits** when done (e.g. `claude -p ...`, `aider --yes`);
- reads its task from **`/task/feature.json`** (read-only) and writes only under **`/work`**;
- needs only **egress to its model's hosts** (provided via the one-door allowlist);
- carries its own credentials via env (THOR stores none).

That's it. THOR provides the walls; the agent does the building; the verdict judges the result.

## Claude Code specifics (one runtime)

- Image: `wall/image/Dockerfile.claude` (node:20 + `@anthropic-ai/claude-code` + an unprivileged cook).
- **Defence-in-depth (Claude-Code-specific, optional):** the room also wires the Leash as a Claude Code
  `PreToolUse` hook (`leash/claude_code_hook.py`) via root-owned managed settings the cook cannot
  disable — so Claude Code gets *real-time* "blocked, here's why" feedback before each Write/Edit/Bash.
  This is a courtesy layer; the *enforcement* is still the walls + verdict (true for every runtime).
- Auth: `CLAUDE_CODE_OAUTH_TOKEN` (from `claude setup-token`) — **no `ANTHROPIC_API_KEY`**.

**Verified:** `test_cook_runtime` (pluggability), `test_claude_code_hook` (6, hook governance),
`test_cook_agent` (in-process governance seam); in the built room image Claude Code 2.1.170 is present,
out-of-scope + traversal writes are DENIED (exit 2), and the managed settings are tamper-proof to the cook.

## Live end-to-end — the named remaining work
- **One-door egress** (`wall/network_enforcer.one_door_room_kwargs`, currently `NotImplementedError`):
  allowlist HTTPS egress to the chosen agent's model hosts (for Claude Code: `api.anthropic.com`,
  `claude.ai`, `platform.claude.com`, `downloads.claude.ai`, `raw.githubusercontent.com`).
- **Manager cook-runner:** provision a room with `runtime.image()`, run `runtime.command(slice)` with
  `runtime.env()`, collect `claim_done`. (The runtime *description* is built + tested; the runner is the
  live integration that needs the egress above.)
