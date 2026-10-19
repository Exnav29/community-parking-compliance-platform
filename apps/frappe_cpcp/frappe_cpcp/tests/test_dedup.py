# SPDX-License-Identifier: Apache-2.0
"""PRD v1.7 section 60 acceptance tests AC-D01..AC-D18 (serial, real DB, real permission hooks).

The truly concurrent cases (D07, D08, D17) are additionally exercised over parallel HTTP in tests/concurrency.
"""
import json
import uuid
from datetime import timedelta

import frappe
from frappe.tests.utils import FrappeTestCase

from frappe_cpcp import setup
from frappe_cpcp.api import allegations as alg
from frappe_cpcp.api import communications as com
from frappe_cpcp.api import enforcement as enf
from frappe_cpcp.api import incidents as inc
from frappe_cpcp.api import ops, reports
from frappe_cpcp.core import allegations as al
from frappe_cpcp.core import episodes as ep
from frappe_cpcp.core.plates import normalize_plate
from frappe_cpcp.services import episodes as svc
from frappe_cpcp.services.common import to_db, utcnow

DOM = "demo-a.example.invalid"
FLAGS = ("fine_assessment_enabled", "clamping_enabled", "towing_enabled", "impound_release_enabled")
HERE = dict(lat=5.605, lon=-0.185)
FAR = dict(lat=5.6095, lon=-0.1805)  # ~700 m away, still inside the estate boundary


def as_user(key):
    frappe.set_user(f"{key}@{DOM}")


def plate():
    return "D" + uuid.uuid4().hex[:7].upper()


