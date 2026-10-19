#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Generate Frappe DocType JSON (and controller stubs that do not yet exist) from compact specs.

Usage:  python scripts/gen_doctypes.py
Controllers that already exist are never overwritten; edit them by hand.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "apps" / "frappe_cpcp" / "frappe_cpcp" / "cpcp" / "doctype"
MODULE = "CPCP"
TS = "2026-10-19 12:00:00.000000"

R_ADMIN, R_SECM, R_OFF = "CPCP Org Admin", "CPCP Security Manager", "CPCP Security Officer"
R_AUD, R_FIN, R_RES, R_TOW, R_SYS = "CPCP Auditor", "CPCP Finance", "CPCP Resident", "CPCP Tow Provider", "System Manager"
CPCP_ROLES = [R_ADMIN, R_SECM, R_OFF, R_AUD, R_FIN, R_RES, R_TOW, "CPCP Board Observer"]


def F(name, ftype="Data", label=None, **kw):
    d = {"fieldname": name, "fieldtype": ftype, "label": label or name.replace("_", " ").title()}
    d.update(kw)
    return d


def scrub(name: str) -> str:
    return re.sub(r"[^a-z0-9_]", "", name.lower().replace(" ", "_").replace("-", "_"))


def perm(role, mode="r", permlevel=0):
    return {
        "role": role, "permlevel": permlevel, "read": 1,
        "write": 1 if "w" in mode else 0, "create": 1 if "c" in mode else 0, "delete": 1 if "d" in mode else 0,
        "report": 1, "export": 0, "share": 0, "print": 0, "email": 0,
    }


STAFF = [R_ADMIN, R_SECM, R_OFF]
CAPABILITY_OPTIONS = "\n".join([
    "resident_registry", "visitor_log", "estate_units", "triage_reports", "capture_evidence",
    "charge_ledger", "receipts_refunds", "incident_reports", "raw_export",
])

