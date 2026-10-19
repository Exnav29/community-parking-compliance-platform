# SPDX-License-Identifier: Apache-2.0
"""Frappe adapter for the central authorization service (``core.authz``).

* ``get_actor`` builds the actor ONLY from server-side Role Assignment records for the
  authenticated session user. Client-supplied tenant/unit/estate identifiers never grant rights.
* ``has_permission`` / ``query_conditions`` are the document- and list-level hooks.
* ``authorize`` is what every whitelisted API calls first.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import frappe
from frappe.utils import get_datetime, getdate, nowdate

from frappe_cpcp.core.authz import MATRIX, Actor, Grant, Resource, Role, decide

_META = json.loads((Path(__file__).parent / "cpcp" / "doctype_meta.json").read_text(encoding="utf-8"))

DOCTYPE_CAPABILITY = {
    "CPCP Estate": "estate_units", "CPCP Gate": "estate_units", "CPCP Zone": "estate_units", "CPCP Unit": "estate_units",
    "CPCP Person": "resident_registry", "CPCP Unit Membership": "resident_registry", "CPCP Vehicle": "resident_registry",
    "CPCP Vehicle Unit Association": "resident_registry",
    "CPCP Visitor Session": "visitor_log", "CPCP Visit Event": "visitor_log",
    "CPCP Parking Allegation": "triage_reports", "CPCP Security Work Item": "triage_reports",
    "CPCP Allegation Review Event": "triage_reports", "CPCP Notification Outbox": "triage_reports",
    "CPCP Violation Incident": "incident_reports", "CPCP Officer Evidence": "capture_evidence",
    "CPCP Audit Event": "audit_history", "CPCP Sensitive Access Event": "audit_history",
    "CPCP Policy Version": "change_policy", "CPCP Role Assignment": "manage_users", "CPCP Access Grant": "manage_users",
}
# Doctypes that hold an `estate` link and can be filtered directly in SQL.
ESTATE_FIELD = {
    "CPCP Estate": "name", "CPCP Gate": "estate", "CPCP Zone": "estate", "CPCP Unit": "estate",
    "CPCP Visitor Session": "estate", "CPCP Parking Allegation": "estate", "CPCP Security Work Item": "estate",
    "CPCP Violation Incident": "estate", "CPCP Policy Version": "estate", "CPCP Role Assignment": "estate",
}
PTYPE_LETTER = {"read": "R", "select": "R", "report": "R", "print": "R", "write": "U", "create": "C",
                "submit": "A", "cancel": "A"}
# delete, export, email, share and import are never granted through DocPerm hooks.


class RoleContextRequired(frappe.ValidationError):
    pass


def org_id() -> str:
    value = frappe.db.get_single_value("CPCP Settings", "org_id")
    if not value:
        frappe.throw("Organization is not configured (CPCP Settings.org_id)", frappe.ValidationError)
    return value


def _utc(dt) -> datetime:
    d = get_datetime(dt)
    return d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d.astimezone(timezone.utc)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _valid_assignments(user: str) -> list[dict]:
    today = getdate(nowdate())
    rows = frappe.get_all(  # keyed by the SERVER-determined session user; not a client-controlled filter
        "CPCP Role Assignment",
        filters={"user": user, "status": "Active"},
        fields=["name", "cpcp_role", "estate", "unit", "valid_from", "valid_until"],
    )
    return [r for r in rows if (not r.valid_from or getdate(r.valid_from) <= today)
            and (not r.valid_until or getdate(r.valid_until) >= today)]


def _grants(user: str) -> tuple[Grant, ...]:
    rows = frappe.get_all("CPCP Access Grant", filters={"grantee": user, "status": "Approved"},
                          fields=["capability", "expires_at", "approved_by", "purpose"])
    return tuple(Grant(r.capability, _utc(r.expires_at), r.approved_by or "", r.purpose or "") for r in rows)


def get_actor(user: str | None = None, role_context: str | None = None) -> Actor:
    """Resolve the acting identity. Raises PermissionError when the user holds no valid assignment."""
    user = user or frappe.session.user
    if user == "Guest":
        raise frappe.PermissionError("authentication required")
    rows = _valid_assignments(user)
    if not rows:
        # Administrator / System Manager are platform-operator identities, not tenant actors.
        raise frappe.PermissionError("no active role assignment")
    roles = sorted({r.cpcp_role for r in rows})
    if role_context is None:
        role_context = frappe.form_dict.get("role_context") if getattr(frappe, "form_dict", None) else None
    if len(roles) > 1 and not role_context:
        raise RoleContextRequired("multiple roles held; an explicit role_context is required")
    chosen = role_context or roles[0]
    if chosen not in roles:  # selects among genuinely held assignments, can never add one
        raise frappe.PermissionError("role context not held")
    mine = [r for r in rows if r.cpcp_role == chosen]
    estates = frozenset(r.estate for r in mine if r.estate)
    if any(not r.estate for r in mine) and chosen == "org_admin":
        estates = frozenset()  # org-wide administrator
    units = frozenset(r.unit for r in mine if r.unit)
    return Actor(user=user, org_id=org_id(), role=Role(chosen), estate_ids=estates, unit_ids=units,
                 grants=_grants(user))


def authorize(capability: str, letter: str, *, estate: str | None = None, unit: str | None = None,
              owner_user: str | None = None, assigned_to: str | None = None, actor: Actor | None = None) -> Actor:
    """Raise PermissionError (403) unless allowed. Denials by an authenticated actor are audited."""
    actor = actor or get_actor()
    res = Resource(org_id=org_id(), estate_id=estate, unit_id=unit, owner_user=owner_user, assigned_to=assigned_to)
    decision = decide(actor, capability, letter, res, now_utc())
    if not decision.allow:
        from frappe_cpcp.services.audit import log_audit  # local import to avoid cycles
        log_audit(action="forbidden", entity=capability, entity_id=letter, reason=decision.reason, actor=actor.user,
                  role=actor.role.value)
        raise frappe.PermissionError("not permitted")  # no reason leaked to the caller
    return actor


def _resource_for(doc, capability: str) -> Resource:
    estate = doc.get("estate") if doc.meta.has_field("estate") else None
    if doc.doctype == "CPCP Estate":
        estate = doc.name
    unit = doc.get("host_unit") or doc.get("unit") or doc.get("reporter_unit")
    owner = doc.get("reporter_user") or doc.get("user") or doc.get("requested_by")
    assigned = doc.get("claimed_by") or doc.get("verified_by")
    if doc.doctype == "CPCP Parking Allegation" and doc.get("name"):
        assigned = frappe.db.get_value("CPCP Security Work Item", {"allegation": doc.name}, "claimed_by") or None
    return Resource(org_id=org_id(), estate_id=estate, unit_id=unit, owner_user=owner, assigned_to=assigned)


def has_permission(doc, ptype=None, user=None, **_kw):
    """Document-level hook. Returns False (never None) so a missing decision cannot fall through."""
    user = user or frappe.session.user
    capability = DOCTYPE_CAPABILITY.get(doc.doctype)
    letter = PTYPE_LETTER.get(ptype or "read")
    if capability is None or letter is None:
        return False
    try:
        actor = get_actor(user)
    except (frappe.PermissionError, RoleContextRequired):
        # System Manager / Administrator keep Desk access to non-sensitive setup doctypes only.
        return bool(user != "Guest" and _META.get(doc.doctype, {}).get("sensitivity") == "STAFF_OPERATIONAL"
                    and capability in ("manage_users", "change_policy") and "System Manager" in frappe.get_roles(user))
    return decide(actor, capability, letter, _resource_for(doc, capability), now_utc()).allow


def query_conditions(user=None, doctype=None) -> str:
    """List-level hook: SQL restricting rows to the actor's estates; '1=0' when ambiguous or denied."""
    user = user or frappe.session.user
    doctype = doctype or frappe.form_dict.get("doctype")
    capability = DOCTYPE_CAPABILITY.get(doctype)
    if capability is None:
        return "1=0"
    try:
        actor = get_actor(user)
    except (frappe.PermissionError, RoleContextRequired):
        return "1=0"
    effective = Role.ORG_ADMIN if actor.role == Role.ESTATE_MANAGER else actor.role
    letters = MATRIX[capability].get(effective, "")
    if actor.role == Role.RESIDENT or not letters or actor.role == Role.PLATFORM_ADMIN:
        return "1=0"
    if letters == "G" or (actor.role == Role.AUDITOR and "G" in letters):
        # Exceptional access: the list opens only while an approved, unexpired grant exists.
        now = now_utc()
        if any(g.capability == capability and g.expires_at > now and g.approved_by != actor.user for g in actor.grants):
            return _estate_sql(actor, doctype)
        return "1=0"
    return _estate_sql(actor, doctype)


