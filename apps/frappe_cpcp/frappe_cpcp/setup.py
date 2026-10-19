# SPDX-License-Identifier: Apache-2.0
"""Per-site organization setup and synthetic demo data.

``configure_org`` is what the control-plane provisioner runs on a freshly created site.
``seed_demo`` loads FICTITIOUS people/plates/units/coordinates only (PRD 56.1, AC-124).

    bench --site org-a.localhost execute frappe_cpcp.setup.configure_org --kwargs '{"org_id":"org-a","display_name":"Demo Estates A"}'
    bench --site org-a.localhost execute frappe_cpcp.setup.seed_demo --kwargs '{"profile":"a"}'
"""
from __future__ import annotations

import os
import secrets

import frappe
from frappe.utils import add_days, nowdate

from frappe_cpcp.install import ensure_roles

DEMO_PASSWORD_ENV = "CPCP_DEMO_PASSWORD"

# Distinct, fully synthetic profiles so two tenants visibly differ (AC-20, AC-23).
PROFILES = {
    "a": {"org_id": "org-a", "display_name": "Demo Estates A (synthetic)", "currency": "GHS", "grace": 15, "penalty": 500,
          "estates": [("Palm Grove (demo)", ["A1", "A2", "B1"])], "domain": "demo-a.example.invalid",
          "boundary": [[-0.19, 5.60], [-0.18, 5.60], [-0.18, 5.61], [-0.19, 5.61], [-0.19, 5.60]]},
    "b": {"org_id": "org-b", "display_name": "Demo Estates B (synthetic)", "currency": "USD", "grace": 10, "penalty": 40,
          "estates": [("Cedar Court (demo)", ["101", "102"]), ("Harbor View (demo)", ["7A", "7B"])], "domain": "demo-b.example.invalid",
          "boundary": [[10.00, 20.00], [10.01, 20.00], [10.01, 20.01], [10.00, 20.01], [10.00, 20.00]]},
}


def configure_org(org_id: str, display_name: str, currency: str = "GHS", timezone_name: str = "Africa/Accra") -> dict:
    """Idempotent. Forces storage timezone to UTC and stores a per-tenant anonymous-intake signing key in site_config."""
    ensure_roles()
    frappe.db.set_single_value("System Settings", "time_zone", "UTC")
    s = frappe.get_single("CPCP Settings")
    s.org_id, s.display_name, s.currency, s.timezone = org_id, display_name, currency, timezone_name
    s.flags.ignore_permissions = True
    s.save()
    from frappe.installer import update_site_config
    for key in ("cpcp_anon_signing_key", "cpcp_sms_callback_secret"):  # per-tenant secrets, kept in the site's own config
        if not frappe.conf.get(key):
            update_site_config(key, secrets.token_hex(32))
    frappe.db.commit()
    return {"org_id": org_id, "gates_all_off": not any(
        s.get(f) for f in ("fine_assessment_enabled", "clamping_enabled", "towing_enabled", "payment_collection_enabled"))}


def _user(email: str, first: str, pwd: str) -> str:
    if not frappe.db.exists("User", email):
        frappe.get_doc({"doctype": "User", "email": email, "first_name": first, "send_welcome_email": 0,
                        "new_password": pwd, "user_type": "System User", "enabled": 1}).insert(ignore_permissions=True)
    elif os.environ.get(DEMO_PASSWORD_ENV):
        from frappe.utils.password import update_password
        update_password(email, pwd)
    return email


def _assign(user, role, estate=None, unit=None, approver="Administrator", valid_until=None):
    filters = {"user": user, "cpcp_role": role}
    if estate:
        filters["estate"] = estate
    if unit:
        filters["unit"] = unit
    if frappe.db.exists("CPCP Role Assignment", filters):
        return
    frappe.get_doc({"doctype": "CPCP Role Assignment", "user": user, "cpcp_role": role, "estate": estate, "unit": unit,
                    "approved_by": approver, "valid_until": valid_until, "basis": "synthetic demo"}).insert(ignore_permissions=True)


