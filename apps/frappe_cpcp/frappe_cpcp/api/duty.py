# SPDX-License-Identifier: Apache-2.0
"""Gate shifts, device/session revocation and break-glass emergency access (PRD 61.4, 61.6, 61.9)."""
import hashlib
from datetime import timedelta

import frappe
from frappe.utils import cint

from frappe_cpcp.core import pbac
from frappe_cpcp.permissions import authorize, get_actor
from frappe_cpcp.services import access, pbac as svc
from frappe_cpcp.services.audit import log_audit
from frappe_cpcp.services.common import deadlock_retry, iso, require, to_db, utcnow
from frappe_cpcp.services.episodes import _outbox, _recipients, _try_insert


def _device_hash(user: str, device_id: str) -> str:
    return hashlib.sha256(f"{user}|{device_id}".encode()).hexdigest()[:24]  # pseudonymous: the raw device id is never stored


# ------------------------------------------------------------------ shifts ------------------------------------------

@frappe.whitelist(methods=["POST"])
@deadlock_retry
def start_shift(estate: str, gate: str, device_id: str) -> dict:
    """Officers declare duty at one gate on one device. The server decides how long it lasts."""
    actor = authorize("gate_operations", "C", estate=estate)
    require(device_id, "device_id")
    if frappe.db.get_value("CPCP Gate", gate, "estate") != estate or not frappe.db.get_value("CPCP Gate", gate, "active"):
        svc._deny(actor, estate, action="shift", record_type="Gate Shift", category="operational_min", purpose="shift", code="gate_not_in_estate", gate=gate)
    dh = _device_hash(actor.user, device_id)
    if frappe.db.exists("CPCP Device Registration", {"user": actor.user, "device_hash": dh, "status": "Revoked"}):
        svc._deny(actor, estate, action="shift", record_type="Gate Shift", category="operational_min", purpose="shift", code=pbac.Code.DEVICE_REVOKED.value, gate=gate, device=dh)
    key = f"{actor.user}:{dh}"
    if not frappe.db.exists("CPCP Device Registration", {"device_key": key}):
        frappe.get_doc({"doctype": "CPCP Device Registration", "user": actor.user, "device_hash": dh, "status": "Active", "device_key": key}).insert(ignore_permissions=True)
    for old in frappe.db.sql("select name from `tabCPCP Gate Shift` where user=%s and status='On Duty' for update", (actor.user,)):
        frappe.db.set_value("CPCP Gate Shift", old[0], {"status": "Ended", "ended_at": to_db(utcnow()), "ended_reason": "superseded by a new shift", "active_key": None}, update_modified=False)
    doc = frappe.get_doc({"doctype": "CPCP Gate Shift", "user": actor.user, "estate": estate, "gate": gate, "device_hash": dh, "status": "On Duty",
                          "started_at": to_db(utcnow()), "ends_at": svc.shift_expiry(), "active_key": actor.user})
    if not _try_insert(doc):
        frappe.throw("Another shift start is in progress; retry", frappe.DuplicateEntryError)
    access.record(actor=actor.user, role=actor.role.value, estate=estate, action="shift_start", record_type="Gate Shift", record_id=doc.name,
                  category="operational_min", purpose="shift", gate=gate, shift=doc.name, device_hash=dh)
    return {"shift": doc.name, "gate": gate, "ends_at": iso(doc.ends_at)}


@frappe.whitelist(methods=["POST"])
def end_shift() -> dict:
    actor = get_actor()
    cur = svc.current_shift(actor.user)
    if not cur:
        return {"ended": False}
    _s, row = cur
    frappe.db.set_value("CPCP Gate Shift", row.name, {"status": "Ended", "ended_at": to_db(utcnow()), "ended_reason": "ended by officer", "active_key": None}, update_modified=False)
    access.record(actor=actor.user, role=actor.role.value, estate=row.estate, action="shift_end", record_type="Gate Shift", record_id=row.name,
                  category="operational_min", purpose="shift", gate=row.gate, shift=row.name, device_hash=row.device_hash)
    return {"ended": True}


@frappe.whitelist()
def my_shift() -> dict:
    actor = get_actor()
    cur = svc.current_shift(actor.user)
    if not cur:
        return {"on_duty": False}
    s, row = cur
    return {"on_duty": s.device_active, "shift": row.name, "estate": row.estate, "gate": row.gate, "ends_at": iso(row.ends_at)}


# ------------------------------------------------------------------ revocation ---------------------------------------

