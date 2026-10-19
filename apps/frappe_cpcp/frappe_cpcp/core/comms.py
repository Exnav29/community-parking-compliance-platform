# SPDX-License-Identifier: Apache-2.0
"""Communication records for verified violations (PRD 41, 42; AC-79..AC-85).

Truthfulness rules enforced here:
  * opening the dialer is NOT a connected call; duration from a device/officer is an unverified estimate;
  * only a provider callback can produce 'verified-provider' provenance;
  * SMS states (queued/accepted/sent/delivered/failed/unknown) and acknowledgement are distinct;
  * out-of-order or replayed provider events never move a message backwards or duplicate it.
"""
from __future__ import annotations

import hashlib
import hmac
import re
from dataclasses import dataclass
from enum import Enum

from .noticeclock import ProofBasis


class Channel(str, Enum):
    CALL_DIALER = "call_dialer"
    CALL_PROVIDER = "call_provider"
    SMS = "sms"


class Provenance(str, Enum):
    REQUESTED_ONLY = "requested-only"
    OFFICER_REPORTED = "officer-reported"
    VERIFIED_PROVIDER = "verified-provider"


class CallOutcome(str, Enum):
    ANSWERED = "Answered"
    NO_ANSWER = "No Answer"
    BUSY = "Busy"
    WRONG_NUMBER = "Wrong Number"
    COULD_NOT_PLACE = "Could Not Place Call"
    CALLBACK_REQUESTED = "Callback Requested"
    OTHER = "Other"


class SmsStatus(str, Enum):
    CREATED = "Message Created"
    QUEUED = "Queued"
    ACCEPTED = "Provider Accepted"
    SENT = "Sent"
    DELIVERED = "Delivered"
    FAILED = "Failed"
    UNKNOWN = "Unknown"


# Monotonic ranks: a later-ranked state is never replaced by an earlier one (out-of-order webhooks).
_RANK = {SmsStatus.CREATED: 0, SmsStatus.QUEUED: 1, SmsStatus.ACCEPTED: 2, SmsStatus.SENT: 3,
         SmsStatus.UNKNOWN: 3, SmsStatus.DELIVERED: 4, SmsStatus.FAILED: 4}
_TERMINAL = {SmsStatus.DELIVERED, SmsStatus.FAILED}


class CommsError(ValueError):
    pass


def advance_sms_status(current: SmsStatus, incoming: SmsStatus) -> SmsStatus:
    """Return the status after applying a provider event. Never regresses; terminal states are final
    except that a provider may correct UNKNOWN/SENT to a terminal outcome."""
    if current in _TERMINAL:
        return current
    return incoming if _RANK[incoming] >= _RANK[current] else current


@dataclass(frozen=True)
class CallRecord:
    channel: Channel
    outcome: CallOutcome | None
    provenance: Provenance
    duration_seconds: int | None
    duration_label: str  # what the UI may truthfully say


def record_dialer_outcome(outcome: CallOutcome, estimated_seconds: int | None = None) -> CallRecord:
    """Mode A (native dialer). Never verified; an entered duration is labelled an unverified estimate."""
    if estimated_seconds is not None and estimated_seconds < 0:
        raise CommsError("duration cannot be negative")
    label = "Officer-entered estimate - unverified" if estimated_seconds is not None else "Duration not recorded"
    return CallRecord(Channel.CALL_DIALER, outcome, Provenance.OFFICER_REPORTED, estimated_seconds, label)


def record_provider_call(outcome: CallOutcome, duration_seconds: int) -> CallRecord:
    """Mode B. Only reachable from a signature-verified provider callback."""
    return CallRecord(Channel.CALL_PROVIDER, outcome, Provenance.VERIFIED_PROVIDER, duration_seconds,
                      "Provider-verified duration")


def requested_only() -> CallRecord:
    return CallRecord(Channel.CALL_DIALER, None, Provenance.REQUESTED_ONLY, None,
                      "Dialer opened - connection not confirmed")


def notice_proof_for(outcome: CallOutcome | None, warning_confirmed_by_officer: bool) -> ProofBasis | None:
    """Which proof (if any) a call can support. An answered call only counts when the officer confirms
    the warning was actually delivered and understood; everything else yields no clock."""
    if outcome == CallOutcome.ANSWERED and warning_confirmed_by_officer:
        return ProofBasis.ANSWERED_CALL_WARNING_CONFIRMED
    return None