def seed_demo(profile: str = "a") -> dict:
    """Load a synthetic organization. Passwords come from the environment or are randomly generated and printed once."""
    prof = PROFILES[profile]
    pwd = os.environ.get(DEMO_PASSWORD_ENV) or secrets.token_urlsafe(12)
    configure_org(prof["org_id"], prof["display_name"], currency=prof["currency"])
    out = {"profile": profile, "users": {}, "estates": {}}
    dom = prof["domain"]
    _user(f"approver@{dom}", "Approver", pwd)  # independent approver for policy and privileged-role separation of duties
    for ename, units in prof["estates"]:
        est = frappe.db.get_value("CPCP Estate", {"estate_name": ename}) or frappe.get_doc({
            "doctype": "CPCP Estate", "estate_name": ename, "jurisdiction": "Synthetic", "currency": prof["currency"],
            "boundary_geojson": frappe.as_json({"type": "Polygon", "coordinates": [prof["boundary"]]})}).insert(ignore_permissions=True).name
        gate = frappe.db.get_value("CPCP Gate", {"estate": est}) or frappe.get_doc(
            {"doctype": "CPCP Gate", "estate": est, "gate_name": "Main Gate"}).insert(ignore_permissions=True).name
        frappe.db.get_value("CPCP Gate", {"estate": est, "gate_name": "Back Gate"}) or frappe.get_doc(
            {"doctype": "CPCP Gate", "estate": est, "gate_name": "Back Gate"}).insert(ignore_permissions=True)
        for label in units:
            if not frappe.db.exists("CPCP Unit", {"estate": est, "unit_label": label.upper()}):
                frappe.get_doc({"doctype": "CPCP Unit", "estate": est, "unit_label": label}).insert(ignore_permissions=True)
        out["estates"][ename] = {"name": est, "gate": gate}
    est1 = next(iter(out["estates"].values()))["name"]
    unit1 = frappe.db.get_value("CPCP Unit", {"estate": est1, "unit_label": prof["estates"][0][1][0].upper()}, "name")

    pol_name = frappe.db.get_value("CPCP Policy Version", {"status": "Active"})
    if not pol_name:
        pol = frappe.get_doc({"doctype": "CPCP Policy Version", "version_label": f"{prof['org_id']} reference (EXAMPLE - requires approval)",
                              "grace_minutes": prof["grace"], "violation_penalty": prof["penalty"], "status": "Draft",
                              "created_by_user": "Administrator"}).insert(ignore_permissions=True)
        pol.status, pol.approved_by = "Active", "approver@" + dom
        pol.flags.ignore_permissions = True
        pol.save()

    users = {
        "admin": ("org_admin", None, None), "secmgr": ("security_manager", est1, None), "officer": ("security_officer", est1, None),
        "resident": ("resident", est1, unit1), "auditor": ("auditor", est1, None), "finance": ("finance", est1, None),
    }
    for key, (role, estate, unit) in users.items():
        email = f"{key}@{dom}"
        _user(email, key.title(), pwd)
        _assign(email, role, estate, unit, approver=f"approver@{dom}" if role in ("org_admin", "security_manager", "finance", "auditor") else "Administrator",
                valid_until=add_days(nowdate(), 90) if role == "auditor" else None)
        out["users"][key] = email

    # A resident household vehicle and a second vehicle (AC-03), fictitious plates.
    p = frappe.db.get_value("CPCP Person", {"full_name": "Ama Demo"}) or frappe.get_doc(
        {"doctype": "CPCP Person", "full_name": "Ama Demo", "phone_source": "0241230001"}).insert(ignore_permissions=True).name
    if not frappe.db.exists("CPCP Unit Membership", {"unit": unit1, "person": p}):
        frappe.get_doc({"doctype": "CPCP Unit Membership", "unit": unit1, "person": p, "membership_type": "Owner",
                        "is_primary_contact": 1, "valid_from": add_days(nowdate(), -365)}).insert(ignore_permissions=True)
    q = frappe.db.get_value("CPCP Person", {"full_name": "Kofi Demo"}) or frappe.get_doc(
        {"doctype": "CPCP Person", "full_name": "Kofi Demo", "phone_source": "0241230002"}).insert(ignore_permissions=True).name
    if not frappe.db.exists("CPCP Unit Membership", {"unit": unit1, "person": q}):
        frappe.get_doc({"doctype": "CPCP Unit Membership", "unit": unit1, "person": q, "membership_type": "Occupant",
                        "is_backup_contact": 1, "valid_from": add_days(nowdate(), -365)}).insert(ignore_permissions=True)
    s_ = frappe.get_single("CPCP Settings")
    if not s_.security_desk_number:
        s_.security_desk_number = "0240000000"
        s_.flags.ignore_permissions = True
        s_.save()
    for plate, make, color in (("ZZ 1001-26", "Toyota", "Silver"), ("ZZ 1002-26", "Honda", "Black")):
        veh = frappe.db.get_value("CPCP Vehicle", {"plate": plate}) or frappe.get_doc(
            {"doctype": "CPCP Vehicle", "plate": plate, "make": make, "color": color}).insert(ignore_permissions=True).name
        if not frappe.db.exists("CPCP Vehicle Unit Association", {"vehicle": veh, "unit": unit1, "status": "Active"}):
            for stale in frappe.get_all("CPCP Vehicle Unit Association", filters={"vehicle": veh, "status": "Active"}, pluck="name"):
                frappe.db.set_value("CPCP Vehicle Unit Association", stale, "status", "Ended")
            frappe.get_doc({"doctype": "CPCP Vehicle Unit Association", "vehicle": veh, "unit": unit1,
                            "verification_status": "Verified", "valid_from": add_days(nowdate(), -30)}).insert(ignore_permissions=True)
    frappe.db.commit()
    out["note"] = f"Users created with password from ${DEMO_PASSWORD_ENV} or: {pwd if not os.environ.get(DEMO_PASSWORD_ENV) else '(from env)'}"
    return out
