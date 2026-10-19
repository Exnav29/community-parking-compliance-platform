# SPDX-License-Identifier: Apache-2.0
"""Acceptance-oriented unit tests for visits, notice clock, charges, allegations, audit and geo."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from frappe_cpcp.core import allegations as al
from frappe_cpcp.core import auditchain, geo, visits as v
from frappe_cpcp.core.charges import (
    ChargeClass, ChargeError, FeeSchedule, add_storage_charge, add_tow_charge, add_violation_penalty,
    apply_payment_once, invoice_total, storage_periods,
)
from frappe_cpcp.core.flags import FeatureDisabled
from frappe_cpcp.core.noticeclock import (
    NoticeError, NoticePolicy, ProofBasis, establish_notice_clock, grace_state,
)

UTC = timezone.utc
T14 = datetime(2026, 10, 19, 14, 0, tzinfo=UTC)
T15 = T14 + timedelta(hours=1)


def mk(plate="GR123425", unit="A1", sid="S1", at=T14, existing=None, key="k-in"):
    return v.check_in(session_id=sid, estate_id="E1", host_unit_id=unit, category="guest", plate=plate, gate="G1",
                      officer="o1", observed_at=at, received_at=at, idempotency_key=key, active_sessions=existing)


# ---- visits (AC-101..AC-120) -----------------------------------------------------------------

def test_ac101_routine_checkout_60_minutes():
    s = v.check_out(mk(), gate="G1", officer="o1", observed_at=T15, received_at=T15, idempotency_key="k-out")
    assert s.status == v.VisitStatus.CHECKED_OUT and s.duration_minutes == 60
    assert s.presence == v.Presence.CONFIRMED_OUT and len(s.events) == 2


def test_ac103_cross_gate_distinct_officers():
    s = v.check_out(mk(), gate="G2", officer="o2", observed_at=T15, received_at=T15, idempotency_key="x")
    assert (s.entry_gate, s.exit_gate, s.entry_officer, s.exit_officer) == ("G1", "G2", "o1", "o2")


def test_ac104_reentry_is_new_session():
    first = v.check_out(mk(), gate="G1", officer="o1", observed_at=T15, received_at=T15, idempotency_key="x")
    second = mk(sid="S2", at=T15 + timedelta(hours=1), existing=[first], key="k2")
    assert second.session_id != first.session_id and first.status == v.VisitStatus.CHECKED_OUT


def test_ac105_checkout_idempotent_and_single_final_exit():
    s = mk()
    out = v.check_out(s, gate="G1", officer="o1", observed_at=T15, received_at=T15, idempotency_key="same")
    again = v.check_out(out, gate="G1", officer="o1", observed_at=T15, received_at=T15, idempotency_key="same")
    assert again is out
    with pytest.raises(v.AlreadyCheckedOut):
        v.check_out(out, gate="G2", officer="o2", observed_at=T15, received_at=T15, idempotency_key="other")


def test_active_duplicate_plate_triggers_already_inside():
    s = mk()
    with pytest.raises(v.AlreadyInside) as e:
        mk(sid="S2", existing=[s], key="k2")
    assert e.value.session_id == "S1"


def test_ac107_overdue_flag_never_closes():
    s = mk()
    assert v.flag_overdue(s, T14 + timedelta(days=2), timedelta(hours=12))
    assert s.status == v.VisitStatus.CHECKED_IN  # unchanged


def test_ac108_supervisor_estimate_is_labelled_and_independent():
    s = mk()
    with pytest.raises(v.VisitError):
        v.supervisor_correct_exit(s, supervisor="o1", estimated_exit_at=T15, reason="r", received_at=T15, idempotency_key="c")
    with pytest.raises(v.VisitError):
        v.supervisor_correct_exit(s, supervisor="sup", estimated_exit_at=T15, reason="", received_at=T15, idempotency_key="c")
    c = v.supervisor_correct_exit(s, supervisor="sup", estimated_exit_at=T15, reason="missed", received_at=T15, idempotency_key="c")
    assert c.estimated and c.presence == v.Presence.UNKNOWN and c.duration is None


def test_ac113_verified_stats_exclude_estimates():
    ok = v.check_out(mk(sid="A", plate="AA11"), gate="G1", officer="o1", observed_at=T15, received_at=T15, idempotency_key="1")
    est = v.supervisor_correct_exit(mk(sid="B", plate="BB22"), supervisor="sup", estimated_exit_at=T15, reason="r",
                                    received_at=T15, idempotency_key="2")
    stats = v.verified_duration_stats([ok, est, mk(sid="C", plate="CC33")])
    assert stats["count"] == 1 and stats["median"] == 60 and stats["excluded"] == 2


def test_ac109_offline_observed_vs_received_kept_distinct():
    later = T15 + timedelta(hours=5)
    s = v.check_out(mk(), gate="G1", officer="o1", observed_at=T15, received_at=later, idempotency_key="off")
    assert s.exit_at == T15 and s.events[-1].received_at == later


def test_exit_before_entry_and_naive_time_rejected():
    with pytest.raises(v.VisitError):
        v.check_out(mk(), gate="G1", officer="o1", observed_at=T14 - timedelta(minutes=1), received_at=T15, idempotency_key="z")
    with pytest.raises(v.VisitError):
        mk(at=datetime(2026, 10, 19, 14, 0))


def test_ac117_same_plate_two_estates_independent():
    a = mk()
    b = v.check_in(session_id="S9", estate_id="E2", host_unit_id="A1", category="guest", plate="GR123425", gate="G1",
                   officer="o9", observed_at=T14, received_at=T14, idempotency_key="k9", active_sessions=[a])
    assert b.estate_id == "E2"
    assert v.resolve_active_matches([a, b], estate_id="E1", plate="GR123425") == [a]


def test_no_vehicle_visit_allowed_and_host_required():
    s = v.check_in(session_id="P1", estate_id="E1", host_unit_id="A1", category="pedestrian", plate=None, gate="G1",
                   officer="o1", observed_at=T14, received_at=T14, idempotency_key="p", no_vehicle=True)
    assert s.plate is None
    with pytest.raises(v.VisitError):
        v.check_in(session_id="P2", estate_id="E1", host_unit_id="", category="g", plate="AB12", gate="G1", officer="o1",
                   observed_at=T14, received_at=T14, idempotency_key="q")


# ---- notice clock (AC-06, AC-84, AC-89) ------------------------------------------------------

POLICY = NoticePolicy(policy_version="P1", grace_minutes=15)
NOW = datetime(2026, 10, 19, 10, 0, tzinfo=UTC)


def test_ac06_unanswered_call_does_not_start_clock():
    for proof in (ProofBasis.CALL_ATTEMPTED_NO_ANSWER, ProofBasis.DIALER_OPENED, ProofBasis.SMS_QUEUED,
                  ProofBasis.SMS_SENT, ProofBasis.SMS_DELIVERED, ProofBasis.WRONG_NUMBER):
        with pytest.raises(NoticeError):
            establish_notice_clock(POLICY, proof=proof, notice_method="x", server_now=NOW)


def test_confirmed_contact_starts_15_minute_clock_and_expiry_is_not_a_penalty():
    n = establish_notice_clock(POLICY, proof=ProofBasis.ANSWERED_CALL_WARNING_CONFIRMED, notice_method="call", server_now=NOW)
    assert n.deadline == NOW + timedelta(minutes=15)
    assert grace_state(n, NOW + timedelta(minutes=14)) == "active"
    assert grace_state(n, NOW + timedelta(minutes=15)) == "expired"
    assert grace_state(None, NOW) == "not_started"


def test_policy_can_opt_in_sms_delivered_but_default_cannot():
    p = NoticePolicy("P2", 10, qualifying_proofs=frozenset({ProofBasis.SMS_DELIVERED}))
    n = establish_notice_clock(p, proof=ProofBasis.SMS_DELIVERED, notice_method="sms", server_now=NOW)
    assert n.grace_minutes == 10


def test_ac89_device_clock_drift_ignored():
    n = establish_notice_clock(POLICY, proof=ProofBasis.EXPLICIT_ACKNOWLEDGMENT, notice_method="x", server_now=NOW,
                               device_reported_at=NOW - timedelta(minutes=20))
    assert n.notice_effective_at == NOW


def test_ac86_emergency_never_uses_ordinary_grace():
    with pytest.raises(NoticeError):
        establish_notice_clock(POLICY, proof=ProofBasis.EXPLICIT_ACKNOWLEDGMENT, notice_method="x", server_now=NOW, is_emergency=True)


# ---- charges (AC-07, AC-09, AC-10, AC-97) ----------------------------------------------------

SCHED = FeeSchedule(version="F1", currency="GHS", violation_penalty=Decimal("500"),
                    storage_rate_per_period=Decimal("100"), storage_period_hours=24, storage_free_hours=0)
ON = {"fine_assessment_enabled": True, "towing_enabled": True, "impound_release_enabled": True}


def test_ac19_everything_gated_by_default():
    with pytest.raises(FeatureDisabled):
        add_violation_penalty([], incident_id="I1", schedule=SCHED, flags={})
    with pytest.raises(FeatureDisabled):
        add_tow_charge([], incident_id="I1", provider_amount=Decimal("300"), currency="GHS", provider_ref="p", schedule_version="F1", flags={})


def test_one_penalty_per_incident_even_after_clamp_then_tow():
    c = add_violation_penalty([], incident_id="I1", schedule=SCHED, flags=ON)
    c = add_violation_penalty(c, incident_id="I1", schedule=SCHED, flags=ON)  # clamp->tow replay
    c = add_tow_charge(c, incident_id="I1", provider_amount=Decimal("300"), currency="GHS", provider_ref="T1", schedule_version="F1", flags=ON)
    arr = datetime(2026, 10, 19, 8, tzinfo=UTC)
    c = add_storage_charge(c, incident_id="I1", yard_arrival=arr, stop_event=arr + timedelta(hours=20), schedule=SCHED, flags=ON)
    assert [x.charge_class for x in c].count(ChargeClass.PARKING_VIOLATION) == 1
    assert invoice_total(c) == Decimal("900.00")  # 500 + 300 + 100 (illustrative)


def test_tow_requires_provider_amount_and_is_idempotent():
    with pytest.raises(ChargeError):
        add_tow_charge([], incident_id="I1", provider_amount=None, currency="GHS", provider_ref="T", schedule_version="F1", flags=ON)
    c = add_tow_charge([], incident_id="I1", provider_amount=Decimal("300"), currency="GHS", provider_ref="T1", schedule_version="F1", flags=ON)
    assert len(add_tow_charge(c, incident_id="I1", provider_amount=Decimal("300"), currency="GHS", provider_ref="T1", schedule_version="F1", flags=ON)) == 1


def test_no_default_penalty_invented():
    empty = FeeSchedule(version="F0", currency="GHS")
    with pytest.raises(ChargeError):
        add_violation_penalty([], incident_id="I1", schedule=empty, flags=ON)


def test_storage_requires_arrival_and_stop_and_rounds_up():
    with pytest.raises(ChargeError):
        add_storage_charge([], incident_id="I1", yard_arrival=None, stop_event=NOW, schedule=SCHED, flags=ON)
    with pytest.raises(ChargeError):
        add_storage_charge([], incident_id="I1", yard_arrival=NOW, stop_event=None, schedule=SCHED, flags=ON)
    assert storage_periods(NOW, NOW + timedelta(hours=25), SCHED) == 2
    assert storage_periods(NOW, NOW + timedelta(hours=24), SCHED) == 1
    free = replace(SCHED, storage_free_hours=24)
    assert storage_periods(NOW, NOW + timedelta(hours=24), free) == 0
    with pytest.raises(ChargeError):
        storage_periods(NOW, NOW - timedelta(hours=1), SCHED)


def test_duplicate_webhook_settles_once():
    ledger: dict = {}
    assert apply_payment_once(ledger, "evt-1", Decimal("100"))
    assert not apply_payment_once(ledger, "evt-1", Decimal("100"))
    assert sum(ledger.values()) == Decimal("100")


# ---- allegations (AC-43..AC-68) --------------------------------------------------------------

def test_resident_cannot_set_security_outcomes():
    with pytest.raises(al.TriageError):
        al.transition(al.State.RECEIVED, al.State.UNDER_REVIEW, actor_is_security=False)
    assert al.transition(al.State.RECEIVED, al.State.UNDER_REVIEW, actor_is_security=True) == al.State.UNDER_REVIEW
    assert al.transition(al.State.SUBMITTED, al.State.WITHDRAWN, actor_is_security=False) == al.State.WITHDRAWN


def test_outcomes_need_reason_and_legal_transitions_only():
    with pytest.raises(al.TriageError):
        al.transition(al.State.UNDER_REVIEW, al.State.NOT_SUBSTANTIATED, actor_is_security=True)
    with pytest.raises(al.TriageError):
        al.transition(al.State.SUBMITTED, al.State.VERIFIED, actor_is_security=True)
    with pytest.raises(al.TriageError):
        al.transition(al.State.CLOSED, al.State.RECEIVED, actor_is_security=True)


def test_promotion_needs_officer_evidence_and_claim_and_links_cluster():
    base = dict(state=al.State.UNDER_REVIEW, officer="o1", officer_evidence_ids=["E1"], rule_version="R1",
                officer_has_active_claim=True, existing_incident_for_cluster=None)
    assert al.promote_to_incident(**base)["create"] is True
    for patch in ({"officer_evidence_ids": []}, {"officer_has_active_claim": False}, {"state": al.State.RECEIVED},
                  {"rule_version": ""}):
        with pytest.raises(al.TriageError):
            al.promote_to_incident(**{**base, **patch})
    linked = al.promote_to_incident(**{**base, "existing_incident_for_cluster": "INC-1"})
    assert linked == {"link_existing": "INC-1", "create": False}


def test_reporter_status_hides_driver_info():
    for s in al.State:
        label = al.reporter_status(s)
        assert "plate" not in label.lower() and "driver" not in label.lower()


def test_ac59_receipt_roundtrip_and_failure_modes():
    r = al.new_receipt()
    assert r.receipt_id.startswith("R-") and len(r.secret) >= 32
    assert al.verify_receipt(r.secret, r.salt, r.verifier)
    assert not al.verify_receipt("wrong", r.salt, r.verifier)
    assert not al.verify_receipt(r.secret, None, None)  # unknown receipt: same boolean as wrong secret
    assert not al.verify_receipt(None, r.salt, r.verifier)
    assert r.secret not in r.verifier and r.secret not in r.salt


def test_receipts_are_unique():
    assert len({al.new_receipt().secret for _ in range(20)}) == 20


def test_community_code_rotation_and_estate_binding():
    key = b"k" * 32
    code = al.community_code(key, "E1", 100)
    assert al.check_community_code(key, "E1", code, 100)
    assert al.check_community_code(key, "E1", code, 101)  # previous epoch tolerated
    assert not al.check_community_code(key, "E1", code, 102)
    assert not al.check_community_code(key, "E2", code, 100)
    assert not al.check_community_code(key, "E1", "", 100)


def test_ac57_anonymous_record_must_have_no_correlators():
    al.assert_anonymous_clean({"narrative": "blocked gate", "reporter_user": None})
    for f in al.ANON_FORBIDDEN_FIELDS + al.ANON_GUEST_ONLY_FIELDS:
        with pytest.raises(al.TriageError):
            al.assert_anonymous_clean({f: "x"})
    al.assert_anonymous_clean({"owner": "Guest", "modified_by": "Guest"})


# ---- audit chain (AC-17, AC-52) --------------------------------------------------------------

def _chain(n=4):
    ch: list = []
    for i in range(n):
        auditchain.append(ch, actor=f"u{i}", role="security_officer", action="lookup", entity="Vehicle", entity_id=f"V{i}",
                          at_utc="2026-10-19T10:00:00Z", request_id=f"r{i}", detail={"i": i})
    return ch


def test_audit_chain_verifies_and_detects_tampering():
    ch = _chain()
    assert auditchain.verify(ch) == (True, None)
    tampered = list(ch)
    tampered[1] = replace(tampered[1], actor="mallory")
    assert auditchain.verify(tampered) == (False, 2)
    assert auditchain.verify(ch[:1] + ch[2:])[0] is False  # deletion
    assert auditchain.verify([ch[1], ch[0]] + ch[2:])[0] is False  # reorder
    assert auditchain.verify(ch[:-1]) == (True, None)  # truncation of tail is only detectable against an anchor


# ---- geo -------------------------------------------------------------------------------------

SQUARE = [(5.60, -0.19), (5.60, -0.18), (5.61, -0.18), (5.61, -0.19)]  # synthetic coordinates


def test_accuracy_tiers():
    assert geo.accuracy_tier(10) == "high" and geo.accuracy_tier(25) == "high"
    assert geo.accuracy_tier(26) == "approximate" and geo.accuracy_tier(75) == "approximate"
    assert geo.accuracy_tier(76).startswith("low") and geo.accuracy_tier(None) == "unknown"


def test_geofence():
    assert geo.geofence_status((5.605, -0.185), SQUARE) == "inside"
    assert geo.geofence_status((5.612, -0.185), SQUARE) == "outside"
    assert geo.geofence_status((6.5, 0.5), SQUARE) == "far"
    assert not geo.valid_coordinate(0, 0) and not geo.valid_coordinate(91, 0)


def test_blur_and_small_cell_suppression():
    a, b = geo.blur_point((5.60512, -0.18512)), geo.blur_point((5.60531, -0.18533))
    assert a == b  # nearby points share a cell
    counts = geo.zone_counts_with_threshold(["Z1"] * 6 + ["Z2"] * 2, k=5)
    assert counts == {"Z1": 6, "Z2": None}
