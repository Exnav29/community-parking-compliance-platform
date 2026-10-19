# SPDX-License-Identifier: Apache-2.0
"""Incident / parking-episode lifecycle management (PRD 60).

* Officers (the assigned one) review candidate links, end an episode with positive evidence, link late reports.
* Managers merge, split, reassign, reopen and credit a duplicated penalty. Nothing is ever deleted: merges and splits
  add link rows, flag the ledger for review and write audit events.
"""
from decimal import Decimal

import frappe
from frappe.utils import cint

from frappe_cpcp.core import allegations as al
from frappe_cpcp.core import charges as ch
from frappe_cpcp.core import episodes as ep
from frappe_cpcp.core import geo
from frappe_cpcp.core.plates import mask_plate
from frappe_cpcp.permissions import authorize
from frappe_cpcp.services import episodes as svc
from frappe_cpcp.services.audit import log_audit
from frappe_cpcp.services.common import deadlock_retry, iso, require, to_db, utcnow

MANAGER_ROLES = ("security_manager", "org_admin", "estate_manager")


def _inc(name: str) -> dict:
    row = frappe.db.get_value("CPCP Violation Incident", name,
                              ["name", "estate", "episode_status", "assigned_officer", "active_key", "plate_snapshot", "merged_into", "penalty_review"], as_dict=True)
    if not row:
        raise frappe.PermissionError("not permitted")
    return row


def _is_manager(actor) -> bool:
    return actor.role.value in MANAGER_ROLES


# ---------------------------------------------------------------- resident precheck ----------------------------

@frappe.whitelist(methods=["POST"])
@deadlock_retry
def precheck_similar(estate: str, latitude=None, longitude=None) -> dict:
    """Privacy-safe hint before submitting. Location only (never a plate, so it cannot be used to probe which vehicles are
    being handled); same shape every time; reveals no reporter, unit, officer, plate or enforcement state."""
    actor = authorize("submit_report", "C", estate=estate)
    cache = frappe.cache()
    k = f"cpcp:precheck:{actor.user}:{utcnow():%Y%m%d%H%M}"
    n = cint(cache.get_value(k) or 0) + 1
    cache.set_value(k, n, expires_in_sec=120)
    if n > 12:
        frappe.throw("Please wait a moment", frappe.TooManyRequestsError)
    similar = False
    if latitude not in (None, "") and longitude not in (None, ""):
        here = (float(latitude), float(longitude))
        pts = frappe.db.sql(
            "select latitude, longitude from `tabCPCP Violation Incident` where estate=%s and active_key is not null and latitude is not null "
            "union all select a.latitude, a.longitude from `tabCPCP Security Work Item` w join `tabCPCP Parking Allegation` a on a.name=w.allegation "
            "where w.estate=%s and w.status in ('Open','Claimed','Escalated') and a.latitude is not null", (estate, estate))
        similar = any(geo.haversine_m(here, (p[0], p[1])) <= 100 for p in pts)
    return {"similar": similar, "message": "Security may already be reviewing a similar parking concern. You can add your observation to help." if similar else ""}


# ---------------------------------------------------------------- officer review ------------------------------

@frappe.whitelist()
def incident_candidates(incident: str) -> dict:
    """Reports attached to a case, each inspectable separately, with the join reason and confidence."""
    inc = _inc(incident)
    authorize("triage_reports", "R", estate=inc["estate"], assigned_to=inc["assigned_officer"])
    rows = frappe.db.sql(
        """select l.allegation, l.link_state, l.join_reason, l.matcher_confidence, l.linked_at, a.category, a.urgent_claim, a.submitted_at, a.mode
           from `tabCPCP Incident Allegation Link` l join `tabCPCP Parking Allegation` a on a.name = l.allegation
           where l.parent = %s order by a.submitted_at asc""", (incident,), as_dict=True)
    return {"incident": incident, "episode_status": inc["episode_status"],
            "already_being_handled": ep.already_being_handled(ep.Episode(inc["episode_status"])),
            "reports": [{"allegation": r.allegation, "link_state": r.link_state, "reason": r.join_reason, "confidence": r.matcher_confidence,
                         "category": r.category, "urgent": bool(r.urgent_claim), "submitted_at": iso(r.submitted_at),
                         "source": "anonymous" if r.mode == "Anonymous" else "identified"} for r in rows]}


