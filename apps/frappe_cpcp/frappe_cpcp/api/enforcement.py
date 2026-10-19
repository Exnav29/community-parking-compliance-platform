# SPDX-License-Identifier: Apache-2.0
"""Policy-driven enforcement, itemized charges and appeals (PRD 8-10; AC-07, AC-09, AC-10, AC-11, AC-19, AC-48, AC-97).

Everything that can coerce or charge is behind legal feature flags that default OFF. Releasing a vehicle and cancelling
an action are never gated and never depend on payment (no unconditional hold-until-paid rule).
"""
from decimal import Decimal

import frappe

from frappe_cpcp.core import charges as ch
from frappe_cpcp.core import episodes as ep
from frappe_cpcp.core.flags import ENFORCEMENT_FLAGS, FeatureDisabled, require_flag
from frappe_cpcp.permissions import authorize
from frappe_cpcp.services import episodes as svc
from frappe_cpcp.services.audit import log_audit
from frappe_cpcp.services.common import deadlock_retry, from_db, iso, require, to_db, utcnow

TERMINAL = ("resolved_closed", "corrected_no_fee", "released")


def flags() -> dict:
    s = frappe.get_single("CPCP Settings")
    return {f: bool(s.get(f)) for f in ENFORCEMENT_FLAGS}


def _gate(name: str):
    try:
        require_flag(flags(), name)
    except FeatureDisabled as e:
        frappe.throw(str(e), frappe.PermissionError)


def _inc(name: str) -> dict:
    row = frappe.db.get_value("CPCP Violation Incident", name,
                              ["name", "estate", "status", "classification", "policy_version", "verified_by", "responsible_unit"], as_dict=True)
    if not row:
        raise frappe.PermissionError("not permitted")
    return row


def _schedule(inc: dict) -> ch.FeeSchedule:
    pol = frappe.db.get_value("CPCP Policy Version", inc["policy_version"],
                              ["version_label", "violation_penalty", "storage_rate_per_period", "storage_period_hours"], as_dict=True)
    cur = frappe.db.get_value("CPCP Estate", inc["estate"], "currency") or "GHS"
    d = lambda v: Decimal(str(v)) if v not in (None, 0, 0.0) else None  # noqa: E731 - blank/0 means "not configured"
    return ch.FeeSchedule(version=pol.version_label, currency=cur, violation_penalty=d(pol.violation_penalty),
                          storage_rate_per_period=d(pol.storage_rate_per_period), storage_period_hours=int(pol.storage_period_hours or 24))


def _existing(incident: str) -> list[ch.Charge]:
    rows = frappe.get_all("CPCP Incident Charge", filters={"incident": incident},
                          fields=["charge_class", "quantity", "unit_price", "currency", "source", "schedule_version", "idempotency_key"])
    return [ch.Charge(incident, ch.ChargeClass(r.charge_class), Decimal(str(r.quantity)), Decimal(str(r.unit_price)), r.currency,
                      r.source or "", r.schedule_version or "", r.idempotency_key) for r in rows]


def _persist(incident: str, charges: list[ch.Charge], actor: str) -> int:
    have = {c.idempotency_key for c in _existing(incident)}
    n = 0
    for c in charges:
        if c.idempotency_key in have:
            continue
        frappe.get_doc({"doctype": "CPCP Incident Charge", "incident": incident, "charge_class": c.charge_class.value,
                        "quantity": float(c.quantity), "unit_price": float(c.unit_price), "amount": float(ch.q(c.amount)),
                        "currency": c.currency, "source": c.source, "schedule_version": c.schedule_version,
                        "idempotency_key": c.idempotency_key, "created_by_user": actor}).insert(ignore_permissions=True)
        n += 1
    return n


def _view(a) -> dict:
    return {"action": a.name, "incident": a.incident, "type": a.action_type, "status": a.status, "proposed_by": a.proposed_by,
            "approved_by": a.approved_by, "executed_at": iso(a.executed_at)}


