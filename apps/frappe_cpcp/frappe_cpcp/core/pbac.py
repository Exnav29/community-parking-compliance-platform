# SPDX-License-Identifier: Apache-2.0
"""Purpose-based access control layered over RBAC (PRD 61).

A role never suffices. Every sensitive request is evaluated against TRUSTED, server-loaded context: the actor's live shift
(estate, gate, device), the case assignment, the target relationship, or an unexpired emergency grant. Nothing that the
client sends (purpose text, case id, gate id, unit id) is evidence on its own; it is only something to validate.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class Purpose(str, Enum):
    GATE_ENTRY = "gate_entry"
    GATE_EXIT = "gate_exit"
    ASSIGNED_CASE = "assigned_case"
    SUPERVISOR_REVIEW = "supervisor_review"
    EMERGENCY = "emergency"


class Disclosure(str, Enum):
    NONE = "none"
    GATE_MINIMUM = "gate_minimum"        # plate, vehicle description, unit label, entry eligibility. No names, no numbers.
    CASE_CONTACT = "case_contact"        # masked contact choices for THIS case; numbers only via the call/SMS action
    EMERGENCY_CONTACT = "emergency_contact"  # minimum contacts for ONE unit, time-boxed


class Code(str, Enum):
    OK = "ok"
    NO_ROLE_SCOPE = "no_role_scope"
    NO_SHIFT = "no_active_shift"
    SHIFT_OTHER_ESTATE = "shift_other_estate"
    GATE_MISMATCH = "gate_mismatch"
    DEVICE_REVOKED = "device_or_session_revoked"
    NO_CASE = "case_not_found_or_closed"
    NOT_ASSIGNED = "not_assigned_to_case"
    TARGET_MISMATCH = "target_not_part_of_case"
    CASE_OTHER_ESTATE = "case_other_estate"
    NO_GRANT = "no_valid_emergency_grant"
    GRANT_SCOPE = "emergency_grant_scope"
    RATE_LIMITED = "rate_limited"


@dataclass(frozen=True)
class Decision:
    allow: bool
    code: Code
    disclosure: Disclosure = Disclosure.NONE


@dataclass(frozen=True)
class Shift:
    user: str
    estate: str
    gate: str
    on_duty: bool
    device_active: bool = True
    ends_at: datetime | None = None  # absolute server-side expiry


@dataclass(frozen=True)
class Case:
    incident: str
    estate: str
    assigned_officer: str | None
    open: bool
    plate: str | None = None
    unit: str | None = None


@dataclass(frozen=True)
class Grant:
    user: str
    estate: str
    unit: str
    expires_at: datetime
    active: bool = True


STAFF_NEEDING_SHIFT = {"security_officer"}
SUPERVISORS = {"security_manager", "org_admin", "estate_manager"}


def _deny(code: Code) -> Decision:
    return Decision(False, code)


def _shift_ok(role: str, user: str, estate: str, shift: Shift | None, now: datetime, client_gate: str | None) -> Code:
    if role not in STAFF_NEEDING_SHIFT:
        return Code.OK  # supervisors are scoped by estate assignment and are reviewed, not shift-gated
    if shift is None or shift.user != user or not shift.on_duty or (shift.ends_at is not None and shift.ends_at <= now):
        return Code.NO_SHIFT
    if not shift.device_active:
        return Code.DEVICE_REVOKED
    if shift.estate != estate:
        return Code.SHIFT_OTHER_ESTATE
    if client_gate is not None and client_gate != shift.gate:
        return Code.GATE_MISMATCH  # a forged or stale gate id never widens access
    return Code.OK


def decide_gate(*, role: str, user: str, estate: str, shift: Shift | None, now: datetime, client_gate: str | None = None) -> Decision:
    """Check-in / check-out / returning-visitor suggestions / plate lookup at the gate."""
    if role not in STAFF_NEEDING_SHIFT and role not in SUPERVISORS:
        return _deny(Code.NO_ROLE_SCOPE)
    code = _shift_ok(role, user, estate, shift, now, client_gate)
    return Decision(code == Code.OK, code, Disclosure.GATE_MINIMUM if code == Code.OK else Disclosure.NONE)


def decide_case(*, role: str, user: str, estate: str, case: Case | None, shift: Shift | None, now: datetime,
                target_plate: str | None = None, target_unit: str | None = None) -> Decision:
    """Resolve an assigned violation. The target (plate/unit) must be the case's own; a claim cannot be used to look elsewhere."""
    if role not in STAFF_NEEDING_SHIFT and role not in SUPERVISORS:
        return _deny(Code.NO_ROLE_SCOPE)
    if case is None or not case.open:
        return _deny(Code.NO_CASE)
    if case.estate != estate:
        return _deny(Code.CASE_OTHER_ESTATE)
    if role in STAFF_NEEDING_SHIFT:
        code = _shift_ok(role, user, estate, shift, now, None)
        if code != Code.OK:
            return _deny(code)
        if case.assigned_officer != user:
            return _deny(Code.NOT_ASSIGNED)
    if target_plate is not None and target_plate != case.plate:
        return _deny(Code.TARGET_MISMATCH)
    if target_unit is not None and target_unit != case.unit:
        return _deny(Code.TARGET_MISMATCH)
    return Decision(True, Code.OK, Disclosure.CASE_CONTACT)


def decide_emergency(*, user: str, estate: str, target_unit: str, grant: Grant | None, now: datetime) -> Decision:
    if grant is None or not grant.active or grant.user != user or grant.expires_at <= now:
        return _deny(Code.NO_GRANT)
    if grant.estate != estate or grant.unit != target_unit:
        return _deny(Code.GRANT_SCOPE)
    return Decision(True, Code.OK, Disclosure.EMERGENCY_CONTACT)


def over_limit(count_in_window: int, limit: int) -> bool:
    return count_in_window >= limit


# Field allow-lists: what each disclosure level may return. Services build responses ONLY from these.
FIELDS = {
    Disclosure.GATE_MINIMUM: ("plate", "make", "color", "unit", "kind", "hint", "eligible", "entry_at", "category"),
    Disclosure.CASE_CONTACT: ("contact_id", "relationship", "first_name", "number_masked"),
    Disclosure.EMERGENCY_CONTACT: ("contact_id", "relationship", "first_name", "number"),
}

# Words that must never appear in a gate-level response.
GATE_FORBIDDEN_KEYS = {"full_name", "name", "phone", "phone_e164", "email", "members", "household", "history", "last_visit", "last_visit_date"}
