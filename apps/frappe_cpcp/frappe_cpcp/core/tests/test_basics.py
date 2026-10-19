# SPDX-License-Identifier: Apache-2.0
import pytest

from frappe_cpcp.core.flags import DEFAULT_FLAGS, FeatureDisabled, is_enabled, require_flag
from frappe_cpcp.core.phones import mask_phone, normalize_phone
from frappe_cpcp.core.plates import mask_plate, normalize_plate


def test_plate_normalization():
    assert normalize_plate("gr 1234-25") == "GR123425"
    assert normalize_plate("  ab-12 ") == "AB12"
    for bad in (None, "", "A", "!!!", "X" * 13):
        with pytest.raises(ValueError):
            normalize_plate(bad)
    assert mask_plate("GR123425") == "GR*****5"


@pytest.mark.parametrize(
    "raw",
    ["024 123 4567", "0241234567", "+233241234567", "233241234567", "00233241234567"],
)
def test_ghana_phone_forms(raw):
    assert normalize_phone(raw) == "+233241234567"


def test_international_and_invalid_phone():
    assert normalize_phone("+44 20 7946 0958") == "+442079460958"
    for bad in ("", None, "12345", "+2332412", "abc"):
        with pytest.raises(ValueError):
            normalize_phone(bad)
    assert mask_phone("+233241234567").startswith("+233")


def test_flags_default_off_and_strict():
    assert not any(DEFAULT_FLAGS.values())
    assert not is_enabled({"clamping_enabled": "yes"}, "clamping_enabled")
    assert not is_enabled({"unknown": True}, "unknown")
    assert is_enabled({"clamping_enabled": True}, "clamping_enabled")
    with pytest.raises(FeatureDisabled):
        require_flag({}, "towing_enabled")