def _end_all(user: str, reason: str, status: str = "Revoked") -> int:
    n = 0
    for (name,) in frappe.db.sql("select name from `tabCPCP Gate Shift` where user=%s and status='On Duty' for update", (user,)):
        frappe.db.set_value("CPCP Gate Shift", name, {"status": status, "ended_at": to_db(utcnow()), "ended_reason": reason, "active_key": None}, update_modified=False)
        n += 1
    return n


def _scope_check(actor, user: str) -> str:
    """The manager may act only on staff of estates they administer. Returns the staff member's estate."""
    rows = frappe.get_all("CPCP Role Assignment", filters={"user": user, "status": "Active"}, fields=["estate", "cpcp_role"])
    estates = {r.estate for r in rows if r.estate}
    if not rows or (actor.estate_ids and not (estates & set(actor.estate_ids))):
        raise frappe.PermissionError("not permitted")
    return next(iter(estates), "")


@frappe.whitelist(methods=["POST"])
@deadlock_retry
def revoke_device(user: str, reason: str) -> dict:
    """Lost or shared device: ends the person's shifts, revokes the device(s) they are using, and kills their web sessions."""
    actor = get_actor()
    estate = _scope_check(actor, user)
    authorize("device_revocation", "A", estate=estate or None)
    require((reason or "").strip(), "reason")
    devices = [r[0] for r in frappe.db.sql("select distinct device_hash from `tabCPCP Gate Shift` where user=%s and status='On Duty'", (user,))]
    for dh in devices:
        key = f"{user}:{dh}"
        name = frappe.db.get_value("CPCP Device Registration", {"device_key": key})
        if name:
            frappe.db.set_value("CPCP Device Registration", name, {"status": "Revoked", "revoked_by": actor.user, "revoked_at": to_db(utcnow()), "reason": reason}, update_modified=False)
    ended = _end_all(user, f"device revoked: {reason}")
    from frappe.sessions import clear_sessions
    clear_sessions(user, force=True)
    log_audit(action="device_revoked", entity="User", entity_id=user, reason=reason, role=actor.role.value, detail={"shifts_ended": ended, "devices": len(devices)})
    access.record(actor=actor.user, role=actor.role.value, estate=estate, action="revoke", record_type="Device", record_id=user, category="operational_min",
                  purpose="supervisor_review", context="device revoked")
    return {"user": user, "shifts_ended": ended, "devices_revoked": len(devices)}


@frappe.whitelist(methods=["POST"])
@deadlock_retry
def suspend_user(user: str, reason: str) -> dict:
    """Immediate loss of all CPCP access for a person: assignments suspended, shifts ended, sessions cleared."""
    actor = get_actor()
    estate = _scope_check(actor, user)
    authorize("device_revocation", "A", estate=estate or None)
    require((reason or "").strip(), "reason")
    for name in frappe.get_all("CPCP Role Assignment", filters={"user": user, "status": "Active"}, pluck="name"):
        frappe.db.set_value("CPCP Role Assignment", name, "status", "Suspended", update_modified=False)
    ended = _end_all(user, f"user suspended: {reason}")
    from frappe.sessions import clear_sessions
    clear_sessions(user, force=True)
    log_audit(action="user_suspended", entity="User", entity_id=user, reason=reason, role=actor.role.value)
    return {"user": user, "shifts_ended": ended}


# ------------------------------------------------------------------ emergency (break-glass) --------------------------