@frappe.whitelist(methods=["POST"])
@deadlock_retry
def propose_action(incident: str, action_type: str, reason: str) -> dict:
    inc = _inc(incident)
    actor = authorize("execute_enforcement", "C", estate=inc["estate"], assigned_to=inc["verified_by"])
    if action_type not in ("Clamp", "Tow", "Cancel", "Release"):
        frappe.throw("Unknown action", frappe.ValidationError)
    if not (reason or "").strip():
        frappe.throw("A reason is required", frappe.ValidationError)
    if action_type in ("Clamp", "Tow"):
        _gate("clamping_enabled" if action_type == "Clamp" else "towing_enabled")
        if inc["status"] in TERMINAL:
            frappe.throw("Incident is already closed or corrected", frappe.ValidationError)
        if inc["classification"] == "Emergency":
            if action_type == "Clamp":
                frappe.throw("Never clamp an emergency obstruction in place; propose a safe removal (tow) instead", frappe.ValidationError)
        else:
            n = frappe.db.get_value("CPCP Warning Notice", {"incident": incident}, "deadline")
            if not n:
                frappe.throw("No established notice: enforcement needs a qualifying notice and an expired grace period", frappe.ValidationError)
            if from_db(n) > utcnow():
                frappe.throw("Grace period has not expired", frappe.ValidationError)
    key = None
    if action_type in ("Clamp", "Tow"):
        svc.lock_incident(incident)
        state = svc.incident_state(incident)
        event = "clamp_executed" if action_type == "Clamp" else "tow_ordered"
        live = frappe.db.get_value("CPCP Enforcement Action", {"incident": incident, "action_type": action_type, "status": ["in", ["Proposed", "Approved", "Executed"]],
                                                              "release_at": ["is", "not set"]}, "name")
        if live or (ep.enforcement_in_progress(state) and event == "clamp_executed"):
            frappe.throw(f"Already being handled: this incident is '{state.value}'. A second {action_type.lower()} cannot be started.", frappe.DuplicateEntryError)
        try:
            ep.apply(state, event)  # the lifecycle must permit this step from the current state
        except ep.EpisodeError as e:
            frappe.throw(str(e), frappe.ValidationError)
        key = f"{incident}:{action_type}"
    a = frappe.get_doc({"doctype": "CPCP Enforcement Action", "incident": incident, "action_type": action_type, "status": "Proposed",
                        "proposed_by": actor.user, "reason": reason, "active_key": key,
                        "legal_basis_reference": frappe.db.get_single_value("CPCP Settings", "legal_approval_reference")})
    if not svc._try_insert(a):  # DB-level uniqueness: at most one live clamp and one live tow per episode
        frappe.throw("Already being handled: a live action of this type exists for the incident", frappe.DuplicateEntryError)
    log_audit(action="enforcement_proposed", entity="CPCP Enforcement Action", entity_id=a.name, reason=reason, role=actor.role.value)
    return _view(a)


@frappe.whitelist(methods=["POST"])
@deadlock_retry
def approve_action(action: str) -> dict:
    a = frappe.get_doc("CPCP Enforcement Action", action)
    inc = _inc(a.incident)
    actor = authorize("approve_enforcement", "A", estate=inc["estate"])
    if a.proposed_by == actor.user:
        frappe.throw("An action cannot be approved by its proposer", frappe.PermissionError)
    if a.status != "Proposed":
        frappe.throw("Only proposed actions can be approved", frappe.ValidationError)
    if a.action_type in ("Clamp", "Tow"):
        _gate("clamping_enabled" if a.action_type == "Clamp" else "towing_enabled")
    frappe.db.set_value("CPCP Enforcement Action", action, {"status": "Approved", "approved_by": actor.user, "approved_at": to_db(utcnow())}, update_modified=False)
    if a.action_type == "Tow":
        svc.apply_event(a.incident, "tow_ordered")
    log_audit(action="enforcement_approved", entity="CPCP Enforcement Action", entity_id=action, role=actor.role.value)
    return _view(frappe.get_doc("CPCP Enforcement Action", action))


