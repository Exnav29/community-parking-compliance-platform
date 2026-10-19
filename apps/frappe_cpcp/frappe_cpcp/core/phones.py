# SPDX-License-Identifier: Apache-2.0
"""Phone normalization with Ghana (+233) support. Source strings are preserved by callers."""
import re

_DIGITS = re.compile(r"\D+")


def normalize_phone(raw: str | None, default_country_code: str = "233") -> str:
    """Return E.164 (``+233...``). Raises ValueError when not plausible.

    ``024 123 4567`` and ``+233241234567`` normalize to ``+233241234567``.
    Other international numbers must be supplied with ``+`` or ``00``.
    """
    if raw is None or not str(raw).strip():
        raise ValueError("phone is required")
    text = str(raw).strip()
    has_plus = text.startswith("+")
    digits = _DIGITS.sub("", text)
    if text.startswith("00") and not has_plus:
        digits, has_plus = digits[2:], True
    if has_plus:
        e164 = digits
    elif digits.startswith("0") and len(digits) == 10:
        e164 = default_country_code + digits[1:]
    elif digits.startswith(default_country_code) and len(digits) == len(default_country_code) + 9:
        e164 = digits
    else:
        raise ValueError("unrecognized phone format")
    if not 8 <= len(e164) <= 15 or e164.startswith("0"):
        raise ValueError("phone length is not plausible")
    if e164.startswith("233") and len(e164) != 12:
        raise ValueError("Ghana numbers have 9 digits after +233")
    return "+" + e164


def mask_phone(e164: str) -> str:
    return e164[:4] + "*" * max(len(e164) - 7, 0) + e164[-3:] if len(e164) > 7 else "*" * len(e164)
