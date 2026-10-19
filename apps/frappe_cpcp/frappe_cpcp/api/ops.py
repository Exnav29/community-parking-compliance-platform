# SPDX-License-Identifier: Apache-2.0
"""Operational read APIs for the mobile and desktop clients: estate context, active cases, incident detail."""
import frappe

from frappe_cpcp.core import episodes as ep
from frappe_cpcp.permissions import authorize, get_actor
from frappe_cpcp.services.common import iso

CLOSED = ("corrected_no_fee", "resolved_closed", "released")


def _scope(actor) -> list[str]:
    if actor.estate_ids:
        return sorted(actor.estate_ids)
    return frappe.get_all("CPCP Estate", filters={"status": "Active"}, pluck="name") if actor.role.value == "org_admin" else []


@frappe.whitelist()
def estate_context() -> list[dict]:
    """Estates in the caller's scope with their gates and zones (no people, no plates)."""
    actor = get_actor()
    out = []
    for e in _scope(actor):
        est = frappe.db.get_value("CPCP Estate", e, ["name", "estate_name", "timezone", "currency", "boundary_geojson"], as_dict=True)
        out.append({"estate": est.name, "name": est.estate_name, "timezone": est.timezone, "currency": est.currency,
                    "boundary": frappe.parse_json(est.boundary_geojson) if est.boundary_geojson else None,
                    "gates": frappe.get_all("CPCP Gate", filters={"estate": e, "active": 1}, fields=["name", "gate_name"]),
                    "zones": frappe.get_all("CPCP Zone", filters={"estate": e}, fields=["name", "zone_name", "zone_type"])})
    return out


@frappe.whitelist()
def active_cases(estate: str) -> list[dict]:
    """Open incidents with their notice clock, so the officer sees a running countdown (server deadline)."""
    actor = get_actor()
    if actor.role.value == "security_officer":
        authorize("verify_incident", "C", estate=estate)  # officers: duty access in their own estate
    else:
        authorize("incident_reports", "R", estate=estate)
    from frappe_cpcp.services import pbac as pb
    ctx = pb.duty_check(actor, estate, action="list", record_type="Violation Incident", category="sensitive_personal")
    filters = {"estate": estate, "status": ["not in", list(CLOSED)], "merged_into": ["is", "not set"], "episode_status": ["!=", "Resolved/Closed"]}
    if actor.role.value == "security_officer":
        filters["assigned_officer"] = actor.user  # "My assigned cases": officers never see other officers' cases
    rows = frappe.get_all("CPCP Violation Incident", filters=filters,
                          fields=["name", "plate_snapshot", "status", "classification", "verified_by", "verified_at", "responsible_unit",
                                  "episode_status", "allegation_count", "priority", "assigned_officer"],
                          order_by="verified_at desc", limit=100)
    out = []
    for r in rows:
        n = frappe.db.get_value("CPCP Warning Notice", {"incident": r.name}, ["deadline", "effective_at"], as_dict=True)
        out.append({"incident": r.name, "plate": r.plate_snapshot, "status": r.status, "classification": r.classification,
                    "episode_status": r.episode_status, "reports": r.allegation_count, "priority": r.priority,
                    "already_being_handled": ep.already_being_handled(ep.Episode(r.episode_status)),
                    "assigned_officer": r.assigned_officer,
                    "verified_at": iso(r.verified_at), "notice_deadline": iso(n.deadline) if n else None,
                    "notice_effective_at": iso(n.effective_at) if n else None,
                    "attempts": frappe.db.count("CPCP Communication Attempt", {"incident": r.name})})
    ctx.allowed(context=f"{len(out)} cases listed")
    return out


@frappe.whitelist()
def incident_detail(incident: str) -> dict:
    row = frappe.db.get_value("CPCP Violation Incident", incident,
                              ["name", "estate", "plate_snapshot", "status", "classification", "rule_version", "latitude", "longitude",
                               "accuracy_m", "pin_source", "pin_correction_reason", "verified_by", "verified_at", "zone", "episode_status",
                               "allegation_count", "priority", "assigned_officer", "first_observed_at", "last_observed_at", "end_evidence"], as_dict=True)
    if not row:
        raise frappe.PermissionError("not permitted")
    actor = authorize("verify_incident" if get_actor().role.value == "security_officer" else "incident_reports",
                      "C" if get_actor().role.value == "security_officer" else "R", estate=row.estate)
    from frappe_cpcp.services import pbac as pb
    pb.case_access(actor, incident, action="view", category="restricted_legal").allowed(record_id=incident)
    allegations = frappe.get_all("CPCP Incident Allegation Link", filters={"parent": incident}, pluck="allegation")
    return {**{k: row[k] for k in ("name", "plate_snapshot", "status", "classification", "rule_version", "pin_source",
                                    "pin_correction_reason", "verified_by")},
            "verified_at": iso(row.verified_at), "episode_status": row.episode_status, "reports": row.allegation_count, "priority": row.priority,
            "assigned_officer": row.assigned_officer, "first_observed_at": iso(row.first_observed_at), "last_observed_at": iso(row.last_observed_at),
            "end_evidence": row.end_evidence,
            "already_being_handled": ep.already_being_handled(ep.Episode(row.episode_status)),
            "location": {"lat": row.latitude, "lon": row.longitude, "accuracy_m": row.accuracy_m,
                                                              "note": "Officer-confirmed vehicle pin; accuracy is the device reading"},
            "source_allegations": allegations,
            "evidence_count": frappe.db.count("CPCP Officer Evidence", {"incident": incident})}
