# SPDX-License-Identifier: Apache-2.0
import pytest

from frappe_cpcp.core import comms as c
from frappe_cpcp.core.noticeclock import ProofBasis


def test_dialer_never_claims_verified_connection():
    r = c.requested_only()
    assert r.provenance == c.Provenance.REQUESTED_ONLY and r.outcome is None and "not confirmed" in r.duration_label
    r = c.record_dialer_outcome(c.CallOutcome.ANSWERED, 90)
    assert r.provenance == c.Provenance.OFFICER_REPORTED and "unverified" in r.duration_label
    assert c.record_dialer_outcome(c.CallOutcome.NO_ANSWER).duration_seconds is None
    with pytest.raises(c.CommsError):
        c.record_dialer_outcome(c.CallOutcome.ANSWERED, -1)


def test_only_provider_path_is_verified():
    r = c.record_provider_call(c.CallOutcome.ANSWERED, 42)
    assert r.provenance == c.Provenance.VERIFIED_PROVIDER and r.duration_seconds == 42


def test_only_confirmed_answered_call_supports_notice():
    assert c.notice_proof_for(c.CallOutcome.ANSWERED, True) == ProofBasis.ANSWERED_CALL_WARNING_CONFIRMED
    assert c.notice_proof_for(c.CallOutcome.ANSWERED, False) is None
    for o in (c.CallOutcome.NO_ANSWER, c.CallOutcome.BUSY, c.CallOutcome.WRONG_NUMBER, c.CallOutcome.CALLBACK_REQUESTED, None):
        assert c.notice_proof_for(o, True) is None


def test_sms_status_is_monotonic_and_terminal():
    S = c.SmsStatus
    assert c.advance_sms_status(S.QUEUED, S.ACCEPTED) == S.ACCEPTED
    assert c.advance_sms_status(S.DELIVERED, S.SENT) == S.DELIVERED  # late 'sent' webhook cannot regress
    assert c.advance_sms_status(S.SENT, S.QUEUED) == S.SENT
    assert c.advance_sms_status(S.FAILED, S.DELIVERED) == S.FAILED  # terminal is final
    assert c.advance_sms_status(S.UNKNOWN, S.DELIVERED) == S.DELIVERED


def test_contact_ordering_and_unit_binding():
    contacts = [
        c.Contact("b", c.Relationship.BACKUP, "A1", "+233241234001"),
        c.Contact("p", c.Relationship.PRIMARY, "A1", "+233241234002"),
        c.Contact("x", c.Relationship.PRIMARY, "B2", "+233241234003"),  # other unit: AC-72
        c.Contact("n", c.Relationship.PRIMARY, "A1", None),  # no number
        c.Contact("s", c.Relationship.DUTY_SUPERVISOR, None, "+233241234004"),
        c.Contact("d", c.Relationship.ONSITE_DRIVER, None, "+233241234005"),
    ]
    assert [x.contact_id for x in c.order_contacts(contacts, "A1")] == ["d", "p", "b", "s"]


def test_template_rules():
    t = "Vehicle {plate} at {zone}. Case {case_id}. Call {security_number}."
    out = c.render_template(t, dict(plate="GR1234", zone="Gate\n1", case_id="INC-1", security_number="0241"), False)
    assert "\n" not in out and "GR1234" in out
    with pytest.raises(c.CommsError):
        c.render_template("Move by {deadline}", {"deadline": "10:00"}, False)  # no clock yet
    assert "10:00" in c.render_template("Move by {deadline}", {"deadline": "10:00"}, True)
    with pytest.raises(c.CommsError):
        c.render_template("{secret}", {"secret": "x"}, True)
    with pytest.raises(c.CommsError):
        c.render_template("{plate}", {}, True)


def test_rate_limits():
    assert c.sms_rate_ok(0, 0) and c.sms_rate_ok(1, 5)
    assert not c.sms_rate_ok(2, 0) and not c.sms_rate_ok(0, 6)


def test_callback_signature_and_idempotency_key():
    body = b'{"id":"m1","status":"delivered"}'
    sig = c.sign_callback(b"s3cret", body)
    assert c.verify_callback(b"s3cret", body, sig)
    assert not c.verify_callback(b"other", body, sig) and not c.verify_callback(b"s3cret", body + b" ", sig)
    assert not c.verify_callback(b"s3cret", body, None) and not c.verify_callback(b"", body, sig)
    k1 = c.event_key("mock", "m1", "delivered", "t1")
    assert k1 == c.event_key("mock", "m1", "delivered", "t1") != c.event_key("mock", "m1", "failed", "t1")


def test_mock_provider_idempotent_and_free():
    p = c.MockSmsProvider()
    a = p.send("+233241234001", "hi", "k1")
    assert p.send("+233241234001", "hi", "k1") == a and len(p.sent) == 1
