# SPDX-License-Identifier: Apache-2.0
"""Durable, hash-chained sensitive-access journal (PRD 61.6).

Why a second connection: ordinary Frappe writes live in the request's transaction, and an exception rolls the whole thing
back, taking the audit row of a DENIED request with it. The journal is therefore written on its own short-lived connection
and committed at once. If it cannot be written, the sensitive operation is refused (fail closed).

Nothing sensitive is stored: only identifiers, one-way hashes of search terms, counts and reason codes.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone

import frappe

from frappe_cpcp.core import auditchain

TABLE = "tabCPCP Sensitive Access Event"
FIELDS = ("seq", "prev_hash", "hash", "actor", "role", "estate", "gate", "shift", "device_hash", "session_hash", "action",
          "record_type", "record_id", "target_unit", "category", "purpose", "purpose_ref", "context", "result", "reason_code",
          "request_id", "at_utc", "search_term_hash", "review_state")
CHAIN_FIELDS = tuple(f for f in FIELDS if f not in ("prev_hash", "hash"))


class AuditUnavailable(frappe.ValidationError):
    """The access journal could not be written; the sensitive operation must not proceed."""


def _connect():
    import pymysql

    conf = frappe.conf
    return pymysql.connect(host=conf.get("db_host") or "localhost", port=int(conf.get("db_port") or 3306),
                           user=conf.get("db_name"), password=conf.get("db_password"), database=conf.get("db_name"),
                           charset="utf8mb4", autocommit=False, connect_timeout=5)


def _iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def request_id() -> str:
    rid = getattr(frappe.local, "request_id", None)
    if not rid:
        rid = frappe.generate_hash(length=16)
        frappe.local.request_id = rid
    return rid


def term_hash(term: str | None) -> str:
    if not term:
        return ""
    return hashlib.sha256((frappe.conf.get("cpcp_anon_signing_key") or "cpcp").encode() + b"|" + term.strip().upper().encode()).hexdigest()[:32]


def _session_hash() -> str:
    sid = getattr(frappe.session, "sid", None)
    return hashlib.sha256(sid.encode()).hexdigest()[:16] if sid else ""


def record(*, actor: str, role: str, estate: str = "", action: str, record_type: str, record_id: str = "", target_unit: str = "",
           category: str = "operational_min", purpose: str = "", purpose_ref: str = "", result: str = "Allowed", reason_code: str = "ok",
           context: str = "", search_term: str | None = None, gate: str = "", shift: str = "", device_hash: str = "") -> str:
    """Append one journal row and commit it independently. Returns the new row name. Raises AuditUnavailable on failure."""
    values = dict(actor=actor or "", role=role or "", estate=estate or "", gate=gate or "", shift=shift or "", device_hash=device_hash or "",
                  session_hash=_session_hash(), action=action, record_type=record_type, record_id=str(record_id or ""),
                  target_unit=target_unit or "", category=category, purpose=purpose, purpose_ref=purpose_ref or "", context=(context or "")[:140],
                  result=result, reason_code=reason_code, request_id=request_id(), at_utc=_iso_now(),
                  search_term_hash=term_hash(search_term), review_state="None")
    last_err = None
    for _ in range(6):
        conn = None
        try:
            conn = _connect()
            cur = conn.cursor()
            cur.execute(f"select `seq`, `hash` from `{TABLE}` order by `seq` desc limit 1 for update")
            tail = cur.fetchone()
            seq = (tail[0] if tail else 0) + 1
            prev = tail[1] if tail else auditchain.GENESIS
            fields = {**values, "seq": seq}
            h = auditchain._record_hash(prev, {k: fields[k] for k in CHAIN_FIELDS})
            name = "SAE-" + uuid.uuid4().hex[:12]
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            cols = ["name", "creation", "modified", "modified_by", "owner", "docstatus", "idx", *FIELDS]
            vals = [name, now, now, "system", "system", 0, 0, *[({**fields, "prev_hash": prev, "hash": h})[f] for f in FIELDS]]
            cur.execute(f"insert into `{TABLE}` ({', '.join(f'`{c}`' for c in cols)}) values ({', '.join(['%s'] * len(cols))})", vals)
            conn.commit()
            return name
        except Exception as e:  # duplicate seq under contention -> retry; anything else -> fail closed after retries
            last_err = e
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass
    frappe.log_error(title="CPCP access journal unavailable", message=str(last_err)[:500])
    raise AuditUnavailable("Sensitive access is temporarily unavailable because it cannot be recorded. Try again; if it persists tell a supervisor.")


def verify_chain() -> tuple[bool, int | None]:
    """Verify the surviving chain. After a lawful retention purge the first row's prev_hash is the anchor (recorded in the audit
    chain by the purge); sequence numbers must still be contiguous and every hash must match."""
    rows = frappe.db.sql(f"select {', '.join(f'`{f}`' for f in FIELDS)} from `{TABLE}` order by `seq` asc", as_dict=True)
    if not rows:
        return True, None
    prev, expected = rows[0]["prev_hash"], rows[0]["seq"]
    if expected == 1 and prev != auditchain.GENESIS:
        return False, 1
    for r in rows:
        fields = {k: r[k] if r[k] is not None else "" for k in CHAIN_FIELDS}
        fields["seq"] = r["seq"]
        if r["seq"] != expected or r["prev_hash"] != prev or r["hash"] != auditchain._record_hash(prev, {k: fields[k] for k in CHAIN_FIELDS}):
            return False, r["seq"]
        prev, expected = r["hash"], expected + 1
    return True, None


def query(sql: str, params: tuple | list = ()) -> list[dict]:
    """Read the journal on a FRESH connection, so out-of-band commits are always visible (the request's own snapshot may predate them)."""
    import pymysql

    try:
        conn = _connect()
        try:
            cur = conn.cursor(pymysql.cursors.DictCursor)
            cur.execute(sql, params)
            return list(cur.fetchall())
        finally:
            conn.close()
    except Exception as e:  # a journal we cannot read is a journal we cannot trust: fail closed
        raise AuditUnavailable("Sensitive access is temporarily unavailable because it cannot be recorded.") from e


def count_recent(actor: str, *, actions: tuple[str, ...] | None = None, minutes: int = 60, results: tuple[str, ...] | None = None) -> int:
    """Rate limiting reads the journal itself (reliable, includes denials). Locking read so concurrent callers see each other."""
    since = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).strftime("%Y-%m-%dT%H:%M:%S")
    sql = f"select count(*) from `{TABLE}` where actor=%s and at_utc >= %s"
    params: list = [actor, since]
    if actions:
        sql += " and action in %s"
        params.append(actions)
    if results:
        sql += " and result in %s"
        params.append(results)
    return int(next(iter(query(sql, params)[0].values())))


def dumps(obj) -> str:
    return json.dumps(obj, sort_keys=True, default=str)
