# SPDX-License-Identifier: Apache-2.0
"""Canonical incident / parking-episode service (PRD 60).

Concurrency model (MariaDB/InnoDB, REPEATABLE READ):
  * identity is a UNIQUE column that is non-NULL only while an episode is live (``active_key`` on incidents,
    ``cluster_key`` on open work items, ``link_key`` on links, ``active_key`` on live enforcement actions);
  * find-or-create = INSERT inside a savepoint; a duplicate-key error means someone else won, so we then read the
    winner with a LOCKING read (``FOR UPDATE``), because a plain SELECT may use an older snapshot and miss it;
  * rows that gate a state change (work item, incident) are locked ``FOR UPDATE`` before they are read.
"""
from __future__ import annotations

import uuid
from datetime import timedelta

import frappe

from frappe_cpcp.core import allegations as al
from frappe_cpcp.core import episodes as ep
from frappe_cpcp.core import matching as mt
from frappe_cpcp.core.plates import normalize_plate
from frappe_cpcp.services.audit import log_audit
from frappe_cpcp.services.common import to_db, utcnow

ACK_TARGET_MINUTES = 10
# Frappe raises UniqueValidationError for non-name unique indexes and DuplicateEntryError for the primary key.
UNIQUE_ERRORS = (frappe.DuplicateEntryError, frappe.UniqueValidationError)
LINK_LIVE = ("Confirmed", "Auto Candidate", "Late", "Merged from")


# ---------------------------------------------------------------- helpers ----------------------------------------

def plate_of(plate_text: str | None) -> str | None:
    if not plate_text:
        return None
    try:
        return normalize_plate(plate_text)
    except ValueError:
        return None


def _try_insert(doc) -> bool:
    """INSERT in a savepoint. True = we created it; False = unique key lost to a concurrent winner."""
    sp = "cpcp_" + uuid.uuid4().hex[:8]
    frappe.db.savepoint(sp)
    doc.flags.ignore_links = True  # every referenced row was read with a locking read; a plain-read link check could miss fresh commits
    try:
        doc.insert(ignore_permissions=True)
        return True
    except UNIQUE_ERRORS:
        frappe.db.rollback(save_point=sp)
        return False


def _lease_hours() -> int:
    return int(frappe.db.get_single_value("CPCP Settings", "claim_lease_hours") or 8)


def incident_by_key(key: str, lock: bool = True) -> dict | None:
    rows = frappe.db.sql(
        "select name, estate, episode_status, latitude, longitude, accuracy_m, zone, assigned_officer, priority, plate_normalized, status, "
        "classification, merged_into from `tabCPCP Violation Incident` where active_key = %s" + (" for update" if lock else ""), (key,), as_dict=True)
    return rows[0] if rows else None


def work_item_by_key(key: str, lock: bool = True) -> dict | None:
    rows = frappe.db.sql(
        "select name, estate, status, incident, claimed_by, urgency, allegation, allegation_count from `tabCPCP Security Work Item` where cluster_key = %s"
        + (" for update" if lock else ""), (key,), as_dict=True)
    return rows[0] if rows else None


def lock_incident(name: str) -> dict:
    rows = frappe.db.sql(
        "select name, estate, episode_status, active_key, assigned_officer, priority, status, classification, merged_into, plate_normalized "
        "from `tabCPCP Violation Incident` where name = %s for update", (name,), as_dict=True)
    if not rows:
        raise frappe.PermissionError("not permitted")
    return rows[0]


def lock_work_item(name: str) -> dict:
    rows = frappe.db.sql(
        "select name, estate, status, incident, claimed_by, lease_expires_at, urgency, allegation, cluster_key, allegation_count "
        "from `tabCPCP Security Work Item` where name = %s for update", (name,), as_dict=True)
    if not rows:
        raise frappe.PermissionError("not permitted")
    return rows[0]


