# SPDX-License-Identifier: Apache-2.0
"""Write-side of the tamper-evident audit chain and the sensitive-access log."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone

import frappe

from frappe_cpcp.core import auditchain


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def request_id() -> str:
    rid = getattr(frappe.local, "request_id", None)
    if not rid:
        rid = frappe.generate_hash(length=16)
        frappe.local.request_id = rid
    return rid


def log_audit(*, action: str, entity: str = "", entity_id: str = "", reason: str = "", detail=None,
              actor: str | None = None, role: str = "") -> None:
    """Append one chained audit event inside the caller's transaction.

    The tail row is read ``FOR UPDATE`` so concurrent writers serialize and the chain stays linear.
    Payloads are reduced to a hash: audit rows never copy whole resident records.
    """
    tail = frappe.db.sql(
        "select `seq`, `hash` from `tabCPCP Audit Event` order by `seq` desc limit 1 for update", as_dict=True)
    seq = (tail[0].seq if tail else 0) + 1
    prev = tail[0].hash if tail else auditchain.GENESIS
    fields = dict(seq=seq, actor=actor or frappe.session.user, role=role, action=action, entity=entity,
                  entity_id=str(entity_id), at_utc=_now_iso(), request_id=request_id(), reason=reason,
                  detail_hash=auditchain.digest(detail))
    h = auditchain._record_hash(prev, fields)  # same function the verifier uses
    frappe.get_doc({"doctype": "CPCP Audit Event", "prev_hash": prev, "hash": h, **fields}).insert(ignore_permissions=True)


def verify_audit_chain() -> tuple[bool, int | None]:
    rows = frappe.get_all("CPCP Audit Event", order_by="seq asc", limit_page_length=0,
                          fields=["seq", "prev_hash", "hash", "actor", "role", "action", "entity", "entity_id",
                                  "at_utc", "request_id", "reason", "detail_hash"])
    chain = [auditchain.AuditRecord(**{k: (r[k] if r[k] is not None else "") for k in r}) for r in rows]
    return auditchain.verify(chain)


def log_sensitive_access(*, record_type: str, record_id: str = "", estate: str = "", context: str = "",
                         result: str = "Allowed", search_term: str | None = None, actor: str | None = None,
                         role: str = "") -> None:
    term_hash = hashlib.sha256(search_term.encode()).hexdigest() if search_term else ""
    frappe.get_doc({
        "doctype": "CPCP Sensitive Access Event", "actor": actor or frappe.session.user, "role": role, "estate": estate,
        "record_type": record_type, "record_id": record_id, "context": context, "result": result,
        "request_id": request_id(), "at_utc": _now_iso(), "search_term_hash": term_hash,
    }).insert(ignore_permissions=True)
