# SPDX-License-Identifier: Apache-2.0
import frappe
from frappe.model.document import Document
from frappe.utils import getdate


class CPCPUnitMembership(Document):
    def validate(self):
        if self.valid_to and getdate(self.valid_to) < getdate(self.valid_from):
            frappe.throw("valid_to cannot precede valid_from")