DOCTYPES: list[dict] = [
    dict(name="CPCP Settings", issingle=1, desc="Organization settings, locale and legal feature gates (all enforcement flags default OFF).",
         fields=[
             F("org_id", reqd=1, description="Opaque organization identifier bound to this isolated site."),
             F("display_name", reqd=1),
             F("locale", default="en-GH"), F("currency", default="GHS"), F("timezone", default="Africa/Accra"),
             F("default_grace_minutes", "Int", default="15"),
             F("visitor_suggestion_retention_days", "Int", default="180", description="Prior-visit suggestions older than this are never offered."),
             F("allegation_rate_limit_per_hour", "Int", default="10"),
             F("sms_provider", "Select", options="mock", default="mock", description="Only the no-cost mock adapter exists until a real provider is approved."),
             F("sms_live_enabled", "Check", default="0", description="Billable production messaging. Needs separate authorization and a legal approval reference."),
             F("security_desk_number", description="Shown in warning templates."),
             F("claim_lease_hours", "Int", default="8", description="A claim lapses after this many hours without activity; managers can reassign sooner."),
             F("repeat_window_days", "Int", default="365", description="Window for counting distinct verified episodes as repeats."),
             F("plate_lookups_per_hour", "Int", default="60", description="Gate plate lookups per officer per hour (hard ceiling)."),
             F("bare_suggestions_per_hour", "Int", default="10", description="Unit lookups WITHOUT a plate hint per officer per hour (stricter: the shape of a browsing attack)."),
             F("shift_max_hours", "Int", default="14", description="A gate shift expires on the server after this long."),
             F("emergency_max_minutes", "Int", default="60"),
             F("suggestion_limit_per_hour", "Int", default="30", description="Returning-visitor suggestion lookups per officer per hour (hard ceiling)."),
             F("access_log_retention_days", "Int", default="730", description="Sensitive-access journal retention; purge is a scheduled, summarised, audited job."),
             F("ar_distinct_units_per_hour", "Int", default="12", description="Review signal: distinct households touched in one hour."),
             F("ar_repeat_unit_per_day", "Int", default="4", description="Review signal: repeated lookups of one household without a case or visit."),
             F("ar_denied_per_hour", "Int", default="5"), F("ar_suggestions_per_hour", "Int", default="20"),
             F("anonymous_label_verified", "Check", default="0",
               description="Only set after logging/linkability review (PRD 34.1). While 0 the UI says 'Confidential', not 'Anonymous'."),
             F("sb_flags", "Section Break", "Legal and policy gates"),
             F("legal_approval_reference", description="Reference to signed association approval and local legal review. Required to enable any gate."),
             F("fine_assessment_enabled", "Check", default="0"), F("clamping_enabled", "Check", default="0"),
             F("towing_enabled", "Check", default="0"), F("impound_release_enabled", "Check", default="0"),
             F("payment_collection_enabled", "Check", default="0"), F("provider_dispatch_enabled", "Check", default="0"),
             F("public_registration_enabled", "Check", default="0"), F("saas_customer_billing_enabled", "Check", default="0"),
         ], perms=[perm(R_ADMIN, "rw"), perm(R_SYS, "rw")]),

    dict(name="CPCP Estate", autoname="format:EST-{#####}", title_field="estate_name",
         fields=[F("estate_name", reqd=1, in_list_view=1), F("address", "Small Text"), F("jurisdiction"),
                 F("timezone", default="Africa/Accra"), F("currency", default="GHS"),
                 F("boundary_geojson", "Code", options="JSON", description="Synthetic or association-drawn polygon (GeoJSON)."),
                 F("status", "Select", options="Active\nInactive", default="Active", in_list_view=1)],
         perms=[perm(R_ADMIN, "rwcd"), perm(R_SECM), perm(R_OFF), perm(R_AUD), perm(R_SYS, "rwcd")]),

    dict(name="CPCP Gate", autoname="format:GATE-{#####}", title_field="gate_name",
         fields=[F("estate", "Link", options="CPCP Estate", reqd=1, in_list_view=1), F("gate_name", reqd=1, in_list_view=1),
                 F("active", "Check", default="1")],
         perms=[perm(R_ADMIN, "rwcd"), perm(R_SECM), perm(R_OFF), perm(R_SYS, "rwcd")]),

    dict(name="CPCP Zone", autoname="format:ZONE-{#####}", title_field="zone_name",
         fields=[F("estate", "Link", options="CPCP Estate", reqd=1, in_list_view=1), F("zone_name", reqd=1, in_list_view=1),
                 F("zone_type", "Select", options="Standard\nVisitor\nRestricted\nEmergency Access\nGate or Driveway", default="Standard", in_list_view=1),
                 F("polygon_geojson", "Code", options="JSON"), F("capacity", "Int")],
         perms=[perm(R_ADMIN, "rwcd"), perm(R_SECM), perm(R_OFF), perm(R_SYS, "rwcd")]),

    dict(name="CPCP Unit", autoname="format:UNIT-{#####}", title_field="unit_label",
         fields=[F("estate", "Link", options="CPCP Estate", reqd=1, in_list_view=1), F("unit_label", reqd=1, in_list_view=1),
                 F("block"), F("occupancy_status", "Select", options="Occupied\nVacant\nUnknown", default="Unknown")],
         perms=[perm(R_ADMIN, "rwcd"), perm(R_SECM), perm(R_OFF), perm(R_AUD), perm(R_SYS, "rwcd")]),

    dict(name="CPCP Person", autoname="format:PER-{#####}", title_field="full_name",
         fields=[F("full_name", reqd=1, in_list_view=1), F("phone_source", description="As entered; preserved for audit."),
                 F("phone_e164", read_only=1, search_index=1), F("preferred_contact", "Select", options="Call\nSMS\nEmail", default="Call"),
                 F("active", "Check", default="1"), F("privacy_notice_status", "Select", options="Not Shown\nShown\nAcknowledged", default="Not Shown"),
                 F("user", "Link", options="User", description="Linked login for self-service residents.")],
         perms=[perm(R_ADMIN, "rwc"), perm(R_SECM, "rwc"), perm(R_AUD)], sensitivity="SENSITIVE_RESIDENT_REGISTRY"),

    dict(name="CPCP Unit Membership", autoname="format:MEM-{#####}",
         fields=[F("unit", "Link", options="CPCP Unit", reqd=1, in_list_view=1), F("person", "Link", options="CPCP Person", reqd=1, in_list_view=1),
                 F("membership_type", "Select", options="Owner\nTenant\nOccupant\nAuthorized Host", reqd=1),
                 F("is_primary_contact", "Check"), F("is_backup_contact", "Check"),
                 F("valid_from", "Date", reqd=1), F("valid_to", "Date"), F("verified_by", "Link", options="User")],
         perms=[perm(R_ADMIN, "rwc"), perm(R_SECM, "rwc"), perm(R_AUD)], sensitivity="SENSITIVE_RESIDENT_REGISTRY"),

    dict(name="CPCP Vehicle", autoname="format:VEH-{#####}", title_field="plate",
         fields=[F("plate", reqd=1, in_list_view=1), F("plate_normalized", read_only=1, search_index=1), F("country", default="GH"),
                 F("make"), F("model"), F("color"),
                 F("status", "Select", options="Active\nInactive\nRevoked", default="Active")],
         perms=[perm(R_ADMIN, "rwc"), perm(R_SECM, "rwc"), perm(R_AUD)], sensitivity="SENSITIVE_RESIDENT_REGISTRY"),

    dict(name="CPCP Vehicle Unit Association", autoname="format:VUA-{#####}",
         fields=[F("vehicle", "Link", options="CPCP Vehicle", reqd=1, in_list_view=1), F("unit", "Link", options="CPCP Unit", reqd=1, in_list_view=1),
                 F("assoc_role", "Select", options="Registered\nCustodian\nPermitted Driver", default="Registered"),
                 F("verification_status", "Select", options="Requested\nVerified\nRejected", default="Verified", in_list_view=1),
                 F("requested_by", "Link", options="User"), F("valid_from", "Date"), F("valid_to", "Date"),
                 F("status", "Select", options="Active\nEnded", default="Active")],
         perms=[perm(R_ADMIN, "rwc"), perm(R_SECM, "rwc"), perm(R_AUD)], sensitivity="SENSITIVE_RESIDENT_REGISTRY"),

    dict(name="CPCP Role Assignment", autoname="format:ROLE-{#####}", title_field="user",
         fields=[F("user", "Link", options="User", reqd=1, in_list_view=1),
                 F("cpcp_role", "Select", options="org_admin\nestate_manager\nsecurity_manager\nsecurity_officer\nresident\nauditor\nfinance\ntow_provider\nboard_observer",
                   reqd=1, in_list_view=1),
                 F("estate", "Link", options="CPCP Estate"), F("unit", "Link", options="CPCP Unit"),
                 F("valid_from", "Date"), F("valid_until", "Date"),
                 F("status", "Select", options="Active\nSuspended\nRevoked", default="Active", in_list_view=1),
                 F("approved_by", "Link", options="User"), F("basis", description="Employment/contract/household basis.")],
         perms=[perm(R_ADMIN, "rwc"), perm(R_SYS, "rwc"), perm(R_AUD)]),

    dict(name="CPCP Visitor Session", autoname="hash", title_field="plate_snapshot", sensitivity="SENSITIVE_VISITOR_LOG",
         fields=[F("estate", "Link", options="CPCP Estate", reqd=1, in_list_view=1), F("host_unit", "Link", options="CPCP Unit", in_list_view=1),
                 F("host_unit_label", read_only=1),
                 F("category", "Select", options="Guest\nContractor\nDelivery\nRide-hail or Taxi\nMotorcycle\nPedestrian\nEmergency Service", default="Guest"),
                 F("plate_snapshot", in_list_view=1), F("plate_normalized", read_only=1, search_index=1),
                 F("status", "Select", options="Expected\nPending Authorization\nChecked In\nChecked Out\nExit Unconfirmed\nNeeds Supervisor Review\nCancelled/Voided",
                   default="Checked In", in_list_view=1, search_index=1),
                 F("presence", "Select", options="Confirmed In\nConfirmed Out\nUnknown/Unverified", default="Confirmed In"),
                 F("entry_at", "Datetime", reqd=1, description="UTC observed time"), F("entry_gate", "Link", options="CPCP Gate"),
                 F("entry_officer", "Link", options="User"),
                 F("exit_at", "Datetime"), F("exit_gate", "Link", options="CPCP Gate"), F("exit_officer", "Link", options="User"),
                 F("exit_method"), F("estimated", "Check"), F("duration_minutes", "Int", read_only=1),
                 F("sync_state", "Select", options="Synced\nAwaiting Sync\nNeeds Review", default="Synced"),
                 F("client_uuid", unique=1, description="Client-generated idempotency key"),
                 F("version", "Int", default="1", read_only=1)],
         perms=[perm(R_ADMIN, "r"), perm(R_SECM, "r"), perm(R_AUD)]),

    dict(name="CPCP Visit Event", autoname="hash", append_only=True, sensitivity="SENSITIVE_VISITOR_LOG",
         fields=[F("session", "Link", options="CPCP Visitor Session", reqd=1, in_list_view=1, search_index=1),
                 F("event_type", "Select", options="ENTRY\nEXIT\nEXIT_CORRECTION\nVOID\nREOPEN_REVIEW", reqd=1, in_list_view=1),
                 F("actor", "Link", options="User"), F("gate", "Link", options="CPCP Gate"),
                 F("observed_at", "Datetime"), F("received_at", "Datetime"),
                 F("idempotency_key", unique=1), F("reason", "Small Text"), F("source", default="online")],
         perms=[perm(R_ADMIN), perm(R_SECM), perm(R_AUD)]),

    dict(name="CPCP Parking Allegation", autoname="format:ALG-{#####}", title_field="category", sensitivity="RESTRICTED_EVIDENCE",
         fields=[F("estate", "Link", options="CPCP Estate", reqd=1, in_list_view=1),
                 F("mode", "Select", options="Identified\nAnonymous\nContactable Confidential", reqd=1, in_list_view=1),
                 F("category", "Select", options="Gate or driveway blocked\nRoadway obstruction\nUnsafe parking\nUnauthorized space\nEmergency access\nOther", reqd=1, in_list_view=1),
                 F("narrative", "Small Text", reqd=1), F("alleged_plate_text", description="Typed manually by reporter; never matched to a registry."),
                 F("latitude", "Float", precision="8"), F("longitude", "Float", precision="8"), F("accuracy_m", "Float"),
                 F("location_source", "Select", options="device\nmanual_pin\nzone_only\nnone", default="none"), F("zone", "Link", options="CPCP Zone"),
                 F("urgent_claim", "Check"),
                 F("state", "Select", options="Submitted\nReceived by Security\nAssigned / Under Review\nVerified and Linked to Official Incident\nResolved without Violation\nNot Substantiated\nDuplicate / Merged\nWithdrawn\nClosed",
                   default="Submitted", in_list_view=1, search_index=1),
                 F("dedup_cluster", search_index=1), F("alleged_plate_hash", hidden=1, search_index=1), F("receipt_id", search_index=1),
                 F("client_uuid", unique=1), F("submitted_at", "Datetime", read_only=1),
                 F("sb_reporter", "Section Break", "Restricted reporter metadata (identified reports only)"),
                 F("reporter_user", "Link", options="User", permlevel=1), F("reporter_unit", "Link", options="CPCP Unit", permlevel=1)],
         perms=[perm(R_ADMIN, "r"), perm(R_SECM, "r"), perm(R_OFF, "r"), perm(R_AUD),
                perm(R_SECM, "r", 1)]),

    dict(name="CPCP Allegation Attachment", autoname="format:ATT-{#####}", append_only=True, sensitivity="RESTRICTED_EVIDENCE",
         desc="A resident photo, stored ONLY after metadata stripping. No Desk access for officers; read through a purpose-checked API.",
         fields=[F("allegation", "Link", options="CPCP Parking Allegation", reqd=1, search_index=1), F("file_url", reqd=1), F("sha256", reqd=1),
                 F("width", "Int"), F("height", "Int"), F("bytes", "Int"), F("source_mode"), F("created_at", "Datetime")],
         perms=[perm(R_ADMIN)]),

    dict(name="CPCP Allegation Receipt", autoname="hash", append_only=True,
         fields=[F("receipt_id", reqd=1, unique=1), F("allegation", "Link", options="CPCP Parking Allegation"),
                 F("salt", reqd=1), F("verifier", reqd=1)],
         perms=[perm(R_SYS)]),

    dict(name="CPCP Security Work Item", autoname="format:SWI-{#####}", sensitivity="STAFF_OPERATIONAL",
         desc="One actionable case. Many allegations may join it; only one active claim; unique open cluster per estate+plate.",
         fields=[F("allegation", "Link", options="CPCP Parking Allegation", reqd=1, description="First allegation (primary)"),
                 F("estate", "Link", options="CPCP Estate", reqd=1, in_list_view=1),
                 F("cluster_key", unique=1, description="Unique while open; empty when closed or when no reliable plate exists"),
                 F("urgency", "Select", options="Normal\nUrgent claimed", default="Normal", in_list_view=1),
                 F("status", "Select", options="Open\nClaimed\nEscalated\nClosed", default="Open", in_list_view=1, search_index=1),
                 F("claimed_by", "Link", options="User"), F("claimed_at", "Datetime"), F("lease_expires_at", "Datetime"),
                 F("acknowledged_at", "Datetime"), F("due_at", "Datetime"), F("escalated_at", "Datetime"),
                 F("allegation_count", "Int", default="1"), F("latest_at", "Datetime"),
                 F("incident", "Link", options="CPCP Violation Incident"),
                 F("candidate_incident", "Link", options="CPCP Violation Incident", description="Possible related case for reviewer comparison"),
                 F("review_needed", "Check"), F("review_note", "Small Text"),
                 F("allegations", "Table", options="CPCP Work Item Allegation")],
         perms=[perm(R_ADMIN, "r"), perm(R_SECM, "r"), perm(R_OFF, "r"), perm(R_AUD)]),

    dict(name="CPCP Work Item Allegation", istable=1, autoname="hash",
         fields=[F("allegation", "Link", options="CPCP Parking Allegation", reqd=1, in_list_view=1),
                 F("joined_at", "Datetime"), F("join_reason"), F("match_confidence", "Float"),
                 F("link_key", unique=1)], perms=[]),

    dict(name="CPCP Notification Outbox", autoname="hash",
         fields=[F("work_item", "Link", options="CPCP Security Work Item"), F("incident", "Link", options="CPCP Violation Incident"), F("ref", description="Reference for notices not tied to a work item or incident (grants, review signals)"), F("recipient_role", "Select", options="security_officer\nsecurity_manager\norg_admin\nauditor"),
                 F("recipient_user", "Link", options="User"), F("channel", "Select", options="in_app\npush", default="in_app"),
                 F("status", "Select", options="Pending\nSent\nDelivered\nFailed\nAcknowledged", default="Pending", in_list_view=1),
                 F("attempts", "Int", default="0"), F("idempotency_key", unique=1),
                 F("payload_minimal", "Code", options="JSON", description="No reporter identity, full plate, photo or exact address.")],
         perms=[perm(R_ADMIN), perm(R_SECM), perm(R_SYS)]),

    dict(name="CPCP Allegation Review Event", autoname="hash", append_only=True, sensitivity="RESTRICTED_EVIDENCE",
         fields=[F("allegation", "Link", options="CPCP Parking Allegation", reqd=1, search_index=1),
                 F("event", "Select", options="Received\nClaim\nNote\nVerify\nDismiss\nDuplicate\nEscalate\nWithdraw\nClose", reqd=1, in_list_view=1),
                 F("actor", "Link", options="User"), F("from_state"), F("to_state"), F("reason", "Small Text")],
         perms=[perm(R_ADMIN), perm(R_SECM), perm(R_OFF), perm(R_AUD)]),

    dict(name="CPCP Violation Incident", autoname="format:INC-{#####}", title_field="plate_snapshot", sensitivity="RESTRICTED_EVIDENCE",
         fields=[F("estate", "Link", options="CPCP Estate", reqd=1, in_list_view=1),
                 F("plate_snapshot", in_list_view=1), F("plate_normalized", search_index=1),
                 F("classification", "Select", options="Ordinary\nEmergency", default="Ordinary"),
                 F("status", "Select", options="recorded\nidentification_pending\ncontact_pending\nnotification_attempted\nnotified\ngrace_active\ncorrected_no_fee\nescalation_pending\napproved\nclamped\ntow_dispatched\nimpounded\nreleased\nresolved_closed",
                   default="recorded", in_list_view=1),
                 F("verified_by", "Link", options="User"), F("verified_at", "Datetime"),
                 F("rule_version"), F("policy_version"), F("latitude", "Float", precision="8"), F("longitude", "Float", precision="8"),
                 F("accuracy_m", "Float"), F("pin_source", "Select", options="device\nmanual_pin\nzone_only"), F("pin_correction_reason", "Small Text"),
                 F("zone", "Link", options="CPCP Zone"),
                 F("responsible_unit", "Link", options="CPCP Unit"), F("match_basis"),
                 F("episode_status", "Select", options="New/Candidate\nUnder Review\nVerified/Open\nWarning Active\nCompliance Confirmed\nClamp Active\nTow Ordered\nTowed/Impounded\nRelease Pending\nResolved/Closed\nReopened for Review", default="Verified/Open", in_list_view=1, search_index=1),
                 F("active_key", unique=1, description="Unique vehicle identity while the episode has not positively ended"),
                 F("plate_hash", search_index=1), F("allegation_count", "Int", default="1"),
                 F("first_observed_at", "Datetime"), F("last_observed_at", "Datetime"),
                 F("ended_at", "Datetime"), F("end_evidence"), F("end_note", "Small Text"),
                 F("merged_into", "Link", options="CPCP Violation Incident"),
                 F("priority", "Select", options="Normal\nUrgent claimed", default="Normal"),
                 F("assigned_officer", "Link", options="User"),
                 F("penalty_review", "Check"), F("penalty_review_note", "Small Text"),
                 F("allegations", "Table", options="CPCP Incident Allegation Link")],
         perms=[perm(R_ADMIN, "r"), perm(R_SECM, "r"), perm(R_OFF, "r"), perm(R_AUD)]),

    dict(name="CPCP Incident Allegation Link", istable=1, autoname="hash",
         fields=[F("allegation", "Link", options="CPCP Parking Allegation", reqd=1, in_list_view=1),
                 F("link_state", "Select", options="Confirmed\nAuto Candidate\nRejected\nLate\nMerged from\nSplit out", default="Confirmed", in_list_view=1),
                 F("join_reason"), F("matcher_confidence", "Float"), F("linked_by", "Link", options="User"),
                 F("linked_at", "Datetime"), F("link_key", unique=1, description="incident:allegation, prevents duplicate links")], perms=[]),

    dict(name="CPCP Officer Evidence", autoname="format:EVD-{#####}", append_only=True, sensitivity="RESTRICTED_EVIDENCE",
         fields=[F("allegation", "Link", options="CPCP Parking Allegation"), F("incident", "Link", options="CPCP Violation Incident"),
                 F("captured_by", "Link", options="User", reqd=1), F("captured_at_server", "Datetime", reqd=1),
                 F("captured_at_device", "Datetime"), F("photo", "Attach Image"), F("sha256"),
                 F("latitude", "Float", precision="8"), F("longitude", "Float", precision="8"), F("accuracy_m", "Float"),
                 F("pin_latitude", "Float", precision="8"), F("pin_longitude", "Float", precision="8"),
                 F("pin_source", "Select", options="device\nmanual_pin\nzone_only"), F("pin_reason", "Small Text"),
                 F("note", "Small Text")],
         perms=[perm(R_ADMIN), perm(R_SECM), perm(R_AUD)]),

    dict(name="CPCP Audit Event", autoname="hash", append_only=True, sensitivity="IMMUTABLE_AUDIT",
         fields=[F("seq", "Int", reqd=1, unique=1), F("prev_hash", reqd=1), F("hash", reqd=1),
                 F("actor", in_list_view=1), F("role"), F("action", in_list_view=1), F("entity"), F("entity_id"),
                 F("at_utc"), F("request_id"), F("reason", "Small Text"), F("detail_hash")],
         perms=[perm(R_ADMIN), perm(R_SECM), perm(R_AUD)]),

    dict(name="CPCP Sensitive Access Event", autoname="hash", append_only=True, sensitivity="IMMUTABLE_AUDIT",
         desc="Hash-chained journal of every sensitive access attempt. Written out-of-band so denials survive a rolled-back request.",
         fields=[F("seq", "Int", unique=1, reqd=1), F("prev_hash"), F("hash"),
                 F("actor", reqd=1, in_list_view=1), F("role"), F("estate", search_index=1), F("gate"), F("shift"),
                 F("device_hash"), F("session_hash"),
                 F("action", description="search, view, contact, history, export, print, emergency, list"),
                 F("record_type", in_list_view=1), F("record_id", description="Identifier or safely derived token; never raw personal data"),
                 F("target_unit", search_index=1), F("category", description="operational_min, sensitive_personal, restricted_safety, restricted_legal, contact_reveal"),
                 F("purpose", search_index=1), F("purpose_ref", description="Validated case, visit or emergency-grant reference"),
                 F("context"), F("result", "Select", options="Allowed\nDenied\nNo Match\nEmergency\nUnsuccessful", in_list_view=1, search_index=1),
                 F("reason_code"), F("request_id", search_index=1), F("at_utc", search_index=1),
                 F("search_term_hash", description="One-way hash of the normalized term, never the term"),
                 F("review_state", default="None")],
         perms=[perm(R_ADMIN), perm(R_AUD)]),

    dict(name="CPCP Communication Attempt", autoname="format:COM-{#####}", sensitivity="RESTRICTED_EVIDENCE",
         desc="One call or SMS attempt for a verified incident. Destination is masked in ordinary views.",
         fields=[F("incident", "Link", options="CPCP Violation Incident", reqd=1, in_list_view=1, search_index=1),
                 F("channel", "Select", options="call_dialer\ncall_provider\nsms", reqd=1, in_list_view=1),
                 F("contact_id", description="Unit Membership or role reference used for routing"),
                 F("relationship", in_list_view=1), F("destination_masked"),
                 F("destination", "Password", description="Encrypted full number; revealed only to authorized duty staff via API."),
                 F("officer", "Link", options="User", reqd=1), F("initiated_at", "Datetime", reqd=1),
                 F("outcome", "Select", options="\nAnswered\nNo Answer\nBusy\nWrong Number\nCould Not Place Call\nCallback Requested\nOther"),
                 F("provenance", "Select", options="requested-only\nofficer-reported\nverified-provider", default="requested-only"),
                 F("duration_seconds", "Int"), F("duration_label"),
                 F("sms_status", "Select", options="\nMessage Created\nQueued\nProvider Accepted\nSent\nDelivered\nFailed\nUnknown"),
                 F("acknowledged", "Check"), F("warning_confirmed", "Check", description="Officer confirmed the warning was delivered and understood"), F("message_text", "Small Text", description="Exact text sent (immutable once sent)"),
                 F("template_version"), F("provider"), F("provider_ref", search_index=1), F("error", "Small Text"),
                 F("client_uuid", unique=1), F("notice", "Link", options="CPCP Warning Notice")],
         perms=[perm(R_ADMIN), perm(R_SECM), perm(R_AUD)]),

    dict(name="CPCP Communication Event", autoname="hash", append_only=True, sensitivity="RESTRICTED_EVIDENCE",
         fields=[F("attempt", "Link", options="CPCP Communication Attempt", reqd=1, search_index=1),
                 F("event_type", reqd=1, in_list_view=1), F("provider_ts"), F("ingested_at", "Datetime"),
                 F("idempotency_key", unique=1, reqd=1), F("signature_valid", "Check")],
         perms=[perm(R_ADMIN), perm(R_SECM), perm(R_AUD)]),

    dict(name="CPCP Warning Notice", autoname="format:WN-{#####}", append_only=True, sensitivity="RESTRICTED_EVIDENCE",
         fields=[F("incident", "Link", options="CPCP Violation Incident", reqd=1, unique=1), F("policy_version", reqd=1),
                 F("notice_method"), F("proof_basis", reqd=1), F("effective_at", "Datetime", reqd=1),
                 F("grace_minutes", "Int", reqd=1), F("deadline", "Datetime", reqd=1),
                 F("attempt", "Link", options="CPCP Communication Attempt"), F("established_by", "Link", options="User"),
                 F("override_reason", "Small Text")],
         perms=[perm(R_ADMIN), perm(R_SECM), perm(R_OFF), perm(R_AUD)]),

    dict(name="CPCP Enforcement Action", autoname="format:ENF-{#####}", sensitivity="RESTRICTED_EVIDENCE",
         desc="Clamp / tow / release records. Every transition is gated by legal flags and separation of duties.",
         fields=[F("incident", "Link", options="CPCP Violation Incident", reqd=1, in_list_view=1, search_index=1),
                 F("action_type", "Select", options="Clamp\nTow\nCancel\nRelease", reqd=1, in_list_view=1),
                 F("status", "Select", options="Proposed\nApproved\nExecuted\nCancelled", default="Proposed", in_list_view=1),
                 F("proposed_by", "Link", options="User", reqd=1), F("approved_by", "Link", options="User"),
                 F("executed_by", "Link", options="User"), F("approved_at", "Datetime"), F("executed_at", "Datetime"),
                 F("legal_basis_reference"), F("reason", "Small Text"),
                 F("provider_ref"), F("yard_arrival_at", "Datetime"), F("release_at", "Datetime"),
                 F("active_key", unique=1, description="incident:type while the action is live; at most one live clamp/tow per episode")],
         perms=[perm(R_ADMIN), perm(R_SECM), perm(R_OFF), perm(R_AUD)]),

    dict(name="CPCP Incident Charge", autoname="format:CHG-{#####}", append_only=True, sensitivity="FINANCIAL",
         fields=[F("incident", "Link", options="CPCP Violation Incident", reqd=1, in_list_view=1, search_index=1),
                 F("charge_class", "Select", options="PARKING_VIOLATION\nTOW_SERVICE\nSTORAGE\nOTHER_APPROVED_SERVICE\nADJUSTMENT_CREDIT\nREFUND", reqd=1, in_list_view=1),
                 F("quantity", "Float", reqd=1), F("unit_price", "Currency", reqd=1), F("amount", "Currency", in_list_view=1),
                 F("currency", reqd=1), F("source"), F("schedule_version"), F("idempotency_key", unique=1, reqd=1),
                 F("created_by_user", "Link", options="User")],
         perms=[perm(R_ADMIN), perm(R_FIN), perm(R_SECM), perm(R_AUD)]),

    dict(name="CPCP Appeal", autoname="format:APL-{#####}", sensitivity="FINANCIAL",
         fields=[F("incident", "Link", options="CPCP Violation Incident", reqd=1, in_list_view=1, search_index=1),
                 F("submitted_by", "Link", options="User", reqd=1), F("submitted_at", "Datetime"),
                 F("reason", "Small Text", reqd=1),
                 F("status", "Select", options="Submitted\nIn Review\nUpheld\nDismissed\nPartially Upheld", default="Submitted", in_list_view=1),
                 F("reviewer", "Link", options="User"), F("decision", "Small Text"), F("decided_at", "Datetime")],
         perms=[perm(R_ADMIN), perm(R_FIN), perm(R_AUD)]),

    dict(name="CPCP Gate Shift", autoname="format:SHIFT-{#####}", sensitivity="STAFF_OPERATIONAL",
         desc="Server-side proof that an officer is on duty at a gate, on a registered device. Expires on the server.",
         fields=[F("user", "Link", options="User", reqd=1, in_list_view=1), F("estate", "Link", options="CPCP Estate", reqd=1),
                 F("gate", "Link", options="CPCP Gate", reqd=1), F("device_hash", reqd=1),
                 F("status", "Select", options="On Duty\nEnded\nRevoked", default="On Duty", in_list_view=1, search_index=1),
                 F("started_at", "Datetime"), F("ends_at", "Datetime"), F("ended_at", "Datetime"), F("ended_reason"),
                 F("active_key", unique=1, description="user while On Duty: at most one live shift per person")],
         perms=[perm(R_ADMIN), perm(R_SECM)]),

    dict(name="CPCP Device Registration", autoname="hash", sensitivity="STAFF_OPERATIONAL",
         fields=[F("user", "Link", options="User", reqd=1), F("device_hash", reqd=1),
                 F("status", "Select", options="Active\nRevoked", default="Active", in_list_view=1),
                 F("revoked_by", "Link", options="User"), F("revoked_at", "Datetime"), F("reason", "Small Text"),
                 F("device_key", unique=1, description="user:device_hash")],
         perms=[perm(R_ADMIN), perm(R_SECM)]),

    dict(name="CPCP Emergency Access", autoname="format:EMG-{#####}", sensitivity="IMMUTABLE_AUDIT",
         desc="Break-glass grant: one household, minimum fields, short expiry, independent review required.",
         fields=[F("requested_by", "Link", options="User", reqd=1, in_list_view=1), F("estate", "Link", options="CPCP Estate", reqd=1),
                 F("unit", "Link", options="CPCP Unit", reqd=1), F("incident", "Link", options="CPCP Violation Incident"),
                 F("reason", "Small Text", reqd=1), F("granted_at", "Datetime"), F("expires_at", "Datetime", in_list_view=1),
                 F("status", "Select", options="Active\nExpired\nReviewed", default="Active", in_list_view=1, search_index=1),
                 F("reveal_count", "Int", default="0"),
                 F("reviewed_by", "Link", options="User"), F("reviewed_at", "Datetime"),
                 F("review_outcome", "Select", options="\nAppropriate\nInappropriate\nNeeds follow-up"), F("review_note", "Small Text")],
         perms=[perm(R_ADMIN), perm(R_AUD)]),

    dict(name="CPCP Access Review Flag", autoname="format:ARF-{#####}", sensitivity="IMMUTABLE_AUDIT",
         desc="A review SIGNAL for human reviewers. Never evidence of misconduct and never triggers discipline automatically.",
         fields=[F("rule", reqd=1, in_list_view=1), F("actor_user", in_list_view=1), F("estate"), F("window_key", unique=1),
                 F("summary", "Small Text", description="Counts and references only; no personal data"), F("count", "Int"),
                 F("severity", "Select", options="Low\nMedium\nHigh", default="Medium"),
                 F("status", "Select", options="New\nIn Review\nClosed - No Action\nEscalated", default="New", in_list_view=1, search_index=1),
                 F("reviewer", "Link", options="User"), F("review_note", "Small Text"), F("created_at", "Datetime"), F("reviewed_at", "Datetime")],
         perms=[perm(R_ADMIN), perm(R_AUD)]),

    dict(name="CPCP Access Grant", autoname="format:GRANT-{#####}", title_field="grantee",
         desc="Time-limited, independently approved exceptional access (auditors, exports). Never a blanket permission.",
         fields=[F("grantee", "Link", options="User", reqd=1, in_list_view=1),
                 F("capability", "Select", options=CAPABILITY_OPTIONS, reqd=1, in_list_view=1),
                 F("purpose", "Small Text", reqd=1), F("expires_at", "Datetime", reqd=1, in_list_view=1),
                 F("status", "Select", options="Requested\nApproved\nRevoked", default="Requested", in_list_view=1),
                 F("requested_by", "Link", options="User", read_only=1), F("approved_by", "Link", options="User", read_only=1)],
         perms=[perm(R_ADMIN, "rwc"), perm(R_AUD), perm(R_SYS)]),

    dict(name="CPCP Policy Version", autoname="format:POL-{#####}", title_field="version_label",
         fields=[F("estate", "Link", options="CPCP Estate"), F("version_label", reqd=1, in_list_view=1),
                 F("status", "Select", options="Draft\nApproved\nActive\nSuperseded", default="Draft", in_list_view=1),
                 F("grace_minutes", "Int", default="15"), F("effective_from", "Datetime"),
                 F("violation_penalty", "Currency", description="Blank = not configured. No default fee is ever assumed."),
                 F("storage_rate_per_period", "Currency"), F("storage_period_hours", "Int", default="24"),
                 F("created_by_user", "Link", options="User", read_only=1), F("approved_by", "Link", options="User", read_only=1)],
         perms=[perm(R_ADMIN, "rwc"), perm(R_SECM), perm(R_FIN), perm(R_AUD), perm(R_SYS, "rwc")]),
]


