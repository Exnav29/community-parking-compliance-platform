# SPDX-License-Identifier: Apache-2.0
"""Protected registry lookups for security operations (PRD 28, 30.2, 40, AC-03, AC-36, AC-37).

Projections are deliberately minimal: no names, phone numbers or history. Every lookup (allowed
or denied) writes a Sensitive Record Access Event.
"""
from datetime import timedelta

import frappe
from frappe.utils import getdate, nowdate

from frappe_cpcp.core.plates import normalize_plate
from frappe_cpcp.permissions import authorize, get_actor
from frappe_cpcp.services.audit import log_sensitive_access
from frappe_cpcp.services.common import from_db, iso, to_db, unit_by_label, utcnow


def _guarded(capability: str, estate: str, record_type: str, context: str, search_term: str | None = None):
    try:
        actor = authorize(capability, "R", estate=estate)
    except frappe.PermissionError:
        try:
            who = get_actor()
            role = who.role.value
        except Exception:
            role = "unknown"
        log_sensitive_access(record_type=record_type, estate=estate or "", context=context, result="Denied",
                             search_term=search_term, role=role)
        raise
    return actor


@frappe.whitelist()
def lookup_plate(estate: str, plate: str) -> dict:
    """Who is this vehicle? Active visitor session first, then current resident registration."""
    actor = _guarded("resident_registry", estate, "Vehicle", "plate lookup", plate)
    log_sensitive_access(record_type="Vehicle", estate=estate, context="plate lookup", search_term=plate, role=actor.role.value)
    try:
        norm = normalize_plate(plate)
    except ValueError:
        frappe.throw("Plate is not valid", frappe.ValidationError)

    visit = frappe.get_all(
        "CPCP Visitor Session",
        filters={"estate": estate, "plate_normalized": norm, "status": ["in", ["Checked In", "Exit Unconfirmed", "Needs Supervisor Review"]]},
        fields=["name", "host_unit_label", "category", "entry_at"], limit=2)
    if len(visit) > 1:
        return {"match": "ambiguous", "candidates": len(visit), "note": "Multiple active visits; resolve explicitly."}
    if visit:
        v = visit[0]
        return {"match": "active_visitor", "session": v.name, "host_unit": v.host_unit_label, "category": v.category,
                "entry_at": iso(v.entry_at), "contact_action": True}

    today = getdate(nowdate())
    rows = frappe.db.sql(
        """select veh.name, veh.plate, veh.make, veh.color, u.unit_label, a.valid_from, a.valid_to
           from `tabCPCP Vehicle` veh
           join `tabCPCP Vehicle Unit Association` a on a.vehicle = veh.name
           join `tabCPCP Unit` u on u.name = a.unit
           where veh.plate_normalized = %(p)s and veh.status = 'Active' and a.status = 'Active'
             and a.verification_status = 'Verified' and u.estate = %(e)s
             and (a.valid_from is null or a.valid_from <= %(t)s) and (a.valid_to is null or a.valid_to >= %(t)s)""",
        {"p": norm, "e": estate, "t": today}, as_dict=True)
    if len(rows) > 1:
        return {"match": "ambiguous", "candidates": len(rows), "note": "Conflicting registrations; supervisor review required."}
    if rows:
        r = rows[0]
        return {"match": "resident_vehicle", "vehicle": {"plate": r.plate, "make": r.make, "color": r.color},
                "unit": r.unit_label, "contact_action": True}
    return {"match": "none"}


@frappe.whitelist()
def lookup_visits_for_unit(estate: str, unit_label: str, limit: int = 10) -> dict:
    """Unit-first gate entry: resident vehicles plus MINIMAL prior-visit candidates for this unit only."""
    actor = _guarded("visitor_log", estate, "Visitor Suggestion", "unit-first lookup")
    unit = unit_by_label(estate, unit_label)
    log_sensitive_access(record_type="Visitor Suggestion", estate=estate, record_id=unit, context="unit-first lookup",
                         role=actor.role.value)
    today = getdate(nowdate())
    resident = frappe.db.sql(
        """select veh.plate, veh.make, veh.color from `tabCPCP Vehicle` veh
           join `tabCPCP Vehicle Unit Association` a on a.vehicle = veh.name
           where a.unit = %(u)s and veh.status = 'Active' and a.status = 'Active' and a.verification_status = 'Verified'
             and (a.valid_from is null or a.valid_from <= %(t)s) and (a.valid_to is null or a.valid_to >= %(t)s)""",
        {"u": unit, "t": today}, as_dict=True)
    days = int(frappe.db.get_single_value("CPCP Settings", "visitor_suggestion_retention_days") or 180)
    cutoff = to_db(utcnow()).replace(microsecond=0) - timedelta(days=days)
    prior = frappe.db.sql(
        """select plate_snapshot as plate, max(entry_at) as last_visit,
                  max(case when status in ('Checked In','Exit Unconfirmed','Needs Supervisor Review') then name end) as active_session
           from `tabCPCP Visitor Session`
           where host_unit = %(u)s and estate = %(e)s and plate_normalized is not null and plate_normalized != ''
             and status != 'Cancelled/Voided' and entry_at >= %(c)s
           group by plate_normalized, plate_snapshot order by max(entry_at) desc limit %(l)s""",
        {"u": unit, "e": estate, "c": cutoff, "l": int(limit)}, as_dict=True)
    return {
        "unit": unit_label.strip().upper(),
        "candidates": [{"kind": "Resident Vehicle", "plate": r.plate, "make": r.make, "color": r.color} for r in resident]
        + [{"kind": "Previously Visited", "plate": p.plate, "hint": "Visited before",
            "last_visit_date": str(from_db(p.last_visit).date()), "active_session": p.active_session} for p in prior],
        "note": "Suggestions are not authorization. Confirm the vehicle present and that it is visiting this unit today.",
    }
