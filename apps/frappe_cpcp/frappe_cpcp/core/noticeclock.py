# SPDX-License-Identifier: Apache-2.0
"""Server-authoritative warning/notice clock (PRD 8, 42.3, AC-06, AC-84, AC-89).

A grace period starts ONLY from a policy-qualifying notice proof. Attempts, failures,
queued/sent/delivered-unacknowledged messages do not start it unless the association's
reviewed policy says so. Device time is never trusted.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum


class ProofBasis(str, Enum):
    ANSWERED_CALL_WARNING_CONFIRMED = "answered_call_warning_confirmed"
    EXPLICIT_ACKNOWLEDGMENT = "explicit_acknowledgment"
    SMS_DELIVERED = "sms_delivered"  # only qualifies if policy opts in (needs legal review)
    SMS_SENT = "sms_sent"
    SMS_QUEUED = "sms_queued"
    CALL_ATTEMPTED_NO_ANSWER = "call_attempted_no_answer"
    DIALER_OPENED = "dialer_opened"
    ON_SITE_DRIVER_NOTIFIED = "on_site_driver_notified"
    WRONG_NUMBER = "wrong_number"


DEFAULT_QUALIFYING = frozenset({
    ProofBasis.ANSWERED_CALL_WARNING_CONFIRMED,
    ProofBasis.EXPLICIT_ACKNOWLEDGMENT,
    ProofBasis.ON_SITE_DRIVER_NOTIFIED,
})


class NoticeError(ValueError):
    pass


@dataclass(frozen=True)
class NoticePolicy:
    policy_version: str
    grace_minutes: int = 15
    qualifying_proofs: frozenset[ProofBasis] = DEFAULT_QUALIFYING
    enforcement_category_ordinary: bool = True  # False => emergency path, no ordinary grace


@dataclass(frozen=True)
class WarningNotice:
    policy_version: str
    notice_method: str
    proof_basis: ProofBasis
    notice_effective_at: datetime  # SERVER time
    grace_minutes: int
    deadline: datetime
    override_reason: str | None = None
    approver: str | None = None


def _utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        raise NoticeError("naive datetimes are rejected")
    return dt.astimezone(timezone.utc)


def qualifies(policy: NoticePolicy, proof: ProofBasis) -> bool:
    return proof in policy.qualifying_proofs


def establish_notice_clock(
    policy: NoticePolicy, *, proof: ProofBasis, notice_method: str, server_now: datetime,
    device_reported_at: datetime | None = None, is_emergency: bool = False,
) -> WarningNotice:
    """Start the grace clock at SERVER time. ``device_reported_at`` is recorded nowhere here:
    a drifted or malicious device clock can neither backdate nor shorten a warning."""
    if is_emergency or not policy.enforcement_category_ordinary:
        raise NoticeError("emergency obstructions use the safety escalation path, not the ordinary grace clock")
    if not qualifies(policy, proof):
        raise NoticeError(f"proof '{proof.value}' does not qualify under policy {policy.policy_version}; "
                          "escalate to supervisor or record no verified contact")
    if policy.grace_minutes <= 0:
        raise NoticeError("grace_minutes must be positive")
    now = _utc(server_now)
    return WarningNotice(
        policy_version=policy.policy_version, notice_method=notice_method, proof_basis=proof,
        notice_effective_at=now, grace_minutes=policy.grace_minutes,
        deadline=now + timedelta(minutes=policy.grace_minutes),
    )


def grace_state(notice: WarningNotice | None, server_now: datetime) -> str:
    """'not_started' | 'active' | 'expired'. Expiry never implies a penalty by itself."""
    if notice is None:
        return "not_started"
    return "expired" if _utc(server_now) >= notice.deadline else "active"


def remaining(notice: WarningNotice, server_now: datetime) -> timedelta:
    return max(notice.deadline - _utc(server_now), timedelta(0))


def next_step_after_failed_contact() -> tuple[str, ...]:
    """Supervised options when no qualifying proof exists (PRD 42.3). Never an automatic penalty."""
    return ("notify_security_manager", "try_authorized_backup", "record_no_verified_contact")
