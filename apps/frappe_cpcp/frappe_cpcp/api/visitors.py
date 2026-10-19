# SPDX-License-Identifier: Apache-2.0
"""Visitor check-in / check-out services (PRD 40, 50; AC-04, AC-69..AC-72, AC-101..AC-120).

All state changes go through ``core.visits`` inside a transaction; clients cannot write final states
directly. Check-in and check-out are idempotent on ``client_uuid``.
"""
from datetime import datetime, timedelta

import frappe

from frappe_cpcp.core import visits as v
from frappe_cpcp.core.plates import normalize_plate
from frappe_cpcp.permissions import authorize
from frappe_cpcp.services.audit import log_audit, log_sensitive_access
from frappe_cpcp.services.common import from_db, iso, require, to_db, unit_by_label, utcnow

ACTIVE_STATUSES = ["Checked In", "Exit Unconfirmed", "Needs Supervisor Review"]
OBSERVED_SKEW = timedelta(minutes=2)
OBSERVED_MAX_AGE = timedelta(days=7)


def _observed(observed_at: str | None, now: datetime) -> tuple[datetime, str]:
    """Server time unless an offline draft supplies an observed time within sane bounds."""
    if not observed_at:
        return now, "online"
    obs = from_db(observed_at)
    if obs > now + OBSERVED_SKEW or obs < now - OBSERVED_MAX_AGE:
        frappe.throw("Observed time is outside the accepted window; record it as a supervised correction",
                     frappe.ValidationError)
    return (obs, "offline_sync") if abs(now - obs) > OBSERVED_SKEW else (now, "online")


def _core_session(doc, events=()):
    return v.VisitSession(
        session_id=doc.name, estate_id=doc.estate, host_unit_id=doc.host_unit, category=doc.category,
        plate=doc.plate_normalized or None, entry_at=from_db(doc.entry_at), entry_gate=doc.entry_gate,
        entry_officer=doc.entry_officer, status=v.VisitStatus(doc.status), presence=v.Presence(doc.presence),
        exit_at=from_db(doc.exit_at), exit_gate=doc.exit_gate, exit_officer=doc.exit_officer,
        exit_method=doc.exit_method, estimated=bool(doc.estimated), events=tuple(events))


def _view(doc) -> dict:
    return {
        "session": doc.name, "status": doc.status, "presence": doc.presence, "plate": doc.plate_snapshot,
        "host_unit": doc.host_unit_label, "category": doc.category, "entry_at": iso(doc.entry_at),
        "entry_gate": doc.entry_gate, "exit_at": iso(doc.exit_at), "exit_gate": doc.exit_gate,
        "duration_minutes": doc.duration_minutes, "estimated": bool(doc.estimated), "sync_state": doc.sync_state,
    }


def _gate_ok(estate: str, gate: str | None) -> None:
    if gate and frappe.db.get_value("CPCP Gate", gate, "estate") != estate:
        frappe.throw("Gate does not belong to this estate", frappe.ValidationError)


@frappe.whitelist(methods=["POST"])
def check_in_visitor(estate: str, host_unit_label: str, client_uuid: str, plate: str | None = None,
                     category: str = "Guest", gate: str | None = None, observed_at: str | None = None,
                     no_vehicle: int = 0, confirm_visiting_today: int = 0) -> dict:
    actor = authorize("visitor_log", "C", estate=estate)
    require(client_uuid, "client_uuid")
    if not int(confirm_visiting_today):
        frappe.throw("Officer must confirm the vehicle is visiting this unit today", frappe.ValidationError)

    prior = frappe.db.get_value("CPCP Visitor Session", {"client_uuid": client_uuid}, ["name", "estate"], as_dict=True)
    if prior:  # idempotent replay (offline retry, double tap)
        if prior.estate != estate:
            raise frappe.PermissionError("not permitted")
        return {"replayed": True, **_view(frappe.get_doc("CPCP Visitor Session", prior.name))}

    _gate_ok(estate, gate)
    unit = unit_by_label(estate, host_unit_label)
    norm = None
    if not int(no_vehicle):
        try:
            norm = normalize_plate(plate)
        except ValueError:
            frappe.throw("A valid plate is required unless this is a no-vehicle visit", frappe.ValidationError)

    now = utcnow()
    observed, source = _observed(observed_at, now)
    active_rows = frappe.get_all("CPCP Visitor Session", filters={"estate": estate, "status": ["in", ACTIVE_STATUSES],
                                                                  "plate_normalized": norm or "__none__"},
                                 fields=["name"])
    active = [_core_session(frappe.get_doc("CPCP Visitor Session", r.name)) for r in active_rows]
    try:
        core = v.check_in(session_id="pending", estate_id=estate, host_unit_id=unit, category=category, plate=norm,
                          gate=gate or "", officer=actor.user, observed_at=observed, received_at=now,
                          idempotency_key=client_uuid + ":in", active_sessions=active, no_vehicle=bool(int(no_vehicle)))
    except v.AlreadyInside as e:
        frappe.throw(f"Already inside (active visit {e.session_id}); view or reconcile it instead of opening another",
                     frappe.DuplicateEntryError)

    doc = frappe.get_doc({
        "doctype": "CPCP Visitor Session", "estate": estate, "host_unit": unit, "host_unit_label": host_unit_label.strip().upper(),
        "category": category, "plate_snapshot": (plate or "").strip().upper() or None, "plate_normalized": norm,
        "status": core.status.value, "presence": core.presence.value, "entry_at": to_db(core.entry_at), "entry_gate": gate,
        "entry_officer": actor.user, "client_uuid": client_uuid, "sync_state": "Synced",
    }).insert(ignore_permissions=True)
    _event(doc.name, "ENTRY", actor.user, gate, observed, now, client_uuid + ":in", source=source)
    log_audit(action="visitor_check_in", entity="CPCP Visitor Session", entity_id=doc.name, role=actor.role.value,
              detail={"estate": estate, "source": source})
    return {"replayed": False, **_view(doc)}


