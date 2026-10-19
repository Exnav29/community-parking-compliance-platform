# SPDX-License-Identifier: Apache-2.0
"""Contact resolution, calls, SMS and notice clock for verified incidents (PRD 41-42).

Authorized duty staff only. Phone numbers are returned masked except to the officer who explicitly starts a call
(logged). An attempt is never presented as a delivered notice: only a confirmed answered call (or a policy-approved
proof) can start the grace clock, and the clock is established by the SERVER.
"""
import json
from datetime import timedelta

import frappe
from frappe.utils import cint, getdate, nowdate

from frappe_cpcp.core import comms as cm
from frappe_cpcp.core import noticeclock as nc
from frappe_cpcp.core.phones import mask_phone
from frappe_cpcp.permissions import authorize
from frappe_cpcp.services import pbac as pb
from frappe_cpcp.services.audit import log_audit
from frappe_cpcp.services.common import deadlock_retry, iso, require, to_db, utcnow

DEFAULT_SMS_TEMPLATE = ("Community Security: Vehicle {plate} is parked in a restricted area at {zone}. Please move it "
                        "immediately. For assistance call {security_number}. Case {case_id}. Enforcement may follow under "
                        "the published estate policy once applicable notice and escalation requirements are met.")
TEMPLATE_VERSION = "default-1"
_MOCK = cm.MockSmsProvider()  # process-local; real adapters are registered here once approved


def _incident(name: str) -> dict:
    row = frappe.db.get_value("CPCP Violation Incident", name,
                              ["name", "estate", "plate_normalized", "plate_snapshot", "status", "policy_version", "classification",
                               "responsible_unit", "zone", "verified_by", "assigned_officer"], as_dict=True)
    if not row:
        raise frappe.PermissionError("not permitted")
    return row


def _active_membership_contacts(unit: str) -> list[tuple[cm.Contact, str]]:
    today = getdate(nowdate())
    rows = frappe.db.sql(
        """select m.name as mid, m.is_primary_contact, m.is_backup_contact, m.modified, p.phone_e164, p.full_name
           from `tabCPCP Unit Membership` m join `tabCPCP Person` p on p.name = m.person
           where m.unit = %(u)s and p.active = 1 and (m.valid_from <= %(t)s) and (m.valid_to is null or m.valid_to >= %(t)s)
             and (m.is_primary_contact = 1 or m.is_backup_contact = 1)""", {"u": unit, "t": today}, as_dict=True)
    out = []
    for r in rows:
        rel = cm.Relationship.PRIMARY if r.is_primary_contact else cm.Relationship.BACKUP
        out.append((cm.Contact(r.mid, rel, unit, r.phone_e164, str(r.modified)[:10]), (r.full_name or "").split(" ")[0]))
    return out


def _resolve(inc: dict) -> dict:
    """Server-authorized projection. Active visitor session first (current host, never a stale one), then resident vehicle."""
    visit = frappe.get_all("CPCP Visitor Session", filters={"estate": inc["estate"], "plate_normalized": inc["plate_normalized"],
                           "status": ["in", ["Checked In", "Exit Unconfirmed", "Needs Supervisor Review"]]}, fields=["host_unit"], limit=2)
    if len(visit) > 1:
        return {"basis": "ambiguous", "unit": None, "contacts": []}
    if visit:
        unit, basis = visit[0].host_unit, "active_visitor"
    else:
        today = getdate(nowdate())
        units = frappe.db.sql(
            """select distinct a.unit from `tabCPCP Vehicle` v join `tabCPCP Vehicle Unit Association` a on a.vehicle = v.name
               join `tabCPCP Unit` u on u.name = a.unit
               where v.plate_normalized = %(p)s and v.status = 'Active' and a.status = 'Active' and a.verification_status = 'Verified'
                 and u.estate = %(e)s and (a.valid_from is null or a.valid_from <= %(t)s) and (a.valid_to is null or a.valid_to >= %(t)s)""",
            {"p": inc["plate_normalized"], "e": inc["estate"], "t": today})
        if len(units) > 1:
            return {"basis": "ambiguous", "unit": None, "contacts": []}
        if not units:
            return {"basis": "none", "unit": None, "contacts": []}
        unit, basis = units[0][0], "resident_vehicle"
    pairs = _active_membership_contacts(unit)
    ordered = cm.order_contacts([c for c, _ in pairs], unit)
    first = {c.contact_id: n for c, n in pairs}
    return {"basis": basis, "unit": unit, "contacts": [(c, first[c.contact_id]) for c in ordered]}