@frappe.whitelist(methods=["POST"])
@deadlock_retry
def review_candidate(incident: str, allegation: str, action: str, reason: str) -> dict:
    """Link to Existing / Create Separate / Needs Investigation / Not Related. Reason is mandatory and audited."""
    inc = _inc(incident)
    actor = authorize("triage_reports", "U", estate=inc["estate"], assigned_to=inc["assigned_officer"])
    if action not in ("link", "separate", "needs_investigation", "not_related") or not (reason or "").strip():
        frappe.throw("A valid action and a reason are required", frappe.ValidationError)
    svc.lock_incident(incident)
    link = frappe.db.get_value("CPCP Incident Allegation Link", {"parent": incident, "allegation": allegation}, ["name", "link_state"], as_dict=True)
    if not link:
        raise frappe.PermissionError("not permitted")
    if action == "link":
        frappe.db.set_value("CPCP Incident Allegation Link", link.name, {"link_state": "Confirmed", "linked_by": actor.user, "linked_at": to_db(utcnow())}, update_modified=False)
        svc.set_allegation_state(allegation, al.State.VERIFIED.value, "Verify", actor.user, f"linked to {incident}: {reason}")
    elif action in ("separate", "not_related"):
        frappe.db.set_value("CPCP Incident Allegation Link", link.name, {"link_state": "Rejected", "linked_by": actor.user, "linked_at": to_db(utcnow())}, update_modified=False)
        row = frappe.db.get_value("CPCP Parking Allegation", allegation, ["name", "estate", "category", "urgent_claim"], as_dict=True)
        svc.set_allegation_state(allegation, al.State.RECEIVED.value, "Received", actor.user, f"{action}: {reason}")
        svc.create_work_item(dict(row), cluster_key=None, review_note=f"{action} from {incident}: {reason}")
    else:
        svc.review_event(allegation, "Note", actor.user, reason=f"needs investigation: {reason}")
    live = frappe.db.sql("select count(*) from `tabCPCP Incident Allegation Link` where parent=%s and link_state in %s", (incident, svc.LINK_LIVE))[0][0]
    frappe.db.set_value("CPCP Violation Incident", incident, "allegation_count", live, update_modified=False)
    log_audit(action=f"candidate_{action}", entity="CPCP Violation Incident", entity_id=incident, reason=reason, role=actor.role.value, detail={"allegation": allegation})
    return {"incident": incident, "allegation": allegation, "action": action, "reports_in_case": live}


@frappe.whitelist(methods=["POST"])
@deadlock_retry
def end_episode(incident: str, evidence: str, note: str) -> dict:
    """Record that the parking episode ENDED, with positive evidence. Payment, clamp removal, a new day or a shift change are rejected."""
    inc = _inc(incident)
    try:
        ev = ep.parse_end_evidence(evidence)
    except ep.EpisodeError as e:
        frappe.throw(str(e), frappe.ValidationError)
    actor = authorize("approve_enforcement", "A", estate=inc["estate"]) if ev == ep.EndEvidence.MANAGER_DETERMINATION else \
        authorize("triage_reports", "U", estate=inc["estate"], assigned_to=inc["assigned_officer"])
    if not (note or "").strip():
        frappe.throw("A note describing what was observed is required", frappe.ValidationError)
    try:
        res = svc.end_episode(incident, ev, note, actor.user)
    except ep.EpisodeError as e:
        frappe.throw(str(e), frappe.ValidationError)
    return res


@frappe.whitelist(methods=["POST"])
@deadlock_retry
def reopen_episode(incident: str, reason: str) -> dict:
    inc = _inc(incident)
    actor = authorize("approve_enforcement", "A", estate=inc["estate"])
    require((reason or "").strip(), "reason")
    svc.lock_incident(incident)
    if not inc["active_key"]:
        norm = frappe.db.get_value("CPCP Violation Incident", incident, "plate_normalized")
        key = ep.active_key(inc["estate"], norm)
        if key and svc.incident_by_key(key, lock=True):
            frappe.throw("A newer episode exists for this vehicle; link reports to it instead", frappe.ValidationError)
        frappe.db.set_value("CPCP Violation Incident", incident, "active_key", key, update_modified=False)
    try:
        svc.apply_event(incident, "reopened", strict=True)
    except ep.EpisodeError as e:
        frappe.throw(str(e), frappe.ValidationError)
    frappe.db.set_value("CPCP Violation Incident", incident, {"ended_at": None, "end_evidence": None}, update_modified=False)
    log_audit(action="episode_reopened", entity="CPCP Violation Incident", entity_id=incident, reason=reason, role=actor.role.value)
    return {"incident": incident, "episode_status": svc.incident_state(incident).value}