# ---- contact resolution ---------------------------------------------------------------------------

class Relationship(str, Enum):
    ONSITE_DRIVER = "On-site driver"
    PRIMARY = "Primary household contact"
    BACKUP = "Backup household contact"
    VISITOR_HOST = "Current host"
    DUTY_SUPERVISOR = "Duty supervisor"


_ORDER = {Relationship.ONSITE_DRIVER: 0, Relationship.VISITOR_HOST: 1, Relationship.PRIMARY: 1,
          Relationship.BACKUP: 2, Relationship.DUTY_SUPERVISOR: 3}


@dataclass(frozen=True)
class Contact:
    contact_id: str
    relationship: Relationship
    unit_id: str | None
    phone_e164: str | None
    verified_on: str | None = None  # ISO date of last verification


def order_contacts(contacts: list[Contact], incident_unit_id: str | None) -> list[Contact]:
    """Routing order; contacts bound to a DIFFERENT unit than the incident's are dropped (AC-72), as are
    contacts without a number. Stable for equal ranks."""
    usable = [c for c in contacts if c.phone_e164 and (c.unit_id is None or c.unit_id == incident_unit_id)]
    return sorted(usable, key=lambda c: _ORDER[c.relationship])


# ---- SMS ------------------------------------------------------------------------------------------

_TEMPLATE_VARS = re.compile(r"\{(\w+)\}")
ALLOWED_VARS = {"plate", "zone", "case_id", "security_number", "deadline"}


def render_template(template: str, values: dict[str, str], clock_established: bool) -> str:
    """Escape control characters; refuse a deadline unless the notice clock really exists (PRD 42.4)."""
    used = set(_TEMPLATE_VARS.findall(template))
    if used - ALLOWED_VARS:
        raise CommsError(f"template uses unsupported variables: {sorted(used - ALLOWED_VARS)}")
    if "deadline" in used and not clock_established:
        raise CommsError("a deadline cannot be promised before the notice clock is established")
    clean = {k: re.sub(r"[\x00-\x1f\x7f{}]", " ", str(v))[:60] for k, v in values.items()}
    missing = used - set(clean)
    if missing:
        raise CommsError(f"missing template values: {sorted(missing)}")
    return _TEMPLATE_VARS.sub(lambda m: clean[m.group(1)], template)


def sms_rate_ok(sent_for_contact_last_hour: int, sent_for_case_total: int, per_contact_hour: int = 2, per_case: int = 6) -> bool:
    return sent_for_contact_last_hour < per_contact_hour and sent_for_case_total < per_case


# ---- provider callbacks ---------------------------------------------------------------------------

def sign_callback(secret: bytes, body: bytes) -> str:
    return hmac.new(secret, body, hashlib.sha256).hexdigest()


def verify_callback(secret: bytes, body: bytes, signature: str | None) -> bool:
    if not secret or not signature:
        return False
    return hmac.compare_digest(sign_callback(secret, body), signature)


def event_key(provider: str, provider_ref: str, status: str, provider_ts: str) -> str:
    """Idempotency key: a replayed webhook maps to the same key and is ignored."""
    return hashlib.sha256(f"{provider}|{provider_ref}|{status}|{provider_ts}".encode()).hexdigest()


class SmsProvider:
    """Adapter interface. Real providers (e.g. a Ghana SMS gateway) implement ``send``; none is enabled by default."""

    name = "abstract"

    def send(self, to_e164: str, text: str, idempotency_key: str) -> str:  # returns provider message id
        raise NotImplementedError


class MockSmsProvider(SmsProvider):
    """Deterministic, no network, no cost. Used for dev, tests and demo mode."""

    name = "mock"

    def __init__(self):
        self.sent: list[tuple[str, str, str]] = []

    def send(self, to_e164: str, text: str, idempotency_key: str) -> str:
        for to, _t, key in self.sent:
            if key == idempotency_key:
                return "mock-" + key[:12]
        self.sent.append((to_e164, text, idempotency_key))
        return "mock-" + idempotency_key[:12]
