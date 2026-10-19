# SPDX-License-Identifier: Apache-2.0
"""Dashboards, hotspot layers and resident-safe community summaries (PRD 11, 30.3, 35.4, 47, 52; AC-12, AC-13, AC-50).

Rules: every number states its denominator; allegations and verified incidents are separate layers; resident views are
aggregate only (k-threshold suppression, delayed, no points); money appears only for finance/admin roles.
"""
from datetime import datetime, time, timedelta

import frappe
from frappe.utils import add_days, getdate, nowdate

from frappe_cpcp.core import geo
from frappe_cpcp.permissions import authorize, get_actor
from frappe_cpcp.services.common import from_db, to_db, utcnow

K_THRESHOLD = 5
RESIDENT_DELAY_HOURS = 24


def _range(date_from, date_to):
    start = getdate(date_from) if date_from else getdate(add_days(nowdate(), -30))
    end = getdate(date_to) if date_to else getdate(nowdate())
    return start, end + timedelta(days=1)


def _median(values: list[float]):
    v = sorted(values)
    n = len(v)
    return None if not n else (v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2)


@frappe.whitelist()
def dashboard(estate: str, date_from: str | None = None, date_to: str | None = None) -> dict:
    role = get_actor().role.value
    if role == "resident":  # residents get community_summary only, never operational counts
        raise frappe.PermissionError("not permitted")
    actor = authorize("aggregate_dashboards", "V" if role in ("auditor", "board_observer") else "R", estate=estate)
    a, b = _range(date_from, date_to)
    rng = {"e": estate, "a": a, "b": b}
    q = lambda sql: frappe.db.sql(sql, rng, as_dict=True)  # noqa: E731
    alleg = q("select mode, state, count(*) n from `tabCPCP Parking Allegation` where estate=%(e)s and submitted_at>=%(a)s and submitted_at<%(b)s group by mode, state")
    total_alleg = sum(r.n for r in alleg)
    verified = sum(r.n for r in alleg if r.state.startswith("Verified"))
    inc = q("select status, classification, count(*) n from `tabCPCP Violation Incident` where estate=%(e)s and verified_at>=%(a)s and verified_at<%(b)s group by status, classification")
    visits = q("select status, presence, estimated, duration_minutes from `tabCPCP Visitor Session` where estate=%(e)s and entry_at>=%(a)s and entry_at<%(b)s")
    durations = [r.duration_minutes for r in visits if r.presence == "Confirmed Out" and not r.estimated and r.duration_minutes is not None]
    comms = q("""select c.channel, c.provenance, c.outcome, c.sms_status, c.acknowledged from `tabCPCP Communication Attempt` c
                 join `tabCPCP Violation Incident` i on i.name=c.incident where i.estate=%(e)s and c.initiated_at>=%(a)s and c.initiated_at<%(b)s""")
    notices = q("select count(*) n from `tabCPCP Warning Notice` w join `tabCPCP Violation Incident` i on i.name=w.incident where i.estate=%(e)s and w.effective_at>=%(a)s and w.effective_at<%(b)s")[0].n
    corrected = q("select count(*) n from `tabCPCP Violation Incident` where estate=%(e)s and status='corrected_no_fee' and verified_at>=%(a)s and verified_at<%(b)s")[0].n
    out = {
        "range": {"from": str(a), "to": str(b - timedelta(days=1))},
        "allegations": {"submitted": total_alleg, "verified": verified,
                        "by_source": {m: sum(r.n for r in alleg if r.mode == m) for m in ("Identified", "Anonymous", "Contactable Confidential")},
                        "conversion_rate": {"numerator": verified, "denominator": total_alleg,
                                            "value": round(verified / total_alleg, 3) if total_alleg else None},
                        "note": "Allegations are unverified resident reports; they are not violations."},
        "verified_incidents": {"total": sum(r.n for r in inc), "by_status": _group(inc, "status"), "by_classification": _group(inc, "classification")},
        "compliance": {"warned": notices, "corrected_without_fee": corrected,
                       "corrected_rate": {"numerator": corrected, "denominator": notices or None,
                                          "value": round(corrected / notices, 3) if notices else None}},
        "visitors": {"arrivals": len(visits), "inside_now_estimate": sum(1 for r in visits if r.status in ("Checked In", "Exit Unconfirmed", "Needs Supervisor Review")),
                     "verified_duration_minutes": {"count": len(durations), "median": _median(durations), "max": max(durations) if durations else None},
                     "excluded_from_duration": len(visits) - len(durations),
                     "caveat": "Operational estimate from recorded arrivals/departures, not a census of persons on site."},
        "communications": {"calls_requested": sum(1 for r in comms if r.channel == "call_dialer"),
                           "calls_answered_officer_reported": sum(1 for r in comms if r.channel == "call_dialer" and r.outcome == "Answered"),
                           "calls_provider_verified": sum(1 for r in comms if r.provenance == "verified-provider"),
                           "sms_accepted": sum(1 for r in comms if r.sms_status in ("Provider Accepted", "Sent", "Delivered")),
                           "sms_delivered": sum(1 for r in comms if r.sms_status == "Delivered"),
                           "sms_failed": sum(1 for r in comms if r.sms_status == "Failed"),
                           "sms_acknowledged": sum(1 for r in comms if r.acknowledged)},
    }
    if actor.role.value in ("org_admin", "estate_manager", "finance"):
        rows = q("""select ch.charge_class, sum(ch.amount) total, count(*) n from `tabCPCP Incident Charge` ch join `tabCPCP Violation Incident` i on i.name=ch.incident
                    where i.estate=%(e)s and ch.creation>=%(a)s and ch.creation<%(b)s group by ch.charge_class""")
        out["finance"] = {r.charge_class: {"total": str(r.total), "lines": r.n} for r in rows}
    return out


