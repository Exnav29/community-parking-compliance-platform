# SPDX-License-Identifier: Apache-2.0
"""PRD v1.7 migration: backfill episode identity without discarding any prior allegation/incident link or history.

* every existing incident gets an episode_status derived from its workflow status, plate_hash and counts;
* live (not closed) incidents get an active_key unless another live incident already holds it (then left NULL and
  flagged for review: duplicates found by the migration are never merged automatically);
* every existing incident-allegation link becomes a 'Confirmed' link with a link_key;
* every existing work item gets its primary allegation as a member row.
"""
import frappe

from frappe_cpcp.core import episodes as ep

STATUS_TO_EPISODE = {
    "recorded": "Verified/Open", "identification_pending": "Verified/Open", "contact_pending": "Verified/Open",
    "notification_attempted": "Verified/Open", "notified": "Warning Active", "grace_active": "Warning Active",
    "corrected_no_fee": "Compliance Confirmed", "escalation_pending": "Warning Active", "approved": "Warning Active",
    "clamped": "Clamp Active", "tow_dispatched": "Tow Ordered", "impounded": "Towed/Impounded", "released": "Resolved/Closed",
    "resolved_closed": "Resolved/Closed",
}


def execute():
    if not frappe.db.has_column("CPCP Violation Incident", "episode_status"):
        return
    seen: set[str] = set()
    for inc in frappe.get_all("CPCP Violation Incident", fields=["name", "estate", "status", "plate_normalized", "episode_status", "active_key"], order_by="creation asc"):
        if inc.active_key:
            seen.add(inc.active_key)
            continue
        episode = STATUS_TO_EPISODE.get(inc.status, "Verified/Open")
        updates = {"episode_status": episode, "plate_hash": ep.plate_hash(inc.plate_normalized) if inc.plate_normalized else None}
        links = frappe.db.count("CPCP Incident Allegation Link", {"parent": inc.name})
        updates["allegation_count"] = max(links, 1)
        key = ep.active_key(inc.estate, inc.plate_normalized)
        live = episode != "Resolved/Closed"
        if live and key and key not in seen:
            updates["active_key"] = key
            seen.add(key)
        elif live and key:
            updates["penalty_review"] = 1
            updates["penalty_review_note"] = "Migration found another live episode for this vehicle; review and merge if they are the same event."
        frappe.db.set_value("CPCP Violation Incident", inc.name, updates, update_modified=False)
    for link in frappe.get_all("CPCP Incident Allegation Link", fields=["name", "parent", "allegation", "link_key"]):
        if not link.link_key:
            frappe.db.set_value("CPCP Incident Allegation Link", link.name, {"link_state": "Confirmed", "join_reason": "migrated link",
                                                                           "link_key": f"{link.parent}:{link.allegation}"}, update_modified=False)
    for wi in frappe.get_all("CPCP Security Work Item", fields=["name", "allegation"]):
        if not frappe.db.exists("CPCP Work Item Allegation", {"parent": wi.name, "allegation": wi.allegation}):
            frappe.get_doc({"doctype": "CPCP Work Item Allegation", "parent": wi.name, "parenttype": "CPCP Security Work Item", "parentfield": "allegations",
                            "idx": 1, "allegation": wi.allegation, "join_reason": "migrated", "link_key": f"{wi.name}:{wi.allegation}"}).db_insert()
    frappe.db.commit()
