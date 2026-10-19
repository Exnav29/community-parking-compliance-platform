# SPDX-License-Identifier: Apache-2.0
"""Resident allegation intake and security triage (PRD 29, 34, 35; AC-43..AC-68).

* An allegation is UNVERIFIED. Nothing here can create a fine, warning clock, tow or driver notice.
* Only security can claim, review and promote; promotion creates a SEPARATE incident.
* Anonymous intake never reads the session, user, unit, device, push token or IP into the record.
"""
import hashlib
import uuid
from datetime import timedelta

import frappe
from frappe.utils import cint

from frappe_cpcp.core import allegations as al
from frappe_cpcp.core import geo
from frappe_cpcp.core.plates import normalize_plate
from frappe_cpcp.permissions import authorize, get_actor
from frappe_cpcp.services.audit import log_audit, log_sensitive_access
from frappe_cpcp.services.common import active_policy, age_minutes, iso, require, to_db, utcnow

ACK_TARGET_MINUTES = 10  # estate-configurable later; escalation job reads this
CATEGORIES = ["Gate or driveway blocked", "Roadway obstruction", "Unsafe parking", "Unauthorized space",
              "Emergency access", "Other"]
ANON_ESTATE_HOURLY_CAP = 30
DEDUP_WINDOW_HOURS = 4


# ---------------------------------------------------------------- intake ----------------------------------------

def _validate_common(estate, category, narrative, lat, lon, accuracy, source):
    if category not in CATEGORIES:
        frappe.throw("Unknown category", frappe.ValidationError)
    narrative = (narrative or "").strip()
    if not narrative or len(narrative) > 2000:
        frappe.throw("Narrative is required (max 2000 characters)", frappe.ValidationError)
    if lat not in (None, "") or lon not in (None, ""):
        lat, lon = float(lat), float(lon)
        if not geo.valid_coordinate(lat, lon):
            frappe.throw("Coordinates are not valid", frappe.ValidationError)
        source = source if source in ("device", "manual_pin") else "manual_pin"
    else:
        lat = lon = accuracy = None
        source = "zone_only" if source == "zone_only" else "none"
    return narrative, lat, lon, (float(accuracy) if accuracy not in (None, "") else None), source


def _plate_hash(plate_text: str | None) -> str | None:
    if not plate_text:
        return None
    try:
        return hashlib.sha256(normalize_plate(plate_text).encode()).hexdigest()
    except ValueError:
        return None


def _dedup_cluster(estate: str, plate_hash: str | None) -> str:
    """Join an open recent allegation about the same plate, else start a new cluster. Reveals no reporter data."""
    if plate_hash:
        cutoff = to_db(utcnow()) - timedelta(hours=DEDUP_WINDOW_HOURS)
        hit = frappe.db.sql(
            """select dedup_cluster from `tabCPCP Parking Allegation`
               where estate=%s and state not in ('Closed','Withdrawn') and dedup_cluster is not null
                 and alleged_plate_hash = %s and submitted_at >= %s order by submitted_at desc limit 1""",
            (estate, plate_hash, cutoff))
        if hit:
            return hit[0][0]
    return "CL-" + uuid.uuid4().hex[:12]


def _create_allegation(*, estate, mode, category, narrative, plate_text, lat, lon, accuracy, source, zone, urgent,
                       client_uuid, reporter_user=None, reporter_unit=None, receipt_id=None) -> "frappe.model.document.Document":
    doc = frappe.get_doc({
        "doctype": "CPCP Parking Allegation", "estate": estate, "mode": mode, "category": category, "narrative": narrative,
        "alleged_plate_text": (plate_text or "").strip().upper() or None, "latitude": lat, "longitude": lon,
        "accuracy_m": accuracy, "location_source": source, "zone": zone, "urgent_claim": 1 if urgent else 0,
        "state": al.State.SUBMITTED.value, "alleged_plate_hash": _plate_hash(plate_text),
        "dedup_cluster": _dedup_cluster(estate, _plate_hash(plate_text)), "receipt_id": receipt_id,
        "client_uuid": client_uuid, "submitted_at": to_db(utcnow()), "reporter_user": reporter_user, "reporter_unit": reporter_unit,
    }).insert(ignore_permissions=True)
    _route_to_security(doc)
    return doc


