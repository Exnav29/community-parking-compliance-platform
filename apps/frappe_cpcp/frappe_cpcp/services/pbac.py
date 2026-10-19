# SPDX-License-Identifier: Apache-2.0
"""Server-side purpose verification (PRD 61.4). Adapter between ``core.pbac`` and Frappe data.

Every function loads trusted state from the database (shift, case, grant, device) and journals the outcome durably BEFORE any
data is returned. A denial raises PermissionError with a generic message (no reason leaked to the caller; the reason code goes
to the journal for reviewers).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

import frappe

from frappe_cpcp.core import pbac
from frappe_cpcp.services import access
from frappe_cpcp.services.common import from_db, to_db, utcnow

OPEN_EPISODE_BLOCK = ("Resolved/Closed",)


@dataclass
class Ctx:
    """A validated purpose. Call ``allowed``/``no_match`` exactly once before returning data (fail closed if the journal is down)."""
    actor: object
    estate: str
    purpose: str
    ref: str
    action: str
    record_type: str
    category: str
    target_unit: str
    gate: str
    shift: str
    device_hash: str
    disclosure: pbac.Disclosure
    term: str | None = None

    def _log(self, result, code="ok", record_id="", context=""):
        access.record(actor=self.actor.user, role=self.actor.role.value, estate=self.estate, action=self.action, record_type=self.record_type,
                      record_id=record_id, target_unit=self.target_unit, category=self.category, purpose=self.purpose, purpose_ref=self.ref,
                      result=result, reason_code=code, context=context, search_term=self.term, gate=self.gate, shift=self.shift,
                      device_hash=self.device_hash)

    def allowed(self, record_id: str = "", context: str = ""):
        self._log("Allowed", "ok", record_id, context)

    def no_match(self, context: str = ""):
        self._log("No Match", "no_match", "", context)


def _deny(actor, estate, *, action, record_type, category, purpose, ref="", code, target_unit="", term=None, gate="", shift="", device="") -> None:
    try:
        access.record(actor=getattr(actor, "user", "unknown"), role=getattr(getattr(actor, "role", None), "value", "unknown"), estate=estate or "",
                      action=action, record_type=record_type, category=category, purpose=purpose, purpose_ref=ref, result="Denied",
                      reason_code=code, target_unit=target_unit, search_term=term, gate=gate, shift=shift, device_hash=device)
    finally:
        raise frappe.PermissionError("not permitted")


def _settings_int(field: str, default: int) -> int:
    return int(frappe.db.get_single_value("CPCP Settings", field, cache=False) or default)


def current_shift(user: str):
    """The user's live shift row, or None. Expiry and device revocation are evaluated on the server clock and DB state."""
    row = frappe.db.get_value("CPCP Gate Shift", {"user": user, "status": "On Duty"},
                              ["name", "estate", "gate", "device_hash", "ends_at", "status"], as_dict=True)
    if not row:
        return None
    device_active = not frappe.db.exists("CPCP Device Registration", {"user": user, "device_hash": row.device_hash, "status": "Revoked"})
    user_enabled = bool(frappe.db.get_value("User", user, "enabled"))
    return pbac.Shift(user=user, estate=row.estate, gate=row.gate, on_duty=True, device_active=device_active and user_enabled,
                      ends_at=from_db(row.ends_at)), row


def gate_access(actor, estate: str, *, action: str, record_type: str, category: str = "operational_min", target_unit: str = "",
                client_gate: str | None = None, purpose: pbac.Purpose = pbac.Purpose.GATE_ENTRY, term: str | None = None,
                rate_actions: tuple[str, ...] | None = None, rate_limit: int | None = None) -> Ctx:
    """Gate workflow purpose: requires an on-duty shift for officers; supervisors are estate-scoped and reviewed."""
    cur = current_shift(actor.user) if actor.role.value == "security_officer" else None
    core_shift, row = cur if cur else (None, None)
    d = pbac.decide_gate(role=actor.role.value, user=actor.user, estate=estate, shift=core_shift, now=utcnow(), client_gate=client_gate)
    gate, shift_name, device = (row.gate, row.name, row.device_hash) if row else ("", "", "")
    if not d.allow:
        _deny(actor, estate, action=action, record_type=record_type, category=category, purpose=purpose.value, code=d.code.value,
              target_unit=target_unit, term=term, gate=client_gate or gate, shift=shift_name, device=device)
    if rate_actions and rate_limit and pbac.over_limit(access.count_recent(actor.user, actions=rate_actions, minutes=60, results=("Allowed", "No Match")), rate_limit):
        _deny(actor, estate, action=action, record_type=record_type, category=category, purpose=purpose.value, code=pbac.Code.RATE_LIMITED.value,
              target_unit=target_unit, term=term, gate=gate, shift=shift_name, device=device)
    return Ctx(actor, estate, purpose.value, shift_name, action, record_type, category, target_unit, gate, shift_name, device, d.disclosure, term)