@frappe.whitelist()
def resolve_violation_contacts(incident: str) -> dict:
    inc = _incident(incident)
    actor = authorize("contact_responsible", "R", estate=inc["estate"], assigned_to=inc["assigned_officer"])
    ctx = pb.case_access(actor, incident, action="contact", category="sensitive_personal")  # assigned, open, and the officer is on duty
    res = _resolve(inc)
    if res["unit"] and not inc["responsible_unit"]:
        frappe.db.set_value("CPCP Violation Incident", incident, {"responsible_unit": res["unit"], "match_basis": res["basis"]}, update_modified=False)
    ctx.allowed(record_id=incident, context=res["basis"])
    return {"basis": res["basis"], "label": {"none": "No Verified Match", "ambiguous": "Ambiguous - supervisor review required"}.get(res["basis"], "Match is a candidate, not proof of who was driving"),
            "contacts": [{"contact_id": c.contact_id, "relationship": c.relationship.value, "first_name": n,
                          "number": mask_phone(c.phone_e164), "last_updated": c.verified_on} for c, n in res["contacts"]],
            "next_if_unreachable": list(nc.next_step_after_failed_contact())}


def _pick(inc: dict, contact_id: str) -> cm.Contact:
    """The contact must come from the server's own resolution; arbitrary ids are rejected."""
    for c, _ in _resolve(inc)["contacts"]:
        if c.contact_id == contact_id:
            return c
    raise frappe.PermissionError("not permitted")


def _attempt_view(a) -> dict:
    return {"attempt": a.name, "channel": a.channel, "relationship": a.relationship, "destination": a.destination_masked,
            "outcome": a.outcome or None, "provenance": a.provenance, "duration": a.duration_label, "sms_status": a.sms_status or None,
            "acknowledged": bool(a.acknowledged), "initiated_at": iso(a.initiated_at)}


@frappe.whitelist(methods=["POST"])
@deadlock_retry
def initiate_call(incident: str, contact_id: str, client_uuid: str) -> dict:
    """Mode A (native dialer). Records that a call was REQUESTED; says nothing about connection."""
    require(client_uuid, "client_uuid")
    inc = _incident(incident)
    actor = authorize("contact_responsible", "C", estate=inc["estate"])
    ctx = pb.case_access(actor, incident, action="contact", category="contact_reveal")
    prior = frappe.db.get_value("CPCP Communication Attempt", {"client_uuid": client_uuid}, "name")
    contact = _pick(inc, contact_id)
    if prior:
        return {"attempt": prior, "replayed": True}
    rec = cm.requested_only()
    a = frappe.get_doc({"doctype": "CPCP Communication Attempt", "incident": incident, "channel": rec.channel.value,
                        "contact_id": contact_id, "relationship": contact.relationship.value,
                        "destination_masked": mask_phone(contact.phone_e164), "destination": contact.phone_e164,
                        "officer": actor.user, "initiated_at": to_db(utcnow()), "provenance": rec.provenance.value,
                        "duration_label": rec.duration_label, "client_uuid": client_uuid}).insert(ignore_permissions=True)
    ctx.allowed(record_id=a.name, context="dialer number revealed")
    log_audit(action="call_requested", entity="CPCP Communication Attempt", entity_id=a.name, role=actor.role.value)
    _event(a.name, "dialer_open_requested", "")
    return {"attempt": a.name, "replayed": False, "dial": contact.phone_e164,
            "note": "Dialer opened is not a connected call. Record the outcome when you return."}


def _event(attempt: str, etype: str, provider_ts: str, key: str | None = None, sig_valid: int = 0) -> bool:
    key = key or frappe.generate_hash(length=24)
    if frappe.db.exists("CPCP Communication Event", {"idempotency_key": key}):
        return False
    frappe.get_doc({"doctype": "CPCP Communication Event", "attempt": attempt, "event_type": etype, "provider_ts": provider_ts,
                    "ingested_at": to_db(utcnow()), "idempotency_key": key, "signature_valid": sig_valid}).insert(ignore_permissions=True)
    return True


