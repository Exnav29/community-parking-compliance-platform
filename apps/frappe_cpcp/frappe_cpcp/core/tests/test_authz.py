# SPDX-License-Identifier: Apache-2.0
from datetime import datetime, timedelta, timezone
from itertools import product

from frappe_cpcp.core.authz import (
    CAPABILITY_CLASS, MATRIX, Actor, DataClass, Grant, Resource, Role, decide, navigation_manifest,
)

NOW = datetime(2026, 10, 19, 12, tzinfo=timezone.utc)
RES = Resource(org_id="orgA", estate_id="E1", unit_id="A1", owner_user="u-self")


def actor(role, **kw):
    base = dict(user="u1", org_id="orgA", role=role, estate_ids=frozenset({"E1"}), unit_ids=frozenset({"A1"}))
    base.update(kw)
    return Actor(**base)


def can(a, cap, letter="R", res=RES):
    return decide(a, cap, letter, res, NOW).allow


def test_default_deny_unknown_capability_and_letter():
    assert not can(actor(Role.ORG_ADMIN), "nope")
    assert not can(actor(Role.ORG_ADMIN), "estate_units", "Z")


def test_platform_admin_never_has_tenant_access():
    pa = actor(Role.PLATFORM_ADMIN)
    for cap, letter in product(MATRIX, "RCUAV"):
        assert not can(pa, cap, letter)


def test_cross_tenant_always_denied():
    other = Resource(org_id="orgB", estate_id="E1", unit_id="A1")
    for role in Role:
        for cap, letter in product(MATRIX, "RCUAV"):
            assert not can(actor(role), cap, letter, other), (role, cap, letter)


def test_resident_has_no_registry_or_visitor_log_even_for_own_unit():
    for cap in ("resident_registry", "visitor_log"):
        for letter in "RCU":
            assert not can(actor(Role.RESIDENT), cap, letter, Resource("orgA", "E1", "A1", owner_user="u1"))
    assert CAPABILITY_CLASS["visitor_log"] is DataClass.SENSITIVE_VISITOR_LOG


def test_resident_self_service_only():
    mine = Resource("orgA", "E1", "A1", owner_user="u1")
    theirs = Resource("orgA", "E1", "B2", owner_user="someone-else")
    r = actor(Role.RESIDENT)
    assert can(r, "own_vehicle_request", "C", mine)
    assert not can(r, "own_vehicle_request", "R", theirs)
    assert can(r, "submit_report", "C")
    assert not can(r, "verify_incident", "C")
    assert not can(r, "approve_enforcement", "A")


def test_auditor_is_read_only_everywhere_even_with_grant():
    g = Grant("resident_registry", NOW + timedelta(hours=1), "approver", "audit")
    a = actor(Role.AUDITOR, grants=(g,))
    for cap, letter in product(MATRIX, "CUA"):
        assert not can(a, cap, letter), (cap, letter)
    assert can(a, "resident_registry", "R")  # granted read
    assert not can(actor(Role.AUDITOR), "resident_registry", "R")  # no grant -> no read


def test_grants_expire_and_need_independent_approver():
    expired = Grant("visitor_log", NOW - timedelta(seconds=1), "approver", "x")
    self_approved = Grant("visitor_log", NOW + timedelta(hours=1), "u1", "x")
    assert not can(actor(Role.AUDITOR, grants=(expired,)), "visitor_log")
    assert not can(actor(Role.AUDITOR, grants=(self_approved,)), "visitor_log")


def test_raw_export_needs_grant_for_everyone():
    for role in Role:
        assert not can(actor(role), "raw_export")
    g = Grant("raw_export", NOW + timedelta(hours=1), "approver", "case-1")
    assert can(actor(Role.ORG_ADMIN, grants=(g,)), "raw_export")
    assert not can(actor(Role.SECURITY_OFFICER, grants=(g,)), "raw_export")


def test_officer_cannot_change_fees_or_approve_enforcement():
    o = actor(Role.SECURITY_OFFICER)
    assert not can(o, "change_policy", "U")
    assert not can(o, "approve_enforcement", "A")
    assert not can(o, "resident_registry", "R")  # PRD v1.8: no standing registry access for officers
    assert not can(o, "visitor_log", "R")
    assert can(o, "gate_operations", "C")  # gate work goes through purpose-checked APIs


