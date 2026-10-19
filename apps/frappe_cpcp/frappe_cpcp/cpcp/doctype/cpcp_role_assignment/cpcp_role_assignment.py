# SPDX-License-Identifier: Apache-2.0
import frappe
from frappe.model.document import Document
from frappe.utils import getdate

from frappe_cpcp.install import FRAPPE_ROLE_FOR

PRIVILEGED = {"org_admin", "estate_manager", "security_manager", "finance", "auditor"}
ESTATE_REQUIRED = {"estate_manager", "security_manager", "security_officer", "tow_provider"}


class CPCPRoleAssignment(Document):
    def validate(self):
        roles = set(frappe.get_roles(self.user))
        if self.user == "Administrator" or "System Manager" in roles:
            frappe.throw("System Manager/Administrator accounts must not hold tenant roles (PRD 30.1)")
        if self.cpcp_role in ESTATE_REQUIRED and not self.estate:
            frappe.throw(f"Role {self.cpcp_role} must be scoped to an estate")
        if self.cpcp_role == "resident" and not self.unit:
            frappe.throw("Residents must be assigned to an explicit unit; it is never guessed")
        if self.unit and not self.estate:
            self.estate = frappe.db.get_value("CPCP Unit", self.unit, "estate")
        if self.estate and self.unit and frappe.db.get_value("CPCP Unit", self.unit, "estate") != self.estate:
            frappe.throw("Unit does not belong to the selected estate")
        if self.valid_from and self.valid_until and getdate(self.valid_until) < getdate(self.valid_from):
            frappe.throw("valid_until cannot precede valid_from")
        if self.cpcp_role in PRIVILEGED:
            if not self.approved_by:
                self.approved_by = frappe.session.user
            if self.approved_by == self.user:
                frappe.throw("Privileged roles cannot be self-approved (separation of duties)")
        if self.cpcp_role == "auditor" and not self.valid_until:
            frappe.throw("Auditor access must expire (set valid_until)")

    def on_update(self):
        sync_user_roles(self.user)

    def on_trash(self):
        frappe.throw("Role assignments are revoked, not deleted (history is retained)", frappe.PermissionError)


def sync_user_roles(user: str) -> None:
    """Keep Frappe roles in step with active assignments; touches only CPCP roles."""
    today = getdate()
    active = frappe.get_all("CPCP Role Assignment", filters={"user": user, "status": "Active"},
                            fields=["cpcp_role", "valid_from", "valid_until"])
    desired = {FRAPPE_ROLE_FOR[r.cpcp_role] for r in active
               if (not r.valid_from or getdate(r.valid_from) <= today) and (not r.valid_until or getdate(r.valid_until) >= today)}
    u = frappe.get_doc("User", user)
    current = {r.role for r in u.roles if r.role.startswith("CPCP ")}
    if current == desired:
        return
    u.roles = [r for r in u.roles if not r.role.startswith("CPCP ")]
    for role in sorted(desired):
        u.append("roles", {"role": role})
    u.flags.ignore_permissions = True
    u.save()