def locked_get(doctype: str, name: str, fields: tuple[str, ...]) -> dict | None:
    """Locking read (FOR UPDATE). Under REPEATABLE READ a plain SELECT may use a snapshot older than a concurrent commit, so
    every read taken INSIDE a critical section (after a conflict, or while deciding membership) must be a locking read."""
    cols = ", ".join(f"`{f}`" for f in fields)
    rows = frappe.db.sql(f"select {cols} from `tab{doctype}` where name = %s for update", (name,), as_dict=True)
    return rows[0] if rows else None


def members_of(wi_name: str, primary: str | None = None) -> list[str]:
    rows = frappe.db.sql("select allegation from `tabCPCP Work Item Allegation` where parent = %s order by idx for update", (wi_name,))
    out = [r[0] for r in rows]
    return out or ([primary] if primary else [])


def locked_count(sql: str, params: tuple) -> int:
    return int(frappe.db.sql(sql + " for update", params)[0][0])


def work_item_for_allegation(allegation: str) -> str | None:
    n = frappe.db.get_value("CPCP Security Work Item", {"allegation": allegation}, "name")
    if n:
        return n
    rows = frappe.db.sql("select parent from `tabCPCP Work Item Allegation` where allegation = %s limit 1", (allegation,))
    return rows[0][0] if rows else None


def _features(alg: dict, inc: dict, plate_match: bool | None) -> mt.Features:
    a_pt = (alg["latitude"], alg["longitude"]) if alg.get("latitude") is not None else None
    i_pt = (inc["latitude"], inc["longitude"]) if inc.get("latitude") is not None else None
    dist = mt.distance_between(a_pt, i_pt)
    zone = None if not (alg.get("zone") and inc.get("zone")) else alg["zone"] == inc["zone"]
    return mt.Features(plate_match=plate_match, same_zone=zone, distance_m=dist,
                       accuracy_sum_m=float(alg.get("accuracy_m") or 0) + float(inc.get("accuracy_m") or 0), case_active=True)


def _recipients(estate: str, roles: tuple[str, ...]) -> list[tuple[str, str]]:
    rows = frappe.get_all("CPCP Role Assignment", filters={"status": "Active", "estate": estate, "cpcp_role": ["in", list(roles)]}, fields=["user", "cpcp_role"])
    return sorted({(r.user, r.cpcp_role) for r in rows})


def _outbox(work_ref: str, users: list[tuple[str, str]], kind: str, key_part: str, payload: dict) -> None:
    for user, role in users:
        key = f"{kind}:{key_part}:{user}"
        if frappe.db.exists("CPCP Notification Outbox", {"idempotency_key": key}):
            continue
        is_wi = bool(frappe.db.exists("CPCP Security Work Item", work_ref))
        is_inc = (not is_wi) and bool(frappe.db.exists("CPCP Violation Incident", work_ref))
        frappe.get_doc({"doctype": "CPCP Notification Outbox", "work_item": work_ref if is_wi else None, "incident": work_ref if is_inc else None, "ref": work_ref,
                        "recipient_user": user, "recipient_role": role, "channel": "in_app", "status": "Pending", "idempotency_key": key,
                        "payload_minimal": frappe.as_json({"kind": kind, **payload})}).insert(ignore_permissions=True)  # no reporter, plate, photo or address


def review_event(allegation: str, event: str, actor: str | None, from_state: str = "", to_state: str = "", reason: str | None = None) -> None:
    frappe.get_doc({"doctype": "CPCP Allegation Review Event", "allegation": allegation, "event": event, "actor": actor,
                    "from_state": from_state, "to_state": to_state, "reason": reason}).insert(ignore_permissions=True)


def set_allegation_state(allegation: str, new_state: str, event: str, actor: str | None, reason: str | None = None) -> None:
    row = locked_get("CPCP Parking Allegation", allegation, ("state",))
    old = row["state"] if row else None
    if old != new_state:
        frappe.db.set_value("CPCP Parking Allegation", allegation, "state", new_state, update_modified=False)
        review_event(allegation, event, actor, old or "", new_state, reason)


