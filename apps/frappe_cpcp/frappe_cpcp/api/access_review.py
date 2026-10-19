# SPDX-License-Identifier: Apache-2.0
"""Access Review dashboard API (PRD 61.7; PBAC-14, PBAC-15, PBAC-17).

Visible to organization admins, designated auditors (read-only) and, for officer activity only, security managers. Security
officers have no entry. Reviewing is itself journaled ("reviewers are reviewed"), and nobody can see signals about themselves.
"""
import csv
import io
from datetime import timedelta

import frappe
from frappe.utils import cint

from frappe_cpcp.permissions import authorize
from frappe_cpcp.services import access, access_review
from frappe_cpcp.services.access import TABLE
from frappe_cpcp.services.common import to_db, utcnow

SAFE_COLS = "at_utc, actor, role, estate, gate, action, record_type, target_unit, category, purpose, purpose_ref, result, reason_code, request_id"


def _scope_sql(actor) -> tuple[str, list]:
    """Which journal rows this reviewer may see. Security managers: officers only (never managers/admins, never their own)."""
    if actor.role.value == "security_manager":
        return " and role = 'security_officer' and actor != %s", [actor.user]
    return "", []


def _record_review(actor, action: str, ctx: str) -> None:
    access.record(actor=actor.user, role=actor.role.value, estate=",".join(sorted(actor.estate_ids))[:60], action=action, record_type="Access Journal",
                  category="restricted_legal", purpose="access_review", context=ctx)


@frappe.whitelist()
def search(actor_user: str | None = None, unit: str | None = None, result: str | None = None, purpose: str | None = None,
           date_from: str | None = None, date_to: str | None = None, limit: int = 200, offset: int = 0) -> dict:
    a = authorize("access_review", "R")
    scope, params = _scope_sql(a)
    sql, p = f"select {SAFE_COLS} from `{TABLE}` where 1=1" + scope, list(params)
    for col, val in (("actor", actor_user), ("target_unit", unit.upper() if unit else None), ("result", result), ("purpose", purpose)):
        if val:
            sql += f" and {col} = %s"
            p.append(val)
    if date_from:
        sql += " and at_utc >= %s"
        p.append(date_from)
    if date_to:
        sql += " and at_utc <= %s"
        p.append(date_to + "T23:59:59" if len(date_to) == 10 else date_to)
    sql += " order by seq desc limit %s offset %s"
    p += [min(cint(limit), 500), cint(offset)]
    rows = access.query(sql, p)  # fresh connection: always the latest committed events
    _record_review(a, "review", f"search returned {len(rows)} rows")
    return {"rows": rows, "count": len(rows)}


@frappe.whitelist()
def summary(date_from: str | None = None, date_to: str | None = None) -> dict:
    """Per-person outcome counts, distinct households, and the most-looked-up households (counts only)."""
    a = authorize("access_review", "R")
    scope, params = _scope_sql(a)
    since = date_from or (utcnow() - timedelta(days=7)).strftime("%Y-%m-%d")
    until = (date_to + "T23:59:59") if date_to else "9999"
    base = f"from `{TABLE}` where at_utc >= %s and at_utc <= %s" + scope
    p = [since, until] + params
    people = access.query(f"select actor, max(role) role, sum(result='Allowed') allowed, sum(result='Denied') denied, sum(result='No Match') no_match, "
                           f"sum(result='Emergency') emergency, count(distinct nullif(target_unit,'')) households {base} group by actor order by denied desc, households desc", p)
    repeats = access.query(f"select target_unit unit, count(*) lookups, count(distinct actor) officers {base} and target_unit != '' and action in ('search','history','history_bare','contact') "
                            "group by target_unit having lookups >= 3 order by lookups desc limit 20", p)
    _record_review(a, "review", "summary")
    return {"people": [{**r, "allowed": int(r["allowed"] or 0), "denied": int(r["denied"] or 0), "no_match": int(r["no_match"] or 0),
                        "emergency": int(r["emergency"] or 0)} for r in people], "most_looked_up_households": repeats,
            "note": "Counts are signals for a fair human review, not evidence of misconduct."}


