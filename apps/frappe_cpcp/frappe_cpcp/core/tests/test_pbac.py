# SPDX-License-Identifier: Apache-2.0
from datetime import datetime, timedelta, timezone

from frappe_cpcp.core import pbac
from frappe_cpcp.core.pbac import Case, Code, Grant, Shift

NOW = datetime(2026, 10, 19, 12, tzinfo=timezone.utc)
SHIFT = Shift("o1", "E1", "G1", on_duty=True)
CASE = Case("INC-1", "E1", "o1", open=True, plate="AB12", unit="A1")


def gate(**kw):
    base = dict(role="security_officer", user="o1", estate="E1", shift=SHIFT, now=NOW)
    base.update(kw)
    return pbac.decide_gate(**base)


def case(**kw):
    base = dict(role="security_officer", user="o1", estate="E1", case=CASE, shift=SHIFT, now=NOW)
    base.update(kw)
    return pbac.decide_case(**base)


def test_gate_requires_live_shift_in_the_same_estate():
    assert gate().allow and gate().disclosure == pbac.Disclosure.GATE_MINIMUM
    assert gate(shift=None).code == Code.NO_SHIFT
    assert gate(shift=Shift("o1", "E1", "G1", on_duty=False)).code == Code.NO_SHIFT
    assert gate(shift=Shift("someone-else", "E1", "G1", True)).code == Code.NO_SHIFT  # a shift belongs to one person
    assert gate(estate="E2").code == Code.SHIFT_OTHER_ESTATE
    assert gate(shift=Shift("o1", "E1", "G1", True, ends_at=NOW)).code == Code.NO_SHIFT  # expired on the server clock
    assert gate(shift=Shift("o1", "E1", "G1", True, device_active=False)).code == Code.DEVICE_REVOKED


def test_forged_gate_never_widens_access():
    assert gate(client_gate="G1").allow
    assert gate(client_gate="G2").code == Code.GATE_MISMATCH


def test_other_roles_have_no_gate_purpose():
    for role in ("resident", "auditor", "finance", "tow_provider"):
        assert gate(role=role).code == Code.NO_ROLE_SCOPE
    assert gate(role="security_manager", shift=None).allow  # supervisors are estate-scoped and reviewed, not shift-gated


def test_case_purpose_needs_assignment_and_matching_target():
    assert case().allow and case().disclosure == pbac.Disclosure.CASE_CONTACT
    assert case(target_plate="AB12").allow and case(target_unit="A1").allow
    assert case(target_plate="ZZ99").code == Code.TARGET_MISMATCH  # PBAC-08: a claim cannot look up another plate
    assert case(target_unit="B2").code == Code.TARGET_MISMATCH     # ...or another unit
    assert case(case=Case("INC-1", "E1", "o2", True, "AB12", "A1")).code == Code.NOT_ASSIGNED
    assert case(case=Case("INC-1", "E1", "o1", False, "AB12", "A1")).code == Code.NO_CASE  # closed -> access ends (PBAC-09)
    assert case(case=None).code == Code.NO_CASE
    assert case(case=Case("INC-1", "E2", "o1", True, "AB12", "A1")).code == Code.CASE_OTHER_ESTATE
    assert case(shift=None).code == Code.NO_SHIFT


def test_supervisor_case_access_is_estate_scoped_but_target_bound():
    assert case(role="security_manager", user="m1", shift=None).allow
    assert case(role="security_manager", user="m1", shift=None, target_plate="ZZ99").code == Code.TARGET_MISMATCH
    assert case(role="security_manager", user="m1", shift=None, estate="E2").code == Code.CASE_OTHER_ESTATE


def test_emergency_grant_is_scoped_and_expires():
    g = Grant("o1", "E1", "A1", NOW + timedelta(minutes=30))
    assert pbac.decide_emergency(user="o1", estate="E1", target_unit="A1", grant=g, now=NOW).allow
    assert pbac.decide_emergency(user="o1", estate="E1", target_unit="B2", grant=g, now=NOW).code == Code.GRANT_SCOPE
    assert pbac.decide_emergency(user="o1", estate="E2", target_unit="A1", grant=g, now=NOW).code == Code.GRANT_SCOPE
    assert pbac.decide_emergency(user="o2", estate="E1", target_unit="A1", grant=g, now=NOW).code == Code.NO_GRANT
    assert pbac.decide_emergency(user="o1", estate="E1", target_unit="A1", grant=g, now=NOW + timedelta(minutes=30)).code == Code.NO_GRANT
    assert pbac.decide_emergency(user="o1", estate="E1", target_unit="A1", grant=None, now=NOW).code == Code.NO_GRANT


def test_disclosure_allow_lists_exclude_identity_at_the_gate():
    gate_fields = set(pbac.FIELDS[pbac.Disclosure.GATE_MINIMUM])
    assert not (gate_fields & pbac.GATE_FORBIDDEN_KEYS)
    assert "number" not in pbac.FIELDS[pbac.Disclosure.CASE_CONTACT]  # raw numbers only via the call action
    assert pbac.over_limit(5, 5) and not pbac.over_limit(4, 5)
