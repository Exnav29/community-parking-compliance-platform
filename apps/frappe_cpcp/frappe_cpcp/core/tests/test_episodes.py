# SPDX-License-Identifier: Apache-2.0
import pytest

from frappe_cpcp.core import episodes as ep
from frappe_cpcp.core import matching as m

E = ep.Episode


def test_happy_path_transitions_and_illegal_ones():
    s = ep.apply(E.CANDIDATE, "verified")
    s = ep.apply(s, "notice_established")
    s = ep.apply(s, "clamp_executed")
    assert s == E.CLAMP_ACTIVE
    s = ep.apply(s, "tow_ordered")
    s = ep.apply(s, "tow_executed")
    s = ep.apply(s, "release_started")
    assert ep.apply(s, "closed") == E.RESOLVED_CLOSED
    for bad in (("closed_from_clamp", E.CLAMP_ACTIVE, "closed"), ("clamp_from_candidate", E.CANDIDATE, "clamp_executed"),
                ("tow_exec_from_open", E.VERIFIED_OPEN, "tow_executed")):
        with pytest.raises(ep.EpisodeError):
            ep.apply(bad[1], bad[2])
    assert ep.apply(E.RESOLVED_CLOSED, "reopened") == E.REOPENED


def test_already_handled_states_block_second_workflow():
    for s in (E.WARNING_ACTIVE, E.CLAMP_ACTIVE, E.TOW_ORDERED, E.TOWED_IMPOUNDED, E.RELEASE_PENDING):
        assert ep.already_being_handled(s)
    for s in (E.CANDIDATE, E.UNDER_REVIEW, E.VERIFIED_OPEN, E.RESOLVED_CLOSED):
        assert not ep.already_being_handled(s)
    assert ep.enforcement_in_progress(E.CLAMP_ACTIVE) and not ep.enforcement_in_progress(E.WARNING_ACTIVE)


def test_only_positive_evidence_releases_identity():
    for raw in ("payment", "clamp_removed", "new_day", "overnight", "elapsed_time", "shift_change"):
        with pytest.raises(ep.EpisodeError):
            ep.parse_end_evidence(raw)
    with pytest.raises(ep.EpisodeError):
        ep.parse_end_evidence("whatever")
    for raw in ("departure_verified", "removal_confirmed", "movement_corroborated", "manager_determination"):
        assert ep.releases_identity(ep.parse_end_evidence(raw))
    assert not ep.releases_identity(ep.parse_end_evidence("resolved_without_departure"))


def test_active_key_is_per_estate_and_plate_and_absent_without_plate():
    a = ep.active_key("E1", "GR123")
    assert a == ep.active_key("E1", "GR123") != ep.active_key("E2", "GR123") != ep.active_key("E1", "GR124")
    assert ep.active_key("E1", None) is None and ep.active_key("E1", "") is None


def test_matching_ignores_elapsed_time_and_never_merges_on_plate_alone():
    near = m.Features(plate_match=True, same_zone=True, distance_m=10, accuracy_sum_m=20)
    assert m.evaluate(near).outcome == m.Outcome.ATTACH_CANDIDATE
    assert "hours" not in m.Features.__dataclass_fields__  # no time input exists: continuity beats elapsed time
    far = m.Features(plate_match=True, same_zone=False, distance_m=800, accuracy_sum_m=30)
    assert m.evaluate(far).outcome == m.Outcome.REVIEW  # AC-D06
    unknown_loc = m.Features(plate_match=True, same_zone=None, distance_m=None)
    d = m.evaluate(unknown_loc)
    assert d.outcome == m.Outcome.ATTACH_CANDIDATE and d.confidence < 0.9


def test_gps_uncertainty_widens_tolerance():
    f = m.Features(plate_match=True, same_zone=None, distance_m=180, accuracy_sum_m=250)
    assert m.evaluate(f).outcome == m.Outcome.ATTACH_CANDIDATE
    assert m.evaluate(m.Features(True, None, 180, 50)).outcome == m.Outcome.REVIEW


def test_missing_plate_goes_to_review_never_merge():
    assert m.evaluate(m.Features(None, True, 20)).outcome == m.Outcome.REVIEW
    assert m.evaluate(m.Features(None, False, 900)).outcome == m.Outcome.NONE
    assert m.evaluate(m.Features(False, True, 5)).outcome == m.Outcome.NONE
    assert m.evaluate(m.Features(True, True, 5, case_active=False)).outcome == m.Outcome.NONE