def _event(session, etype, actor, gate, observed, received, key, reason=None, source="online"):
    frappe.get_doc({"doctype": "CPCP Visit Event", "session": session, "event_type": etype, "actor": actor, "gate": gate,
                    "observed_at": to_db(observed), "received_at": to_db(received), "idempotency_key": key,
                    "reason": reason, "source": source}).insert(ignore_permissions=True)


@frappe.whitelist(methods=["POST"])
def check_out_visitor(session: str, client_uuid: str, gate: str | None = None, observed_at: str | None = None) -> dict:
    """Close exactly this session. Exactly one authorized exit is committed even under concurrency."""
    require(client_uuid, "client_uuid")
    estate = frappe.db.get_value("CPCP Visitor Session", session, "estate")
    if not estate:
        raise frappe.PermissionError("not permitted")  # unknown id is indistinguishable from forbidden
    actor = authorize("visitor_log", "U", estate=estate)
    _gate_ok(estate, gate)
    frappe.db.sql("select name from `tabCPCP Visitor Session` where name = %s for update", (session,))
    doc = frappe.get_doc("CPCP Visitor Session", session)
    events = [
        v.VisitEvent(v.EventType(e.event_type), e.actor or "", e.gate, from_db(e.observed_at), from_db(e.received_at),
                     e.idempotency_key)
        for e in frappe.get_all("CPCP Visit Event", filters={"session": session},
                                fields=["event_type", "actor", "gate", "observed_at", "received_at", "idempotency_key"])
    ]
    now = utcnow()
    observed, source = _observed(observed_at, now)
    key = client_uuid + ":out"
    try:
        closed = v.check_out(_core_session(doc, events), gate=gate or "", officer=actor.user, observed_at=observed,
                             received_at=now, idempotency_key=key)
    except v.AlreadyCheckedOut:
        frappe.throw(f"Already checked out at {iso(doc.exit_at)} (gate {doc.exit_gate}); no second exit was recorded",
                     frappe.DuplicateEntryError)
    except v.VisitError as e:
        frappe.throw(str(e), frappe.ValidationError)
    if any(e.idempotency_key == key for e in events):  # replay of our own earlier success
        return {"replayed": True, **_view(doc)}
    doc.update({"status": closed.status.value, "presence": closed.presence.value, "exit_at": to_db(closed.exit_at),
                "exit_gate": gate, "exit_officer": actor.user, "exit_method": closed.exit_method, "estimated": 0,
                "duration_minutes": closed.duration_minutes, "version": (doc.version or 1) + 1})
    doc.save(ignore_permissions=True)
    _event(session, "EXIT", actor.user, gate, observed, now, key, source=source)
    log_audit(action="visitor_check_out", entity="CPCP Visitor Session", entity_id=session, role=actor.role.value,
              detail={"duration_minutes": closed.duration_minutes})
    return {"replayed": False, **_view(doc)}


@frappe.whitelist(methods=["POST"])
def supervisor_correct_exit(session: str, client_uuid: str, estimated_exit_at: str, reason: str) -> dict:
    """Append-only supervisor correction; the result is labelled ESTIMATED and excluded from verified stats."""
    estate = frappe.db.get_value("CPCP Visitor Session", session, "estate")
    if not estate:
        raise frappe.PermissionError("not permitted")
    actor = authorize("approve_enforcement", "A", estate=estate)  # supervisor-level authority, distinct from checkout
    frappe.db.sql("select name from `tabCPCP Visitor Session` where name = %s for update", (session,))
    doc = frappe.get_doc("CPCP Visitor Session", session)
    now = utcnow()
    try:
        c = v.supervisor_correct_exit(_core_session(doc), supervisor=actor.user, estimated_exit_at=from_db(estimated_exit_at),
                                      reason=reason, received_at=now, idempotency_key=client_uuid + ":corr")
    except v.VisitError as e:
        frappe.throw(str(e), frappe.ValidationError)
    doc.update({"status": c.status.value, "presence": c.presence.value, "exit_at": to_db(c.exit_at), "exit_officer": actor.user,
                "exit_method": c.exit_method, "estimated": 1, "duration_minutes": None})
    doc.save(ignore_permissions=True)
    _event(session, "EXIT_CORRECTION", actor.user, None, c.exit_at, now, client_uuid + ":corr", reason=reason)
    log_audit(action="visitor_exit_corrected", entity="CPCP Visitor Session", entity_id=session, reason=reason, role=actor.role.value)
    return _view(doc)


@frappe.whitelist()
def active_visitors(estate: str, plate: str | None = None, unit_label: str | None = None, limit: int = 50) -> list[dict]:
    """Visitors currently inside, estate-scoped, minimal columns. Cross-gate: any gate in the estate sees all."""
    actor = authorize("visitor_log", "R", estate=estate)
    filters = {"estate": estate, "status": ["in", ACTIVE_STATUSES]}
    if plate:
        try:
            filters["plate_normalized"] = normalize_plate(plate)
        except ValueError:
            return []
    if unit_label:
        filters["host_unit_label"] = unit_label.strip().upper()
    rows = frappe.get_all("CPCP Visitor Session", filters=filters, order_by="entry_at desc", limit=min(int(limit), 200),
                          fields=["name"])
    log_sensitive_access(record_type="Visitor Session", estate=estate, context="active visitors list", role=actor.role.value)
    return [_view(frappe.get_doc("CPCP Visitor Session", r.name)) for r in rows]
