# SPDX-License-Identifier: Apache-2.0
import frappe
from frappe.model.document import Document

from frappe_cpcp.core.plates import normalize_plate


class CPCPVehicle(Document):
    def validate(self):
        try:
            self.plate_normalized = normalize_plate(self.plate)
        except ValueError as e:
            frappe.throw(str(e))
        # A plate is a search key, not an identity: two ACTIVE records for one plate need conflict resolution.
        clash = frappe.db.exists("CPCP Vehicle", {"plate_normalized": self.plate_normalized, "country": self.country,
                                                  "status": "Active", "name": ("!=", self.name)})
        if clash and self.status == "Active":
            frappe.throw(f"An active vehicle with this plate already exists ({clash}); resolve the conflict first")
