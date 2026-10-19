# SPDX-License-Identifier: Apache-2.0
"""Candidate discovery for duplicate allegations (PRD 60.5). Stage 1 only: it NEVER authorizes a penalty.

Elapsed time is deliberately absent from the decision: an open/clamped/towed episode stays a candidate for hours or
days. A plate match is strong but not conclusive; a plate match with an incompatible location goes to review.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from . import geo


class Outcome(str, Enum):
    ATTACH_CANDIDATE = "attach_candidate"  # add as an unconfirmed link on the existing case/cluster
    REVIEW = "review"                      # surface to a reviewer with a comparison; do not merge
    NONE = "none"


@dataclass(frozen=True)
class Features:
    plate_match: bool | None        # True/False when both plates exist, None when either is missing/uncertain
    same_zone: bool | None
    distance_m: float | None
    accuracy_sum_m: float = 0.0
    case_active: bool = True


@dataclass(frozen=True)
class Decision:
    outcome: Outcome
    confidence: float
    reason: str


MIN_TOLERANCE_M = 100.0


def distance_between(a: tuple[float, float] | None, b: tuple[float, float] | None) -> float | None:
    return None if a is None or b is None else geo.haversine_m(a, b)


def location_compatible(f: Features) -> bool | None:
    """True/False when we can tell, None when location evidence is absent (treated as 'not contradicting')."""
    if f.distance_m is not None:
        return f.distance_m <= max(MIN_TOLERANCE_M, f.accuracy_sum_m)
    if f.same_zone is not None:
        return f.same_zone
    return None


def evaluate(f: Features) -> Decision:
    if not f.case_active:
        return Decision(Outcome.NONE, 0.0, "no active case to attach to")
    loc = location_compatible(f)
    if f.plate_match is True:
        if loc is False:
            return Decision(Outcome.REVIEW, 0.5, "plate matches but location differs: possible misread, duplicate plates, or the vehicle moved")
        return Decision(Outcome.ATTACH_CANDIDATE, 0.9 if loc else 0.7, "plate matches an active episode")
    if f.plate_match is False:
        return Decision(Outcome.NONE, 0.0, "different plate")
    # plate missing or uncertain: location may suggest a candidate, never a merge
    if loc:
        return Decision(Outcome.REVIEW, 0.4, "no usable plate; same place as an active episode")
    return Decision(Outcome.NONE, 0.0, "no usable plate and no location overlap")