class TestDedup(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        frappe.set_user("Administrator")
        cls.seed = setup.seed_demo("a")
        e = next(iter(cls.seed["estates"].values()))
        cls.estate = e["name"]
        cls.gate = e["gate"]
        from frappe_cpcp.api import duty
        for who in ("officer", "officer2"):  # PRD v1.8: gate work needs a live shift
            frappe.set_user(f"{who}@demo-a.example.invalid")
            duty.start_shift(cls.estate, cls.gate, f"test-device-{who}")
        frappe.set_user("Administrator")
        frappe.db.set_single_value("CPCP Settings", "allegation_rate_limit_per_hour", 100000)

    @classmethod
    def tearDownClass(cls):
        frappe.set_user("Administrator")
        frappe.db.set_single_value("CPCP Settings", "allegation_rate_limit_per_hour", 10)
        super().tearDownClass()

    def tearDown(self):
        frappe.set_user("Administrator")
        self._flags(False)

    # ------------------------------------------------------------------ helpers
    def _flags(self, on):
        frappe.set_user("Administrator")
        s = frappe.get_single("CPCP Settings")
        for f in FLAGS:
            s.set(f, 1 if on else 0)
        s.legal_approval_reference = "TEST-APPROVAL" if on else ""
        s.flags.ignore_permissions = True
        s.save()

    def report(self, who, p, loc=HERE, urgent=0, with_plate=True, cu=None):
        as_user(who)
        return alg.submit_identified(self.estate, "Gate or driveway blocked", f"blocked ({who})", cu or str(uuid.uuid4()),
                                     plate_text=p if with_plate else None, latitude=loc["lat"], longitude=loc["lon"],
                                     accuracy_m=10, location_source="device", urgent=urgent)

    def wi(self, ref):
        return svc.work_item_for_allegation(ref)

    def claim_and_verify(self, ref, p, who="officer", loc=HERE):
        as_user(who)
        alg.claim_work_item(self.wi(ref))
        return alg.verify_and_create_violation(ref, p, uuid.uuid4().hex, loc["lat"], loc["lon"], 8)

    def incident_of(self, p):
        return frappe.db.get_value("CPCP Violation Incident", {"plate_normalized": normalize_plate(p), "merged_into": ["is", "not set"]}, "name", order_by="creation desc")

    def clamp(self, incident, who="officer"):
        """Drive an incident through confirmed notice -> expired grace -> approved clamp (all gates on)."""
        self._flags(True)
        as_user(who)
        cid = com.resolve_violation_contacts(incident)["contacts"]
        if not cid:
            return None
        a = com.initiate_call(incident, cid[0]["contact_id"], str(uuid.uuid4()))["attempt"]
        com.record_call_outcome(a, "Answered", warning_confirmed=1)
        n = com.establish_notice_clock(incident, a)["notice"]
        frappe.db.set_value("CPCP Warning Notice", n, "deadline", to_db(utcnow() - timedelta(minutes=1)))
        c = enf.propose_action(incident, "Clamp", "grace expired")
        as_user("secmgr")
        enf.approve_action(c["action"])
        as_user(who)
        enf.execute_action(c["action"])
        return c["action"]

    def link_unit_vehicle(self, p):
        """Register the plate as a resident vehicle of unit A1 so contacts resolve (clamp flows need a responsible party)."""
        frappe.set_user("Administrator")
        unit = frappe.db.get_value("CPCP Unit", {"estate": self.estate, "unit_label": "A1"})
        v = frappe.get_doc({"doctype": "CPCP Vehicle", "plate": p}).insert()
        frappe.get_doc({"doctype": "CPCP Vehicle Unit Association", "vehicle": v.name, "unit": unit, "verification_status": "Verified"}).insert()

    def charges(self, incident, cls="PARKING_VIOLATION"):
        return frappe.db.count("CPCP Incident Charge", {"incident": incident, "charge_class": cls})

    # ------------------------------------------------------------------ AC-D01
    def test_d01_three_reports_one_incident_one_penalty(self):
        p = plate()
        self.link_unit_vehicle(p)
        refs = [self.report(u, p)["reference"] for u in ("resident", "resident2", "resident3")]
        self.assertEqual(len(set(refs)), 3)  # three immutable allegations
        self.assertEqual(len({self.wi(r) for r in refs}), 1)  # one actionable work item
        self.assertEqual(frappe.db.get_value("CPCP Security Work Item", self.wi(refs[0]), "allegation_count"), 3)
        q = [x for x in (as_user("officer"), alg.triage_queue(self.estate))[1] if x["work_item"] == self.wi(refs[0])][0]
        self.assertEqual(q["reports_label"], "3 independent reports")
        v = self.claim_and_verify(refs[0], p)
        self.assertTrue(v["created"])
        self.assertEqual(frappe.db.count("CPCP Violation Incident", {"plate_normalized": normalize_plate(p)}), 1)
        self.assertEqual(frappe.db.count("CPCP Incident Allegation Link", {"parent": v["incident"], "link_state": "Confirmed"}), 3)
        self.clamp(v["incident"])
        self.assertEqual(self.charges(v["incident"]), 1)  # exactly one base penalty
        for r in refs:  # originals untouched
            self.assertTrue(frappe.db.get_value("CPCP Parking Allegation", r, "narrative").startswith("blocked ("))

    # ------------------------------------------------------------------ AC-D02
    def test_d02_report_after_claim_does_not_steal_claim_or_start_second_workflow(self):
        p = plate()
        r1 = self.report("resident", p)["reference"]
        wi = self.wi(r1)
        as_user("officer")
        alg.claim_work_item(wi)
        r2 = self.report("resident2", p)["reference"]
        self.assertEqual(self.wi(r2), wi)  # joined, no second claimable item
        row = frappe.db.get_value("CPCP Security Work Item", wi, ["claimed_by", "allegation_count"], as_dict=True)
        self.assertEqual((row.claimed_by, row.allegation_count), (f"officer@{DOM}", 2))
        as_user("officer2")
        with self.assertRaises(frappe.DuplicateEntryError):
            alg.claim_work_item(wi)
        self.assertEqual(frappe.db.count("CPCP Security Work Item", {"cluster_key": ["is", "set"], "estate": self.estate, "allegation": ["in", [r1, r2]]}), 1)
        upd = frappe.get_all("CPCP Notification Outbox", filters={"idempotency_key": ["like", f"report_update:{wi}:{r2}:%"]}, fields=["recipient_user"])
        self.assertEqual([u.recipient_user for u in upd], [f"officer@{DOM}"])  # the owner is told, nobody else is paged

    # ------------------------------------------------------------------ AC-D03
    def test_d03_report_after_many_hours_attaches_to_open_or_clamped_episode(self):
        p = plate()
        self.link_unit_vehicle(p)
        r1 = self.report("resident", p)["reference"]
        old = to_db(utcnow() - timedelta(hours=6))
        frappe.db.set_value("CPCP Parking Allegation", r1, "submitted_at", old)
        frappe.db.set_value("CPCP Security Work Item", self.wi(r1), "creation", old)
        r2 = self.report("resident2", p)["reference"]  # 6 h later: beyond the old four-hour window
        self.assertEqual(self.wi(r2), self.wi(r1))
        v = self.claim_and_verify(r1, p)
        self.clamp(v["incident"])
        frappe.db.set_value("CPCP Violation Incident", v["incident"], "verified_at", to_db(utcnow() - timedelta(hours=30)))
        r3 = self.report("resident3", p)["reference"]
        self.assertIsNone(self.wi(r3))  # attached to the clamped case, not a new work item
        self.assertEqual(frappe.db.get_value("CPCP Violation Incident", v["incident"], "allegation_count"), 3)
        self.assertEqual(self.incident_of(p), v["incident"])

    # ------------------------------------------------------------------ AC-D04
    def test_d04_overnight_clamped_vehicle_single_penalty_across_midnight_and_shift_change(self):
        p = plate()
        self.link_unit_vehicle(p)
        r1 = self.report("resident", p)["reference"]
        v = self.claim_and_verify(r1, p)
        self.clamp(v["incident"])
        back = to_db(utcnow() - timedelta(hours=20))
        frappe.db.set_value("CPCP Violation Incident", v["incident"], {"verified_at": back, "first_observed_at": back})
        as_user("secmgr")
        inc.reassign_incident(v["incident"], f"officer2@{DOM}", "shift change")
        r2 = self.report("resident2", p)["reference"]  # after midnight, new shift
        self.assertIsNone(self.wi(r2))
        self.assertEqual(frappe.db.get_value("CPCP Violation Incident", v["incident"], "assigned_officer"), f"officer2@{DOM}")
        notified = frappe.get_all("CPCP Notification Outbox", filters={"incident": v["incident"], "idempotency_key": ["like", f"report_update:{v['incident']}:{r2}:%"]}, pluck="recipient_user")
        self.assertEqual(notified, [f"officer2@{DOM}"])
        self.assertEqual(self.charges(v["incident"]), 1)
        self.assertEqual(frappe.db.count("CPCP Enforcement Action", {"incident": v["incident"], "action_type": "Clamp"}), 1)
        self.assertEqual(ep.Episode(frappe.db.get_value("CPCP Violation Incident", v["incident"], "episode_status")), ep.Episode.CLAMP_ACTIVE)

    # ------------------------------------------------------------------ AC-D05
    def test_d05_departure_then_new_offense_within_four_hours_is_a_new_episode(self):
        p = plate()
        self.link_unit_vehicle(p)
        r1 = self.report("resident", p)["reference"]
        v1 = self.claim_and_verify(r1, p)
        self.clamp(v1["incident"])
        as_user("officer")
        for bad in ("payment", "clamp_removed", "new_day", "shift_change"):
            with self.assertRaises(frappe.ValidationError):
                inc.end_episode(v1["incident"], bad, "not evidence")
        enf_action = frappe.get_all("CPCP Enforcement Action", filters={"incident": v1["incident"]}, pluck="name")[0]
        with self.assertRaises(frappe.ValidationError):  # clamp still live: removing it alone is not proof of departure
            inc.end_episode(v1["incident"], "departure_verified", "saw it leave")
        enf.release_vehicle(enf_action)
        # release closed the case but did NOT free the vehicle identity
        r_same = self.report("resident2", p)["reference"]
        self.assertIsNone(self.wi(r_same))
        as_user("officer")
        res = inc.end_episode(v1["incident"], "departure_verified", "left through the main gate at 10:12")
        self.assertTrue(res["identity_released"])
        r2 = self.report("resident3", p)["reference"]  # minutes later: returns and re-offends
        self.assertIsNotNone(self.wi(r2))
        v2 = self.claim_and_verify(r2, p)
        self.assertTrue(v2["created"])
        self.assertNotEqual(v2["incident"], v1["incident"])
        self.clamp(v2["incident"])
        self.assertEqual((self.charges(v1["incident"]), self.charges(v2["incident"])), (1, 1))  # one penalty per distinct episode

    def test_d05b_resolved_without_departure_evidence_is_not_a_new_billable_episode(self):
        p = plate()
        r1 = self.report("resident", p)["reference"]
        v1 = self.claim_and_verify(r1, p)
        as_user("officer")
        res = inc.end_episode(v1["incident"], "resolved_without_departure", "closed administratively")
        self.assertFalse(res["identity_released"])
        r2 = self.report("resident2", p)["reference"]
        self.assertIsNone(self.wi(r2))  # attaches to the closed episode instead of opening a new one
        self.assertEqual(frappe.db.count("CPCP Violation Incident", {"plate_normalized": normalize_plate(p)}), 1)

    # ------------------------------------------------------------------ AC-D06
    def test_d06_same_plate_other_location_or_uncertain_plate_needs_review_not_merge(self):
        p = plate()
        r1 = self.report("resident", p)["reference"]
        v = self.claim_and_verify(r1, p)
        far = self.report("resident2", p, loc=FAR)["reference"]
        wi = self.wi(far)
        self.assertIsNotNone(wi)  # not auto-merged
        row = frappe.db.get_value("CPCP Security Work Item", wi, ["candidate_incident", "review_needed"], as_dict=True)
        self.assertEqual((row.candidate_incident, bool(row.review_needed)), (v["incident"], True))
        self.assertEqual(frappe.db.get_value("CPCP Violation Incident", v["incident"], "allegation_count"), 1)
        noplate = self.report("resident3", None, with_plate=False)["reference"]  # uncertain plate, same place
        row2 = frappe.db.get_value("CPCP Security Work Item", self.wi(noplate), ["candidate_incident", "review_needed", "cluster_key"], as_dict=True)
        self.assertTrue(row2.candidate_incident)  # the nearest active case is offered for comparison, never merged
        self.assertEqual((bool(row2.review_needed), row2.cluster_key), (True, None))
        self.assertEqual(frappe.db.get_value("CPCP Violation Incident", v["incident"], "allegation_count"), 1)
        as_user("officer")
        q = {x["work_item"]: x for x in alg.triage_queue(self.estate)}
        self.assertTrue(q[self.wi(noplate)]["possible_related_case"] and q[self.wi(far)]["possible_related_case"])  # reviewer gets the comparison pointer
        c = inc.incident_candidates(v["incident"])
        self.assertEqual(c["reports"][0]["link_state"], "Confirmed")

    # ------------------------------------------------------------------ AC-D07
    def test_d07_two_officers_promoting_separate_allegations_yield_one_incident_and_no_double_charge(self):
        p = plate()
        a = self.report("resident", "TYPO" + p, loc=HERE)["reference"]  # a typo plate produces a separate work item
        b = self.report("resident2", p)["reference"]
        self.assertNotEqual(self.wi(a), self.wi(b))
        as_user("officer")
        alg.claim_work_item(self.wi(a))
        as_user("officer2")
        alg.claim_work_item(self.wi(b))
        as_user("officer")
        v1 = alg.verify_and_create_violation(a, p, uuid.uuid4().hex, 5.605, -0.185, 8)
        as_user("officer2")
        v2 = alg.verify_and_create_violation(b, p, uuid.uuid4().hex, 5.605, -0.185, 8)
        self.assertEqual((v1["created"], v2["created"]), (True, False))
        self.assertEqual(v1["incident"], v2["incident"])
        self.assertEqual(frappe.db.count("CPCP Violation Incident", {"plate_normalized": normalize_plate(p)}), 1)
        self.assertEqual(frappe.db.count("CPCP Incident Allegation Link", {"parent": v1["incident"]}), 2)
        self.assertEqual(frappe.db.count("CPCP Officer Evidence", {"incident": v1["incident"]}), 2)  # each officer's evidence preserved
        self.assertEqual(self.charges(v1["incident"]), 0)

    # ------------------------------------------------------------------ AC-D08
    def test_d08_same_client_operation_is_idempotent_but_distinct_reports_are_kept(self):
        p = plate()
        cu = str(uuid.uuid4())
        a = self.report("resident", p, cu=cu)
        b = self.report("resident", p, cu=cu)  # network retry
        self.assertTrue(b["replayed"])
        self.assertEqual(a["reference"], b["reference"])
        c = self.report("resident2", p)  # genuinely separate report
        self.assertNotEqual(c["reference"], a["reference"])
        self.assertEqual(frappe.db.count("CPCP Parking Allegation", {"alleged_plate_text": p}), 2)

    # ------------------------------------------------------------------ AC-D09
    def test_d09_clamp_or_tow_active_shows_single_status_and_duplicates_start_nothing(self):
        p = plate()
        self.link_unit_vehicle(p)
        r1 = self.report("resident", p)["reference"]
        v = self.claim_and_verify(r1, p)
        self.clamp(v["incident"])
        before = frappe.db.count("CPCP Enforcement Action", {"incident": v["incident"]})
        for u in ("resident2", "resident3"):
            self.report(u, p)
        self.assertEqual(frappe.db.count("CPCP Enforcement Action", {"incident": v["incident"]}), before)
        as_user("officer")
        with self.assertRaises(frappe.DuplicateEntryError):
            enf.propose_action(v["incident"], "Clamp", "second clamp")
        cases = [c for c in ops.active_cases(self.estate) if c["incident"] == v["incident"]][0]
        self.assertTrue(cases["already_being_handled"])
        self.assertEqual((cases["episode_status"], cases["reports"]), ("Clamp Active", 3))
        self.assertTrue(inc.incident_candidates(v["incident"])["already_being_handled"])
        self.assertEqual(self.charges(v["incident"]), 1)

    # ------------------------------------------------------------------ AC-D10
    def test_d10_tow_and_storage_are_separate_lines_and_charging_is_idempotent(self):
        frappe.set_user("Administrator")
        pol = frappe.get_doc({"doctype": "CPCP Policy Version", "version_label": "storage-test", "grace_minutes": 15, "violation_penalty": 500,
                              "storage_rate_per_period": 100, "storage_period_hours": 24, "status": "Draft", "created_by_user": "Administrator"}).insert()
        pol.status, pol.approved_by = "Active", f"approver@{DOM}"
        pol.flags.ignore_permissions = True
        pol.save()
        p = plate()
        self.link_unit_vehicle(p)
        r1 = self.report("resident", p)["reference"]
        v = self.claim_and_verify(r1, p)
        c = self.clamp(v["incident"])
        as_user("officer")
        t = enf.propose_action(v["incident"], "Tow", "persisting")["action"]
        as_user("secmgr")
        enf.approve_action(t)
        as_user("officer")
        enf.execute_action(t, provider_ref="TOW-9", provider_amount=300)
        with self.assertRaises(frappe.ValidationError):  # re-execution (retry) is refused, not duplicated
            enf.execute_action(t, provider_ref="TOW-9", provider_amount=300)
        enf.record_yard_arrival(t)
        frappe.db.set_value("CPCP Enforcement Action", t, "yard_arrival_at", to_db(utcnow() - timedelta(hours=25)))
        enf.release_vehicle(t)
        classes = [line["class"] for line in (as_user("admin"), enf.get_invoice(v["incident"]))[1]["lines"]]
        self.assertEqual((classes.count("PARKING_VIOLATION"), classes.count("TOW_SERVICE"), classes.count("STORAGE")), (1, 1, 1))
        self.assertEqual(enf.get_invoice(v["incident"])["total"], "1000.00")  # 500 + 300 + 2 storage periods x 100 (illustrative values)
        from frappe_cpcp.core import charges as ch
        again = ch.Charge(v["incident"], ch.ChargeClass.PARKING_VIOLATION, 1, 500, "GHS", "x", "", ch.idempotency_key(v["incident"], ch.ChargeClass.PARKING_VIOLATION))
        self.assertEqual(enf._persist(v["incident"], [again], "t"), 0)  # replayed charge write is a no-op
        self.assertTrue(c)

    # ------------------------------------------------------------------ AC-D11
    def test_d11_resident_checks_and_acknowledgements_leak_nothing(self):
        p = plate()
        r1 = self.report("resident", p)["reference"]
        v = self.claim_and_verify(r1, p)
        as_user("resident2")
        pre = inc.precheck_similar(self.estate, HERE["lat"], HERE["lon"])
        self.assertTrue(pre["similar"])
        self.assertEqual(set(pre), {"similar", "message"})
        blob = json.dumps(pre)
        for secret in (p, v["incident"], "officer", "resident@", "A1", "clamp"):
            self.assertNotIn(secret, blob)
        ack = alg.submit_identified(self.estate, "Unsafe parking", "me too", str(uuid.uuid4()), plate_text=p, latitude=HERE["lat"], longitude=HERE["lon"], accuracy_m=10)
        self.assertEqual(set(ack), {"replayed", "reference", "status", "note"})
        self.assertNotIn(v["incident"], json.dumps(ack))
        none = inc.precheck_similar(self.estate, 5.601, -0.1801)
        self.assertEqual(set(none), {"similar", "message"})  # identical shape when nothing is nearby
        for fn, args in ((inc.incident_candidates, (v["incident"],)), (ops.incident_detail, (v["incident"],)), (alg.triage_queue, (self.estate,))):
            with self.assertRaises(frappe.PermissionError):
                fn(*args)
        mine = [x["reference"] for x in alg.my_reports()]
        self.assertIn(ack["reference"], mine)
        self.assertNotIn(r1, mine)  # another resident's report is never listed

    # ------------------------------------------------------------------ AC-D12
    def test_d12_anonymous_allegations_link_without_correlators(self):
        p = plate()
        r1 = self.report("resident", p)["reference"]
        v = self.claim_and_verify(r1, p)
        frappe.set_user("Administrator")
        code = al.community_code(frappe.conf.get("cpcp_anon_signing_key").encode(), self.estate, int(utcnow().timestamp() // (7 * 86400)))
        frappe.set_user("Guest")
        a1 = alg.submit_anonymous(self.estate, code, "Gate or driveway blocked", "anon one", plate_text=p, latitude=HERE["lat"], longitude=HERE["lon"], accuracy_m=10)
        a2 = alg.submit_anonymous(self.estate, code, "Gate or driveway blocked", "anon two", plate_text=p, latitude=HERE["lat"], longitude=HERE["lon"], accuracy_m=10)
        frappe.set_user("Administrator")
        refs = [frappe.db.get_value("CPCP Allegation Receipt", {"receipt_id": a["receipt_id"]}, "allegation") for a in (a1, a2)]
        self.assertEqual(len(set(refs)), 2)  # each anonymous report preserved individually
        for ref in refs:
            doc = frappe.get_doc("CPCP Parking Allegation", ref)
            al.assert_anonymous_clean(doc.as_dict())
            self.assertEqual(doc.owner, "Guest")
            link = frappe.get_doc("CPCP Incident Allegation Link", {"parent": v["incident"], "allegation": ref})
            self.assertIsNone(link.linked_by)  # automatic candidate linkage records no person
            self.assertEqual(link.link_state, "Auto Candidate")
        self.assertEqual(frappe.db.get_value("CPCP Violation Incident", v["incident"], "allegation_count"), 3)

    # ------------------------------------------------------------------ AC-D13
    def test_d13_merge_and_split_are_non_destructive_and_flag_duplicate_penalties(self):
        p = plate()
        q = "SIM" + plate()  # the same real car mistyped as another plate
        self.link_unit_vehicle(p)
        self.link_unit_vehicle(q)
        v1 = self.claim_and_verify(self.report("resident", p)["reference"], p)
        v2 = self.claim_and_verify(self.report("resident2", q, loc=FAR)["reference"], q, loc=FAR)
        self.clamp(v1["incident"])
        self.clamp(v2["incident"])
        self.assertEqual((self.charges(v1["incident"]), self.charges(v2["incident"])), (1, 1))
        as_user("officer")
        with self.assertRaises(frappe.PermissionError):
            inc.merge_incidents(v2["incident"], v1["incident"], "same car")
        as_user("secmgr")
        with self.assertRaises(frappe.ValidationError):
            inc.merge_incidents(v2["incident"], v1["incident"], "same car")  # source still has a live clamp
        act = frappe.get_all("CPCP Enforcement Action", filters={"incident": v2["incident"]}, pluck="name")[0]
        as_user("officer")
        enf.release_vehicle(act)
        as_user("secmgr")
        with self.assertRaises(frappe.ValidationError):
            inc.merge_incidents(v2["incident"], v1["incident"], "")
        res = inc.merge_incidents(v2["incident"], v1["incident"], "plate was misread")
        self.assertTrue(res["penalty_review_flagged"])
        self.assertEqual((self.charges(v1["incident"]), self.charges(v2["incident"])), (1, 1))  # nothing silently deleted
        self.assertTrue(frappe.db.get_value("CPCP Violation Incident", v1["incident"], "penalty_review"))
        self.assertEqual(frappe.db.get_value("CPCP Violation Incident", v2["incident"], "merged_into"), v1["incident"])
        self.assertEqual(frappe.db.count("CPCP Incident Allegation Link", {"parent": v2["incident"]}), 1)  # history kept on the source
        as_user("admin")
        inc.credit_duplicate_penalty(v2["incident"], "duplicate base penalty after merge")
        self.assertEqual(enf.get_invoice(v2["incident"])["total"], "0.00")
        self.assertEqual(self.charges(v2["incident"]), 1)  # credit is an added line; the original remains visible
        as_user("secmgr")
        n_before = frappe.db.get_value("CPCP Violation Incident", v1["incident"], "allegation_count")
        moved = frappe.get_all("CPCP Incident Allegation Link", filters={"parent": v1["incident"], "link_state": "Merged from"}, pluck="allegation")
        sp = inc.split_incident(v1["incident"], moved[0], "not actually the same car")
        self.assertEqual(frappe.db.get_value("CPCP Violation Incident", v1["incident"], "allegation_count"), n_before - 1)
        self.assertEqual(frappe.db.get_value("CPCP Incident Allegation Link", {"parent": v1["incident"], "allegation": moved[0]}, "link_state"), "Split out")
        self.assertTrue(frappe.db.get_value("CPCP Security Work Item", sp["work_item"], "review_needed"))
        self.assertTrue(frappe.db.count("CPCP Audit Event", {"action": ["in", ["incidents_merged", "incident_split", "duplicate_penalty_credited"]]}) >= 3)

    # ------------------------------------------------------------------ AC-D14
    def test_d14_repeat_offender_counts_distinct_episodes_not_allegations(self):
        rep, single = plate(), plate()
        for _ in range(2):  # two distinct episodes, three reports each
            refs = [self.report(u, rep)["reference"] for u in ("resident", "resident2", "resident3")]
            v = self.claim_and_verify(refs[0], rep)
            as_user("officer")
            inc.end_episode(v["incident"], "departure_verified", "left the estate")
        refs = [self.report(u, single)["reference"] for u in ("resident", "resident2", "resident3")]
        self.claim_and_verify(refs[0], single)
        as_user("secmgr")
        res = inc.repeat_offenders(self.estate)
        from frappe_cpcp.core.plates import mask_plate
        mine = [r for r in res["repeat_vehicles"] if r["plate"] == mask_plate(rep)]
        self.assertEqual((len(mine), mine[0]["episodes"], mine[0]["reports_attached"]), (1, 2, 6))
        self.assertFalse([r for r in res["repeat_vehicles"] if r["plate"] == mask_plate(single)])  # 3 reports, 1 episode: not a repeat
        self.assertEqual(res["basis"], "distinct verified episodes")
        as_user("officer")
        with self.assertRaises(frappe.PermissionError):
            inc.repeat_offenders(self.estate)

    # ------------------------------------------------------------------ AC-D15
    def test_d15_late_allegation_links_to_closed_episode_without_charge_and_new_episode_still_possible(self):
        p = plate()
        v1 = self.claim_and_verify(self.report("resident", p)["reference"], p)
        as_user("officer")
        inc.end_episode(v1["incident"], "departure_verified", "gone")
        late = self.report("resident2", p)["reference"]
        wi_late = self.wi(late)
        self.assertIsNotNone(wi_late)  # identity released: it is a fresh report
        # a complaint that is actually about the earlier conduct is linked as a LATE allegation instead
        as_user("officer")
        alg.claim_work_item(wi_late)
        r = inc.link_late_allegation(late, v1["incident"], "complainant describes yesterday's blocking")
        self.assertTrue(r["linked"])
        self.assertEqual(frappe.db.get_value("CPCP Incident Allegation Link", {"parent": v1["incident"], "allegation": late}, "link_state"), "Late")
        self.assertEqual(self.charges(v1["incident"]), 0)
        self.assertEqual(frappe.db.get_value("CPCP Violation Incident", v1["incident"], "episode_status"), "Resolved/Closed")
        new = self.report("resident3", p)["reference"]  # a genuinely new offense can still be filed
        self.assertTrue(self.claim_and_verify(new, p)["created"])

    # ------------------------------------------------------------------ AC-D16
    def test_d16_dashboard_and_maps_do_not_inflate(self):
        p = plate()
        refs = [self.report(u, p)["reference"] for u in ("resident", "resident2", "resident3")]
        v = self.claim_and_verify(refs[0], p)
        as_user("secmgr")
        d = reports.dashboard(self.estate)
        self.assertGreaterEqual(d["allegations"]["submitted"], d["episodes"]["unique_incidents"] + 2)
        self.assertGreaterEqual(d["episodes"]["duplicate_reports_linked"], 2)
        self.assertEqual(d["episodes"]["verified_violations"], d["episodes"]["unique_incidents"])
        self.assertIn("never inflate", d["episodes"]["note"])
        h = reports.hotspots(self.estate)
        ids = [pt["id"] for pt in h["verified_incidents"]["points"]]
        self.assertEqual(ids.count(v["incident"]), 1)  # one pin for the episode
        self.assertGreaterEqual(len([x for x in h["allegations"]["points"] if x["id"] in refs]), 3)  # complaint intensity is its own layer
        as_user("admin")
        self.assertIn("distinct_base_penalties", reports.dashboard(self.estate)["finance"])

    # ------------------------------------------------------------------ AC-D17
    def test_d17_no_cross_estate_matching_or_visibility(self):
        frappe.set_user("Administrator")
        e2 = frappe.get_doc({"doctype": "CPCP Estate", "estate_name": f"Second {uuid.uuid4().hex[:5]}"}).insert().name
        email = f"officerb@{DOM}"
        if not frappe.db.exists("User", email):
            setup._user(email, "OfficerB", "Tmp-pass-12345!")
        frappe.get_doc({"doctype": "CPCP Role Assignment", "user": email, "cpcp_role": "security_officer", "estate": e2, "approved_by": "Administrator"}).insert()
        p = plate()
        v = self.claim_and_verify(self.report("resident", p)["reference"], p)
        # the same plate reported in the other estate (as a manager-level user with scope there) must not touch estate A
        frappe.set_user("Administrator")
        alg_b = frappe.get_doc({"doctype": "CPCP Parking Allegation", "estate": e2, "mode": "Identified", "category": "Unsafe parking", "narrative": "other estate",
                                "alleged_plate_text": p, "state": "Submitted", "client_uuid": str(uuid.uuid4()), "submitted_at": to_db(utcnow()),
                                "alleged_plate_hash": svc.ep.plate_hash(normalize_plate(p))}).insert()
        routing = svc.route_allegation(alg_b.as_dict())
        self.assertEqual(routing["action"], "new_work_item")
        self.assertEqual(frappe.db.get_value("CPCP Security Work Item", routing["work_item"], "estate"), e2)
        self.assertEqual(frappe.db.get_value("CPCP Violation Incident", v["incident"], "allegation_count"), 1)
        frappe.set_user(email)
        with self.assertRaises(frappe.PermissionError):
            alg.triage_queue(self.estate)
        with self.assertRaises(frappe.PermissionError):
            inc.incident_candidates(v["incident"])
        as_user("officer")
        with self.assertRaises(frappe.PermissionError):
            alg.triage_queue(e2)
        self.assertNotIn(routing["work_item"], [x["work_item"] for x in alg.triage_queue(self.estate)])

    # ------------------------------------------------------------------ AC-D18
    def test_d18_urgent_second_report_raises_priority_without_bypassing_approvals(self):
        p = plate()
        self.link_unit_vehicle(p)
        v = self.claim_and_verify(self.report("resident", p)["reference"], p)
        self.assertEqual(frappe.db.get_value("CPCP Violation Incident", v["incident"], "priority"), "Normal")
        actions_before = frappe.db.count("CPCP Enforcement Action", {"incident": v["incident"]})
        self.report("resident2", p, urgent=1)
        self.assertEqual(frappe.db.get_value("CPCP Violation Incident", v["incident"], "priority"), "Urgent claimed")
        mgr = frappe.get_all("CPCP Notification Outbox", filters={"incident": v["incident"], "idempotency_key": ["like", "priority_escalated:%"]}, pluck="recipient_user")
        self.assertIn(f"secmgr@{DOM}", mgr)
        self.assertEqual(frappe.db.count("CPCP Enforcement Action", {"incident": v["incident"]}), actions_before)
        self.assertEqual(self.charges(v["incident"]), 0)
        self._flags(True)  # enforcement still needs notice + expired grace + independent approval
        as_user("officer")
        with self.assertRaises(frappe.ValidationError):
            enf.propose_action(v["incident"], "Tow", "urgent")
        # same for an urgent report that joins an unverified work item
        p2 = plate()
        r = self.report("resident", p2)["reference"]
        self.report("resident2", p2, urgent=1)
        self.assertEqual(frappe.db.get_value("CPCP Security Work Item", self.wi(r), "urgency"), "Urgent claimed")