# ---------------------------------------------------------------- episode state ----------------------------------

def apply_event(incident: str, event: str, *, strict: bool = False) -> str:
    """Advance the episode state machine. Non-strict: an event that does not apply leaves the state alone."""
    cur = frappe.db.get_value("CPCP Violation Incident", incident, "episode_status") or ep.Episode.VERIFIED_OPEN.value
    try:
        new = ep.apply(ep.Episode(cur), event)
    except ep.EpisodeError:
        if strict:
            raise
        return cur
    frappe.db.set_value("CPCP Violation Incident", incident, "episode_status", new.value, update_modified=False)
    return new.value


def incident_state(incident: str) -> ep.Episode:
    return ep.Episode(frappe.db.get_value("CPCP Violation Incident", incident, "episode_status") or ep.Episode.VERIFIED_OPEN.value)


# ---------------------------------------------------------------- linking ----------------------------------------

def attach_to_incident(incident: str, allegation: str, *, link_state: str, reason: str, confidence: float | None = None,
                       actor: str | None = None) -> bool:
    """Create an explicit incident-allegation link. Idempotent (unique link_key); never overwrites the allegation."""
    inc = lock_incident(incident)
    link_key = f"{incident}:{allegation}"
    if frappe.db.exists("CPCP Incident Allegation Link", {"link_key": link_key}):
        return False
    n = locked_count("select count(*) from `tabCPCP Incident Allegation Link` where parent=%s", (incident,))
    doc = frappe.get_doc({"doctype": "CPCP Incident Allegation Link", "parent": incident, "parenttype": "CPCP Violation Incident",
                          "parentfield": "allegations", "idx": n + 1, "allegation": allegation, "link_state": link_state,
                          "join_reason": reason, "matcher_confidence": confidence, "linked_by": actor, "linked_at": to_db(utcnow()),
                          "link_key": link_key})
    if not _try_insert(doc):
        return False
    live = locked_count("select count(*) from `tabCPCP Incident Allegation Link` where parent=%s and link_state in %s", (incident, LINK_LIVE))
    frappe.db.set_value("CPCP Violation Incident", incident, {"allegation_count": live, "last_observed_at": to_db(utcnow())}, update_modified=False)
    a = locked_get("CPCP Parking Allegation", allegation, ("urgent_claim", "estate"))
    if a["urgent_claim"] and inc["priority"] != "Urgent claimed":
        frappe.db.set_value("CPCP Violation Incident", incident, "priority", "Urgent claimed", update_modified=False)  # priority only: no approvals bypassed
        _outbox(incident, _recipients(inc["estate"], ("security_manager",)), "priority_escalated", f"{incident}:{allegation}", {"incident": incident, "urgent": True})
        log_audit(action="priority_escalated", entity="CPCP Violation Incident", entity_id=incident, reason="urgent additional report")
    if link_state == "Confirmed":
        set_allegation_state(allegation, al.State.VERIFIED.value, "Verify", actor, f"linked to incident {incident}")
    else:
        set_allegation_state(allegation, al.State.RECEIVED.value, "Received", None, "attached as candidate to an existing case")
    notify = [(inc["assigned_officer"], "security_officer")] if inc["assigned_officer"] else _recipients(inc["estate"], ("security_manager",))
    _outbox(incident, notify, "report_update", f"{incident}:{allegation}", {"incident": incident, "count": live, "urgent": bool(a["urgent_claim"])})
    log_audit(action="allegation_linked", entity="CPCP Violation Incident", entity_id=incident, reason=reason,
              detail={"allegation": allegation, "state": link_state, "confidence": confidence})
    return True


