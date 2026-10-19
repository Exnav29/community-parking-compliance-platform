# SPDX-License-Identifier: Apache-2.0
"""Resident allegation triage (PRD 29, 34, 35).

An allegation is unverified. Only an authorized officer may promote it, and promotion creates
a SEPARATE incident; the allegation text is never rewritten. Anonymous reports carry no
reporter correlator and use a one-time secret receipt stored only as a slow hash.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from dataclasses import dataclass
from enum import Enum


class Mode(str, Enum):
    IDENTIFIED = "Identified"
    ANONYMOUS = "Anonymous"
    CONTACTABLE_CONFIDENTIAL = "Contactable Confidential"


class State(str, Enum):
    SUBMITTED = "Submitted"
    RECEIVED = "Received by Security"
    UNDER_REVIEW = "Assigned / Under Review"
    VERIFIED = "Verified and Linked to Official Incident"
    RESOLVED = "Resolved without Violation"
    NOT_SUBSTANTIATED = "Not Substantiated"
    DUPLICATE = "Duplicate / Merged"
    WITHDRAWN = "Withdrawn"
    CLOSED = "Closed"


TERMINAL_OUTCOMES = {State.VERIFIED, State.RESOLVED, State.NOT_SUBSTANTIATED, State.DUPLICATE, State.WITHDRAWN}

TRANSITIONS: dict[State, set[State]] = {
    State.SUBMITTED: {State.RECEIVED, State.WITHDRAWN},
    State.RECEIVED: {State.UNDER_REVIEW, State.DUPLICATE, State.WITHDRAWN},
    State.UNDER_REVIEW: {State.VERIFIED, State.RESOLVED, State.NOT_SUBSTANTIATED, State.DUPLICATE, State.WITHDRAWN},
    State.VERIFIED: {State.CLOSED},
    State.RESOLVED: {State.CLOSED},
    State.NOT_SUBSTANTIATED: {State.CLOSED},
    State.DUPLICATE: {State.CLOSED},
    State.WITHDRAWN: {State.CLOSED},
    State.CLOSED: set(),
}

# Reporter-visible, privacy-safe labels (never alleged-driver identity, plate or contacts).
REPORTER_STATUS = {
    State.SUBMITTED: "Received", State.RECEIVED: "Received", State.UNDER_REVIEW: "Under Review",
    State.VERIFIED: "Action Taken", State.RESOLVED: "Resolved", State.NOT_SUBSTANTIATED: "Not Substantiated",
    State.DUPLICATE: "Duplicate", State.WITHDRAWN: "Withdrawn", State.CLOSED: "Closed",
}

# States that mean "an official determination", settable only by authorized security.
SECURITY_ONLY = {State.UNDER_REVIEW, State.VERIFIED, State.RESOLVED, State.NOT_SUBSTANTIATED, State.DUPLICATE}


class TriageError(ValueError):
    pass


def can_transition(src: State, dst: State) -> bool:
    return dst in TRANSITIONS[src]


def transition(src: State, dst: State, *, actor_is_security: bool, reason: str | None = None) -> State:
    if not can_transition(src, dst):
        raise TriageError(f"illegal transition {src.value} -> {dst.value}")
    if dst in SECURITY_ONLY and not actor_is_security:
        raise TriageError("only authorized security can set investigation and verification outcomes")
    if dst in (State.RESOLVED, State.NOT_SUBSTANTIATED, State.DUPLICATE) and not reason:
        raise TriageError("a factual reason is required for this outcome")
    return dst


def reporter_status(state: State) -> str:
    return REPORTER_STATUS[state]


def promote_to_incident(*, state: State, officer: str, officer_evidence_ids: list[str], rule_version: str,
                        officer_has_active_claim: bool, existing_incident_for_cluster: str | None) -> dict:
    """Validate 'Verify & Create Violation'. Returns the new incident's seed; the allegation is untouched."""
    if state != State.UNDER_REVIEW:
        raise TriageError("allegation must be claimed and under review before verification")
    if not officer_has_active_claim:
        raise TriageError("officer does not hold the active claim")
    if not officer_evidence_ids:
        raise TriageError("independent officer evidence is required; resident evidence does not replace it")
    if not rule_version:
        raise TriageError("a published rule version is required")
    if existing_incident_for_cluster:
        # Multiple allegations about one real-world violation link to ONE incident (no duplicate penalties).
        return {"link_existing": existing_incident_for_cluster, "create": False}
    return {"create": True, "verified_by": officer, "rule_version": rule_version, "evidence": list(officer_evidence_ids)}


# ---- anonymous receipt ----------------------------------------------------------------------

@dataclass(frozen=True)
class Receipt:
    receipt_id: str  # public, non-secret lookup handle
    secret: str  # shown once; never stored
    salt: str
    verifier: str  # scrypt hash of the secret; the only stored credential


_SCRYPT = dict(n=2**14, r=8, p=1, dklen=32)


def _hash(secret: str, salt: bytes) -> bytes:
    return hashlib.scrypt(secret.encode(), salt=salt, **_SCRYPT)


def new_receipt() -> Receipt:
    receipt_id = "R-" + secrets.token_hex(6).upper()
    secret = base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")  # 160 bits
    salt = secrets.token_bytes(16)
    return Receipt(receipt_id, secret, salt.hex(), _hash(secret, salt).hex())


def verify_receipt(secret: str | None, salt_hex: str | None, verifier_hex: str | None) -> bool:
    """Constant-time check. Missing record and wrong secret are indistinguishable to callers."""
    dummy_salt = b"\x00" * 16
    try:
        salt = bytes.fromhex(salt_hex) if salt_hex else dummy_salt
        expected = bytes.fromhex(verifier_hex) if verifier_hex else b"\x00" * 32
    except ValueError:
        salt, expected = dummy_salt, b"\x00" * 32
    candidate = _hash(secret or "", salt)
    return bool(salt_hex and verifier_hex) and hmac.compare_digest(candidate, expected)


# ---- anonymous community code ---------------------------------------------------------------

def community_code(signing_key: bytes, estate_id: str, epoch: int) -> str:
    """Rotating association-wide code for the anonymous intake route. Not tied to any resident.
    ``epoch`` is e.g. the ISO week number; callers accept the current and previous epoch."""
    mac = hmac.new(signing_key, f"{estate_id}:{epoch}".encode(), hashlib.sha256).digest()
    return base64.b32encode(mac)[:10].decode()


def check_community_code(signing_key: bytes, estate_id: str, presented: str, epoch: int) -> bool:
    return any(
        hmac.compare_digest(community_code(signing_key, estate_id, e), (presented or "").upper())
        for e in (epoch, epoch - 1)
    )


# Fields that must be absent/None on an anonymous allegation. Server-side guard used by the API and tests.
ANON_FORBIDDEN_FIELDS = ("reporter_user", "reporter_unit", "reporter_phone", "reporter_email", "device_id",
                         "push_token", "ip_address", "session_id")
# Framework audit columns must carry the shared Guest identity, never a person.
ANON_GUEST_ONLY_FIELDS = ("owner", "modified_by")


def assert_anonymous_clean(record: dict) -> None:
    leaked = [f for f in ANON_FORBIDDEN_FIELDS if record.get(f)]
    leaked += [f for f in ANON_GUEST_ONLY_FIELDS if record.get(f) not in (None, "", "Guest")]
    if leaked:
        raise TriageError(f"anonymous allegation carries correlators: {leaked}")