@frappe.whitelist(methods=["POST"])
@deadlock_retry
def execute_action(action: str, provider_ref: str | None = None, provider_amount: float | None = None) -> dict:
    a = frappe.get_doc("CPCP Enforcement Action", action)
    inc = _inc(a.incident)
    actor = authorize("execute_enforcement", "U", estate=inc["estate"], assigned_to=inc["verified_by"])
    if a.status != "Approved":
        frappe.throw("Only approved actions can be executed", frappe.ValidationError)
    f = flags()
    sched = _schedule(inc)
    new_status = {"Clamp": "clamped", "Tow": "tow_dispatched", "Cancel": "escalation_pending", "Release": "released"}[a.action_type]
    if a.action_type in ("Clamp", "Tow"):
        _gate("clamping_enabled" if a.action_type == "Clamp" else "towing_enabled")
        _gate("fine_assessment_enabled")  # an enforcement action must be accountable on the ledger
        try:
            cs = ch.add_violation_penalty(_existing(a.incident), incident_id=a.incident, schedule=sched, flags=f)
            if a.action_type == "Tow":
                cs = ch.add_tow_charge(cs, incident_id=a.incident, provider_amount=Decimal(str(provider_amount)) if provider_amount else None,
                                       currency=sched.currency, provider_ref=provider_ref or a.name, schedule_version=sched.version, flags=f)
        except ch.ChargeError as e:
            frappe.throw(str(e), frappe.ValidationError)
        _persist(a.incident, cs, actor.user)
    frappe.db.set_value("CPCP Enforcement Action", action, {"status": "Executed", "executed_by": actor.user, "executed_at": to_db(utcnow()),
                                                            "provider_ref": provider_ref}, update_modified=False)
    frappe.db.set_value("CPCP Violation Incident", a.incident, "status", new_status, update_modified=False)
    if a.action_type == "Clamp":
        svc.apply_event(a.incident, "clamp_executed")
    elif a.action_type == "Cancel":  # cancelling frees the live action so it can be properly re-proposed
        for live in frappe.get_all("CPCP Enforcement Action", filters={"incident": a.incident, "action_type": ["in", ["Clamp", "Tow"]], "status": ["in", ["Proposed", "Approved"]]}, pluck="name"):
            frappe.db.set_value("CPCP Enforcement Action", live, {"status": "Cancelled", "active_key": None}, update_modified=False)
    log_audit(action="enforcement_executed", entity="CPCP Enforcement Action", entity_id=action, role=actor.role.value)
    return _view(frappe.get_doc("CPCP Enforcement Action", action))


@frappe.whitelist(methods=["POST"])
@deadlock_retry
def record_yard_arrival(action: str) -> dict:
    a = frappe.get_doc("CPCP Enforcement Action", action)
    inc = _inc(a.incident)
    authorize("execute_enforcement", "U", estate=inc["estate"], assigned_to=inc["verified_by"])
    if a.action_type != "Tow" or a.status != "Executed":
        frappe.throw("Only an executed tow can have a yard arrival", frappe.ValidationError)
    if a.yard_arrival_at:
        frappe.throw("Yard arrival already recorded", frappe.DuplicateEntryError)
    frappe.db.set_value("CPCP Enforcement Action", action, "yard_arrival_at", to_db(utcnow()), update_modified=False)
    frappe.db.set_value("CPCP Violation Incident", a.incident, "status", "impounded", update_modified=False)
    svc.apply_event(a.incident, "tow_executed")
    return {"action": action, "yard_arrival_at": iso(utcnow())}


@frappe.whitelist(methods=["POST"])
@deadlock_retry
def release_vehicle(action: str) -> dict:
    """Never gated by payment or by the enforcement flags: release/cancellation must always remain possible.
    Storage is computed from verified yard arrival to this release, only if impound charging is enabled."""
    a = frappe.get_doc("CPCP Enforcement Action", action)
    inc = _inc(a.incident)
    actor = authorize("execute_enforcement", "U", estate=inc["estate"], assigned_to=inc["verified_by"])
    if a.status != "Executed" or a.action_type not in ("Clamp", "Tow"):
        frappe.throw("Only an executed clamp or tow can be released", frappe.ValidationError)
    if a.release_at:
        frappe.throw("Already released", frappe.DuplicateEntryError)
    now = utcnow()
    frappe.db.set_value("CPCP Enforcement Action", action, {"release_at": to_db(now)}, update_modified=False)
    frappe.db.set_value("CPCP Violation Incident", a.incident, "status", "released", update_modified=False)
    frappe.db.set_value("CPCP Enforcement Action", action, "active_key", None, update_modified=False)
    svc.apply_event(a.incident, "release_started")
    svc.apply_event(a.incident, "closed")  # identity is NOT released: only positive departure evidence ends the episode
    storage = None
    f = flags()
    if a.action_type == "Tow" and a.yard_arrival_at and f.get("towing_enabled") and f.get("impound_release_enabled"):
        sched = _schedule(inc)
        if sched.storage_rate_per_period is not None:
            cs = ch.add_storage_charge(_existing(a.incident), incident_id=a.incident, yard_arrival=from_db(a.yard_arrival_at), stop_event=now,
                                       schedule=sched, flags=f)
            _persist(a.incident, cs, actor.user)
            storage = "computed"
    log_audit(action="vehicle_released", entity="CPCP Enforcement Action", entity_id=action, role=actor.role.value, detail={"storage": storage})
    return {"action": action, "released_at": iso(now), "storage": storage or "not charged"}