def duty_check(actor, estate: str, *, action: str, record_type: str, category: str = "operational_min") -> Ctx:
    return gate_access(actor, estate, action=action, record_type=record_type, category=category, purpose=pbac.Purpose.ASSIGNED_CASE)


def _case_row(incident: str):
    return frappe.db.get_value("CPCP Violation Incident", incident,
                               ["name", "estate", "assigned_officer", "episode_status", "plate_normalized", "responsible_unit", "merged_into"], as_dict=True)


def case_access(actor, incident: str, *, action: str, record_type: str = "Violation Incident", category: str = "sensitive_personal",
                target_plate: str | None = None, target_unit: str | None = None, estate_hint: str | None = None) -> Ctx:
    """Assigned-case purpose: the case must exist, be open, belong to the actor (officers) and own the requested target."""
    row = _case_row(incident) if incident else None  # an empty or missing reference must never match anything
    estate = row.estate if row else (estate_hint or "")
    cur = current_shift(actor.user) if actor.role.value == "security_officer" else None
    core_shift, srow = cur if cur else (None, None)
    case = None if not row else pbac.Case(row.name, row.estate, row.assigned_officer,
                                          open=(row.episode_status not in OPEN_EPISODE_BLOCK and not row.merged_into),
                                          plate=row.plate_normalized, unit=row.responsible_unit)
    d = pbac.decide_case(role=actor.role.value, user=actor.user, estate=estate, case=case, shift=core_shift, now=utcnow(),
                         target_plate=target_plate, target_unit=target_unit)
    gate, shift_name, device = (srow.gate, srow.name, srow.device_hash) if srow else ("", "", "")
    purpose = pbac.Purpose.ASSIGNED_CASE if actor.role.value == "security_officer" else pbac.Purpose.SUPERVISOR_REVIEW
    unit_label = ""
    if row and row.responsible_unit:
        unit_label = frappe.db.get_value("CPCP Unit", row.responsible_unit, "unit_label") or ""
    if not d.allow:
        _deny(actor, estate, action=action, record_type=record_type, category=category, purpose=purpose.value, ref=incident, code=d.code.value,
              target_unit=unit_label, gate=gate, shift=shift_name, device=device)
    return Ctx(actor, estate, purpose.value, incident, action, record_type, category, unit_label, gate, shift_name, device, d.disclosure)


def emergency_access(actor, grant_name: str, unit: str, *, action: str = "emergency") -> Ctx:
    g = frappe.db.get_value("CPCP Emergency Access", grant_name, ["name", "requested_by", "estate", "unit", "expires_at", "status"], as_dict=True)
    grant = None if not g else pbac.Grant(g.requested_by, g.estate, g.unit, from_db(g.expires_at), active=(g.status == "Active"))
    estate = g.estate if g else ""
    d = pbac.decide_emergency(user=actor.user, estate=estate, target_unit=unit, grant=grant, now=utcnow())
    label = frappe.db.get_value("CPCP Unit", unit, "unit_label") or ""
    if not d.allow:
        _deny(actor, estate, action=action, record_type="Emergency Access", category="contact_reveal", purpose=pbac.Purpose.EMERGENCY.value,
              ref=grant_name, code=d.code.value, target_unit=label)
    return Ctx(actor, estate, pbac.Purpose.EMERGENCY.value, grant_name, action, "Emergency Access", "contact_reveal", label, "", "", "", d.disclosure)


def shift_expiry():
    return to_db(utcnow() + timedelta(hours=_settings_int("shift_max_hours", 14)))
