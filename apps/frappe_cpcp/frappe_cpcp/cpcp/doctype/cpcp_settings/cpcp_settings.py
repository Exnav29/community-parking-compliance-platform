# SPDX-License-Identifier: Apache-2.0
import frappe
from frappe.model.document import Document

from frappe_cpcp.core.flags import ENFORCEMENT_FLAGS


class CPCPSettings(Document):
    def validate(self):
        enabling = [f for f in ENFORCEMENT_FLAGS if self.get(f)]
        if enabling and not (self.legal_approval_reference or "").strip():
            frappe.throw(
                "Legal gates cannot be enabled without a signed approval / legal review reference: "
                + ", ".join(enabling), frappe.ValidationError)
        if self.default_grace_minutes is not None and int(self.default_grace_minutes) <= 0:
            frappe.throw("Grace period must be a positive number of minutes")
        before = self.get_doc_before_save()
        if before:
            changed = [f for f in ENFORCEMENT_FLAGS if bool(before.get(f)) != bool(self.get(f))]
            if changed:
                from frappe_cpcp.services.audit import log_audit
                log_audit(action="legal_flag_change", entity="CPCP Settings", entity_id=",".join(changed),
                          reason=self.legal_approval_reference or "", detail={f: bool(self.get(f)) for f in changed})
