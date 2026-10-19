# SPDX-License-Identifier: Apache-2.0
"""Central authorization service: the normative PRD section 28 matrix as data.

Letters: R read, C create, U update/operate, A approve, V aggregate view,
S self/household/assigned only, G only with an explicit, unexpired grant.
Default deny. Every Frappe hook and whitelisted API must call ``decide``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class Role(str, Enum):
    PLATFORM_ADMIN = "platform_admin"
    ORG_ADMIN = "org_admin"  # association owner / management company admin
    ESTATE_MANAGER = "estate_manager"
    SECURITY_MANAGER = "security_manager"
    SECURITY_OFFICER = "security_officer"
    RESIDENT = "resident"
    AUDITOR = "auditor"
    FINANCE = "finance"
    TOW_PROVIDER = "tow_provider"
    BOARD_OBSERVER = "board_observer"


class DataClass(str, Enum):
    PUBLIC_AGGREGATE = "PUBLIC_AGGREGATE"
    SELF_HOUSEHOLD = "SELF_HOUSEHOLD"
    STAFF_OPERATIONAL = "STAFF_OPERATIONAL"
    SENSITIVE_RESIDENT_REGISTRY = "SENSITIVE_RESIDENT_REGISTRY"
    SENSITIVE_VISITOR_LOG = "SENSITIVE_VISITOR_LOG"
    RESTRICTED_EVIDENCE = "RESTRICTED_EVIDENCE"
    FINANCIAL = "FINANCIAL"
    IMMUTABLE_AUDIT = "IMMUTABLE_AUDIT"


# capability -> {role: letters}. Roles absent from a row have no access.
# Estate managers inherit the org_admin row (restricted to appointed estates by scope).
MATRIX: dict[str, dict[Role, str]] = {
    "estate_units": {Role.ORG_ADMIN: "RCU", Role.SECURITY_MANAGER: "R", Role.SECURITY_OFFICER: "R", Role.AUDITOR: "G"},
    # PRD v1.8: security OFFICERS hold no standing registry/visitor-log access. They reach protected data only through
    # purpose-checked APIs (gate_operations / contact_responsible), never by browsing. Managers keep administrative access,
    # which is logged and independently reviewed.
    "resident_registry": {Role.ORG_ADMIN: "RCU", Role.SECURITY_MANAGER: "RCU", Role.AUDITOR: "G"},
    "visitor_log": {Role.ORG_ADMIN: "RCU", Role.SECURITY_MANAGER: "RCU", Role.AUDITOR: "G"},
    "gate_operations": {Role.ORG_ADMIN: "RCU", Role.SECURITY_MANAGER: "RCU", Role.SECURITY_OFFICER: "RCU"},
    "access_review": {Role.ORG_ADMIN: "RU", Role.AUDITOR: "R", Role.SECURITY_MANAGER: "R"},
    "emergency_access": {Role.ORG_ADMIN: "RCA", Role.SECURITY_MANAGER: "RCA", Role.SECURITY_OFFICER: "C"},
    "device_revocation": {Role.ORG_ADMIN: "A", Role.SECURITY_MANAGER: "A"},
    "own_vehicle_request": {Role.ORG_ADMIN: "RCU", Role.SECURITY_MANAGER: "RCU", Role.SECURITY_OFFICER: "RCU", Role.RESIDENT: "SRCU"},
    "submit_report": {Role.ORG_ADMIN: "C", Role.SECURITY_MANAGER: "C", Role.SECURITY_OFFICER: "C", Role.RESIDENT: "C"},
    "triage_reports": {Role.ORG_ADMIN: "RCU", Role.SECURITY_MANAGER: "RCUA", Role.SECURITY_OFFICER: "SRCU", Role.RESIDENT: "SR", Role.AUDITOR: "G"},
    "verify_incident": {Role.ORG_ADMIN: "RCU", Role.SECURITY_MANAGER: "RCU", Role.SECURITY_OFFICER: "RCU"},
    "capture_evidence": {Role.ORG_ADMIN: "RCU", Role.SECURITY_MANAGER: "RCU", Role.SECURITY_OFFICER: "SRCU", Role.RESIDENT: "SR", Role.AUDITOR: "G", Role.FINANCE: "SR", Role.TOW_PROVIDER: "SR"},
    "contact_responsible": {Role.ORG_ADMIN: "RCU", Role.SECURITY_MANAGER: "RCU", Role.SECURITY_OFFICER: "RCU"},
    "issue_warning": {Role.ORG_ADMIN: "RCU", Role.SECURITY_MANAGER: "RCU", Role.SECURITY_OFFICER: "RCU"},
    "approve_enforcement": {Role.ORG_ADMIN: "A", Role.SECURITY_MANAGER: "A"},
    "execute_enforcement": {Role.ORG_ADMIN: "RCU", Role.SECURITY_MANAGER: "RCU", Role.SECURITY_OFFICER: "SRCU", Role.TOW_PROVIDER: "SU"},
    "change_policy": {Role.ORG_ADMIN: "RCUA"},
    "charge_ledger": {Role.ORG_ADMIN: "RCUA", Role.SECURITY_MANAGER: "R", Role.SECURITY_OFFICER: "R", Role.RESIDENT: "SR", Role.AUDITOR: "G", Role.FINANCE: "RCU", Role.TOW_PROVIDER: "SR"},
    "receipts_refunds": {Role.ORG_ADMIN: "RCUA", Role.RESIDENT: "SR", Role.AUDITOR: "G", Role.FINANCE: "RCU", Role.TOW_PROVIDER: "SR"},
    "submit_appeal": {Role.ORG_ADMIN: "RC", Role.RESIDENT: "SRC"},
    "resolve_appeal": {Role.ORG_ADMIN: "A", Role.FINANCE: "RU"},
    "aggregate_dashboards": {Role.ORG_ADMIN: "R", Role.SECURITY_MANAGER: "R", Role.SECURITY_OFFICER: "R", Role.RESIDENT: "V", Role.AUDITOR: "V", Role.FINANCE: "R", Role.BOARD_OBSERVER: "V"},
    "incident_reports": {Role.ORG_ADMIN: "R", Role.SECURITY_MANAGER: "R", Role.SECURITY_OFFICER: "SR", Role.RESIDENT: "SR", Role.AUDITOR: "G", Role.FINANCE: "R", Role.TOW_PROVIDER: "SR"},
    "audit_history": {Role.ORG_ADMIN: "R", Role.SECURITY_MANAGER: "R", Role.SECURITY_OFFICER: "SR", Role.RESIDENT: "SR", Role.AUDITOR: "R", Role.FINANCE: "SR", Role.TOW_PROVIDER: "SR"},
    "manage_users": {Role.ORG_ADMIN: "RCUA", Role.SECURITY_MANAGER: "C"},
    "raw_export": {Role.ORG_ADMIN: "G", Role.SECURITY_MANAGER: "G", Role.AUDITOR: "G"},
    "audit_mutation": {},  # nobody, ever
}

CAPABILITY_CLASS: dict[str, DataClass] = {
    "resident_registry": DataClass.SENSITIVE_RESIDENT_REGISTRY,
    "visitor_log": DataClass.SENSITIVE_VISITOR_LOG,
    "gate_operations": DataClass.SENSITIVE_VISITOR_LOG,
    "access_review": DataClass.IMMUTABLE_AUDIT,
    "own_vehicle_request": DataClass.SELF_HOUSEHOLD,
    "capture_evidence": DataClass.RESTRICTED_EVIDENCE,
    "charge_ledger": DataClass.FINANCIAL,
    "receipts_refunds": DataClass.FINANCIAL,
    "audit_history": DataClass.IMMUTABLE_AUDIT,
    "aggregate_dashboards": DataClass.PUBLIC_AGGREGATE,
}

# Roles whose scope is the whole organization when no estate list is assigned.
ORG_WIDE_ROLES = {Role.ORG_ADMIN}


@dataclass(frozen=True)
class Grant:
    capability: str
    expires_at: datetime
    approved_by: str  # independent approver, required for exceptional access
    purpose: str


@dataclass(frozen=True)
class Actor:
    user: str
    org_id: str
    role: Role  # the ACTIVE role context (never inferred from other memberships)
    estate_ids: frozenset[str] = frozenset()
    unit_ids: frozenset[str] = frozenset()
    active: bool = True
    expires_at: datetime | None = None
    grants: tuple[Grant, ...] = ()


@dataclass(frozen=True)
class Resource:
    org_id: str
    estate_id: str | None = None
    unit_id: str | None = None
    owner_user: str | None = None
    assigned_to: str | None = None


@dataclass(frozen=True)
class Decision:
    allow: bool
    reason: str
    needs_audit: bool = field(default=True)


def _deny(reason: str) -> Decision:
    return Decision(False, reason)


def _has_grant(actor: Actor, capability: str, now: datetime) -> bool:
    return any(
        g.capability == capability and g.expires_at > now and g.approved_by and g.approved_by != actor.user
        for g in actor.grants
    )


def _in_scope(actor: Actor, res: Resource) -> bool:
    if actor.estate_ids:
        return res.estate_id is None or res.estate_id in actor.estate_ids
    return actor.role in ORG_WIDE_ROLES


# Capabilities where an UNCLAIMED item in the officer's own estate counts as "assigned to me",
# so the officer can see and claim it (PRD 35.1). Never extended to enforcement execution.
UNCLAIMED_VISIBLE_TO_ESTATE_OFFICERS = {"triage_reports"}


def _is_self(actor: Actor, res: Resource, capability: str = "") -> bool:
    if res.owner_user is not None and res.owner_user == actor.user:
        return True
    if res.assigned_to is not None and res.assigned_to == actor.user:
        return True
    if res.unit_id is not None and res.unit_id in actor.unit_ids:
        return True
    return (
        capability in UNCLAIMED_VISIBLE_TO_ESTATE_OFFICERS
        and actor.role == Role.SECURITY_OFFICER
        and res.assigned_to is None
        and res.estate_id is not None
        and res.estate_id in actor.estate_ids
    )


def decide(actor: Actor, capability: str, letter: str, resource: Resource, now: datetime) -> Decision:
    """Return an allow/deny decision. ``letter`` is one of R, C, U, A, V."""
    if letter not in ("R", "C", "U", "A", "V"):
        return _deny("unknown action letter")
    if capability == "audit_mutation":
        return _deny("audit and evidence history is immutable")
    row = MATRIX.get(capability)
    if row is None:
        return _deny("unknown capability")
    if actor.role == Role.PLATFORM_ADMIN:
        return _deny("platform operators have no routine tenant-data access")
    if not actor.active or (actor.expires_at is not None and actor.expires_at <= now):
        return _deny("membership expired, suspended or ambiguous")
    if actor.org_id != resource.org_id:
        return _deny("cross-organization access denied")
    role = Role.ORG_ADMIN if actor.role == Role.ESTATE_MANAGER else actor.role
    letters = row.get(role, "")
    if not letters:
        return _deny("role has no access to capability")
    # Hard invariants independent of table edits.
    if role == Role.AUDITOR and letter in ("C", "U", "A"):
        return _deny("auditors are read-only")
    if role == Role.RESIDENT and CAPABILITY_CLASS.get(capability) in (
        DataClass.SENSITIVE_RESIDENT_REGISTRY,
        DataClass.SENSITIVE_VISITOR_LOG,
    ):
        return _deny("residents have no registry or visitor-log access")

    if letter == "V":  # aggregate view is a distinct, non-record permission
        return Decision("V" in letters or "R" in letters, "aggregate view")

    grant_only = letters == "G"
    if grant_only or (role == Role.AUDITOR and "G" in letters):
        if letter == "R" and _has_grant(actor, capability, now) and _in_scope(actor, resource):
            return Decision(True, "explicit time-limited grant")
        return _deny("requires approved, unexpired grant")

    if letter not in letters:
        return _deny("action not permitted for role")
    if "S" in letters:
        if _is_self(actor, resource, capability) and (_in_scope(actor, resource) or role == Role.RESIDENT):
            return Decision(True, "self/assigned scope")
        return _deny("record is not yours or assigned to you")
    if _in_scope(actor, resource):
        return Decision(True, "role permits")
    return _deny("outside assigned estate scope")


def capability_matrix_table() -> list[tuple[str, str, str]]:
    """Flattened (capability, role, letters) rows for docs and manifests."""
    return [(cap, role.value, letters) for cap, row in MATRIX.items() for role, letters in row.items()]


def navigation_manifest(role: Role) -> list[str]:
    """Server-authoritative list of capabilities a role may even see in navigation."""
    effective = Role.ORG_ADMIN if role == Role.ESTATE_MANAGER else role
    return sorted(cap for cap, row in MATRIX.items() if row.get(effective) and cap != "audit_mutation")
