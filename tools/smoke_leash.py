"""
ONE-TIME smoke demonstration of the Leash's Phase 2a milestone (governance core).

Proves the deny-before-execute loop against a REAL worktree on disk:
  AC-1  an out-of-scope write is DENIED before the file is created (verified: file absent).
  AC-2  the denial carries a structured reason back to the cook.
  AC-3  every decision is a signed, hash-chained EventLog entry (verified by re-reading + verifying).
  AC-4  with the governor (adapter) DOWN, the action is denied — fail-closed (file absent).
  AC-11 the frozen policy cannot be mutated (the cook can't relax its own rules).
  (+ partial AC-7) a dependency-manifest write ESCALATES and is held (file absent).

NOT the formal proving suite (Rule 2). Deferred to Phase 2b: the raw-egress lock (AC-5),
credentials (AC-6), cook-adapter (AC-8), kill-switch (AC-9), load test (AC-10).
No faked results (Rule 11): every check prints the REAL observed outcome.

Run (inside the WSL venv, from ~/thor-enterprise):  python tools/smoke_leash.py
"""
from __future__ import annotations

import dataclasses
import os
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
os.chdir(REPO)

from adapters import agt_adapter
from leash.decision import DecisionRecorder, EventLog
from leash.policy import FrozenPolicy, Verdict
from leash.proxy import InRoomProxy

ROOM = "room-leash-demo"


class DownAdapter:
    """Stands in for an unreachable governor (AC-4): every check raises."""
    def check_action(self, action):
        raise ConnectionError("adapter unreachable")


def fresh_worktree() -> str:
    wt = REPO / ".smoke" / "leash-work"
    if wt.exists():
        shutil.rmtree(wt)
    (wt / "src").mkdir(parents=True)
    return str(wt)


def exists(worktree: str, rel: str) -> bool:
    return os.path.exists(os.path.join(worktree, rel))


def main() -> int:
    results: dict[str, bool] = {}
    worktree = fresh_worktree()

    # Frozen Kind-B policy: only src/ is in scope; infra/ and *secrets* are forbidden.
    policy = FrozenPolicy(
        room_id=ROOM,
        scope_files=("src/",),
        forbidden_patterns=("infra/", "**/secrets*"),
        language_lock="python",
        frozen_at=0.0,
    )
    agt_adapter.load_policy(policy)
    print(f"policy loaded: hash={policy.policy_hash[:12]} scope={policy.scope_files} "
          f"forbidden={policy.forbidden_patterns}")

    # Fresh signed EventLog for this demo.
    log_path = str(REPO / ".thor" / "leash-eventlog.jsonl")
    if os.path.exists(log_path):
        os.remove(log_path)
    recorder = DecisionRecorder(EventLog(log_path))
    proxy = InRoomProxy(agt_adapter, recorder, worktree)

    def cook_writes(path, content):
        return proxy.handle_tool_call(
            {"name": "write_file", "room_id": ROOM, "args": {"path": path, "content": content}}
        )

    print("\n== allow (in-scope) ==")
    allow = cook_writes("src/login.js", "// real code")
    ok_allow = allow["status"] == "allow" and exists(worktree, "src/login.js")
    print(f"   {allow}  file_written={exists(worktree, 'src/login.js')}")

    print("== AC-1 — deny (out-of-scope), file must NOT be created ==")
    deny = cook_writes("infra/secrets.tf", "leak")
    ac1 = deny["status"] == "deny" and not exists(worktree, "infra/secrets.tf")
    results["AC-1 out-of-scope denied before write"] = ac1
    print(f"   {deny}  file_written={exists(worktree, 'infra/secrets.tf')}")

    # AC-2 — the denial carried a structured reason back to the cook.
    ac2 = bool(deny.get("reason")) and "scope" in deny.get("reason", "").lower() \
        or "forbidden" in deny.get("reason", "").lower()
    results["AC-2 denial reason reaches cook"] = bool(ac2)
    print(f"== AC-2 — reason to cook: {deny.get('reason')!r}")

    print("== partial AC-7 — dependency manifest escalates + is held (file absent) ==")
    esc = cook_writes("package.json", '{"deps":{}}')
    ac7 = esc["status"] == "escalate" and esc.get("held") and not exists(worktree, "package.json")
    results["AC-7(partial) dependency add escalates+held"] = bool(ac7)
    print(f"   {esc}  file_written={exists(worktree, 'package.json')}")

    print("== AC-4 — governor DOWN => fail-closed deny (file absent) ==")
    proxy_down = InRoomProxy(DownAdapter(), recorder, worktree)
    downres = proxy_down.handle_tool_call(
        {"name": "write_file", "room_id": ROOM, "args": {"path": "src/should_not_write.js", "content": "x"}}
    )
    ac4 = downres["status"] == "deny" and "governor_unavailable" in downres.get("reason", "") \
        and not exists(worktree, "src/should_not_write.js")
    results["AC-4 fail-closed when governor down"] = ac4
    print(f"   {downres}  file_written={exists(worktree, 'src/should_not_write.js')}")

    print("== AC-3 — decisions are signed, hash-chained events (verify by re-reading) ==")
    chain_ok = recorder.eventlog.verify_chain()
    n_events = recorder.eventlog.count()
    # 4 governed actions above (allow, deny, escalate, down) -> at least 4 decided events
    ac3 = chain_ok and n_events >= 4
    results["AC-3 signed hash-chained decision log"] = ac3
    print(f"   verify_chain={chain_ok}  events_recorded={n_events}")

    print("== AC-11 — frozen policy cannot be mutated from inside the room ==")
    try:
        policy.scope_files = ("anything",)  # type: ignore[misc]
        ac11 = False  # mutation succeeded -> FAIL
    except dataclasses.FrozenInstanceError:
        ac11 = True
    results["AC-11 policy frozen / read-only"] = ac11
    print(f"   attempted policy mutation rejected={ac11}")

    print("\n==== LEASH SMOKE RESULTS (real, observed) ====")
    for k, v in results.items():
        print(f"   [{'PASS' if v else 'FAIL'}] {k}")
    print(f"   [{'PASS' if ok_allow else 'FAIL'}] (sanity) in-scope write allowed + executed")
    headline = results["AC-1 out-of-scope denied before write"] and \
        results["AC-4 fail-closed when governor down"] and \
        results["AC-3 signed hash-chained decision log"]
    print(f"\n   HEADLINE (governs + fails safe + audits): {'PASS' if headline else 'FAIL'}")
    return 0 if (all(results.values()) and ok_allow) else 1


if __name__ == "__main__":
    sys.exit(main())
