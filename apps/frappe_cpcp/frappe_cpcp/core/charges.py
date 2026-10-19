# SPDX-License-Identifier: Apache-2.0
"""Charge engine (PRD 9, 10). Exactly one violation penalty per incident.

Money is Decimal. No fee has a default amount: tow/storage need configured or provider
amounts. Every computation is gated on legal feature flags (default OFF).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum

from .flags import require_flag


class ChargeClass(str, Enum):
    PARKING_VIOLATION = "PARKING_VIOLATION"
    TOW_SERVICE = "TOW_SERVICE"
    STORAGE = "STORAGE"
    OTHER_APPROVED_SERVICE = "OTHER_APPROVED_SERVICE"
    ADJUSTMENT_CREDIT = "ADJUSTMENT_CREDIT"
    REFUND = "REFUND"


class ChargeError(ValueError):
    pass


@dataclass(frozen=True)
class FeeSchedule:
    version: str
    currency: str
    violation_penalty: Decimal | None = None  # e.g. Decimal("500") in the Ghana reference template
    storage_rate_per_period: Decimal | None = None
    storage_period_hours: int = 24
    storage_free_hours: int = 0
    storage_cap: Decimal | None = None
    rounding_places: int = 2


@dataclass(frozen=True)
class Charge:
    incident_id: str
    charge_class: ChargeClass
    quantity: Decimal
    unit_price: Decimal
    currency: str
    source: str
    schedule_version: str
    idempotency_key: str

    @property
    def amount(self) -> Decimal:
        sign = Decimal(-1) if self.charge_class in (ChargeClass.ADJUSTMENT_CREDIT, ChargeClass.REFUND) else Decimal(1)
        return sign * self.quantity * self.unit_price


def q(value: Decimal, places: int = 2) -> Decimal:
    return value.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)


def idempotency_key(incident_id: str, charge_class: ChargeClass, discriminator: str = "") -> str:
    return f"{incident_id}:{charge_class.value}:{discriminator}"


def add_violation_penalty(existing: list[Charge], *, incident_id: str, schedule: FeeSchedule, flags: dict) -> list[Charge]:
    """Add the single core penalty. Clamp-then-tow, retries and duplicate allegations cannot add a second."""
    require_flag(flags, "fine_assessment_enabled")
    if schedule.violation_penalty is None:
        raise ChargeError("fee schedule has no violation penalty configured")
    if any(c.incident_id == incident_id and c.charge_class == ChargeClass.PARKING_VIOLATION for c in existing):
        return list(existing)  # idempotent: exactly one base penalty per incident
    return list(existing) + [Charge(
        incident_id, ChargeClass.PARKING_VIOLATION, Decimal(1), schedule.violation_penalty, schedule.currency,
        "fee_schedule", schedule.version, idempotency_key(incident_id, ChargeClass.PARKING_VIOLATION),
    )]


def add_tow_charge(existing: list[Charge], *, incident_id: str, provider_amount: Decimal | None, currency: str,
                   provider_ref: str, schedule_version: str, flags: dict) -> list[Charge]:
    """Tow cost must come from an actual provider record; there is no default."""
    require_flag(flags, "towing_enabled")
    if provider_amount is None or provider_amount <= 0:
        raise ChargeError("an authorized provider amount is required; defaults are never invented")
    key = idempotency_key(incident_id, ChargeClass.TOW_SERVICE, provider_ref)
    if any(c.idempotency_key == key for c in existing):
        return list(existing)
    return list(existing) + [Charge(incident_id, ChargeClass.TOW_SERVICE, Decimal(1), provider_amount, currency,
                                    f"provider:{provider_ref}", schedule_version, key)]


def storage_periods(start: datetime, stop: datetime, schedule: FeeSchedule) -> int:
    """Billable periods between verified yard arrival and the confirmed stop event.
    Partial periods round up; the free window is subtracted first."""
    if start.tzinfo is None or stop.tzinfo is None:
        raise ChargeError("storage timestamps must be timezone-aware")
    if stop < start:
        raise ChargeError("storage stop precedes yard arrival")
    billable = (stop - start) - timedelta(hours=schedule.storage_free_hours)
    if billable <= timedelta(0):
        return 0
    return math.ceil(billable / timedelta(hours=schedule.storage_period_hours))


def add_storage_charge(existing: list[Charge], *, incident_id: str, yard_arrival: datetime | None,
                       stop_event: datetime | None, schedule: FeeSchedule, flags: dict) -> list[Charge]:
    """Never starts before verified yard arrival nor runs without a confirmed stop (PRD 9, 17.9)."""
    require_flag(flags, "towing_enabled")
    require_flag(flags, "impound_release_enabled")
    if schedule.storage_rate_per_period is None:
        raise ChargeError("no storage rate configured")
    if yard_arrival is None or stop_event is None:
        raise ChargeError("storage requires verified yard arrival and a confirmed stop/release event")
    n = storage_periods(yard_arrival, stop_event, schedule)
    rest = [c for c in existing if not (c.incident_id == incident_id and c.charge_class == ChargeClass.STORAGE)]
    if n == 0:
        return rest
    price = schedule.storage_rate_per_period
    if schedule.storage_cap is not None and price * n > schedule.storage_cap:
        price, n = schedule.storage_cap, 1
    return rest + [Charge(incident_id, ChargeClass.STORAGE, Decimal(n), q(price, schedule.rounding_places),
                          schedule.currency, "fee_schedule", schedule.version,
                          idempotency_key(incident_id, ChargeClass.STORAGE))]


def invoice_total(charges: list[Charge], places: int = 2) -> Decimal:
    return q(sum((c.amount for c in charges), Decimal(0)), places)


def itemize(charges: list[Charge]) -> list[dict]:
    return [{"class": c.charge_class.value, "qty": str(c.quantity), "unit": str(c.unit_price),
             "amount": str(q(c.amount)), "source": c.source, "schedule": c.schedule_version} for c in charges]


def apply_payment_once(ledger: dict[str, Decimal], event_id: str, amount: Decimal) -> bool:
    """Idempotent settlement: a replayed provider webhook (same event_id) is a no-op."""
    if event_id in ledger:
        return False
    ledger[event_id] = amount
    return True