@frappe.whitelist(methods=["POST"])
@deadlock_retry
def mark_corrected(incident: str, note: str) -> dict:
    inc = _inc(incident)
    actor = authorize("issue_warning", "U", estate=inc["estate"])
    if inc["status"] in ("clamped", "tow_dispatched", "impounded", "released", "resolved_closed"):
        frappe.throw("Enforcement has already been executed; use release/appeal", frappe.ValidationError)
    frappe.db.set_value("CPCP Violation Incident", incident, "status", "corrected_no_fee", update_modified=False)
    svc.apply_event(incident, "compliance_confirmed")
    log_audit(action="incident_corrected", entity="CPCP Violation Incident", entity_id=incident, reason=note, role=actor.role.value)
    return {"incident": incident, "status": "corrected_no_fee", "charges": 0}


@frappe.whitelist()
def get_invoice(incident: str) -> dict:
    inc = _inc(incident)
    actor = authorize("charge_ledger", "R", estate=inc["estate"], unit=inc["responsible_unit"])
    if actor.role.value in ("security_officer", "security_manager"):  # minimal status only, never amounts (PRD 10)
        n = frappe.db.count("CPCP Incident Charge", {"incident": incident})
        return {"incident": incident, "status": "charges recorded" if n else "no charges"}
    lines = _existing(incident)
    return {"incident": incident, "currency": lines[0].currency if lines else None, "lines": ch.itemize(lines), "total": str(ch.invoice_total(lines))}


@frappe.whitelist(methods=["POST"])
@deadlock_retry
def submit_appeal(incident: str, reason: str) -> dict:
    inc = _inc(incident)
    actor = authorize("submit_appeal", "C", estate=inc["estate"], unit=inc["responsible_unit"])
    require((reason or "").strip(), "reason")
    if frappe.db.exists("CPCP Appeal", {"incident": incident, "status": ["in", ["Submitted", "In Review"]]}):
        frappe.throw("An appeal is already open for this incident", frappe.DuplicateEntryError)
    a = frappe.get_doc({"doctype": "CPCP Appeal", "incident": incident, "submitted_by": actor.user, "submitted_at": to_db(utcnow()),
                        "reason": reason, "status": "Submitted"}).insert(ignore_permissions=True)
    log_audit(action="appeal_submitted", entity="CPCP Appeal", entity_id=a.name, role=actor.role.value)
    return {"appeal": a.name, "status": a.status}


@frappe.whitelist(methods=["POST"])
@deadlock_retry
def decide_appeal(appeal: str, status: str, decision: str, credit_amount: float | None = None) -> dict:
    a = frappe.get_doc("CPCP Appeal", appeal)
    inc = _inc(a.incident)
    actor = authorize("resolve_appeal", "A", estate=inc["estate"])
    if status not in ("Upheld", "Dismissed", "Partially Upheld") or not (decision or "").strip():
        frappe.throw("A decision and valid status are required", frappe.ValidationError)
    if a.status not in ("Submitted", "In Review"):
        frappe.throw("Appeal already decided", frappe.ValidationError)
    involved = {inc["verified_by"]} | set(frappe.get_all("CPCP Enforcement Action", filters={"incident": a.incident}, pluck="proposed_by"))
    if actor.user in involved:
        frappe.throw("The original enforcing officer cannot decide the appeal", frappe.PermissionError)
    lines = _existing(a.incident)
    total = ch.invoice_total(lines)
    credit = Decimal(0)
    if status == "Upheld":
        credit = total
    elif status == "Partially Upheld":
        credit = Decimal(str(credit_amount or 0))
        if credit <= 0 or credit > total:
            frappe.throw("Partial credit must be positive and not exceed the invoice total", frappe.ValidationError)
    if credit > 0:
        cur = lines[0].currency
        _persist(a.incident, [ch.Charge(a.incident, ch.ChargeClass.ADJUSTMENT_CREDIT, Decimal(1), credit, cur, f"appeal:{appeal}", "",
                                        ch.idempotency_key(a.incident, ch.ChargeClass.ADJUSTMENT_CREDIT, appeal))], actor.user)
    frappe.db.set_value("CPCP Appeal", appeal, {"status": status, "reviewer": actor.user, "decision": decision, "decided_at": to_db(utcnow())}, update_modified=False)
    log_audit(action="appeal_decided", entity="CPCP Appeal", entity_id=appeal, reason=decision, role=actor.role.value, detail={"status": status, "credit": str(credit)})
    return {"appeal": appeal, "status": status, "credit": str(credit)}
