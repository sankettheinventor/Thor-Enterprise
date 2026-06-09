"""
BUG-3 (MEDIUM — optional replay lock).

manager.core.approve() only checks/consumes the one-time nonce `if nonce is not None`. A signature
submitted with NO nonce skips replay protection entirely: a captured/pre-signed signature over the
no-nonce card material is accepted, and the card is approved. The nonce must be MANDATORY — an absent
nonce → reject, card stays open.

Uses the real signed-ledger Manager (Postgres) → runs in `make qa` against the ISOLATED QA database.
Un-deferred.
"""
from manager.core import ThorManager


def _operator():
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
    from wall.identity_stamper import _b64
    priv = Ed25519PrivateKey.generate()
    pub = _b64(priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw))
    return priv, pub, _b64


def test_bug3_nonce_mandatory(fresh_ledger):
    """A signature submitted with NO nonce must be REJECTED — the replay lock is not optional."""
    mgr = ThorManager(fresh_ledger)
    priv, pub, _b64 = _operator()
    mgr.register_operator(pub)
    card = mgr.raise_card("plan", "FB3", {"feature_id": "FB3"})
    mgr.issue_challenge(card)   # the system issued a one-time nonce: a nonce-bound signature is REQUIRED

    # attacker bypasses the replay lock by signing the NO-NONCE material and submitting nonce=None
    material_no_nonce = mgr.card_material(card, mgr._get_card(card)["payload"])
    sig = _b64(priv.sign(material_no_nonce.encode()))
    r = mgr.approve(card, sig, pub, nonce=None)

    assert r["verified"] is False, \
        "approve() accepted a signature with NO nonce — the replay lock is optional (BUG-3)"
    assert mgr.is_card_approved(card) is False, "card must stay OPEN when the nonce is missing"