@frappe.whitelist(methods=["POST"])
@deadlock_retry
def link_late_allegation(allegation: str, incident: str, reason: str) -> dict:
    """Link a report to an existing case ("Link to Existing"). For an episode that has already ended it is a LATE link: an audit
    marker only, no state change and no charge. For a live episode it is a confirmed link."""
    i = _inc(incident)
    a = frappe.db.get_value("CPCP Parking Allegation", allegation, ["estate", "name"], as_dict=True)
    if not a or a.estate != i["estate"]:
        raise frappe.PermissionError("not permitted")
    actor = authorize("triage_reports", "U", estate=i["estate"], assigned_to=i["assigned_officer"])
    require((reason or "").strip(), "reason")
    ended = bool(frappe.db.get_value("CPCP Violation Incident", incident, "ended_at"))
    state = "Late" if ended else "Confirmed"
    ok = svc.attach_to_incident(incident, allegation, link_state=state, reason=f"{state.lower()} link: {reason}", actor=actor.user)
    wi = svc.work_item_for_allegation(allegation)
    if wi and frappe.db.count("CPCP Work Item Allegation", {"parent": wi}) <= 1:  # a solo work item is now redundant
        frappe.db.set_value("CPCP Security Work Item", wi, {"status": "Closed", "cluster_key": None, "incident": incident}, update_modified=False)
    return {"linked": ok, "incident": incident, "link_state": state,
            "note": "Recorded against the existing case. No new charge was created."}


# ---------------------------------------------------------------- manager operations ---------------------------

@frappe.whitelist(methods=["POST"])
@deadlock_retry
def merge_incidents(source: str, target: str, reason: str) -> dict:
    s, t = _inc(source), _inc(target)
    if source == target or s["estate"] != t["estate"]:
        frappe.throw("Choose two different incidents in the same estate", frappe.ValidationError)
    actor = authorize("approve_enforcement", "A", estate=s["estate"])
    require((reason or "").strip(), "reason")
    for n in sorted((source, target)):  # consistent lock order prevents deadlocks between concurrent merges
        svc.lock_incident(n)
    if frappe.db.count("CPCP Enforcement Action", {"incident": source, "status": ["in", list(svc.LIVE_ACTION_STATES)], "release_at": ["is", "not set"],
                                                  "action_type": ["in", ["Clamp", "Tow"]]}):
        frappe.throw("Cancel or release the source incident's live enforcement first", frappe.ValidationError)
    moved = 0
    for allegation in frappe.get_all("CPCP Incident Allegation Link", filters={"parent": source, "link_state": ["in", list(svc.LINK_LIVE)]}, pluck="allegation"):
        moved += int(svc.attach_to_incident(target, allegation, link_state="Merged from", reason=f"merged from {source}: {reason}", actor=actor.user))
    frappe.db.set_value("CPCP Violation Incident", source, {"merged_into": target, "active_key": None, "episode_status": ep.Episode.RESOLVED_CLOSED.value,
                                                           "ended_at": to_db(utcnow()), "end_evidence": "manager_determination", "end_note": f"merged into {target}: {reason}"}, update_modified=False)
    def penalties(i):
        return frappe.db.count("CPCP Incident Charge", {"incident": i, "charge_class": "PARKING_VIOLATION"})
    flagged = penalties(source) > 0 and penalties(target) > 0
    if flagged:  # NEVER hide or delete a duplicated penalty: flag it for lawful reversal
        note = f"Two base penalties exist after merging {source} into {target}; review and credit the duplicate."
        for i in (source, target):
            frappe.db.set_value("CPCP Violation Incident", i, {"penalty_review": 1, "penalty_review_note": note}, update_modified=False)
    log_audit(action="incidents_merged", entity="CPCP Violation Incident", entity_id=target, reason=reason, role=actor.role.value,
              detail={"source": source, "reports_moved": moved, "penalty_review": flagged})
    return {"target": target, "reports_moved": moved, "penalty_review_flagged": flagged}


