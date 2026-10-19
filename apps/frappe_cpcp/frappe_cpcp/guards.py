# SPDX-License-Identifier: Apache-2.0
"""Request-level guard for sensitive doctypes (PRD 61.5 / 61.6; PBAC-04, PBAC-12, PBAC-15).

Frappe exposes records through many doors: /app lists and forms, /api/resource, frappe.client.*, reportview, search/autocomplete,
export, print/PDF, share/email. This guard runs on EVERY request (``before_request`` hook) and, when a request names a sensitive
doctype, decides once and journals durably:

  * security officers and any role without registry authority: DENIED, journaled, no data;
  * exports / print / email / share of sensitive doctypes: DENIED for everyone (bulk disclosure needs a separate approved-export flow);
  * managers and administrators (including the platform Administrator): allowed for administration but ALWAYS journaled, so they are
    reviewable by independent reviewers;
  * auditors: only with an unexpired, independently approved grant.

CPCP's own whitelisted APIs (frappe_cpcp.api.*) never take a doctype and enforce their own purpose checks, so they pass through.
"""
from __future__ import annotations

import json
from urllib.parse import unquote

import frappe

from frappe_cpcp.services import access

SENSITIVE_DOCTYPES = {
    "CPCP Person", "CPCP Unit Membership", "CPCP Vehicle", "CPCP Vehicle Unit Association", "CPCP Visitor Session", "CPCP Visit Event",
    "CPCP Communication Attempt", "CPCP Communication Event", "CPCP Officer Evidence", "CPCP Parking Allegation", "CPCP Allegation Receipt",
    "CPCP Allegation Review Event", "CPCP Warning Notice", "CPCP Enforcement Action", "CPCP Incident Charge", "CPCP Appeal",
    "CPCP Sensitive Access Event", "CPCP Access Review Flag", "CPCP Emergency Access", "CPCP Gate Shift", "CPCP Device Registration",
    "CPCP Audit Event", "CPCP Access Grant", "CPCP Role Assignment",
}
CATEGORY = {
    "CPCP Person": "sensitive_personal", "CPCP Unit Membership": "sensitive_personal", "CPCP Vehicle": "sensitive_personal",
    "CPCP Vehicle Unit Association": "sensitive_personal", "CPCP Visitor Session": "restricted_safety", "CPCP Visit Event": "restricted_safety",
    "CPCP Communication Attempt": "contact_reveal", "CPCP Communication Event": "restricted_legal", "CPCP Officer Evidence": "restricted_legal",
    "CPCP Parking Allegation": "restricted_safety", "CPCP Allegation Receipt": "restricted_safety", "CPCP Allegation Review Event": "restricted_safety",
}
READ_ROLES = {"org_admin", "estate_manager", "security_manager"}
BLOCKED_ACTIONS = ("export", "print", "pdf", "email", "share", "download")
_DOCTYPE_KEYS = ("doctype", "dt", "ref_doctype", "reference_doctype", "parent_doctype")
PASS_PREFIXES = ("/assets", "/files", "/private", "/api/method/login", "/api/method/logout", "/api/method/ping", "/api/method/frappe_cpcp.api.",
                 "/api/method/frappe.auth", "/api/method/frappe.sessions", "/api/method/frappe.realtime", "/api/method/frappe.desk.desktop",
                 "/api/method/frappe.desk.notifications", "/api/method/frappe.apps")


def _name_from_form() -> str:
    fd = frappe.form_dict
    return str(fd.get("name") or fd.get("docname") or "")[:60]