def _group(rows, key):
    d: dict = {}
    for r in rows:
        d[r[key]] = d.get(r[key], 0) + r.n
    return d


@frappe.whitelist()
def hotspots(estate: str, date_from: str | None = None, date_to: str | None = None, classification: str | None = None,
             status: str | None = None, zone: str | None = None) -> dict:
    """Management/security map data. Two clearly labelled layers: verified incidents (officer-confirmed pins) and
    unverified allegations (reporter-claimed pins). Reporter positions are never plotted."""
    authorize("incident_reports", "R", estate=estate) if get_actor().role.value != "security_officer" else authorize("verify_incident", "C", estate=estate)
    a, b = _range(date_from, date_to)
    start_dt, end_dt = datetime.combine(a, time.min), datetime.combine(b, time.min)
    f = {"estate": estate, "verified_at": ["between", [start_dt, end_dt]]}
    if classification:
        f["classification"] = classification
    if status:
        f["status"] = status
    if zone:
        f["zone"] = zone
    inc = frappe.get_all("CPCP Violation Incident", filters=f, fields=["name", "latitude", "longitude", "accuracy_m", "classification", "status", "verified_at", "pin_source", "zone"], limit=2000)
    af = {"estate": estate, "latitude": ["is", "set"], "submitted_at": [">=", start_dt], "state": ["not in", ["Withdrawn"]]}
    if zone:
        af["zone"] = zone
    alg = frappe.get_all("CPCP Parking Allegation", filters=af, fields=["name", "latitude", "longitude", "category", "state", "submitted_at", "mode"], limit=2000)
    by_zone: dict = {}
    for r in inc:
        by_zone[r.zone or "unzoned"] = by_zone.get(r.zone or "unzoned", 0) + 1
    return {
        "verified_incidents": {"label": "Verified violations (officer-confirmed pin)",
                               "points": [{"id": r.name, "lat": r.latitude, "lon": r.longitude, "accuracy_m": r.accuracy_m,
                                           "tier": geo.accuracy_tier(r.accuracy_m), "classification": r.classification, "status": r.status,
                                           "date": str(from_db(r.verified_at).date()), "pin_source": r.pin_source}
                                          for r in inc if r.latitude is not None]},
        "allegations": {"label": "UNVERIFIED allegations (reporter-claimed vehicle pin)",
                        "points": [{"id": r.name, "lat": r.latitude, "lon": r.longitude, "category": r.category, "state": r.state,
                                    "date": str(from_db(r.submitted_at).date())} for r in alg]},
        "zone_counts": by_zone,
        "caveat": "Density shows reports and enforcement attention, not causation. Compare against capacity or patrol hours before drawing conclusions.",
    }


@frappe.whitelist()
def community_summary(estate: str) -> dict:
    """Resident-safe aggregate: zone totals for the last 90 days, delayed 24h, cells under K suppressed, no points/IDs."""
    authorize("aggregate_dashboards", "V", estate=estate)
    end = to_db(utcnow() - timedelta(hours=RESIDENT_DELAY_HOURS))
    start = to_db(utcnow() - timedelta(days=90))
    rows = frappe.get_all("CPCP Violation Incident", filters={"estate": estate, "verified_at": ["between", [start, end]]}, fields=["zone"], limit=5000)
    names = {z.name: z.zone_name for z in frappe.get_all("CPCP Zone", filters={"estate": estate}, fields=["name", "zone_name"])}
    counts = geo.zone_counts_with_threshold([r.zone or "unzoned" for r in rows], K_THRESHOLD)
    return {"window_days": 90, "delay_hours": RESIDENT_DELAY_HOURS, "min_cell_size": K_THRESHOLD,
            "zones": [{"zone": names.get(z, "Other areas"), "count": c if c is not None else f"fewer than {K_THRESHOLD}"} for z, c in counts.items()],
            "note": "Counts of verified parking issues by area. Small counts are hidden to protect privacy."}
