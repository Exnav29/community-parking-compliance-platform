# SPDX-License-Identifier: Apache-2.0
"""Plate normalization. A normalized plate is a search key, never an identity."""
import re

_STRIP = re.compile(r"[\s\-_.·]+")
_ALLOWED = re.compile(r"^[A-Z0-9]{2,12}$")


def normalize_plate(raw: str | None) -> str:
    """Upper-case and strip separators. Raises ValueError for unusable input.

    Foreign/unusual plates are accepted (2-12 alphanumerics); format hints are
    non-blocking per PRD 40.3.
    """
    if raw is None:
        raise ValueError("plate is required")
    value = _STRIP.sub("", str(raw).upper())
    if not _ALLOWED.match(value):
        raise ValueError("plate must be 2-12 letters/digits after normalization")
    return value


def mask_plate(normalized: str) -> str:
    """Mask the middle of a plate for low-trust displays (keeps 2 + 1 chars)."""
    if len(normalized) <= 3:
        return "*" * len(normalized)
    return normalized[:2] + "*" * (len(normalized) - 3) + normalized[-1]
