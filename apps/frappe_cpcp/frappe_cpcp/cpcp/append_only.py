# SPDX-License-Identifier: Apache-2.0
"""Base class for immutable, append-only records (audit, evidence, events, receipts)."""
import frappe
from frappe.model.document import Document


class AppendOnlyDocument(Document):
    """Inserts are allowed; updates and deletes are refused for every user, including Administrator.

    Direct SQL and bench console access remain possible, which is why the audit chain is hash-linked:
    tampering is detectable even where it cannot be prevented.
    """

    def validate(self):
        if not self.is_new():
            frappe.throw(f"{self.doctype} records are append-only and cannot be modified", frappe.PermissionError)

    def on_trash(self):
        frappe.throw(f"{self.doctype} records are append-only and cannot be deleted", frappe.PermissionError)
