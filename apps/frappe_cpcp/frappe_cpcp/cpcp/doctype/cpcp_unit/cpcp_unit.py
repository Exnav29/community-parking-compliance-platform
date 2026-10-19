# SPDX-License-Identifier: Apache-2.0
import frappe
from frappe.model.document import Document


class CPCPUnit(Document):
    def validate(self):
        self.unit_label = (self.unit_label or "").strip().upper()
        if frappe.db.exists("CPCP Unit", {"estate": self.estate, "unit_label": self.unit_label, "name": ("!=", self.name)}):
            frappe.throw(f"Unit {self.unit_label} already exists in this estate")