def join_work_item(wi_name: str, allegation: str, *, reason: str, confidence: float | None = None) -> str:
    """Add an allegation to an existing open work item (no new claimable item). If the item was already promoted to an
    incident while we waited for its lock, the allegation is attached to that incident instead."""
    wi = lock_work_item(wi_name)
    if wi["incident"]:
        attach_to_incident(wi["incident"], allegation, link_state="Auto Candidate", reason=reason, confidence=confidence)
        return "attached_incident"
    link_key = f"{wi_name}:{allegation}"
    if frappe.db.exists("CPCP Work Item Allegation", {"link_key": link_key}):
        return "joined_work_item"
    n = locked_count("select count(*) from `tabCPCP Work Item Allegation` where parent=%s", (wi_name,))
    doc = frappe.get_doc({"doctype": "CPCP Work Item Allegation", "parent": wi_name, "parenttype": "CPCP Security Work Item",
                          "parentfield": "allegations", "idx": n + 1, "allegation": allegation, "joined_at": to_db(utcnow()),
                          "join_reason": reason, "match_confidence": confidence, "link_key": link_key})
    if not _try_insert(doc):
        return "joined_work_item"
    cnt = locked_count("select count(*) from `tabCPCP Work Item Allegation` where parent=%s", (wi_name,))
    updates = {"allegation_count": cnt, "latest_at": to_db(utcnow())}
    a = (locked_get("CPCP Parking Allegation", allegation, ("urgent_claim",)) or {}).get("urgent_claim")
    if a and wi["urgency"] != "Urgent claimed":
        updates["urgency"] = "Urgent claimed"
        _outbox(wi_name, _recipients(wi["estate"], ("security_manager",)), "priority_escalated", f"{wi_name}:{allegation}", {"work_item": wi_name, "urgent": True})
    frappe.db.set_value("CPCP Security Work Item", wi_name, updates, update_modified=False)
    set_allegation_state(allegation, al.State.RECEIVED.value, "Received", None, "joined an open case")
    if wi["claimed_by"]:
        _outbox(wi_name, [(wi["claimed_by"], "security_officer")], "report_update", f"{wi_name}:{allegation}", {"work_item": wi_name, "count": cnt, "urgent": bool(a)})
    return "joined_work_item"


def create_work_item(alg: dict, *, cluster_key: str | None, review_incident: str | None = None, review_note: str | None = None) -> tuple[str, bool]:
    """Find-or-create. With a cluster_key the UNIQUE index guarantees a single open item per estate+plate."""
    now = utcnow()
    doc = frappe.get_doc({
        "doctype": "CPCP Security Work Item", "allegation": alg["name"], "estate": alg["estate"], "cluster_key": cluster_key,
        "urgency": "Urgent claimed" if alg.get("urgent_claim") else "Normal", "status": "Open", "allegation_count": 1,
        "latest_at": to_db(now), "due_at": to_db(now + timedelta(minutes=ACK_TARGET_MINUTES)),
        "candidate_incident": review_incident, "review_needed": 1 if (review_incident or review_note) else 0, "review_note": review_note,
        "allegations": [{"allegation": alg["name"], "joined_at": to_db(now), "join_reason": "first report", "link_key": None}],
    })
    sp = "cpcp_" + uuid.uuid4().hex[:8]
    frappe.db.savepoint(sp)
    doc.flags.ignore_links = True
    try:
        doc.insert(ignore_permissions=True)
    except UNIQUE_ERRORS:
        frappe.db.rollback(save_point=sp)
        if cluster_key is None:
            raise
        winner = work_item_by_key(cluster_key, lock=True)
        if winner is None:
            raise
        return winner["name"], False
    frappe.db.set_value("CPCP Work Item Allegation", {"parent": doc.name, "allegation": alg["name"]}, "link_key", f"{doc.name}:{alg['name']}", update_modified=False)
    users = _recipients(alg["estate"], ("security_officer", "security_manager"))
    _outbox(doc.name, users, "resident_report", doc.name,
            {"work_item": doc.name, "category": alg["category"], "urgent": bool(alg.get("urgent_claim"))})
    set_allegation_state(alg["name"], al.State.RECEIVED.value, "Received", None)
    return doc.name, True


