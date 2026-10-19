# SPDX-License-Identifier: Apache-2.0
import frappe

ROLES = {
    # name: desk_access
    "CPCP Org Admin": 1,
    "CPCP Security Manager": 1,
    "CPCP Security Officer": 1,
    "CPCP Auditor": 1,
    "CPCP Finance": 1,
    "CPCP Tow Provider": 0,
    "CPCP Resident": 0,
    "CPCP Board Observer": 0,
}

# CPCP role (core.authz.Role value) -> Frappe role carrying DocPerm. Never System Manager.
FRAPPE_ROLE_FOR = {
    "org_admin": "CPCP Org Admin",
    "estate_manager": "CPCP Org Admin",
    "security_manager": "CPCP Security Manager",
    "security_officer": "CPCP Security Officer",
    "resident": "CPCP Resident",
    "auditor": "CPCP Auditor",
    "finance": "CPCP Finance",
    "tow_provider": "CPCP Tow Provider",
    "board_observer": "CPCP Board Observer",
}


def ensure_roles():
    for name, desk in ROLES.items():
        if not frappe.db.exists("Role", name):
            frappe.get_doc({"doctype": "Role", "role_name": name, "desk_access": desk}).insert(ignore_permissions=True)


def after_install():
    ensure_roles()
    frappe.db.commit()