@frappe.whitelist(methods=["POST"])
@deadlock_retry
def record_call_outcome(attempt: str, outcome: str, warning_confirmed: int = 0, estimated_seconds: int | None = None) -> dict:
    a = frappe.get_doc("CPCP Communication Attempt", attempt)
    inc = _incident(a.incident)
    actor = authorize("contact_responsible", "U", estate=inc["estate"])
    pb.case_access(actor, a.incident, action="write", category="operational_min").allowed(record_id=attempt)
    if a.channel != "call_dialer":
        frappe.throw("Provider-mediated calls are recorded by the provider callback only", frappe.ValidationError)
    if a.officer != actor.user and actor.role.value not in ("security_manager", "org_admin", "estate_manager"):
        raise frappe.PermissionError("not permitted")
    if a.outcome:
        frappe.throw("Outcome already recorded; add a new attempt for a follow-up", frappe.ValidationError)
    try:
        rec = cm.record_dialer_outcome(cm.CallOutcome(outcome), cint(estimated_seconds) if estimated_seconds not in (None, "") else None)
    except (ValueError, cm.CommsError) as e:
        frappe.throw(str(e), frappe.ValidationError)
    confirmed = 1 if (cint(warning_confirmed) and rec.outcome == cm.CallOutcome.ANSWERED) else 0
    fields = {"outcome": rec.outcome.value, "provenance": rec.provenance.value, "duration_label": rec.duration_label,
              "warning_confirmed": confirmed}
    if rec.duration_seconds is not None:  # an unknown duration stays unknown (never stored as 0)
        fields["duration_seconds"] = rec.duration_seconds
    frappe.db.set_value("CPCP Communication Attempt", attempt, fields, update_modified=False)
    _event(attempt, "outcome_reported:" + rec.outcome.value, "")
    if inc["status"] == "recorded":
        frappe.db.set_value("CPCP Violation Incident", a.incident, "status", "notification_attempted", update_modified=False)
    log_audit(action="call_outcome", entity="CPCP Communication Attempt", entity_id=attempt, role=actor.role.value, detail={"outcome": outcome})
    proof = cm.notice_proof_for(rec.outcome, bool(confirmed))
    return {"attempt": attempt, "outcome": rec.outcome.value, "duration": rec.duration_label,
            "can_establish_notice": proof is not None,
            "next": "establish_notice_clock" if proof else list(nc.next_step_after_failed_contact())}


@frappe.whitelist(methods=["POST"])
@deadlock_retry
def establish_notice_clock(incident: str, attempt: str) -> dict:
    """Server-authoritative. The device clock and any attempt that is not a confirmed notice cannot start it."""
    inc = _incident(incident)
    actor = authorize("issue_warning", "C", estate=inc["estate"])
    pb.case_access(actor, incident, action="write", category="operational_min").allowed(record_id=incident, context="notice clock")
    a = frappe.get_doc("CPCP Communication Attempt", attempt)
    if a.incident != incident:
        raise frappe.PermissionError("not permitted")
    if frappe.db.exists("CPCP Warning Notice", {"incident": incident}):
        frappe.throw("A notice clock already exists for this incident", frappe.DuplicateEntryError)
    pol = frappe.db.get_value("CPCP Policy Version", inc["policy_version"], ["name", "version_label", "grace_minutes"], as_dict=True)
    if not pol:
        frappe.throw("Incident has no policy snapshot", frappe.ValidationError)
    proof = cm.notice_proof_for(cm.CallOutcome(a.outcome) if a.outcome else None, bool(a.warning_confirmed))
    if proof is None:
        frappe.throw("This attempt does not qualify as notice. Record no verified contact, try an authorized backup, or notify the security manager.", frappe.ValidationError)
    try:
        n = nc.establish_notice_clock(nc.NoticePolicy(pol.version_label, int(pol.grace_minutes)), proof=proof, notice_method=a.channel,
                                      server_now=utcnow(), is_emergency=inc["classification"] == "Emergency")
    except nc.NoticeError as e:
        frappe.throw(str(e), frappe.ValidationError)
    doc = frappe.get_doc({"doctype": "CPCP Warning Notice", "incident": incident, "policy_version": pol.version_label,
                          "notice_method": n.notice_method, "proof_basis": n.proof_basis.value, "effective_at": to_db(n.notice_effective_at),
                          "grace_minutes": n.grace_minutes, "deadline": to_db(n.deadline), "attempt": attempt,
                          "established_by": actor.user}).insert(ignore_permissions=True)
    frappe.db.set_value("CPCP Violation Incident", incident, "status", "grace_active", update_modified=False)
    from frappe_cpcp.services import episodes as svc
    svc.apply_event(incident, "notice_established")
    frappe.db.set_value("CPCP Communication Attempt", attempt, "notice", doc.name, update_modified=False)
    log_audit(action="notice_clock_established", entity="CPCP Warning Notice", entity_id=doc.name, role=actor.role.value,
              detail={"deadline": iso(doc.deadline), "proof": n.proof_basis.value})
    return {"notice": doc.name, "effective_at": iso(doc.effective_at), "deadline": iso(doc.deadline), "grace_minutes": doc.grace_minutes}


