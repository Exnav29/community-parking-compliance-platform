# SPDX-License-Identifier: Apache-2.0
"""Parking-episode lifecycle and identity (PRD 60.1, 60.5, 60.6).

One physical parking episode == one canonical incident. Identity is held by an ``active_key`` that is released only
by POSITIVE end-of-episode evidence; elapsed time, a new calendar day, payment and clamp removal never release it.
"""
from __future__ import annotations

import hashlib
from enum import Enum


class Episode(str, Enum):
    CANDIDATE = "New/Candidate"
    UNDER_REVIEW = "Under Review"
    VERIFIED_OPEN = "Verified/Open"
    WARNING_ACTIVE = "Warning Active"
    COMPLIANCE_CONFIRMED = "Compliance Confirmed"
    CLAMP_ACTIVE = "Clamp Active"
    TOW_ORDERED = "Tow Ordered"
    TOWED_IMPOUNDED = "Towed/Impounded"
    RELEASE_PENDING = "Release Pending"
    RESOLVED_CLOSED = "Resolved/Closed"
    REOPENED = "Reopened for Review"


E = Episode
# event -> {from_state: to_state}
_T: dict[str, dict[Episode, Episode]] = {
    "review_started": {E.CANDIDATE: E.UNDER_REVIEW},
    "verified": {E.CANDIDATE: E.VERIFIED_OPEN, E.UNDER_REVIEW: E.VERIFIED_OPEN},
    "notice_established": {E.VERIFIED_OPEN: E.WARNING_ACTIVE, E.REOPENED: E.WARNING_ACTIVE},
    "compliance_confirmed": {E.VERIFIED_OPEN: E.COMPLIANCE_CONFIRMED, E.WARNING_ACTIVE: E.COMPLIANCE_CONFIRMED,
                             E.REOPENED: E.COMPLIANCE_CONFIRMED},
    "clamp_executed": {E.WARNING_ACTIVE: E.CLAMP_ACTIVE, E.VERIFIED_OPEN: E.CLAMP_ACTIVE, E.REOPENED: E.CLAMP_ACTIVE},
    "tow_ordered": {E.WARNING_ACTIVE: E.TOW_ORDERED, E.VERIFIED_OPEN: E.TOW_ORDERED, E.CLAMP_ACTIVE: E.TOW_ORDERED,
                    E.REOPENED: E.TOW_ORDERED},
    "tow_executed": {E.TOW_ORDERED: E.TOWED_IMPOUNDED, E.CLAMP_ACTIVE: E.TOWED_IMPOUNDED},
    "release_started": {E.CLAMP_ACTIVE: E.RELEASE_PENDING, E.TOWED_IMPOUNDED: E.RELEASE_PENDING, E.TOW_ORDERED: E.RELEASE_PENDING},
    "closed": {E.COMPLIANCE_CONFIRMED: E.RESOLVED_CLOSED, E.RELEASE_PENDING: E.RESOLVED_CLOSED, E.VERIFIED_OPEN: E.RESOLVED_CLOSED,
               E.WARNING_ACTIVE: E.RESOLVED_CLOSED, E.UNDER_REVIEW: E.RESOLVED_CLOSED, E.CANDIDATE: E.RESOLVED_CLOSED,
               E.REOPENED: E.RESOLVED_CLOSED},
    "reopened": {E.RESOLVED_CLOSED: E.REOPENED, E.COMPLIANCE_CONFIRMED: E.REOPENED},
}

HANDLED = {E.WARNING_ACTIVE, E.CLAMP_ACTIVE, E.TOW_ORDERED, E.TOWED_IMPOUNDED, E.RELEASE_PENDING}
ENFORCING = {E.CLAMP_ACTIVE, E.TOW_ORDERED, E.TOWED_IMPOUNDED, E.RELEASE_PENDING}


class EpisodeError(ValueError):
    pass


def apply(state: Episode, event: str) -> Episode:
    try:
        return _T[event][state]
    except KeyError:
        raise EpisodeError(f"event '{event}' is not allowed from '{state.value}'") from None


def already_being_handled(state: Episode) -> bool:
    """True once a warning/enforcement path is under way: further reports enrich it, never start a second."""
    return state in HANDLED


def enforcement_in_progress(state: Episode) -> bool:
    return state in ENFORCING


class EndEvidence(str, Enum):
    DEPARTURE_VERIFIED = "departure_verified"          # security saw the vehicle leave
    REMOVAL_CONFIRMED = "removal_confirmed"            # authorized tow completed and vehicle left the site
    MOVEMENT_CORROBORATED = "movement_corroborated"    # moved away and re-parked elsewhere, corroborated
    MANAGER_DETERMINATION = "manager_determination"    # documented, manager-approved
    RESOLVED_WITHOUT_DEPARTURE = "resolved_without_departure"  # closed administratively; identity is KEPT


_POSITIVE = {EndEvidence.DEPARTURE_VERIFIED, EndEvidence.REMOVAL_CONFIRMED, EndEvidence.MOVEMENT_CORROBORATED,
             EndEvidence.MANAGER_DETERMINATION}
# Things that look like proof but are not (PRD 60.6).
NEVER_EVIDENCE = {"payment", "paid", "clamp_removed", "new_day", "overnight", "elapsed_time", "shift_change"}


def parse_end_evidence(raw: str) -> EndEvidence:
    if raw in NEVER_EVIDENCE:
        raise EpisodeError(f"'{raw}' is not evidence that the parking episode ended")
    try:
        return EndEvidence(raw)
    except ValueError:
        raise EpisodeError(f"unknown end-of-episode evidence '{raw}'") from None


def releases_identity(evidence: EndEvidence) -> bool:
    """Only positive evidence frees the vehicle identity so a later offense can be a NEW episode."""
    return evidence in _POSITIVE


def active_key(estate: str, plate_normalized: str | None) -> str | None:
    """Unique-while-active identity. None (no key) when the plate is missing/uncertain: such cases can never be
    auto-merged or auto-billed; they go to manual review."""
    if not plate_normalized:
        return None
    return hashlib.sha256(f"{estate}|{plate_normalized}".encode()).hexdigest()[:40]


def plate_hash(plate_normalized: str) -> str:
    return hashlib.sha256(plate_normalized.encode()).hexdigest()