def _route_to_security(alg) -> None:
    """Atomically (same transaction) create the work item and a durable outbox row per recipient.
    A failed push can never lose the work item: delivery is a separate, retried concern."""
    now = utcnow()
    wi = frappe.get_doc({
        "doctype": "CPCP Security Work Item", "allegation": alg.name, "estate": alg.estate,
        "urgency": "Urgent claimed" if alg.urgent_claim else "Normal", "status": "Open",
        "due_at": to_db(now + timedelta(minutes=ACK_TARGET_MINUTES)),
    }).insert(ignore_permissions=True)
    recipients = frappe.get_all(
        "CPCP Role Assignment", filters={"status": "Active", "estate": alg.estate, "cpcp_role": ["in", ["security_officer", "security_manager"]]},
        fields=["user", "cpcp_role"])
    for r in {(x.user, x.cpcp_role) for x in recipients}:
        frappe.get_doc({
            "doctype": "CPCP Notification Outbox", "work_item": wi.name, "recipient_user": r[0], "recipient_role": r[1],
            "channel": "in_app", "status": "Pending", "idempotency_key": f"{wi.name}:{r[0]}:in_app",
            "payload_minimal": frappe.as_json({"kind": "resident_report", "work_item": wi.name, "category": alg.category,
                                               "urgent": bool(alg.urgent_claim)}),  # no reporter, plate, photo, address
        }).insert(ignore_permissions=True)
    _review_event(alg.name, "Received", actor=None, from_state=al.State.SUBMITTED.value, to_state=al.State.RECEIVED.value)
    frappe.db.set_value("CPCP Parking Allegation", alg.name, "state", al.State.RECEIVED.value, update_modified=False)


def _review_event(allegation, event, actor, from_state="", to_state="", reason=None):
    frappe.get_doc({"doctype": "CPCP Allegation Review Event", "allegation": allegation, "event": event, "actor": actor,
                    "from_state": from_state, "to_state": to_state, "reason": reason}).insert(ignore_permissions=True)


def _check_rate(user: str) -> None:
    limit = cint(frappe.db.get_single_value("CPCP Settings", "allegation_rate_limit_per_hour") or 10)
    cutoff = to_db(utcnow()) - timedelta(hours=1)
    n = frappe.db.count("CPCP Parking Allegation", {"reporter_user": user, "submitted_at": [">=", cutoff]})
    if n >= limit:
        frappe.throw("Too many reports in the last hour; please try again later or contact security directly",
                     frappe.TooManyRequestsError)


@frappe.whitelist(methods=["POST"])
def submit_identified(estate: str, category: str, narrative: str, client_uuid: str, plate_text: str | None = None,
                      latitude=None, longitude=None, accuracy_m=None, location_source: str | None = None,
                      zone: str | None = None, urgent: int = 0) -> dict:
    """Identified report: the authenticated reporter and unit are kept in restricted metadata."""
    actor = authorize("submit_report", "C", estate=estate)
    require(client_uuid, "client_uuid")
    prior = frappe.db.get_value("CPCP Parking Allegation", {"client_uuid": client_uuid}, ["name", "reporter_user"], as_dict=True)
    if prior:
        if prior.reporter_user != actor.user:
            raise frappe.PermissionError("not permitted")
        return {"replayed": True, "reference": prior.name}
    _check_rate(actor.user)
    narrative, lat, lon, acc, src = _validate_common(estate, category, narrative, latitude, longitude, accuracy_m, location_source)
    unit = next(iter(actor.unit_ids), None) if actor.role.value == "resident" else None
    doc = _create_allegation(estate=estate, mode="Identified", category=category, narrative=narrative, plate_text=plate_text,
                             lat=lat, lon=lon, accuracy=acc, source=src, zone=zone, urgent=cint(urgent), client_uuid=client_uuid,
                             reporter_user=actor.user, reporter_unit=unit)
    log_audit(action="allegation_submitted", entity="CPCP Parking Allegation", entity_id=doc.name, role=actor.role.value,
              detail={"mode": "Identified"})
    return {"replayed": False, "reference": doc.name, "status": al.reporter_status(al.State.RECEIVED),
            "note": "Reported as unverified. Security will review; this does not start any warning or fine."}