# ---------------------------------------------------------------- routing ----------------------------------------

def route_allegation(alg: dict) -> dict:
    """Stage 1 (candidate discovery) + atomic placement. Never creates an incident, a clock or a charge."""
    norm = plate_of(alg.get("alleged_plate_text"))
    key = ep.active_key(alg["estate"], norm)
    if key:
        # LOCK ORDER (prevents deadlock with promote_work_item): work item first, then incident.
        existing = work_item_by_key(key, lock=True)
        if existing:
            first = locked_get("CPCP Parking Allegation", existing["allegation"], ("latitude", "longitude", "accuracy_m", "zone"))
            d = mt.evaluate(_features(alg, first, True))
            if d.outcome == mt.Outcome.ATTACH_CANDIDATE:
                res = join_work_item(existing["name"], alg["name"], reason=d.reason, confidence=d.confidence)
                return {"action": res, "work_item": existing["name"]}
            wi, _ = create_work_item(alg, cluster_key=None, review_note=f"same plate as {existing['name']} but {d.reason}")
            return {"action": "review_candidate", "work_item": wi, "reason": d.reason}
        inc = incident_by_key(key, lock=True)  # live OR positively-unresolved episode for this vehicle
        if inc:
            d = mt.evaluate(_features(alg, inc, True))
            if d.outcome == mt.Outcome.ATTACH_CANDIDATE:
                attach_to_incident(inc["name"], alg["name"], link_state="Auto Candidate", reason=d.reason, confidence=d.confidence)
                return {"action": "attached_incident", "incident": inc["name"], "confidence": d.confidence}
            wi, created = create_work_item(alg, cluster_key=None, review_incident=inc["name"], review_note=d.reason)
            return {"action": "review_candidate", "work_item": wi, "incident": inc["name"], "reason": d.reason}
        # no episode and no open work item: the UNIQUE cluster_key lets exactly one concurrent creator win
        wi, created = create_work_item(alg, cluster_key=key)
        if not created:  # lost the race for the unique key: join the winner
            res = join_work_item(wi, alg["name"], reason="concurrent first reports", confidence=0.9)
            return {"action": res, "work_item": wi}
        return {"action": "new_work_item", "work_item": wi}
    # no usable plate: never auto-merged; offer the closest active episode to the reviewer
    best, best_c, best_d = None, 0.0, float("inf")
    for inc in frappe.db.sql(
            "select name, latitude, longitude, accuracy_m, zone from `tabCPCP Violation Incident` where estate=%s and active_key is not null",
            (alg["estate"],), as_dict=True):
        f = _features(alg, inc, None)
        d = mt.evaluate(f)
        dist = f.distance_m if f.distance_m is not None else 1e9
        if d.outcome == mt.Outcome.REVIEW and (d.confidence > best_c or (d.confidence == best_c and dist < best_d)):
            best, best_c, best_d = inc["name"], d.confidence, dist
    wi, _ = create_work_item(alg, cluster_key=None, review_incident=best, review_note="no usable plate" if not best else "no usable plate; possible related case")
    return {"action": "review_candidate" if best else "new_work_item", "work_item": wi, "incident": best}


# ---------------------------------------------------------------- promotion --------------------------------------

