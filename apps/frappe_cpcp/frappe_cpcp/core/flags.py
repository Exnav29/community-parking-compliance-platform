# SPDX-License-Identifier: Apache-2.0
"""Legal / policy feature flags. Every enforcement-related flag defaults OFF (PRD 3, 15, AC-19)."""

ENFORCEMENT_FLAGS = (
    "fine_assessment_enabled",
    "clamping_enabled",
    "towing_enabled",
    "impound_release_enabled",
    "payment_collection_enabled",
    "provider_dispatch_enabled",
    "public_registration_enabled",
    "saas_customer_billing_enabled",
)

DEFAULT_FLAGS = {name: False for name in ENFORCEMENT_FLAGS}


class FeatureDisabled(PermissionError):
    """Raised when an action is attempted while its legal gate is off."""


def is_enabled(flags: dict | None, name: str) -> bool:
    """Unknown flags are OFF. Only an explicit ``True`` (not truthy strings) enables."""
    if name not in DEFAULT_FLAGS:
        return False
    return bool((flags or {}).get(name) is True)


def require_flag(flags: dict | None, name: str) -> None:
    if not is_enabled(flags, name):
        raise FeatureDisabled(f"'{name}' is disabled pending legal authorization")