def _estate_sql(actor: Actor, doctype: str) -> str:
    field = ESTATE_FIELD.get(doctype)
    if not actor.estate_ids:
        return "" if actor.role == Role.ORG_ADMIN else "1=0"
    quoted = ", ".join(frappe.db.escape(e) for e in sorted(actor.estate_ids))
    if field:
        return f"`tab{doctype}`.`{field}` in ({quoted})"
    if doctype == "CPCP Vehicle":
        return ("`tabCPCP Vehicle`.name in (select a.vehicle from `tabCPCP Vehicle Unit Association` a "
                f"join `tabCPCP Unit` u on u.name = a.unit where u.estate in ({quoted}))")
    if doctype == "CPCP Vehicle Unit Association":
        return f"`tabCPCP Vehicle Unit Association`.unit in (select name from `tabCPCP Unit` where estate in ({quoted}))"
    if doctype == "CPCP Unit Membership":
        return f"`tabCPCP Unit Membership`.unit in (select name from `tabCPCP Unit` where estate in ({quoted}))"
    if doctype == "CPCP Person":
        return ("`tabCPCP Person`.name in (select m.person from `tabCPCP Unit Membership` m join `tabCPCP Unit` u "
                f"on u.name = m.unit where u.estate in ({quoted}))")
    if doctype == "CPCP Visit Event":
        return f"`tabCPCP Visit Event`.session in (select name from `tabCPCP Visitor Session` where estate in ({quoted}))"
    if doctype in ("CPCP Allegation Review Event", "CPCP Officer Evidence"):
        col = "allegation"
        return f"`tab{doctype}`.{col} in (select name from `tabCPCP Parking Allegation` where estate in ({quoted}))"
    if doctype == "CPCP Sensitive Access Event":
        return f"`tabCPCP Sensitive Access Event`.estate in ({quoted})"
    return "" if actor.role == Role.ORG_ADMIN else "1=0"