@frappe.whitelist(methods=["POST"])
@deadlock_retry
def send_case_sms(incident: str, contact_id: str, client_uuid: str) -> dict:
    require(client_uuid, "client_uuid")
    inc = _incident(incident)
    actor = authorize("contact_responsible", "C", estate=inc["estate"])
    ctx = pb.case_access(actor, incident, action="contact", category="contact_reveal")
    prior = frappe.db.get_value("CPCP Communication Attempt", {"client_uuid": client_uuid}, "name")
    if prior:
        return {"attempt": prior, "replayed": True}
    s = frappe.get_single("CPCP Settings")
    provider = s.sms_provider or "mock"
    if provider != "mock" and not s.sms_live_enabled:
        frappe.throw("Billable messaging is disabled pending authorization", frappe.ValidationError)
    contact = _pick(inc, contact_id)
    hour_ago = to_db(utcnow() - timedelta(hours=1))
    per_contact = frappe.db.count("CPCP Communication Attempt", {"incident": incident, "contact_id": contact_id, "channel": "sms", "initiated_at": [">=", hour_ago]})
    per_case = frappe.db.count("CPCP Communication Attempt", {"incident": incident, "channel": "sms"})
    if not cm.sms_rate_ok(per_contact, per_case):
        frappe.throw("SMS limit reached for this case/contact; ask the security manager to approve an exceptional retry", frappe.TooManyRequestsError)
    zone = frappe.db.get_value("CPCP Zone", inc["zone"], "zone_name") if inc["zone"] else "the estate"
    text = cm.render_template(DEFAULT_SMS_TEMPLATE, {"plate": inc["plate_snapshot"], "zone": zone, "case_id": inc["name"],
                              "security_number": s.security_desk_number or "the security desk"}, bool(frappe.db.exists("CPCP Warning Notice", {"incident": incident})))
    a = frappe.get_doc({"doctype": "CPCP Communication Attempt", "incident": incident, "channel": "sms", "contact_id": contact_id,
                        "relationship": contact.relationship.value, "destination_masked": mask_phone(contact.phone_e164),
                        "destination": contact.phone_e164, "officer": actor.user, "initiated_at": to_db(utcnow()),
                        "sms_status": cm.SmsStatus.CREATED.value, "message_text": text, "template_version": TEMPLATE_VERSION,
                        "provider": provider, "provenance": cm.Provenance.REQUESTED_ONLY.value, "duration_label": "n/a",
                        "client_uuid": client_uuid}).insert(ignore_permissions=True)
    ref = _MOCK.send(contact.phone_e164, text, client_uuid)
    frappe.db.set_value("CPCP Communication Attempt", a.name, {"provider_ref": ref, "sms_status": cm.SmsStatus.ACCEPTED.value}, update_modified=False)
    _event(a.name, "provider_accepted", "")
    log_audit(action="sms_sent", entity="CPCP Communication Attempt", entity_id=a.name, role=actor.role.value, detail={"len": len(text)})
    ctx.allowed(record_id=a.name, context="sms sent via server; number not revealed")
    return {"attempt": a.name, "replayed": False, "status": cm.SmsStatus.ACCEPTED.value,
            "note": "Accepted by the provider. This is not delivery, and not acknowledgement."}


def ingest_callback(body: bytes, signature: str | None) -> dict:
    """Provider webhook: authenticated by HMAC with this site's secret, idempotent, monotonic."""
    secret = (frappe.conf.get("cpcp_sms_callback_secret") or "").encode()
    if not cm.verify_callback(secret, body, signature):
        frappe.local.response["http_status_code"] = 401
        return {"ok": False}
    data = json.loads(body or b"{}")
    ref, status, ts = str(data.get("id", "")), str(data.get("status", "")).lower(), str(data.get("ts", ""))
    key = cm.event_key(str(data.get("provider", "mock")), ref, status, ts)
    att = frappe.db.get_value("CPCP Communication Attempt", {"provider_ref": ref}, ["name", "sms_status"], as_dict=True)
    if not att:
        return {"ok": True}  # unknown reference: acknowledge generically, reveal nothing
    if not _event(att.name, "provider:" + status, ts, key, sig_valid=1):
        return {"ok": True, "duplicate": True}
    mapped = {"queued": cm.SmsStatus.QUEUED, "accepted": cm.SmsStatus.ACCEPTED, "sent": cm.SmsStatus.SENT,
              "delivered": cm.SmsStatus.DELIVERED, "failed": cm.SmsStatus.FAILED}.get(status, cm.SmsStatus.UNKNOWN)
    new = cm.advance_sms_status(cm.SmsStatus(att.sms_status or cm.SmsStatus.CREATED.value), mapped)
    frappe.db.set_value("CPCP Communication Attempt", att.name, {"sms_status": new.value, "error": data.get("error")}, update_modified=False)
    return {"ok": True, "status": new.value}