@frappe.whitelist()
def flags(status: str | None = None) -> list[dict]:
    a = authorize("access_review", "R")
    f = {"status": status} if status else {}
    rows = frappe.get_all("CPCP Access Review Flag", filters=f, fields=["name", "rule", "actor_user", "estate", "summary", "count", "severity", "status", "created_at", "reviewer"],
                          order_by="creation desc", limit=200)
    if a.role.value == "security_manager":  # managers see signals about officers only
        officers = set(frappe.get_all("CPCP Role Assignment", filters={"cpcp_role": "security_officer"}, pluck="user"))
        rows = [r for r in rows if r.actor_user in officers and r.actor_user != a.user]
    else:
        rows = [r for r in rows if r.actor_user != a.user]  # nobody reviews signals about themselves
    _record_review(a, "review", f"flags {len(rows)}")
    return rows


@frappe.whitelist(methods=["POST"])
def review_flag(flag: str, outcome: str, note: str) -> dict:
    a = authorize("access_review", "U")  # auditors hold read only; managers hold none
    f = frappe.db.get_value("CPCP Access Review Flag", flag, ["actor_user", "status"], as_dict=True)
    if not f or f.actor_user == a.user:
        raise frappe.PermissionError("not permitted")
    if outcome not in ("In Review", "Closed - No Action", "Escalated") or not (note or "").strip():
        frappe.throw("An outcome and a note are required", frappe.ValidationError)
    frappe.db.set_value("CPCP Access Review Flag", flag, {"status": outcome, "reviewer": a.user, "review_note": note, "reviewed_at": to_db(utcnow())}, update_modified=False)
    _record_review(a, "review", f"flag {flag} -> {outcome}")
    return {"flag": flag, "status": outcome, "note": "A signal is not a finding. No action is taken automatically."}


@frappe.whitelist(methods=["POST"])
def run_detection() -> dict:
    a = authorize("access_review", "U")
    access_review.expire_emergency_grants()
    raised = access_review.run_detection()
    _record_review(a, "review", f"detection run: {sum(raised.values())} signals")
    return {"raised": raised}


@frappe.whitelist()
def pending_emergency_reviews() -> list[dict]:
    a = authorize("access_review", "R")
    rows = frappe.get_all("CPCP Emergency Access", filters={"status": ["in", ["Active", "Expired"]]},
                          fields=["name", "requested_by", "estate", "unit", "granted_at", "expires_at", "status", "reveal_count", "reason"])
    return [r for r in rows if r.requested_by != a.user]


@frappe.whitelist()
def export_log(date_from: str | None = None, date_to: str | None = None) -> dict:
    """Audit export for organization admins only. Contains identifiers and outcomes, never personal data. The export is itself journaled."""
    a = authorize("access_review", "U")
    if a.role.value not in ("org_admin", "estate_manager"):
        raise frappe.PermissionError("not permitted")
    sql, p = f"select {SAFE_COLS} from `{TABLE}` where 1=1", []
    if date_from:
        sql += " and at_utc >= %s"
        p.append(date_from)
    if date_to:
        sql += " and at_utc <= %s"
        p.append(date_to + "T23:59:59" if len(date_to) == 10 else date_to)
    rows = access.query(sql + " order by seq asc limit 5000", p)
    out = io.StringIO()
    w = csv.DictWriter(out, fieldnames=list(rows[0].keys()) if rows else SAFE_COLS.replace(" ", "").split(","))
    w.writeheader()
    w.writerows(rows)
    access.record(actor=a.user, role=a.role.value, action="export", record_type="Access Journal", category="restricted_legal", purpose="access_review",
                  context=f"{len(rows)} rows exported")
    return {"rows": len(rows), "csv": out.getvalue()}


@frappe.whitelist()
def verify_chain() -> dict:
    authorize("access_review", "R")
    ok, bad = access.verify_chain()
    return {"intact": ok, "first_bad_seq": bad}


@frappe.whitelist()
def verify_audit_chain() -> dict:
    """Integrity of the general audit chain (policy, enforcement, merges...) for reviewers."""
    authorize("access_review", "R")
    from frappe_cpcp.services.audit import verify_audit_chain as _verify
    ok, bad = _verify()
    return {"intact": ok, "first_bad_seq": bad}
