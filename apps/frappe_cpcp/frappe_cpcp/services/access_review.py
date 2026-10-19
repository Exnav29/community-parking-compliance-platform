# SPDX-License-Identifier: Apache-2.0
"""Misuse-detection signals over the access journal (PRD 61.7). Signals go to designated reviewers, never to the person concerned,
and they are NOT findings: nothing here accuses, suspends or disciplines anyone."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import frappe
from frappe.utils import cint

from frappe_cpcp.services.access import TABLE
from frappe_cpcp.services.common import to_db, utcnow

GATE_PURPOSES = ("gate_entry", "gate_exit")
OUT_OF_DUTY_CODES = ("no_active_shift", "shift_other_estate", "gate_mismatch", "device_or_session_revoked", "not_assigned_to_case",
                     "target_not_part_of_case", "case_other_estate", "case_not_found_or_closed", "unknown_purpose")


def _setting(field: str, default: int) -> int:
    return cint(frappe.db.get_single_value("CPCP Settings", field) or default)


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def _flag(rule: str, actor: str, estate: str, bucket: str, count: int, summary: str, severity: str) -> bool:
    key = f"{rule}:{actor}:{bucket}"
    if frappe.db.exists("CPCP Access Review Flag", {"window_key": key}):
        return False
    frappe.get_doc({"doctype": "CPCP Access Review Flag", "rule": rule, "actor_user": actor, "estate": estate, "window_key": key,
                    "summary": summary, "count": count, "severity": severity, "status": "New", "created_at": to_db(utcnow())}).insert(ignore_permissions=True)
    _notify_reviewers(rule, actor, estate, key)
    return True


def _notify_reviewers(rule: str, actor: str, estate: str, key: str) -> None:
    """Reviewers are org admins and auditors of the estate's organization, excluding the person the signal is about."""
    from frappe_cpcp.services.episodes import _outbox

    users = {(r.user, r.cpcp_role) for r in frappe.get_all("CPCP Role Assignment", filters={"status": "Active", "cpcp_role": ["in", ["org_admin", "auditor"]]},
                                                          fields=["user", "cpcp_role"]) if r.user != actor}
    _outbox(key, sorted(users), "access_review_signal", key, {"rule": rule})  # payload carries the rule only: no names, no units


def run_detection(now: datetime | None = None, window_minutes: int = 60) -> dict:
    """Idempotent per (rule, actor, hour). Returns counts of flags raised per rule."""
    now = now or utcnow()
    since, day_since = _iso(now - timedelta(minutes=window_minutes)), _iso(now - timedelta(hours=24))
    bucket = now.strftime("%Y%m%d%H")
    raised: dict[str, int] = {}

    def add(rule, actor, estate, count, summary, severity="Medium"):
        if _flag(rule, actor, estate or "", bucket, count, summary, severity):
            raised[rule] = raised.get(rule, 0) + 1

    q = lambda sql, *p: frappe.db.sql(sql, p, as_dict=True)  # noqa: E731
    ok_results = ("Allowed", "No Match")

    for r in q(f"select actor, max(estate) estate, count(distinct target_unit) n from `{TABLE}` where at_utc>=%s and result in %s and target_unit != '' "
               "and purpose in %s group by actor having n >= %s", since, ok_results, GATE_PURPOSES, _setting("ar_distinct_units_per_hour", 12)):
        add("many_households_in_an_hour", r.actor, r.estate, r.n, f"{r.n} different households looked up within {window_minutes} minutes", "High")

    for r in q(f"select actor, max(estate) estate, target_unit, count(*) n from `{TABLE}` where at_utc>=%s and result in %s and target_unit != '' "
               "and action in ('history','history_bare','search') and purpose in %s group by actor, target_unit having n >= %s",
               day_since, ok_results, GATE_PURPOSES, _setting("ar_repeat_unit_per_day", 4)):
        add("repeat_lookup_same_household", r.actor, r.estate, r.n, f"{r.n} lookups of one household in 24 hours without a case or visit reference", "Medium")

    for r in q(f"select actor, max(estate) estate, count(*) n from `{TABLE}` where at_utc>=%s and result='Denied' group by actor having n >= %s",
               since, _setting("ar_denied_per_hour", 5)):
        add("repeated_denied_attempts", r.actor, r.estate, r.n, f"{r.n} denied sensitive-access attempts within {window_minutes} minutes", "High")

    for r in q(f"select actor, max(estate) estate, count(*) n from `{TABLE}` where at_utc>=%s and action in ('history','history_bare') and result in %s "
               "group by actor having n >= %s", since, ok_results, _setting("ar_suggestions_per_hour", 20)):
        add("high_volume_suggestion_lookups", r.actor, r.estate, r.n, f"{r.n} returning-visitor suggestion lookups within {window_minutes} minutes", "Medium")

    for r in q(f"select actor, max(estate) estate, count(*) n from `{TABLE}` where at_utc>=%s and result='Denied' and reason_code in %s group by actor having n >= 2",
               since, OUT_OF_DUTY_CODES):
        add("outside_assigned_duty", r.actor, r.estate, r.n, f"{r.n} attempts outside the person's shift, gate, estate or assigned case", "Medium")

    for r in q(f"select actor, max(estate) estate, count(*) n from `{TABLE}` where at_utc>=%s and category='contact_reveal' and result='Denied' group by actor having n >= 1",
               since):
        add("contact_reveal_without_workflow", r.actor, r.estate, r.n, f"{r.n} attempts to reveal contact details without a matching assigned case", "High")

    for r in q(f"select actor, max(estate) estate, count(*) n from `{TABLE}` where at_utc>=%s and result='Emergency' and action='emergency_grant' group by actor", since):
        add("emergency_access_used", r.actor, r.estate, r.n, f"{r.n} break-glass emergency grant(s) issued; independent review required", "High")

    for r in q(f"select actor, max(role) role, max(estate) estate, count(*) n from `{TABLE}` where at_utc>=%s and result='Allowed' and purpose in ('administration','supervisor_review') "
               "and role in ('org_admin','estate_manager','security_manager','platform_admin') group by actor having n >= 40", since):
        add("privileged_access_volume", r.actor, r.estate, r.n, f"{r.n} sensitive records opened by a {r.role} within {window_minutes} minutes", "Medium")

    overdue = frappe.get_all("CPCP Emergency Access", filters={"status": "Expired", "reviewed_at": ["is", "not set"]}, fields=["name", "requested_by", "estate"])
    for g in overdue:
        add("emergency_review_overdue", g.requested_by, g.estate, 1, f"Emergency grant {g.name} expired without an independent review", "High")
    return raised


def run_detection_job():
    """Scheduler entry (hourly). Also expires emergency grants. Never raises into the scheduler."""
    try:
        expire_emergency_grants()
        run_detection()
        frappe.db.commit()
    except Exception:
        frappe.log_error(title="CPCP access review detection failed")


def expire_emergency_grants() -> int:
    n = 0
    for g in frappe.get_all("CPCP Emergency Access", filters={"status": "Active", "expires_at": ["<=", to_db(utcnow())]}, pluck="name"):
        frappe.db.set_value("CPCP Emergency Access", g, "status", "Expired", update_modified=False)
        n += 1
    return n


def utc_floor(dt: datetime) -> datetime:
    return dt.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)