@frappe.whitelist(methods=["POST"])
@deadlock_retry
def request_emergency(estate: str, unit_label: str, reason: str, incident: str | None = None) -> dict:
    """Immediate, narrow, short and loudly reviewed. One household, contacts only, never a general bypass."""
    actor = authorize("emergency_access", "C", estate=estate)
    reason = (reason or "").strip()
    unit = frappe.db.get_value("CPCP Unit", {"estate": estate, "unit_label": (unit_label or "").strip().upper()}, "name")
    gate_ctx_needed = actor.role.value == "security_officer"
    if gate_ctx_needed:
        svc.gate_access(actor, estate, action="emergency_request", record_type="Emergency Access", category="contact_reveal", purpose=pbac.Purpose.EMERGENCY)
    if len(reason) < 20 or not unit:
        svc._deny(actor, estate, action="emergency_request", record_type="Emergency Access", category="contact_reveal", purpose=pbac.Purpose.EMERGENCY.value,
                  code="reason_too_short_or_unknown_unit", target_unit=unit_label or "")
    today = to_db(utcnow() - timedelta(hours=24))
    if frappe.db.count("CPCP Emergency Access", {"requested_by": actor.user, "creation": [">=", today]}) >= 3:
        svc._deny(actor, estate, action="emergency_request", record_type="Emergency Access", category="contact_reveal", purpose=pbac.Purpose.EMERGENCY.value,
                  code="emergency_limit_reached", target_unit=unit_label)
    mins = min(cint(frappe.db.get_single_value("CPCP Settings", "emergency_max_minutes") or 60), 120)
    now = utcnow()
    doc = frappe.get_doc({"doctype": "CPCP Emergency Access", "requested_by": actor.user, "estate": estate, "unit": unit, "incident": incident, "reason": reason,
                          "granted_at": to_db(now), "expires_at": to_db(now + timedelta(minutes=mins)), "status": "Active"}).insert(ignore_permissions=True)
    label = frappe.db.get_value("CPCP Unit", unit, "unit_label")
    access.record(actor=actor.user, role=actor.role.value, estate=estate, action="emergency_grant", record_type="Emergency Access", record_id=doc.name,
                  target_unit=label, category="contact_reveal", purpose="emergency", purpose_ref=doc.name, result="Emergency", reason_code="break_glass_granted",
                  context="grant issued; independent review required")
    _outbox(doc.name, _recipients(estate, ("security_manager",)) + [(u, "org_admin") for u in frappe.get_all("CPCP Role Assignment", filters={"status": "Active", "cpcp_role": "org_admin"}, pluck="user")],
            "emergency_access", doc.name, {"grant": doc.name, "estate": estate})
    log_audit(action="emergency_access_granted", entity="CPCP Emergency Access", entity_id=doc.name, reason=reason, role=actor.role.value)
    return {"grant": doc.name, "expires_at": iso(doc.expires_at), "scope": f"unit {label} only",
            "notice": "This emergency access is recorded and will be reviewed by a manager."}


@frappe.whitelist()
def emergency_contacts(grant: str, unit_label: str) -> dict:
    """The only data an emergency grant opens: the household's designated contacts. Every reveal is journaled."""
    actor = get_actor()
    estate = frappe.db.get_value("CPCP Emergency Access", grant, "estate") or ""
    unit = frappe.db.get_value("CPCP Unit", {"estate": estate, "unit_label": (unit_label or "").strip().upper()}, "name") or ""
    ctx = svc.emergency_access(actor, grant, unit)
    from frappe_cpcp.api.communications import _active_membership_contacts
    pairs = _active_membership_contacts(unit)
    out = [{"contact_id": c.contact_id, "relationship": c.relationship.value, "first_name": n, "number": c.phone_e164} for c, n in pairs if c.phone_e164]
    ctx.allowed(record_id=grant, context=f"{len(out)} contacts revealed")
    ctx.action = "emergency"
    frappe.db.sql("update `tabCPCP Emergency Access` set reveal_count = reveal_count + 1 where name=%s", (grant,))
    return {"unit": unit_label.upper(), "contacts": out, "note": "Use for the emergency only. This access is recorded and reviewed."}


@frappe.whitelist(methods=["POST"])
def review_emergency(grant: str, outcome: str, note: str) -> dict:
    g = frappe.db.get_value("CPCP Emergency Access", grant, ["requested_by", "estate", "status"], as_dict=True)
    if not g:
        raise frappe.PermissionError("not permitted")
    actor = authorize("emergency_access", "A", estate=g.estate)
    if actor.user == g.requested_by:
        raise frappe.PermissionError("not permitted")  # independent review: never the requester
    if outcome not in ("Appropriate", "Inappropriate", "Needs follow-up") or not (note or "").strip():
        frappe.throw("An outcome and a note are required", frappe.ValidationError)
    frappe.db.set_value("CPCP Emergency Access", grant, {"status": "Reviewed", "reviewed_by": actor.user, "reviewed_at": to_db(utcnow()),
                                                          "review_outcome": outcome, "review_note": note}, update_modified=False)
    access.record(actor=actor.user, role=actor.role.value, estate=g.estate, action="emergency_review", record_type="Emergency Access", record_id=grant,
                  category="restricted_legal", purpose="supervisor_review", purpose_ref=grant, context=outcome)
    log_audit(action="emergency_access_reviewed", entity="CPCP Emergency Access", entity_id=grant, reason=note, role=actor.role.value, detail={"outcome": outcome})
    return {"grant": grant, "status": "Reviewed", "outcome": outcome}