def promote_work_item(wi_name: str, officer: str, *, plate_text: str, norm: str, classification: str, pol: dict, location: dict,
                      pin_source: str, pin_reason: str | None) -> tuple[str, bool]:
    """Turn a (locked) work item into the canonical incident, or link it to the one that already exists."""
    wi = lock_work_item(wi_name)
    estate = wi["estate"]
    key = ep.active_key(estate, norm)
    members = members_of(wi_name, wi["allegation"])
    submitted = [(locked_get("CPCP Parking Allegation", m, ("submitted_at",)) or {}).get("submitted_at") for m in members]
    now = utcnow()
    links = [{"allegation": m, "link_state": "Confirmed", "join_reason": "confirmed by officer verification", "linked_by": officer,
              "linked_at": to_db(now), "link_key": None} for m in members]
    doc = frappe.get_doc({
        "doctype": "CPCP Violation Incident", "estate": estate, "plate_snapshot": plate_text.strip().upper(), "plate_normalized": norm,
        "plate_hash": ep.plate_hash(norm), "active_key": key, "classification": classification, "status": "recorded",
        "episode_status": ep.Episode.VERIFIED_OPEN.value, "verified_by": officer, "assigned_officer": officer, "verified_at": to_db(now),
        "first_observed_at": min(s for s in submitted if s) if any(submitted) else to_db(now), "last_observed_at": to_db(now),
        "allegation_count": len(members), "priority": wi["urgency"], "rule_version": pol["version_label"], "policy_version": pol["name"],
        "latitude": location["lat"], "longitude": location["lon"], "accuracy_m": location["accuracy_m"], "pin_source": pin_source,
        "pin_correction_reason": pin_reason, "allegations": links})
    created = _try_insert(doc)
    if created:
        for m in members:
            frappe.db.set_value("CPCP Incident Allegation Link", {"parent": doc.name, "allegation": m}, "link_key", f"{doc.name}:{m}", update_modified=False)
        incident = doc.name
    else:
        existing = incident_by_key(key, lock=True) if key else None
        if not existing:
            raise frappe.ValidationError("Could not place the incident; please retry")
        incident = existing["name"]
        for m in members:
            attach_to_incident(incident, m, link_state="Confirmed", reason="officer verification matched an existing episode", actor=officer)
    for m in members:
        set_allegation_state(m, al.State.VERIFIED.value, "Verify", officer, f"incident {incident}")
    frappe.db.set_value("CPCP Security Work Item", wi_name, {"status": "Closed", "incident": incident, "cluster_key": None}, update_modified=False)
    return incident, created


# ---------------------------------------------------------------- end of episode ---------------------------------

LIVE_ACTION_STATES = ("Proposed", "Approved", "Executed")


def end_episode(incident: str, evidence: ep.EndEvidence, note: str, actor: str) -> dict:
    inc = lock_incident(incident)
    live = frappe.db.count("CPCP Enforcement Action", {"incident": incident, "status": ["in", list(LIVE_ACTION_STATES)], "release_at": ["is", "not set"],
                                                      "action_type": ["in", ["Clamp", "Tow"]]})
    if live and evidence != ep.EndEvidence.MANAGER_DETERMINATION:
        raise frappe.ValidationError("A clamp or tow is still live: release it first. Clamp removal alone is not proof the vehicle left.")
    state = ep.Episode(inc["episode_status"])
    if state != ep.Episode.RESOLVED_CLOSED:
        for event in ("release_started", "closed") if state in (ep.Episode.CLAMP_ACTIVE, ep.Episode.TOWED_IMPOUNDED, ep.Episode.TOW_ORDERED) else ("closed",):
            try:
                state = ep.apply(state, event)
            except ep.EpisodeError:
                if event == "closed":
                    raise
    updates = {"episode_status": state.value, "ended_at": to_db(utcnow()), "end_evidence": evidence.value, "end_note": note}
    if ep.releases_identity(evidence):
        updates["active_key"] = None  # a later offense by this vehicle can now be a NEW episode
    frappe.db.set_value("CPCP Violation Incident", incident, updates, update_modified=False)
    log_audit(action="episode_ended", entity="CPCP Violation Incident", entity_id=incident, reason=note,
              detail={"evidence": evidence.value, "identity_released": ep.releases_identity(evidence)})
    return {"incident": incident, "episode_status": state.value, "identity_released": ep.releases_identity(evidence)}
