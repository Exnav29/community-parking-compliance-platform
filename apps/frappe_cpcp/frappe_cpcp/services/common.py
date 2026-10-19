# SPDX-License-Identifier: Apache-2.0
"""Small shared helpers. All stored datetimes are naive UTC (site system timezone is forced to UTC)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import frappe


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def to_db(dt: datetime) -> datetime:
    """Aware datetime -> naive UTC for storage."""
    if dt.tzinfo is None:
        raise ValueError("naive datetime")
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def from_db(value) -> datetime | None:
    if value is None:
        return None
    dt = frappe.utils.get_datetime(value)
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def iso(dt) -> str | None:
    d = from_db(dt)
    return d.strftime("%Y-%m-%dT%H:%M:%SZ") if d else None


def require(value, name: str):
    if value in (None, ""):
        frappe.throw(f"{name} is required", frappe.ValidationError)
    return value


def unit_by_label(estate: str, label: str) -> str:
    name = frappe.db.get_value("CPCP Unit", {"estate": estate, "unit_label": (label or "").strip().upper()}, "name")
    if not name:
        frappe.throw("Unit not found in this estate", frappe.ValidationError)
    return name


def active_policy(estate: str | None):
    """Active policy for the estate, else the organization-wide one. Returns a dict or None."""
    for est in ([estate] if estate else []) + [None]:
        filters = {"status": "Active"}
        filters["estate"] = est if est else ("is", "not set")
        rows = frappe.get_all("CPCP Policy Version", filters=filters, order_by="modified desc", limit=1,
                              fields=["name", "version_label", "grace_minutes", "violation_penalty"])
        if rows:
            return rows[0]
    return None


def age_minutes(dt) -> int | None:
    d = from_db(dt)
    return None if d is None else int((utcnow() - d).total_seconds() // 60)


def minutes_ago(n: int) -> datetime:
    return to_db(utcnow() - timedelta(minutes=n))


def deadlock_retry(fn=None, *, attempts: int = 4):
    """Re-run a whole request-level operation when InnoDB aborts it as a deadlock victim (or a lock wait times out).

    InnoDB rolls back the victim's entire transaction, so the retry restarts from the beginning; every write path guarded
    by this decorator is idempotent (client UUIDs, unique keys), so a retry can never double-apply.
    """
    import functools
    import random
    import time

    def deco(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            for i in range(attempts):
                try:
                    return f(*args, **kwargs)
                except (frappe.QueryDeadlockError, frappe.QueryTimeoutError):
                    frappe.db.rollback()
                    if i == attempts - 1:
                        raise
                    time.sleep(random.uniform(0.02, 0.08) * (i + 1))

        return wrapper

    return deco(fn) if fn else deco
