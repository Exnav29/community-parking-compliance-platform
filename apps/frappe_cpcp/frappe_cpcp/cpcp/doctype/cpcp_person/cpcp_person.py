# SPDX-License-Identifier: Apache-2.0
import frappe
from frappe.model.document import Document

from frappe_cpcp.core.phones import normalize_phone


class CPCPPerson(Document):
    def validate(self):
        if self.phone_source:
            try:
                self.phone_e164 = normalize_phone(self.phone_source)
            except ValueError:
                frappe.throw("Phone number is not valid (Ghana 024..., +233... or international +...)")
        else:
            self.phone_e164 = None
