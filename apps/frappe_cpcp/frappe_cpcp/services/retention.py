# SPDX-License-Identifier: Apache-2.0
"""Configurable retention for the sensitive-access journal (PRD 61.6).

Deletion is possible ONLY here (raw SQL, scheduled, summarised in the main audit chain). Emergency grants and rows under review are
kept. Because the journal is hash-chained, the first surviving row's ``prev_hash`` becomes the anchor of the remaining chain and the
purge records the last removed sequence number and hash in the audit chain, so a later verification can tell a lawful purge from tampering.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import frappe
from frappe.utils import cint

from frappe_cpcp.services.access import TABLE
from frappe_cpcp.services.audit import log_audit


def purge_expired_access_events(now: datetime | None = None, days: int | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    days = days or cint(frappe.db.get_single_value("CPCP Settings", "access_log_retention_days") or 730)
    cutoff = (now - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S")
    # Only a CONTIGUOUS prefix of the chain can be removed (so the remainder still verifies from its own anchor).
    rows = frappe.db.sql(f"select seq, hash, at_utc, result, review_state from `{TABLE}` order by seq asc", as_dict=True)
    last = None
    for r in rows[:-1]:  # always keep the newest row so the chain keeps its anchor
        if r["at_utc"] >= cutoff or r["result"] == "Emergency" or r["review_state"] != "None":
            break
        last = r
    if not last:
        return {"purged": 0}
    frappe.db.sql(f"delete from `{TABLE}` where seq <= %s", (last["seq"],))
    log_audit(action="access_journal_purged", entity="CPCP Sensitive Access Event", entity_id=str(last["seq"]), reason=f"retention {days} days",
              detail={"through_seq": last["seq"], "through_hash": last["hash"]})
    return {"purged": int(last["seq"]), "anchor_hash": last["hash"]}
