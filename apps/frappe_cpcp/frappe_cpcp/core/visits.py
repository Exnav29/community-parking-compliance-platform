# SPDX-License-Identifier: Apache-2.0
"""Visitor session lifecycle (PRD sections 40 and 50).

A visit is a time-bounded session. Checkout is single-shot and idempotent; expiry,
shift change or midnight NEVER close a session; corrections are append-only events.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from enum import Enum


class VisitStatus(str, Enum):
    EXPECTED = "Expected"
    PENDING_AUTH = "Pending Authorization"
    CHECKED_IN = "Checked In"
    CHECKED_OUT = "Checked Out"
    EXIT_UNCONFIRMED = "Exit Unconfirmed"
    NEEDS_REVIEW = "Needs Supervisor Review"
    VOIDED = "Cancelled/Voided"


class Presence(str, Enum):
    CONFIRMED_IN = "Confirmed In"
    CONFIRMED_OUT = "Confirmed Out"
    UNKNOWN = "Unknown/Unverified"


class EventType(str, Enum):
    ENTRY = "ENTRY"
    EXIT = "EXIT"
    EXIT_CORRECTION = "EXIT_CORRECTION"
    VOID = "VOID"
    REOPEN_REVIEW = "REOPEN_REVIEW"


class VisitError(ValueError):
    pass


class AlreadyInside(VisitError):
    """Same plate already has an active session at the estate (PRD 40.1.7, 50.3)."""

    def __init__(self, session_id: str):
        super().__init__("vehicle already has an active visit; review before opening another")
        self.session_id = session_id


class AlreadyCheckedOut(VisitError):
    pass


ACTIVE = {VisitStatus.CHECKED_IN, VisitStatus.EXIT_UNCONFIRMED, VisitStatus.NEEDS_REVIEW}


@dataclass(frozen=True)
class VisitEvent:
    event_type: EventType
    actor: str
    gate: str | None
    observed_at: datetime
    received_at: datetime
    idempotency_key: str
    reason: str | None = None
    source: str = "online"


@dataclass(frozen=True)
class VisitSession:
    session_id: str
    estate_id: str
    host_unit_id: str
    category: str
    plate: str | None
    entry_at: datetime
    entry_gate: str
    entry_officer: str
    status: VisitStatus = VisitStatus.CHECKED_IN
    presence: Presence = Presence.CONFIRMED_IN
    exit_at: datetime | None = None
    exit_gate: str | None = None
    exit_officer: str | None = None
    exit_method: str | None = None
    estimated: bool = False
    events: tuple[VisitEvent, ...] = field(default_factory=tuple)

    @property
    def duration(self) -> timedelta | None:
        """Verified duration only: None unless a non-estimated confirmed exit exists."""
        if self.exit_at is None or self.estimated or self.presence != Presence.CONFIRMED_OUT:
            return None
        return self.exit_at - self.entry_at

    @property
    def duration_minutes(self) -> int | None:
        d = self.duration
        return None if d is None else int(d.total_seconds() // 60)


def _aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        raise VisitError("timestamps must be timezone-aware (store UTC)")
    return dt.astimezone(timezone.utc)


def check_in(
    *, session_id: str, estate_id: str, host_unit_id: str, category: str, plate: str | None, gate: str,
    officer: str, observed_at: datetime, received_at: datetime, idempotency_key: str,
    active_sessions: list[VisitSession] | None = None, no_vehicle: bool = False,
) -> VisitSession:
    """Open a new session. Raises AlreadyInside for a duplicate active plate at the estate."""
    if not host_unit_id:
        raise VisitError("host unit is required (confirm visiting this unit today)")
    if plate is None and not no_vehicle:
        raise VisitError("plate required unless no-vehicle category")
    for s in active_sessions or []:
        if s.estate_id == estate_id and plate and s.plate == plate and s.status in ACTIVE:
            raise AlreadyInside(s.session_id)
    ev = VisitEvent(EventType.ENTRY, officer, gate, _aware(observed_at), _aware(received_at), idempotency_key)
    return VisitSession(
        session_id=session_id, estate_id=estate_id, host_unit_id=host_unit_id, category=category, plate=plate,
        entry_at=_aware(observed_at), entry_gate=gate, entry_officer=officer, events=(ev,),
    )


def check_out(
    session: VisitSession, *, gate: str, officer: str, observed_at: datetime, received_at: datetime,
    idempotency_key: str, method: str = "officer_confirmed",
) -> VisitSession:
    """Close exactly this session. Replaying the same idempotency key returns the same result."""
    if any(e.idempotency_key == idempotency_key and e.event_type == EventType.EXIT for e in session.events):
        return session  # idempotent retry
    if session.status == VisitStatus.CHECKED_OUT:
        raise AlreadyCheckedOut("session already checked out")
    if session.status in (VisitStatus.VOIDED, VisitStatus.EXPECTED, VisitStatus.PENDING_AUTH):
        raise VisitError(f"cannot check out from status {session.status.value}")
    obs = _aware(observed_at)
    if obs < session.entry_at:
        raise VisitError("exit cannot precede entry")
    ev = VisitEvent(EventType.EXIT, officer, gate, obs, _aware(received_at), idempotency_key)
    return replace(
        session, status=VisitStatus.CHECKED_OUT, presence=Presence.CONFIRMED_OUT, exit_at=obs, exit_gate=gate,
        exit_officer=officer, exit_method=method, estimated=False, events=session.events + (ev,),
    )


def supervisor_correct_exit(
    session: VisitSession, *, supervisor: str, estimated_exit_at: datetime, reason: str, received_at: datetime,
    idempotency_key: str, gate: str | None = None,
) -> VisitSession:
    """Append-only supervisor correction; result is labelled estimated, never 'verified'."""
    if not reason:
        raise VisitError("a reason is required for corrections")
    if supervisor == session.entry_officer:
        raise VisitError("correction requires an independent supervisor")
    est = _aware(estimated_exit_at)
    if est < session.entry_at:
        raise VisitError("exit cannot precede entry")
    ev = VisitEvent(EventType.EXIT_CORRECTION, supervisor, gate, est, _aware(received_at), idempotency_key, reason)
    return replace(
        session, status=VisitStatus.CHECKED_OUT, presence=Presence.UNKNOWN, exit_at=est, exit_gate=gate,
        exit_officer=supervisor, exit_method="supervisor_estimate", estimated=True, events=session.events + (ev,),
    )


def flag_overdue(session: VisitSession, now: datetime, threshold: timedelta) -> bool:
    """Review reminder only. Never changes state (PRD 50.3, 50.6, AC-107)."""
    return session.status in ACTIVE and (_aware(now) - session.entry_at) > threshold


def void(session: VisitSession, *, actor: str, reason: str, received_at: datetime, idempotency_key: str) -> VisitSession:
    if not reason:
        raise VisitError("a reason is required")
    ev = VisitEvent(EventType.VOID, actor, None, _aware(received_at), _aware(received_at), idempotency_key, reason)
    return replace(session, status=VisitStatus.VOIDED, presence=Presence.UNKNOWN, events=session.events + (ev,))


def resolve_active_matches(sessions: list[VisitSession], *, estate_id: str, plate: str | None = None,
                           unit_id: str | None = None) -> list[VisitSession]:
    """Active sessions at ONE estate. Callers must present a choice when len > 1 (never auto-pick)."""
    out = []
    for s in sessions:
        if s.estate_id != estate_id or s.status not in ACTIVE:
            continue
        if plate and s.plate != plate:
            continue
        if unit_id and s.host_unit_id != unit_id:
            continue
        out.append(s)
    return out


def verified_duration_stats(sessions: list[VisitSession]) -> dict:
    """Only confirmed, non-estimated exits count towards verified duration (AC-113)."""
    mins = sorted(m for s in sessions if (m := s.duration_minutes) is not None)
    n = len(mins)
    if not n:
        return {"count": 0, "median": None, "p90": None, "max": None, "excluded": len(sessions)}
    median = mins[n // 2] if n % 2 else (mins[n // 2 - 1] + mins[n // 2]) / 2
    p90 = mins[min(n - 1, int(round(0.9 * (n - 1))))]
    return {"count": n, "median": median, "p90": p90, "max": mins[-1], "excluded": len(sessions) - n}
