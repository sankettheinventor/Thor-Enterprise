"""
Audit blocker #6 — GDPR Art.17 erasure on the append-only, hash-chained ledger.

Proves the tombstone + redaction-at-read pattern: an erased subject's identifiers vanish from everything
SERVED (audit feed/export), the erasure is itself auditable, AND verify_chain still holds because the raw
rows are never mutated. Pure-logic tests run in the fast CI lane; the end-to-end test is deferred (Postgres).
"""
import json

import pytest

from compliance import erasure

SUBJECT = "op_pubkey_AAAABBBBCCCC"


# ---- fast lane: the redaction logic is pure (no DB) ----

def test_redaction_masks_subject_everywhere_and_is_pure():
    events = [
        {"seq": 0, "event_type": "card.approved", "actor": SUBJECT, "payload": {"signer": SUBJECT, "note": "ok"}},
        {"seq": 1, "event_type": "subject.erasure", "payload": {"subject": SUBJECT, "requested_by": "operator"}},
        {"seq": 2, "event_type": "feature.added", "payload": "free text mentioning " + SUBJECT},
    ]
    before = json.dumps(events)
    out = erasure.redact_events(events)
    flat = json.dumps(out)
    assert SUBJECT not in flat, "erased subject must not appear anywhere in served events"
    assert "[erased]" in flat
    assert json.dumps(events) == before, "redaction must be non-mutating on the raw events"


def test_no_erasure_is_a_noop():
    events = [{"seq": 0, "event_type": "x", "actor": "manager", "payload": {"a": 1}}]
    assert erasure.redact_events(events) == events


def test_erased_subjects_reads_tombstones():
    events = [{"event_type": "subject.erasure", "payload": json.dumps({"subject": "k1"})},
              {"event_type": "subject.erasure", "payload": {"subject": "k2"}},
              {"event_type": "other", "payload": {}}]
    assert erasure.erased_subjects(events) == {"k1", "k2"}


# ---- deferred: the full flow through a real Manager + chained ledger ----

@pytest.mark.deferred
def test_erasure_redacts_served_audit_but_chain_still_verifies(fresh_ledger):
    from manager.core import ThorManager
    mgr = ThorManager(fresh_ledger)

    # a subject (operator pubkey) appears in the ledger as an actor + in payloads (use non-projected
    # event types so the projection's strict schemas don't reject our synthetic records)
    mgr._record("operator.note", {"signer": SUBJECT, "ref": "c1"}, actor=SUBJECT)
    mgr._record("operator.note", {"context": "approved by " + SUBJECT})
    assert mgr.eventlog.verify_chain()

    from dashboard.service import DashboardService
    svc = DashboardService(mgr)
    assert SUBJECT in svc.audit_export(), "precondition: subject visible before erasure"

    # honor the erasure request
    erasure.request_erasure(mgr, SUBJECT, requested_by="operator")

    export = svc.audit_export()
    assert SUBJECT not in export, "served audit export still leaks the erased subject"
    assert "[erased]" in export
    feed_flat = json.dumps(svc.audit_feed())
    assert SUBJECT not in feed_flat, "served audit feed still leaks the erased subject"

    # the erasure is itself on the record (provable compliance) and the chain is INTACT (rows untouched)
    raw = mgr.eventlog.all_events()
    assert any(e["event_type"] == erasure.ERASURE_EVENT for e in raw), "erasure must be auditable"
    assert mgr.eventlog.verify_chain(), "the hash-chain must still verify after erasure (redaction != deletion)"