def target_doctype(path: str, form: dict) -> str | None:
    """Which doctype is this request about? Looks at the URL and every parameter Frappe's generic endpoints use."""
    if path.startswith("/api/resource/"):
        return unquote(path[len("/api/resource/"):].split("/", 1)[0])
    for k in _DOCTYPE_KEYS:
        v = form.get(k)
        if isinstance(v, str) and v in SENSITIVE_DOCTYPES:
            return v
    for k in ("doc", "docs", "data", "filters"):  # JSON payloads of frappe.client.insert/save/set_value/...
        v = form.get(k)
        if isinstance(v, str) and ("CPCP " in v):
            try:
                j = json.loads(v)
                for item in (j if isinstance(j, list) else [j]):
                    if isinstance(item, dict) and item.get("doctype") in SENSITIVE_DOCTYPES:
                        return item["doctype"]
            except ValueError:
                pass
    for v in form.values():
        if isinstance(v, str) and v in SENSITIVE_DOCTYPES:
            return v
    if "/printview" in path or "download_pdf" in path:
        return form.get("doctype") if form.get("doctype") in SENSITIVE_DOCTYPES else None
    return None


def classify_action(path: str, method: str) -> str:
    p = path.lower()
    if any(w in p for w in BLOCKED_ACTIONS):
        return "export" if "export" in p or "download" in p else ("print" if "print" in p or "pdf" in p else "share")
    if "search" in p or "autocomplete" in p:
        return "search"
    if any(w in p for w in ("getdoc", "client.get", "get_value", "get_count")) or (p.startswith("/api/resource/") and p.count("/") >= 4 and method == "GET"):
        return "view"
    if method in ("POST", "PUT", "DELETE") or any(w in p for w in ("insert", "save", "set_value", "delete", "submit", "cancel")):
        return "write"
    return "list"


def _role_info(user: str):
    from frappe_cpcp.permissions import RoleContextRequired, get_actor

    if user == "Administrator":
        return "platform_admin", "", None
    if user == "Guest":
        return "guest", "", None
    try:
        a = get_actor(user)
        return a.role.value, ",".join(sorted(a.estate_ids)), a
    except RoleContextRequired:
        return "ambiguous", "", None
    except frappe.PermissionError:
        return "none", "", None


def _guest_throttle() -> bool:
    """Unauthenticated probes are journaled but capped per minute so the journal cannot be flooded."""
    from frappe.utils import cint
    from frappe_cpcp.services.common import utcnow

    cache = frappe.cache()
    key = f"cpcp:guestjournal:{utcnow():%Y%m%d%H%M}"
    n = cint(cache.get_value(key) or 0) + 1
    cache.set_value(key, n, expires_in_sec=120)
    return n <= 20


def check_request(path: str, method: str, form: dict, user: str) -> None:
    """Raise PermissionError (HTTP 403) if the request must not proceed. Pure of Frappe request globals so tests can call it."""
    if path.startswith(PASS_PREFIXES):
        return
    dt = target_doctype(path, form)
    if not dt:
        return
    role, estate, actor = _role_info(user)
    action = classify_action(path, method)
    rid = str(form.get("name") or form.get("docname") or "")[:60]
    category = CATEGORY.get(dt, "restricted_legal")
    base = dict(actor=user, role=role, estate=estate.split(",")[0] if estate else "", action=action, record_type=dt.replace("CPCP ", ""), record_id=rid,
                category=category, context=f"{method} {path[:80]}")
    if action in ("export", "print", "share"):
        access.record(**base, purpose="desk_access", result="Denied", reason_code="bulk_disclosure_requires_approved_export")
        raise frappe.PermissionError("not permitted")
    allowed = False
    if role in READ_ROLES or role == "platform_admin":
        allowed = True
    elif role == "auditor" and actor is not None:
        allowed = any(g.capability and g.expires_at for g in actor.grants)  # fine-grained check happens in has_permission
    if not allowed:
        if user == "Guest" and not _guest_throttle():
            raise frappe.PermissionError("not permitted")
        access.record(**base, purpose="desk_access", result="Denied", reason_code=f"role_{role}_no_desk_access")
        raise frappe.PermissionError("not permitted")
    access.record(**base, purpose="administration", result="Allowed", reason_code="administrative_access")


def before_request():
    """Frappe hook: runs for every web request."""
    req = getattr(frappe.local, "request", None)
    if req is None:
        return
    check_request(req.path, req.method, dict(frappe.form_dict), frappe.session.user)
