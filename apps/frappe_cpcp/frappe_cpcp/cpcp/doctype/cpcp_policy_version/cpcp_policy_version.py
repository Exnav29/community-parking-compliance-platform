# SPDX-License-Identifier: Apache-2.0
import frappe
from frappe.model.document import Document


class CPCPPolicyVersion(Document):
    """Draft -> Approved -> Active. Approval needs an independent approver; Active versions are frozen."""

    def validate(self):
        if not self.created_by_user:
            self.created_by_user = frappe.session.user
        if (self.grace_minutes or 0) <= 0:
            frappe.throw("Grace period must be positive")
        if self.violation_penalty is not None and float(self.violation_penalty or 0) < 0:
            frappe.throw("Penalty cannot be negative")
        before = self.get_doc_before_save()
        if before and before.status in ("Active", "Superseded"):
            immutable = ("grace_minutes", "violation_penalty", "storage_rate_per_period", "storage_period_hours", "version_label")
            if any(before.get(f) != self.get(f) for f in immutable):
                frappe.throw("Active and superseded policy versions are immutable; create a new draft version")
        if self.status in ("Approved", "Active"):
            if not self.approved_by:
                self.approved_by = frappe.session.user
            if self.approved_by == self.created_by_user:
                frappe.throw("Policy approval requires an independent approver (separation of duties)")

    def on_update(self):
        if self.status == "Active":
            others = frappe.get_all("CPCP Policy Version", filters={"status": "Active", "estate": self.estate, "name": ("!=", self.name)})
            for o in others:
                frappe.db.set_value("CPCP Policy Version", o.name, "status", "Superseded")
            from frappe_cpcp.services.audit import log_audit
            log_audit(action="policy_activated", entity="CPCP Policy Version", entity_id=self.name,
                      detail={"grace": self.grace_minutes, "penalty": str(self.violation_penalty)})

    def on_trash(self):
        frappe.throw("Policy versions are retained", frappe.PermissionError)