@frappe.whitelist(allow_guest=True, methods=["POST"])
@deadlock_retry
def provider_callback() -> dict:
    return ingest_callback(frappe.request.get_data(), frappe.get_request_header("X-CPCP-Signature"))


@frappe.whitelist(methods=["POST"])
@deadlock_retry
def acknowledge_sms(attempt: str, note: str) -> dict:
    """Explicit acknowledgement (e.g. the recipient replied or called back), recorded by an officer with a note."""
    a = frappe.get_doc("CPCP Communication Attempt", attempt)
    inc = _incident(a.incident)
    actor = authorize("contact_responsible", "U", estate=inc["estate"])
    pb.case_access(actor, a.incident, action="write", category="operational_min").allowed(record_id=attempt)
    if a.channel != "sms" or not (note or "").strip():
        frappe.throw("An SMS attempt and a note describing the acknowledgement are required", frappe.ValidationError)
    frappe.db.set_value("CPCP Communication Attempt", attempt, "acknowledged", 1, update_modified=False)
    _event(attempt, "acknowledged_by_officer", "")
    log_audit(action="sms_acknowledged", entity="CPCP Communication Attempt", entity_id=attempt, reason=note, role=actor.role.value)
    return {"attempt": attempt, "acknowledged": True}


@frappe.whitelist()
def comms_timeline(incident: str) -> dict:
    inc = _incident(incident)
    actor = authorize("contact_responsible", "R", estate=inc["estate"], assigned_to=inc["assigned_officer"])
    pb.case_access(actor, incident, action="view", record_type="Communication Timeline", category="restricted_legal").allowed(record_id=incident)
    rows = frappe.get_all("CPCP Communication Attempt", filters={"incident": incident}, order_by="initiated_at asc",
                          fields=["name", "channel", "relationship", "destination_masked", "outcome", "provenance", "duration_label",
                                  "sms_status", "acknowledged", "initiated_at", "message_text", "officer"])
    notice = frappe.db.get_value("CPCP Warning Notice", {"incident": incident}, ["effective_at", "deadline", "proof_basis", "grace_minutes"], as_dict=True)
    return {"attempts": [{"attempt": r.name, "channel": r.channel, "relationship": r.relationship, "destination": r.destination_masked,
                          "outcome": r.outcome or None, "provenance": r.provenance, "duration": r.duration_label,
                          "sms_status": r.sms_status or None, "acknowledged": bool(r.acknowledged), "initiated_at": iso(r.initiated_at),
                          "officer": r.officer, "message_text": r.message_text} for r in rows],
            "notice": None if not notice else {"effective_at": iso(notice.effective_at), "deadline": iso(notice.deadline),
                                               "proof_basis": notice.proof_basis, "grace_minutes": notice.grace_minutes}}


@frappe.whitelist()
def preview_sms(incident: str, contact_id: str) -> dict:
    """Exact text that would be sent, plus the recipient label, before the officer explicitly confirms (PRD 42.2)."""
    inc = _incident(incident)
    actor = authorize("contact_responsible", "C", estate=inc["estate"])
    pb.case_access(actor, incident, action="contact", category="sensitive_personal").allowed(record_id=incident, context="sms preview")
    contact = _pick(inc, contact_id)
    s = frappe.get_single("CPCP Settings")
    zone = frappe.db.get_value("CPCP Zone", inc["zone"], "zone_name") if inc["zone"] else "the estate"
    text = cm.render_template(DEFAULT_SMS_TEMPLATE, {"plate": inc["plate_snapshot"], "zone": zone, "case_id": inc["name"],
                              "security_number": s.security_desk_number or "the security desk"},
                              bool(frappe.db.exists("CPCP Warning Notice", {"incident": incident})))
    return {"text": text, "recipient": f"{contact.relationship.value} ({mask_phone(contact.phone_e164)})", "template_version": TEMPLATE_VERSION}
