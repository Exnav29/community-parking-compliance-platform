# SPDX-License-Identifier: Apache-2.0
"""Facts used to PROVE a restore (AC-18): counts, both hash chains, ledger totals and the SHA-256 of private files.

    bench --site SITE execute frappe_cpcp.ops.backup_facts.collect
Contains counts and hashes only; no personal data.
"""
import hashlib
import json

import frappe

COUNTED = ["CPCP Estate", "CPCP Unit", "CPCP Person", "CPCP Vehicle", "CPCP Visitor Session", "CPCP Visit Event", "CPCP Parking Allegation",
           "CPCP Allegation Attachment", "CPCP Security Work Item", "CPCP Violation Incident", "CPCP Officer Evidence", "CPCP Communication Attempt",
           "CPCP Warning Notice", "CPCP Enforcement Action", "CPCP Incident Charge", "CPCP Appeal", "CPCP Policy Version", "CPCP Role Assignment",
           "CPCP Gate Shift", "CPCP Emergency Access", "CPCP Access Review Flag"]


def collect() -> None:
    from frappe_cpcp.services import access
    from frappe_cpcp.services.audit import verify_audit_chain

    facts: dict = {"site": frappe.local.site, "counts": {dt: frappe.db.count(dt) for dt in COUNTED}}
    facts["access_journal"] = {"rows": access.query("select count(*) n from `tabCPCP Sensitive Access Event`")[0]["n"], "chain_intact": access.verify_chain()[0]}
    facts["audit_chain"] = {"rows": frappe.db.count("CPCP Audit Event"), "intact": verify_audit_chain()[0]}
    ledger = frappe.db.sql("select charge_class, count(*), coalesce(sum(amount),0) from `tabCPCP Incident Charge` group by charge_class order by charge_class")
    facts["ledger"] = [[c, int(n), str(t)] for c, n, t in ledger]
    files = []
    for f in frappe.get_all("File", filters={"is_private": 1, "attached_to_doctype": ["in", ["CPCP Allegation Attachment", "CPCP Officer Evidence"]]},
                            fields=["name", "file_url", "attached_to_doctype"], order_by="file_url asc", limit=200):
        doc = frappe.get_doc("File", f.name)
        content = doc.get_content()
        content = content.encode("latin-1") if isinstance(content, str) else content
        files.append([f.file_url, hashlib.sha256(content).hexdigest()])
    facts["private_files"] = {"count": len(files), "digest": hashlib.sha256(json.dumps(files).encode()).hexdigest(), "sample": files[:3]}
    print(json.dumps(facts, sort_keys=True))


def ensure_sample_private_file() -> None:
    """Make sure the site holds at least one real private file so a restore proof compares file bytes (idempotent, synthetic image)."""
    import io

    from PIL import Image

    from frappe_cpcp.services import photos

    if frappe.db.exists("File", {"is_private": 1, "attached_to_doctype": "CPCP Allegation Attachment"}):
        return
    allegation = frappe.db.get_value("CPCP Parking Allegation", {}, "name")
    if not allegation:
        return
    buf = io.BytesIO()
    Image.new("RGB", (64, 48), (10, 120, 200)).save(buf, "JPEG")
    photos.store(allegation, [buf.getvalue()], source_mode="Identified")
    frappe.db.commit()