def test_officer_estate_scope():
    o = actor(Role.SECURITY_OFFICER)
    assert can(o, "gate_operations", "R", Resource("orgA", "E1"))
    assert not can(o, "gate_operations", "R", Resource("orgA", "E2"))


def test_security_manager_cannot_edit_fees():
    m = actor(Role.SECURITY_MANAGER)
    assert not can(m, "change_policy", "U") and not can(m, "change_policy", "A")
    assert can(m, "approve_enforcement", "A")


def test_finance_separation():
    f = actor(Role.FINANCE)
    assert not can(f, "visitor_log") and not can(f, "resident_registry")
    assert not can(f, "verify_incident", "C") and not can(f, "approve_enforcement", "A")
    assert can(f, "receipts_refunds", "U")


def test_expired_or_suspended_denied():
    assert not can(actor(Role.ORG_ADMIN, active=False), "estate_units")
    assert not can(actor(Role.ORG_ADMIN, expires_at=NOW), "estate_units")
    assert can(actor(Role.ORG_ADMIN, expires_at=NOW + timedelta(days=1)), "estate_units")


def test_audit_immutable_for_all_roles():
    for role in Role:
        for letter in "RCUAV":
            assert not can(actor(role), "audit_mutation", letter)


def test_estate_manager_limited_to_appointed_estates():
    m = actor(Role.ESTATE_MANAGER)
    assert can(m, "estate_units", "U", Resource("orgA", "E1"))
    assert not can(m, "estate_units", "U", Resource("orgA", "E2"))


def test_org_admin_with_no_estate_list_is_org_wide_but_not_cross_tenant():
    a = actor(Role.ORG_ADMIN, estate_ids=frozenset())
    assert can(a, "estate_units", "U", Resource("orgA", "E9"))


def test_non_org_wide_role_without_estates_has_no_scope():
    assert not can(actor(Role.SECURITY_OFFICER, estate_ids=frozenset()), "visitor_log")


def test_tow_provider_only_assigned_jobs():
    t = actor(Role.TOW_PROVIDER, user="tow1")
    assert not can(t, "resident_registry") and not can(t, "visitor_log") and not can(t, "gate_operations")
    assert can(t, "execute_enforcement", "U", Resource("orgA", "E1", assigned_to="tow1"))
    assert not can(t, "execute_enforcement", "U", Resource("orgA", "E1", assigned_to="other"))


def test_navigation_manifest_hides_registry_from_residents():
    nav = navigation_manifest(Role.RESIDENT)
    assert "resident_registry" not in nav and "visitor_log" not in nav
    assert "submit_report" in nav
    assert "audit_mutation" not in navigation_manifest(Role.ORG_ADMIN)


def test_aggregate_view_for_resident_and_board_observer():
    assert can(actor(Role.RESIDENT), "aggregate_dashboards", "V")
    assert can(actor(Role.BOARD_OBSERVER), "aggregate_dashboards", "V")
    assert not can(actor(Role.BOARD_OBSERVER), "incident_reports", "R")


def test_officer_can_see_and_claim_unclaimed_triage_in_own_estate_only():
    o = actor(Role.SECURITY_OFFICER)
    unclaimed = Resource("orgA", "E1")
    assert can(o, "triage_reports", "R", unclaimed) and can(o, "triage_reports", "U", unclaimed)
    assert not can(o, "triage_reports", "R", Resource("orgA", "E2"))
    assert not can(o, "triage_reports", "U", Resource("orgA", "E1", assigned_to="other-officer"))
    # the same latitude is NOT given for enforcement execution
    assert not can(o, "execute_enforcement", "U", Resource("orgA", "E1"))


def test_v18_no_officer_standing_access_to_sensitive_classes():
    o = actor(Role.SECURITY_OFFICER)
    for cap in ("resident_registry", "visitor_log", "access_review", "device_revocation"):
        for letter in "RCUA":
            assert not can(o, cap, letter), (cap, letter)
    assert not can(actor(Role.SECURITY_OFFICER), "access_review", "R")
    assert can(actor(Role.AUDITOR), "access_review", "R") and not can(actor(Role.AUDITOR), "access_review", "U")
    assert can(actor(Role.SECURITY_OFFICER), "emergency_access", "C") and not can(actor(Role.SECURITY_OFFICER), "emergency_access", "A")