def _cache_counter(key: str, ttl: int) -> int:
    cache = frappe.cache()
    n = cint(cache.get_value(key) or 0) + 1
    cache.set_value(key, n, expires_in_sec=ttl)
    return n


@frappe.whitelist(allow_guest=True, methods=["POST"])
def submit_anonymous(estate: str, community_code: str, category: str, narrative: str, plate_text: str | None = None,
                     latitude=None, longitude=None, accuracy_m=None, location_source: str | None = None,
                     zone: str | None = None, urgent: int = 0, client_uuid: str | None = None) -> dict:
    """Identity-unlinked intake. Deliberately does NOT read frappe.session.user, headers, IP or device data.

    Estate selection uses a rotating association-wide community code, never a resident login. Abuse control is a
    per-estate hourly cap (no per-person or per-IP tracking is stored).
    """
    if frappe.session.user != "Guest":
        # An authenticated session must not reach this path: it would invite correlation. Clients call it unauthenticated.
        frappe.throw("Anonymous reports must be sent without signing in", frappe.ValidationError)
    key = (frappe.conf.get("cpcp_anon_signing_key") or "").encode()
    if len(key) < 32:
        frappe.throw("Anonymous intake is not configured for this organization", frappe.ValidationError)
    if not frappe.db.exists("CPCP Estate", {"name": estate, "status": "Active"}):
        frappe.throw("Invalid estate or community code", frappe.ValidationError)
    epoch = int(utcnow().timestamp() // (7 * 86400))
    if not al.check_community_code(key, estate, community_code, epoch):
        frappe.throw("Invalid estate or community code", frappe.ValidationError)
    if _cache_counter(f"cpcp:anon:{estate}:{utcnow():%Y%m%d%H}", 3600) > ANON_ESTATE_HOURLY_CAP:
        frappe.throw("This intake is busy; please try again later", frappe.TooManyRequestsError)
    narrative, lat, lon, acc, src = _validate_common(estate, category, narrative, latitude, longitude, accuracy_m, location_source)
    cu = client_uuid or uuid.uuid4().hex
    prior = frappe.db.get_value("CPCP Parking Allegation", {"client_uuid": cu}, "name")
    if prior:
        return {"replayed": True, "note": "Already received. The one-time secret cannot be shown again."}
    receipt = al.new_receipt()
    doc = _create_allegation(estate=estate, mode="Anonymous", category=category, narrative=narrative, plate_text=plate_text,
                             lat=lat, lon=lon, accuracy=acc, source=src, zone=zone, urgent=cint(urgent), client_uuid=cu,
                             receipt_id=receipt.receipt_id)
    al.assert_anonymous_clean(doc.as_dict())
    frappe.get_doc({"doctype": "CPCP Allegation Receipt", "receipt_id": receipt.receipt_id, "allegation": doc.name,
                    "salt": receipt.salt, "verifier": receipt.verifier}).insert(ignore_permissions=True)
    log_audit(action="allegation_submitted", entity="CPCP Parking Allegation", entity_id=doc.name, role="anonymous",
              actor="anonymous", detail={"mode": "Anonymous"})
    return {"replayed": False, "receipt_id": receipt.receipt_id, "secret": receipt.secret,
            "note": "Save this secret now; it is shown once. Without it there is no way to check status or receive follow-up."}


@frappe.whitelist(allow_guest=True, methods=["POST"])
def anonymous_status(receipt_id: str, secret: str) -> dict:
    """Pull-only generic status. Wrong secret and unknown receipt are indistinguishable."""
    if _cache_counter(f"cpcp:anonstatus:{utcnow():%Y%m%d%H%M}", 120) > 120:
        frappe.throw("Please try again shortly", frappe.TooManyRequestsError)
    rec = frappe.db.get_value("CPCP Allegation Receipt", {"receipt_id": receipt_id or ""}, ["allegation", "salt", "verifier"], as_dict=True)
    ok = al.verify_receipt(secret, rec.salt if rec else None, rec.verifier if rec else None)
    if not (ok and rec):
        return {"found": False}
    state = al.State(frappe.db.get_value("CPCP Parking Allegation", rec.allegation, "state"))
    return {"found": True, "status": al.reporter_status(state), "follow_up": "unavailable for anonymous reports"}


@frappe.whitelist()
def my_reports() -> list[dict]:
    """Identified reports of the signed-in reporter ONLY. Anonymous reports never appear in any account."""
    actor = get_actor()
    if actor.role.value != "resident":
        frappe.throw("Residents only", frappe.PermissionError)
    rows = frappe.get_all("CPCP Parking Allegation", filters={"reporter_user": actor.user, "mode": "Identified"},
                          fields=["name", "category", "state", "submitted_at"], order_by="submitted_at desc", limit=100)
    return [{"reference": r.name, "category": r.category, "status": al.reporter_status(al.State(r.state)),
             "submitted_at": iso(r.submitted_at)} for r in rows]


# ---------------------------------------------------------------- triage ----------------------------------------

def _wi(work_item: str):
    row = frappe.db.get_value("CPCP Security Work Item", work_item, ["name", "allegation", "estate", "claimed_by", "status"], as_dict=True)
    if not row:
        raise frappe.PermissionError("not permitted")
    return row


@frappe.whitelist()
def triage_queue(estate: str) -> list[dict]:
    """Estate-scoped queue with a coarse, privacy-safe projection. No reporter fields, plates or photos."""
    actor = authorize("triage_reports", "R", estate=estate)
    rows = frappe.get_all("CPCP Security Work Item", filters={"estate": estate, "status": ["in", ["Open", "Claimed", "Escalated"]]},
                          fields=["name", "allegation", "urgency", "status", "claimed_by", "creation", "acknowledged_at"], order_by="creation asc")
    out = []
    for r in rows:
        mine_or_free = actor.role.value in ("org_admin", "estate_manager", "security_manager") or r.claimed_by in (None, "", actor.user)
        if not mine_or_free:
            continue
        a = frappe.db.get_value("CPCP Parking Allegation", r.allegation, ["category", "state", "mode", "zone", "latitude", "longitude"], as_dict=True)
        coarse = frappe.db.get_value("CPCP Zone", a.zone, "zone_name") if a.zone else (
            f"{round(a.latitude, 3)}, {round(a.longitude, 3)}" if a.latitude is not None else "location not provided")
        out.append({"work_item": r.name, "allegation": r.allegation, "category": a.category, "urgency": r.urgency,
                    "state": a.state, "age_minutes": age_minutes(r.creation), "claimed": bool(r.claimed_by),
                    "claimed_by": r.claimed_by if r.claimed_by in (actor.user,) or actor.role.value != "security_officer" else "another officer",
                    "coarse_location": coarse, "follow_up_available": a.mode != "Anonymous"})
    return out


@frappe.whitelist(methods=["POST"])
def claim_work_item(work_item: str) -> dict:
    """Atomic claim: of two simultaneous officers exactly one wins; the other gets a truthful refusal."""
    wi = _wi(work_item)
    actor = authorize("triage_reports", "U", estate=wi.estate)
    now = to_db(utcnow())
    frappe.db.sql(
        """update `tabCPCP Security Work Item` set claimed_by=%s, claimed_at=%s, acknowledged_at=%s, status='Claimed'
           where name=%s and status='Open' and (claimed_by is null or claimed_by='')""",
        (actor.user, now, now, work_item))
    if frappe.db.sql("select row_count()")[0][0] != 1:
        holder = frappe.db.get_value("CPCP Security Work Item", work_item, "claimed_by")
        frappe.throw("Already claimed by another officer" if holder != actor.user else "You already hold this claim",
                     frappe.DuplicateEntryError)
    state = al.State(frappe.db.get_value("CPCP Parking Allegation", wi.allegation, "state"))
    new = al.transition(state, al.State.UNDER_REVIEW, actor_is_security=True)
    frappe.db.set_value("CPCP Parking Allegation", wi.allegation, "state", new.value, update_modified=False)
    _review_event(wi.allegation, "Claim", actor.user, state.value, new.value)
    frappe.db.sql("update `tabCPCP Notification Outbox` set status='Acknowledged' where work_item=%s and recipient_user=%s", (work_item, actor.user))
    log_audit(action="work_item_claimed", entity="CPCP Security Work Item", entity_id=work_item, role=actor.role.value)
    return {"work_item": work_item, "allegation": wi.allegation, "claimed_by": actor.user}


@frappe.whitelist()
def open_allegation(allegation: str) -> dict:
    """Full resident-submitted content for the claimant/manager. Reporter identity stays hidden by default."""
    a = frappe.db.get_value("CPCP Parking Allegation", allegation,
                            ["name", "estate", "mode", "category", "narrative", "alleged_plate_text", "latitude", "longitude",
                             "accuracy_m", "location_source", "urgent_claim", "state", "submitted_at"], as_dict=True)
    if not a:
        raise frappe.PermissionError("not permitted")
    claimed_by = frappe.db.get_value("CPCP Security Work Item", {"allegation": allegation}, "claimed_by")
    actor = authorize("triage_reports", "R", estate=a.estate, assigned_to=claimed_by or None)
    log_sensitive_access(record_type="Parking Allegation", record_id=allegation, estate=a.estate, context="open", role=actor.role.value)
    return {"allegation": a.name, "label": "UNVERIFIED RESIDENT ALLEGATION", "mode": a.mode, "category": a.category,
            "narrative": a.narrative, "alleged_plate_text": a.alleged_plate_text,
            "location": {"lat": a.latitude, "lon": a.longitude, "accuracy_m": a.accuracy_m, "source": a.location_source,
                         "note": "Reporter-supplied; not verified vehicle position"},
            "urgent_claim": bool(a.urgent_claim), "state": a.state, "submitted_at": iso(a.submitted_at),
            "reporter": "hidden" if a.mode == "Identified" else "follow-up unavailable: anonymous report"}


@frappe.whitelist(methods=["POST"])
def reveal_reporter(allegation: str, reason: str) -> dict:
    """Manager-only, reasoned, logged. Anonymous reports have nothing to reveal."""
    a = frappe.db.get_value("CPCP Parking Allegation", allegation, ["estate", "mode", "reporter_user"], as_dict=True)
    if not a:
        raise frappe.PermissionError("not permitted")
    actor = authorize("triage_reports", "A", estate=a.estate)  # approve-level: security manager / org admin only
    if len((reason or "").strip()) < 10:
        frappe.throw("A documented follow-up purpose (min 10 characters) is required", frappe.ValidationError)
    log_sensitive_access(record_type="Reporter Identity", record_id=allegation, estate=a.estate, context=reason, role=actor.role.value)
    log_audit(action="reporter_identity_revealed", entity="CPCP Parking Allegation", entity_id=allegation, reason=reason, role=actor.role.value)
    if a.mode != "Identified":
        return {"reporter": None, "note": "Anonymous report: no identity is stored."}
    return {"reporter_user": a.reporter_user}


MAX_PHOTO_BYTES = 6 * 1024 * 1024
_MAGIC = {b"\xff\xd8\xff": ("jpg", "image/jpeg"), b"\x89PNG\r\n\x1a\n": ("png", "image/png")}


def _store_evidence_photo(b64: str | None, name: str | None, claimed_sha256: str | None) -> tuple[str | None, str | None]:
    """Validate (type by magic bytes, size), hash server-side, store PRIVATELY. A client hash that disagrees is rejected
    (integrity); the server hash is what gets recorded."""
    if not b64:
        return None, None
    import base64
    import binascii

    if "," in b64[:64]:  # tolerate a data: URL prefix
        b64 = b64.split(",", 1)[1]
    try:
        raw = base64.b64decode(b64, validate=True)
    except (binascii.Error, ValueError):
        frappe.throw("Photo is not valid base64", frappe.ValidationError)
    if not raw or len(raw) > MAX_PHOTO_BYTES:
        frappe.throw("Photo is empty or larger than 6 MB", frappe.ValidationError)
    ext = next((e for magic, (e, _m) in _MAGIC.items() if raw.startswith(magic)), None)
    if ext is None:
        frappe.throw("Only JPEG or PNG evidence photos are accepted", frappe.ValidationError)
    digest = hashlib.sha256(raw).hexdigest()
    if claimed_sha256 and claimed_sha256.lower() != digest:
        frappe.throw("Photo integrity check failed (hash mismatch); capture it again", frappe.ValidationError)
    from frappe.utils.file_manager import save_file

    f = save_file(f"evidence-{digest[:12]}.{ext}", raw, None, None, is_private=1)
    return digest, f.file_url


@frappe.whitelist(methods=["POST"])
def verify_and_create_violation(allegation: str, plate: str, officer_photo_sha256: str | None, device_lat: float, device_lon: float,
                                device_accuracy_m: float, pin_lat: float | None = None, pin_lon: float | None = None,
                                pin_source: str = "device", pin_reason: str | None = None, geofence_override_reason: str | None = None,
                                classification: str = "Ordinary", note: str | None = None, photo_base64: str | None = None,
                                photo_name: str | None = None) -> dict:
    """One guided action: officer attests independently, a NEW linked incident is created, the allegation is untouched."""
    a = frappe.db.get_value("CPCP Parking Allegation", allegation, ["name", "estate", "state", "dedup_cluster"], as_dict=True)
    if not a:
        raise frappe.PermissionError("not permitted")
    wi = frappe.db.get_value("CPCP Security Work Item", {"allegation": allegation}, ["name", "claimed_by"], as_dict=True)
    actor = authorize("verify_incident", "C", estate=a.estate)
    pol = active_policy(a.estate)
    if not pol:
        frappe.throw("No active policy version: an administrator must activate a policy before incidents can be verified", frappe.ValidationError)
    try:
        norm = normalize_plate(plate)
    except ValueError:
        frappe.throw("Officer must confirm a valid plate", frappe.ValidationError)
    if pin_source == "manual_pin" and not (pin_reason or "").strip():
        frappe.throw("A reason is required when the vehicle pin differs from the device reading", frappe.ValidationError)
    if not geo.valid_coordinate(float(device_lat), float(device_lon)):
        frappe.throw("Device coordinates are not valid", frappe.ValidationError)
    boundary = frappe.db.get_value("CPCP Estate", a.estate, "boundary_geojson")
    if boundary:
        poly = [(c[1], c[0]) for c in frappe.parse_json(boundary)["coordinates"][0]]
        pin = (float(pin_lat if pin_lat is not None else device_lat), float(pin_lon if pin_lon is not None else device_lon))
        if geo.geofence_status(pin, poly) != "inside" and not (geofence_override_reason or "").strip():
            frappe.throw("Location is outside the estate boundary; provide an override reason or correct the pin", frappe.ValidationError)

    photo_hash, photo_url = _store_evidence_photo(photo_base64, photo_name, officer_photo_sha256)
    officer_photo_sha256 = photo_hash or officer_photo_sha256
    existing = frappe.db.sql(
        """select i.name from `tabCPCP Violation Incident` i join `tabCPCP Incident Allegation Link` l on l.parent = i.name
           join `tabCPCP Parking Allegation` p on p.name = l.allegation where p.dedup_cluster = %s and p.estate = %s limit 1""",
        (a.dedup_cluster, a.estate))
    try:
        seed = al.promote_to_incident(
            state=al.State(a.state), officer=actor.user, officer_evidence_ids=[officer_photo_sha256 or ""] if officer_photo_sha256 else [],
            rule_version=pol.version_label, officer_has_active_claim=bool(wi and wi.claimed_by == actor.user),
            existing_incident_for_cluster=existing[0][0] if existing else None)
    except al.TriageError as e:
        frappe.throw(str(e), frappe.ValidationError)

    now = utcnow()
    if seed["create"]:
        incident = frappe.get_doc({
            "doctype": "CPCP Violation Incident", "estate": a.estate, "plate_snapshot": plate.strip().upper(), "plate_normalized": norm,
            "classification": classification if classification in ("Ordinary", "Emergency") else "Ordinary", "status": "recorded",
            "verified_by": actor.user, "verified_at": to_db(now), "rule_version": pol.version_label, "policy_version": pol.name,
            "latitude": float(pin_lat if pin_lat is not None else device_lat), "longitude": float(pin_lon if pin_lon is not None else device_lon),
            "accuracy_m": float(device_accuracy_m), "pin_source": pin_source, "pin_correction_reason": pin_reason or geofence_override_reason,
            "allegations": [{"allegation": allegation}]}).insert(ignore_permissions=True).name
    else:
        incident = seed["link_existing"]
        inc = frappe.get_doc("CPCP Violation Incident", incident)
        inc.append("allegations", {"allegation": allegation})
        inc.save(ignore_permissions=True)
    frappe.get_doc({
        "doctype": "CPCP Officer Evidence", "allegation": allegation, "incident": incident, "captured_by": actor.user,
        "captured_at_server": to_db(now), "sha256": officer_photo_sha256, "photo": photo_url, "latitude": float(device_lat), "longitude": float(device_lon),
        "accuracy_m": float(device_accuracy_m), "pin_latitude": float(pin_lat) if pin_lat is not None else None,
        "pin_longitude": float(pin_lon) if pin_lon is not None else None, "pin_source": pin_source, "pin_reason": pin_reason,
        "note": note}).insert(ignore_permissions=True)
    if photo_url:
        evidence = frappe.get_all("CPCP Officer Evidence", filters={"photo": photo_url}, pluck="name", limit=1)
        frappe.db.set_value("File", {"file_url": photo_url}, {"attached_to_doctype": "CPCP Officer Evidence",
                                                             "attached_to_name": evidence[0], "attached_to_field": "photo"})
    new_state = al.transition(al.State(a.state), al.State.VERIFIED, actor_is_security=True)
    frappe.db.set_value("CPCP Parking Allegation", allegation, "state", new_state.value, update_modified=False)
    frappe.db.set_value("CPCP Security Work Item", wi.name, "status", "Closed", update_modified=False)
    _review_event(allegation, "Verify", actor.user, a.state, new_state.value, reason=f"incident {incident}")
    log_audit(action="allegation_verified", entity="CPCP Violation Incident", entity_id=incident, role=actor.role.value,
              detail={"allegation": allegation, "created": seed["create"], "policy": pol.name})
    return {"incident": incident, "created": seed["create"], "rule_version": pol.version_label,
            "financial_consequence": "none - fines, warnings and enforcement remain separately gated"}


@frappe.whitelist(methods=["POST"])
def close_allegation(allegation: str, outcome: str, reason: str) -> dict:
    """Not Substantiated / Resolved / Duplicate. Never generates a warning, fee, clamp or tow."""
    outcomes = {"Not Substantiated": al.State.NOT_SUBSTANTIATED, "Resolved without Violation": al.State.RESOLVED,
                "Duplicate / Merged": al.State.DUPLICATE}
    if outcome not in outcomes:
        frappe.throw("Unknown outcome", frappe.ValidationError)
    a = frappe.db.get_value("CPCP Parking Allegation", allegation, ["estate", "state"], as_dict=True)
    if not a:
        raise frappe.PermissionError("not permitted")
    wi = frappe.db.get_value("CPCP Security Work Item", {"allegation": allegation}, ["name", "claimed_by"], as_dict=True)
    actor = authorize("triage_reports", "U", estate=a.estate, assigned_to=wi.claimed_by if wi else None)
    try:
        new = al.transition(al.State(a.state), outcomes[outcome], actor_is_security=True, reason=reason)
    except al.TriageError as e:
        frappe.throw(str(e), frappe.ValidationError)
    frappe.db.set_value("CPCP Parking Allegation", allegation, "state", new.value, update_modified=False)
    if wi:
        frappe.db.set_value("CPCP Security Work Item", wi.name, "status", "Closed", update_modified=False)
    _review_event(allegation, "Dismiss" if outcome != "Duplicate / Merged" else "Duplicate", actor.user, a.state, new.value, reason)
    log_audit(action="allegation_closed", entity="CPCP Parking Allegation", entity_id=allegation, reason=reason, role=actor.role.value)
    return {"allegation": allegation, "state": new.value}
