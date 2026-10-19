# SPDX-License-Identifier: Apache-2.0
import frappe
from frappe.model.document import Document
from frappe.utils import get_datetime, now_datetime


class CPCPAccessGrant(Document):
    def validate(self):
        if not self.requested_by:
            self.requested_by = frappe.session.user
        if get_datetime(self.expires_at) <= now_datetime():
            frappe.throw("Grant expiry must be in the future")
        if (get_datetime(self.expires_at) - now_datetime()).days > 30:
            frappe.throw("Exceptional access grants are limited to 30 days")
        if self.status == "Approved":
            if not self.approved_by:
                self.approved_by = frappe.session.user
            if self.approved_by in (self.requested_by, self.grantee):
                frappe.throw("Grants need an independent approver (not the requester or the grantee)")
            from frappe_cpcp.services.audit import log_audit
            log_audit(action="grant_approved", entity="CPCP Access Grant", entity_id=self.name or "",
                      reason=self.purpose or "", detail={"capability": self.capability, "grantee": self.grantee})