@frappe.whitelist(methods=["POST"])
@deadlock_retry
def split_incident(incident: str, allegations: str, reason: str) -> dict:
    """Move some reports out of a case into a fresh review work item (comma-separated allegation references)."""
    inc = _inc(incident)
    actor = authorize("approve_enforcement", "A", estate=inc["estate"])
    require((reason or "").strip(), "reason")
    refs = [x.strip() for x in (allegations or "").split(",") if x.strip()]
    if not refs:
        frappe.throw("Choose at least one report", frappe.ValidationError)
    svc.lock_incident(incident)
    moved = []
    for ref in refs:
        link = frappe.db.get_value("CPCP Incident Allegation Link", {"parent": incident, "allegation": ref}, "name")
        if not link:
            raise frappe.PermissionError("not permitted")
        frappe.db.set_value("CPCP Incident Allegation Link", link, {"link_state": "Split out", "linked_by": actor.user, "linked_at": to_db(utcnow())}, update_modified=False)
        moved.append(ref)
    first = frappe.db.get_value("CPCP Parking Allegation", moved[0], ["name", "estate", "category", "urgent_claim"], as_dict=True)
    wi, _ = svc.create_work_item(dict(first), cluster_key=None, review_note=f"split from {incident}: {reason}")
    for ref in moved[1:]:
        svc.join_work_item(wi, ref, reason=f"split from {incident}")
    for ref in moved:
        svc.set_allegation_state(ref, al.State.RECEIVED.value, "Received", actor.user, f"split from {incident}")
    live = frappe.db.sql("select count(*) from `tabCPCP Incident Allegation Link` where parent=%s and link_state in %s", (incident, svc.LINK_LIVE))[0][0]
    frappe.db.set_value("CPCP Violation Incident", incident, "allegation_count", live, update_modified=False)
    log_audit(action="incident_split", entity="CPCP Violation Incident", entity_id=incident, reason=reason, role=actor.role.value, detail={"moved": moved, "work_item": wi})
    return {"work_item": wi, "moved": moved, "remaining": live}


@frappe.whitelist(methods=["POST"])
@deadlock_retry
def reassign_work_item(work_item: str, user: str, reason: str) -> dict:
    """Manager reassignment (resolves a stalled or split-brain claim). The new owner must be an active officer of the estate."""
    wi = svc.lock_work_item(work_item)
    actor = authorize("approve_enforcement", "A", estate=wi["estate"])
    require((reason or "").strip(), "reason")
    if not frappe.db.exists("CPCP Role Assignment", {"user": user, "cpcp_role": "security_officer", "estate": wi["estate"], "status": "Active"}):
        frappe.throw("Target must be an active security officer of this estate", frappe.ValidationError)
    now = utcnow()
    from datetime import timedelta
    frappe.db.set_value("CPCP Security Work Item", work_item, {"claimed_by": user, "claimed_at": to_db(now), "status": "Claimed",
                                                              "lease_expires_at": to_db(now + timedelta(hours=svc._lease_hours()))}, update_modified=False)
    log_audit(action="work_item_reassigned", entity="CPCP Security Work Item", entity_id=work_item, reason=reason, role=actor.role.value, detail={"to": user})
    return {"work_item": work_item, "claimed_by": user}


@frappe.whitelist(methods=["POST"])
@deadlock_retry
def reassign_incident(incident: str, user: str, reason: str) -> dict:
    """Shift handover / takeover by a manager. Past assignments stay in the audit trail; the new owner is alerted."""
    inc = _inc(incident)
    actor = authorize("approve_enforcement", "A", estate=inc["estate"])
    require((reason or "").strip(), "reason")
    if not frappe.db.exists("CPCP Role Assignment", {"user": user, "cpcp_role": "security_officer", "estate": inc["estate"], "status": "Active"}):
        frappe.throw("Target must be an active security officer of this estate", frappe.ValidationError)
    svc.lock_incident(incident)
    frappe.db.set_value("CPCP Violation Incident", incident, "assigned_officer", user, update_modified=False)
    svc._outbox(incident, [(user, "security_officer")], "case_reassigned", f"{incident}:{user}:{utcnow():%H%M%S%f}", {"incident": incident})
    log_audit(action="incident_reassigned", entity="CPCP Violation Incident", entity_id=incident, reason=reason, role=actor.role.value,
              detail={"from": inc["assigned_officer"], "to": user})
    return {"incident": incident, "assigned_officer": user}


