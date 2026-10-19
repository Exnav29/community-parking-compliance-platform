# SPDX-License-Identifier: Apache-2.0
"""Purpose-checked lookups for security operations (PRD 61; AC-03; PBAC-01..08, PBAC-10).

There is NO household directory here. Each call needs a server-verified purpose:
  * gate:  the officer has a live shift at this estate (and the gate they claim is the gate they are on);
  * case:  a violation assigned to the officer, and the target plate/unit must be that case's own.
Responses are built from allow-lists: plate, vehicle description, unit label and eligibility. Never names, numbers or histories.
Every outcome (allowed, denied, no match) is journaled durably BEFORE data is returned; if the journal is down the call fails.
"""
from datetime import timedelta

import frappe
from frappe.utils import getdate, nowdate

from frappe_cpcp.core.plates import normalize_plate
from frappe_cpcp.permissions import authorize
from frappe_cpcp.services import pbac as svc
from frappe_cpcp.services.common import deadlock_retry, iso, to_db, utcnow

ACTIVE = ["Checked In", "Exit Unconfirmed", "Needs Supervisor Review"]
MAX_SUGGESTIONS = 3
PLATE_LOOKUPS_PER_HOUR = 60


def _limit(field: str, default: int) -> int:
    return int(frappe.db.get_single_value("CPCP Settings", field, cache=False) or default)


def _lookup_core(estate: str, norm: str) -> tuple[dict, str]:
    """Operational minimum for one plate. Returns (payload, unit_label)."""
    visit = frappe.get_all("CPCP Visitor Session", filters={"estate": estate, "plate_normalized": norm, "status": ["in", ACTIVE]},
                           fields=["name", "host_unit_label", "category", "entry_at"], limit=2)
    if len(visit) > 1:
        return {"match": "ambiguous", "note": "Multiple active visits; ask a supervisor."}, ""
    if visit:
        v = visit[0]
        return {"match": "active_visitor", "unit": v.host_unit_label, "kind": "Visitor inside", "category": v.category,
                "entry_at": iso(v.entry_at), "eligible": True}, v.host_unit_label
    today = getdate(nowdate())
    rows = frappe.db.sql(
        """select veh.plate, veh.make, veh.color, u.unit_label
           from `tabCPCP Vehicle` veh
           join `tabCPCP Vehicle Unit Association` a on a.vehicle = veh.name
           join `tabCPCP Unit` u on u.name = a.unit
           where veh.plate_normalized = %(p)s and veh.status = 'Active' and a.status = 'Active'
             and a.verification_status = 'Verified' and u.estate = %(e)s
             and (a.valid_from is null or a.valid_from <= %(t)s) and (a.valid_to is null or a.valid_to >= %(t)s)""",
        {"p": norm, "e": estate, "t": today}, as_dict=True)
    if len(rows) > 1:
        return {"match": "ambiguous", "note": "Conflicting registrations; supervisor review required."}, ""
    if rows:
        r = rows[0]
        return {"match": "resident_vehicle", "plate": r.plate, "make": r.make, "color": r.color, "unit": r.unit_label,
                "kind": "Resident vehicle", "eligible": True}, r.unit_label
    return {"match": "none"}, ""


@frappe.whitelist()
def lookup_plate(estate: str, plate: str, purpose: str = "gate", reference: str | None = None, gate: str | None = None) -> dict:
    """Who is this vehicle? ``purpose`` is a request to be validated, never a grant: gate -> live shift; case -> assigned violation."""
    actor = authorize("gate_operations", "R", estate=estate)
    try:
        norm = normalize_plate(plate)
    except ValueError:
        frappe.throw("Plate is not valid", frappe.ValidationError)
    if purpose == "gate":
        ctx = svc.gate_access(actor, estate, action="search", record_type="Vehicle", client_gate=gate, term=norm,
                              rate_actions=("search",), rate_limit=_limit("plate_lookups_per_hour", PLATE_LOOKUPS_PER_HOUR))
    elif purpose == "case":
        ctx = svc.case_access(actor, reference or "", action="search", record_type="Vehicle", category="operational_min", target_plate=norm, estate_hint=estate)
        ctx.term = norm
    else:  # an invented purpose is a denial, not a fallback
        svc._deny(actor, estate, action="search", record_type="Vehicle", category="operational_min", purpose=str(purpose)[:30],
                  ref=str(reference or "")[:30], code="unknown_purpose", term=norm)
    out, unit = _lookup_core(estate, norm)
    ctx.target_unit = unit
    if out["match"] == "none":
        ctx.no_match()
    else:
        ctx.allowed(context=out["match"])
    return out


