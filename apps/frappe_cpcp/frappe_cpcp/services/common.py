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