@frappe.whitelist(methods=["POST"])
@deadlock_retry
def credit_duplicate_penalty(incident: str, reason: str) -> dict:
    """After a merge flagged two base penalties, credit the duplicate. Append-only: the original line stays visible."""
    inc = _inc(incident)
    actor = authorize("resolve_appeal", "A", estate=inc["estate"])
    require((reason or "").strip(), "reason")
    if not inc["penalty_review"]:
        frappe.throw("This incident is not flagged for duplicate-penalty review", frappe.ValidationError)
    line = frappe.get_all("CPCP Incident Charge", filters={"incident": incident, "charge_class": "PARKING_VIOLATION"}, fields=["amount", "currency"], limit=1)
    if not line:
        frappe.throw("No base penalty on this incident", frappe.ValidationError)
    from frappe_cpcp.api import enforcement as enf
    credit = ch.Charge(incident, ch.ChargeClass.ADJUSTMENT_CREDIT, Decimal(1), Decimal(str(line[0].amount)), line[0].currency, "duplicate-penalty review", "",
                       ch.idempotency_key(incident, ch.ChargeClass.ADJUSTMENT_CREDIT, "duplicate"))
    n = enf._persist(incident, [credit], actor.user)
    frappe.db.set_value("CPCP Violation Incident", incident, "penalty_review", 0, update_modified=False)
    log_audit(action="duplicate_penalty_credited", entity="CPCP Violation Incident", entity_id=incident, reason=reason, role=actor.role.value)
    return {"incident": incident, "credit_lines_added": n}


# ---------------------------------------------------------------- repeat offenders ----------------------------

@frappe.whitelist()
def repeat_offenders(estate: str, window_days: int | None = None) -> dict:
    """Repeat = distinct VERIFIED EPISODES in the window (not allegation counts). Merged-away incidents and incidents whose
    appeal was upheld do not count. Plates are masked."""
    authorize("approve_enforcement", "A", estate=estate)
    days = cint(window_days) or cint(frappe.db.get_single_value("CPCP Settings", "repeat_window_days") or 365)
    from datetime import timedelta
    since = to_db(utcnow() - timedelta(days=days))
    rows = frappe.db.sql(
        """select i.plate_hash, max(i.plate_snapshot) plate, count(*) episodes, sum(i.allegation_count) allegations, min(i.verified_at) first_at, max(i.verified_at) last_at
           from `tabCPCP Violation Incident` i
           where i.estate=%s and i.verified_at >= %s and i.merged_into is null and i.plate_hash is not null
             and not exists (select 1 from `tabCPCP Appeal` ap where ap.incident=i.name and ap.status='Upheld')
           group by i.plate_hash having count(*) >= 2 order by episodes desc""", (estate, since), as_dict=True)
    return {"window_days": days, "basis": "distinct verified episodes",
            "repeat_vehicles": [{"plate": mask_plate(r.plate.replace(' ', '').replace('-', '')), "episodes": r.episodes, "reports_attached": r.allegations or 0,
                                 "first": iso(r.first_at), "last": iso(r.last_at)} for r in rows]}


@frappe.whitelist()
def list_cases(estate: str, episode_status: str | None = None, search: str | None = None, limit: int = 100) -> list[dict]:
    """Management case list (all incidents, not only open ones). Not available to officers, who only see their assigned cases."""
    actor = authorize("incident_reports", "R", estate=estate)
    if actor.role.value == "security_officer":
        raise frappe.PermissionError("not permitted")
    from frappe_cpcp.services import access
    f = {"estate": estate, "merged_into": ["is", "not set"]}
    if episode_status:
        f["episode_status"] = episode_status
    rows = frappe.get_all("CPCP Violation Incident", filters=f, order_by="verified_at desc", limit=min(cint(limit), 300),
                          fields=["name", "plate_snapshot", "classification", "episode_status", "status", "allegation_count", "priority", "assigned_officer",
                                  "verified_at", "ended_at", "end_evidence", "penalty_review", "responsible_unit"])
    if search:
        term = search.strip().upper().replace(" ", "")
        rows = [r for r in rows if term in (r.plate_snapshot or "").upper().replace(" ", "").replace("-", "") or term == r.name]
    access.record(actor=actor.user, role=actor.role.value, estate=estate, action="list", record_type="Violation Incident", category="restricted_legal",
                  purpose="supervisor_review", context=f"{len(rows)} cases listed")
    return [{**r, "verified_at": iso(r.verified_at), "ended_at": iso(r.ended_at)} for r in rows]