@frappe.whitelist()
@deadlock_retry
def lookup_visits_for_unit(estate: str, unit_label: str, plate_hint: str | None = None, gate: str | None = None) -> dict:
    """Unit-first gate entry. A second discriminator (a few characters of the plate the officer can SEE) narrows the answer to what
    is on the gate in front of them. Without it the answer is capped and rate-limited. Never returns names, numbers, dates or counts."""
    actor = authorize("gate_operations", "R", estate=estate)
    hint = None
    if plate_hint and len(plate_hint.strip()) >= 2:
        try:
            hint = normalize_plate(plate_hint.strip().ljust(2, "0"))
        except ValueError:
            hint = None
    unit_norm = (unit_label or "").strip().upper()
    action = "history" if hint else "history_bare"
    limit = _limit("suggestion_limit_per_hour", 30) if hint else _limit("bare_suggestions_per_hour", 10)  # no plate hint = the shape of a browsing attack: stricter
    ctx = svc.gate_access(actor, estate, action=action, record_type="Visitor Suggestion", category="restricted_safety", target_unit=unit_norm,
                          client_gate=gate, rate_actions=(action,), rate_limit=limit)
    unit = frappe.db.get_value("CPCP Unit", {"estate": estate, "unit_label": unit_norm}, "name")
    if not unit:
        ctx.no_match("unknown unit")
        return {"unit": unit_norm, "candidates": [], "note": "No suggestions."}
    today = getdate(nowdate())
    resident = frappe.db.sql(
        """select veh.plate, veh.make, veh.color from `tabCPCP Vehicle` veh
           join `tabCPCP Vehicle Unit Association` a on a.vehicle = veh.name
           where a.unit = %(u)s and veh.status = 'Active' and a.status = 'Active' and a.verification_status = 'Verified'
             and (a.valid_from is null or a.valid_from <= %(t)s) and (a.valid_to is null or a.valid_to >= %(t)s)""",
        {"u": unit, "t": today}, as_dict=True)
    cutoff = to_db(utcnow()) - timedelta(days=_limit("visitor_suggestion_retention_days", 180))
    prior = frappe.db.sql(
        """select plate_snapshot as plate, plate_normalized as norm,
                  max(case when status in ('Checked In','Exit Unconfirmed','Needs Supervisor Review') then 1 else 0 end) as inside
           from `tabCPCP Visitor Session`
           where host_unit = %(u)s and estate = %(e)s and plate_normalized is not null and plate_normalized != ''
             and status != 'Cancelled/Voided' and entry_at >= %(c)s
           group by plate_normalized, plate_snapshot order by max(entry_at) desc limit 12""",
        {"u": unit, "e": estate, "c": cutoff}, as_dict=True)
    cands = [{"kind": "Resident vehicle", "plate": r.plate, "make": r.make, "color": r.color} for r in resident
             if not hint or normalize_plate(r.plate).find(hint) >= 0]
    cands += [{"kind": "Visited before", "plate": p.plate, "hint": "Visited before", "already_inside": bool(p.inside)} for p in prior
              if not hint or (p.norm or "").find(hint) >= 0]
    cands = cands[:MAX_SUGGESTIONS]
    if cands:
        ctx.allowed(context=f"{len(cands)} candidates, hint={'yes' if hint else 'no'}")
    else:
        ctx.no_match()
    return {"unit": unit_norm, "candidates": cands, "narrowed_by_plate": bool(hint),
            "note": "Suggestions are not authorization. Confirm the vehicle present and that it is visiting this unit today. This lookup is recorded."}