def build(spec: dict) -> dict:
    fields = spec["fields"]
    is_table = bool(spec.get("istable"))
    doc = {
        "actions": [], "allow_rename": 0, "creation": TS, "doctype": "DocType", "engine": "InnoDB",
        "field_order": [f["fieldname"] for f in fields], "fields": fields, "index_web_pages_for_search": 0,
        "issingle": spec.get("issingle", 0), "istable": 1 if is_table else 0, "links": [], "modified": TS,
        "modified_by": "Administrator", "module": MODULE, "name": spec["name"], "owner": "Administrator",
        "permissions": spec.get("perms", []), "sort_field": "modified", "sort_order": "DESC", "states": [],
        "track_changes": 0 if spec.get("append_only") else 1, "description": spec.get("desc", ""),
    }
    if spec.get("autoname"):
        doc["autoname"] = spec["autoname"]
        doc["naming_rule"] = {"hash": "Random", }.get(spec["autoname"], "Expression") if spec["autoname"].startswith(("format:", "hash")) else "By fieldname"
        if spec["autoname"] == "hash":
            doc["naming_rule"] = "Random"
            doc.pop("autoname")
        else:
            doc["naming_rule"] = "Expression (old style)"
    if spec.get("title_field"):
        doc["title_field"] = spec["title_field"]
    for f in doc["fields"]:
        if f["fieldtype"] == "Select" and not f.get("options"):
            raise ValueError(f"{spec['name']}.{f['fieldname']} Select needs options")
    return doc


def main() -> None:
    names = set()
    for spec in DOCTYPES:
        assert spec["name"] not in names, spec["name"]
        names.add(spec["name"])
        d = scrub(spec["name"])
        folder = ROOT / d
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "__init__.py").touch()
        (folder / f"{d}.json").write_text(json.dumps(build(spec), indent=1) + "\n", encoding="utf-8")
        ctrl = folder / f"{d}.py"
        if not ctrl.exists():
            cls = spec["name"].replace(" ", "")  # Frappe derives the controller class from the DocType name
            ctrl.write_text(
                "# SPDX-License-Identifier: Apache-2.0\nfrom frappe.model.document import Document\n\n\n"
                f"class {cls}(Document):\n    pass\n", encoding="utf-8")
    meta = {s["name"]: {"append_only": bool(s.get("append_only")), "sensitivity": s.get("sensitivity", "STAFF_OPERATIONAL")}
            for s in DOCTYPES}
    (ROOT.parent / "doctype_meta.json").write_text(json.dumps(meta, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"generated {len(DOCTYPES)} doctypes")


if __name__ == "__main__":
    main()
