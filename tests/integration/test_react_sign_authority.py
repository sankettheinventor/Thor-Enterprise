"""
P7: the React cockpit's human-signs authority is real. The browser signs the Manager's challenge with
the operator's Ed25519 key (@noble/ed25519, in src/sign.js) — and that browser-produced signature is
ACCEPTED by the Python Manager, while a replayed nonce and a forged signature are REJECTED. This is the
cross-language proof that the SPA's signature is the same authority the moat enforces. Deferred; skips if
node + the ui deps aren't installed (never fakes green).
"""
import glob
import json
import os
import subprocess

import pytest

pytestmark = pytest.mark.deferred


def _node():
    c = sorted(glob.glob(os.path.expanduser("~/.nvm/versions/node/*/bin/node")))
    return c[-1] if c else None


@pytest.mark.skipif(not _node() or not os.path.isdir("ui/node_modules/@noble"),
                    reason="node + ui deps not installed (run npm install in ui/)")
def test_browser_signature_accepted_replay_and_forgery_rejected(fresh_ledger):
    from manager.core import ThorManager

    mgr = ThorManager(fresh_ledger)
    card_id = mgr.raise_card("qa_fail", "F1", {"feature_id": "F1"}, held=True)
    priv_hex = os.urandom(32).hex()
    nonce = mgr.issue_challenge(card_id)
    material = mgr.card_material(card_id, mgr._get_card(card_id)["payload"], nonce)

    out = subprocess.run([_node(), "scripts/sign_probe.mjs", priv_hex, material],
                         cwd="ui", capture_output=True, text=True, check=True).stdout
    signed = json.loads(out)
    mgr.register_operator(signed["pub"])

    # (1) the browser-produced signature is ACCEPTED
    assert mgr.approve(card_id, signed["sig"], signed["pub"], nonce)["verified"] is True

    # (2) REPLAY the same nonce/signature -> rejected (nonce consumed, card now approved)
    assert mgr.approve(card_id, signed["sig"], signed["pub"], nonce)["verified"] is False

    # (3) FORGERY — a valid-looking signature for the WRONG material/card -> rejected
    card2 = mgr.raise_card("qa_fail", "F2", {"feature_id": "F2"}, held=True)
    n2 = mgr.issue_challenge(card2)
    assert mgr.approve(card2, signed["sig"], signed["pub"], n2)["verified"] is False
