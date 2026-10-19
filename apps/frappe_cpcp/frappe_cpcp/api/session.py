# SPDX-License-Identifier: Apache-2.0
"""Session/navigation endpoints. The server decides what the client may even render (PRD 30.1)."""
import frappe

from frappe_cpcp.core.authz import navigation_manifest
from frappe_cpcp.permissions import _valid_assignments, get_actor, org_id


@frappe.whitelist()
def whoami(role_context: str | None = None) -> dict:
    """Roles held, the active role context and the permitted navigation manifest."""
    rows = _valid_assignments(frappe.session.user)
    if not rows:
        raise frappe.PermissionError("no active role assignment")
    held = sorted({r.cpcp_role for r in rows})
    actor = get_actor(role_context=role_context or (held[0] if len(held) == 1 else None))
    return {
        "organization": org_id(),
        "display_name": frappe.db.get_single_value("CPCP Settings", "display_name"),
        "roles_held": held,
        "active_role": actor.role.value,
        "estates": sorted(actor.estate_ids),
        "navigation": navigation_manifest(actor.role),
        "enforcement_gates": {  # surfaced so clients never render live-enforcement controls while gates are off
            f: bool(frappe.db.get_single_value("CPCP Settings", f))
            for f in ("fine_assessment_enabled", "clamping_enabled", "towing_enabled", "payment_collection_enabled")
        },
        "anonymous_label": "Anonymous" if frappe.db.get_single_value("CPCP Settings", "anonymous_label_verified") else "Confidential",
    }


@frappe.whitelist(allow_guest=True)
def ping() -> dict:
    """Unauthenticated health probe. Reveals nothing about the tenant."""
    return {"ok": True}
