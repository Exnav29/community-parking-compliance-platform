# SPDX-License-Identifier: Apache-2.0
"""Integration tests: contact resolution, calls/SMS truthfulness, notice clock, gated enforcement, charges, appeals."""
import json
import uuid
from datetime import timedelta

import frappe
from frappe.tests.utils import FrappeTestCase

from frappe_cpcp import setup
from frappe_cpcp.api import allegations as alg
from frappe_cpcp.api import communications as com
from frappe_cpcp.api import enforcement as enf
from frappe_cpcp.api import incidents as inc_api
from frappe_cpcp.core import episodes as ep
from frappe_cpcp.core.plates import normalize_plate
from frappe_cpcp.core import comms as cm
from frappe_cpcp.services.common import to_db, utcnow

DOM = "demo-a.example.invalid"
FLAGS = ("fine_assessment_enabled", "clamping_enabled", "towing_enabled")


def as_user(key):
    frappe.set_user(f"{key}@{DOM}")


class TestCommsEnforcement(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        frappe.set_user("Administrator")
        cls.seed = setup.seed_demo("a")
        e = next(iter(cls.seed["estates"].values()))
        cls.estate, cls.gate = e["name"], e["gate"]
        frappe.db.set_single_value("CPCP Settings", "allegation_rate_limit_per_hour", 10000)  # tests file many reports

    @classmethod
    def tearDownClass(cls):
        frappe.db.set_single_value("CPCP Settings", "allegation_rate_limit_per_hour", 10)
        super().tearDownClass()

    def tearDown(self):
        frappe.set_user("Administrator")
        self._flags(False)

    def _flags(self, on: bool):
        frappe.set_user("Administrator")
        s = frappe.get_single("CPCP Settings")
        for f in FLAGS:
            s.set(f, 1 if on else 0)
        s.legal_approval_reference = "TEST-APPROVAL-001" if on else ""
        s.flags.ignore_permissions = True
        s.save()

    def _end_existing_episode(self, plate):
        """One vehicle == one live episode (PRD 60). Fixtures end the previous one with a documented manager determination."""
        frappe.set_user("Administrator")
        row = frappe.db.get_value("CPCP Violation Incident", {"active_key": ep.active_key(self.estate, normalize_plate(plate))}, "name")
        if row:
            as_user("secmgr")
            inc_api.end_episode(row, "manager_determination", "test fixture: previous episode ended")

    def _incident(self, classification="Ordinary", plate="ZZ1001-26") -> str:
        self._end_existing_episode(plate)
        as_user("resident")
        r = alg.submit_identified(self.estate, "Unsafe parking", "test", str(uuid.uuid4()), plate_text=f"T{uuid.uuid4().hex[:6]}")
        wi = frappe.get_all("CPCP Security Work Item", filters={"allegation": r["reference"]}, pluck="name")[0]
        as_user("officer")
        alg.claim_work_item(wi)
        v = alg.verify_and_create_violation(r["reference"], plate, uuid.uuid4().hex, 5.605, -0.185, 8, classification=classification)
        return v["incident"]

    # ------------------------------------------------------------------ contacts / calls ----------------
    def test_contact_resolution_minimal_ordered_and_scoped(self):
        inc = self._incident()
        res = com.resolve_violation_contacts(inc)
        self.assertEqual(res["basis"], "resident_vehicle")
        self.assertEqual([c["relationship"] for c in res["contacts"]][:2], ["Primary household contact", "Backup household contact"])
        blob = json.dumps(res)
        self.assertNotIn("0241230001", blob)
        self.assertNotIn("+233241230001", blob)
        as_user("resident")
        with self.assertRaises(frappe.PermissionError):
            com.resolve_violation_contacts(inc)
        as_user("auditor")
        with self.assertRaises(frappe.PermissionError):
            com.resolve_violation_contacts(inc)

    def test_arbitrary_contact_ids_rejected(self):
        inc = self._incident()
        with self.assertRaises(frappe.PermissionError):
            com.initiate_call(inc, "MEM-99999", str(uuid.uuid4()))

    def test_unanswered_call_is_not_notice_and_confirmed_answer_starts_clock(self):
        inc = self._incident()
        cid = com.resolve_violation_contacts(inc)["contacts"][0]["contact_id"]
        r = com.initiate_call(inc, cid, str(uuid.uuid4()))
        self.assertTrue(r["dial"].startswith("+233"))
        a = frappe.get_doc("CPCP Communication Attempt", r["attempt"])
        self.assertEqual(a.provenance, "requested-only")  # opening the dialer proves nothing
        with self.assertRaises(frappe.ValidationError):
            com.establish_notice_clock(inc, a.name)  # no outcome yet
        out = com.record_call_outcome(a.name, "No Answer", warning_confirmed=1)
        self.assertFalse(out["can_establish_notice"])
        with self.assertRaises(frappe.ValidationError):
            com.establish_notice_clock(inc, a.name)
        self.assertFalse(frappe.db.exists("CPCP Warning Notice", {"incident": inc}))
        # follow-up attempt answered AND warning confirmed
        r2 = com.initiate_call(inc, cid, str(uuid.uuid4()))
        res = com.record_call_outcome(r2["attempt"], "Answered", warning_confirmed=1, estimated_seconds=70)
        self.assertTrue(res["can_establish_notice"])
        self.assertIn("unverified", res["duration"])
        n = com.establish_notice_clock(inc, r2["attempt"])
        self.assertEqual(n["grace_minutes"], 15)
        self.assertEqual(frappe.db.get_value("CPCP Violation Incident", inc, "status"), "grace_active")
        with self.assertRaises(frappe.DuplicateEntryError):
            com.establish_notice_clock(inc, r2["attempt"])

    def test_answered_without_officer_confirmation_does_not_qualify(self):
        inc = self._incident()
        cid = com.resolve_violation_contacts(inc)["contacts"][0]["contact_id"]
        r = com.initiate_call(inc, cid, str(uuid.uuid4()))
        self.assertFalse(com.record_call_outcome(r["attempt"], "Answered", warning_confirmed=0)["can_establish_notice"])

    def test_call_start_is_idempotent(self):
        inc = self._incident()
        cid = com.resolve_violation_contacts(inc)["contacts"][0]["contact_id"]
        k = str(uuid.uuid4())
        a, b = com.initiate_call(inc, cid, k), com.initiate_call(inc, cid, k)
        self.assertEqual(a["attempt"], b["attempt"])
        self.assertTrue(b["replayed"])

    # ------------------------------------------------------------------ SMS ------------------------------
    def test_sms_states_are_distinct_and_callbacks_safe(self):
        inc = self._incident()
        cid = com.resolve_violation_contacts(inc)["contacts"][0]["contact_id"]
        k = str(uuid.uuid4())
        r = com.send_case_sms(inc, cid, k)
        self.assertEqual(r["status"], "Provider Accepted")
        self.assertTrue(com.send_case_sms(inc, cid, k)["replayed"])
        a = frappe.get_doc("CPCP Communication Attempt", r["attempt"])
        self.assertNotIn("deadline", a.message_text.lower())  # no promised deadline before a clock exists
        self.assertIn("Case " + inc, a.message_text)
        secret = frappe.conf.get("cpcp_sms_callback_secret").encode()
        body = lambda st, ts: json.dumps({"provider": "mock", "id": a.provider_ref, "status": st, "ts": ts}).encode()  # noqa: E731
        bad = com.ingest_callback(body("delivered", "t1"), "forged")
        self.assertFalse(bad["ok"])
        self.assertEqual(frappe.db.get_value("CPCP Communication Attempt", a.name, "sms_status"), "Provider Accepted")
        ok = body("delivered", "t2")
        self.assertEqual(com.ingest_callback(ok, cm.sign_callback(secret, ok))["status"], "Delivered")
        self.assertTrue(com.ingest_callback(ok, cm.sign_callback(secret, ok))["duplicate"])  # replay
        late = body("sent", "t1")
        com.ingest_callback(late, cm.sign_callback(secret, late))
        self.assertEqual(frappe.db.get_value("CPCP Communication Attempt", a.name, "sms_status"), "Delivered")  # no regression
        self.assertFalse(frappe.db.get_value("CPCP Communication Attempt", a.name, "acknowledged"))  # delivered != acknowledged
        self.assertEqual(frappe.db.count("CPCP Communication Event", {"attempt": a.name, "event_type": "provider:delivered"}), 1)
        unknown = json.dumps({"id": "nope", "status": "delivered", "ts": "x"}).encode()
        self.assertTrue(com.ingest_callback(unknown, cm.sign_callback(secret, unknown))["ok"])  # generic

    def test_sms_forbidden_for_resident_and_rate_limited(self):
        inc = self._incident()
        cid = com.resolve_violation_contacts(inc)["contacts"][0]["contact_id"]
        com.send_case_sms(inc, cid, str(uuid.uuid4()))
        com.send_case_sms(inc, cid, str(uuid.uuid4()))
        with self.assertRaises(frappe.TooManyRequestsError):
            com.send_case_sms(inc, cid, str(uuid.uuid4()))
        as_user("resident")
        with self.assertRaises(frappe.PermissionError):
            com.send_case_sms(inc, cid, str(uuid.uuid4()))

    def test_timeline_masks_numbers(self):
        inc = self._incident()
        cid = com.resolve_violation_contacts(inc)["contacts"][0]["contact_id"]
        com.initiate_call(inc, cid, str(uuid.uuid4()))
        tl = com.comms_timeline(inc)
        self.assertNotIn("0241230001", json.dumps(tl))
        self.assertEqual(tl["attempts"][0]["provenance"], "requested-only")

    # ------------------------------------------------------------------ enforcement ----------------------
    def _notice_expired(self, inc):
        cid = com.resolve_violation_contacts(inc)["contacts"][0]["contact_id"]
        a = com.initiate_call(inc, cid, str(uuid.uuid4()))["attempt"]
        com.record_call_outcome(a, "Answered", warning_confirmed=1)
        n = com.establish_notice_clock(inc, a)["notice"]
        frappe.db.set_value("CPCP Warning Notice", n, "deadline", to_db(utcnow() - timedelta(minutes=1)))  # test-only time travel

    def test_ac19_enforcement_unavailable_while_gates_off(self):
        inc = self._incident()
        for t in ("Clamp", "Tow"):
            with self.assertRaises(frappe.PermissionError):
                enf.propose_action(inc, t, "attempt")
        self.assertEqual(frappe.db.count("CPCP Incident Charge", {"incident": inc}), 0)
        as_user("finance")
        with self.assertRaises(frappe.PermissionError):
            enf.propose_action(inc, "Tow", "x")

    def test_clamp_then_tow_one_penalty_itemized_with_separation_of_duties(self):
        inc = self._incident()
        self._flags(True)
        as_user("officer")
        with self.assertRaises(frappe.ValidationError):
            enf.propose_action(inc, "Clamp", "no notice yet")
        self._notice_expired(inc)
        clamp = enf.propose_action(inc, "Clamp", "grace expired")
        with self.assertRaises(frappe.PermissionError):
            enf.approve_action(clamp["action"])  # officer cannot approve (and never their own)
        with self.assertRaises(frappe.ValidationError):
            enf.execute_action(clamp["action"])  # not approved yet
        as_user("secmgr")
        enf.approve_action(clamp["action"])
        as_user("officer")
        enf.execute_action(clamp["action"])
        tow = enf.propose_action(inc, "Tow", "obstruction persists")
        as_user("secmgr")
        enf.approve_action(tow["action"])
        as_user("officer")
        with self.assertRaises(frappe.ValidationError):
            enf.execute_action(tow["action"])  # no provider amount: fees are never invented
        enf.execute_action(tow["action"], provider_ref="TOW-1", provider_amount=300)
        as_user("admin")
        inv = enf.get_invoice(inc)
        classes = [line["class"] for line in inv["lines"]]
        self.assertEqual(classes.count("PARKING_VIOLATION"), 1)
        self.assertEqual(classes.count("TOW_SERVICE"), 1)
        self.assertEqual(inv["total"], "800.00")  # 500 once + 300 tow (clamp then tow: no second penalty)
        as_user("officer")
        self.assertNotIn("lines", enf.get_invoice(inc))  # guards see status only
        enf.record_yard_arrival(tow["action"])
        self._flags(False)  # release must still work with every gate off
        as_user("officer")
        self.assertIn("released_at", enf.release_vehicle(tow["action"]))
        self.assertEqual(frappe.db.get_value("CPCP Violation Incident", inc, "status"), "released")

    def test_emergency_obstruction_never_clamped(self):
        inc = self._incident(classification="Emergency")
        self._flags(True)
        as_user("officer")
        with self.assertRaises(frappe.ValidationError):
            enf.propose_action(inc, "Clamp", "x")
        self.assertEqual(enf.propose_action(inc, "Tow", "gate blocked, safe removal")["status"], "Proposed")

    def test_grace_must_expire_and_correction_closes_without_fee(self):
        inc = self._incident()
        cid = com.resolve_violation_contacts(inc)["contacts"][0]["contact_id"]
        a = com.initiate_call(inc, cid, str(uuid.uuid4()))["attempt"]
        com.record_call_outcome(a, "Answered", warning_confirmed=1)
        com.establish_notice_clock(inc, a)
        self._flags(True)
        as_user("officer")
        with self.assertRaises(frappe.ValidationError):
            enf.propose_action(inc, "Tow", "too early")
        r = enf.mark_corrected(inc, "moved within grace")
        self.assertEqual((r["status"], r["charges"]), ("corrected_no_fee", 0))
        with self.assertRaises(frappe.ValidationError):
            enf.propose_action(inc, "Tow", "after correction")
        self.assertEqual(frappe.db.count("CPCP Incident Charge", {"incident": inc}), 0)

    def test_appeal_independent_review_and_credit(self):
        inc = self._incident()
        self._flags(True)
        as_user("officer")
        self._notice_expired(inc)
        c = enf.propose_action(inc, "Clamp", "r")
        as_user("secmgr")
        enf.approve_action(c["action"])
        as_user("officer")
        enf.execute_action(c["action"])
        as_user("resident")
        ap = enf.submit_appeal(inc, "I was loading groceries")["appeal"]
        with self.assertRaises(frappe.DuplicateEntryError):
            enf.submit_appeal(inc, "again")
        self.assertEqual(enf.get_invoice(inc)["total"], "500.00")  # resident sees own household invoice
        as_user("officer")
        with self.assertRaises(frappe.PermissionError):
            enf.decide_appeal(ap, "Upheld", "x")  # officers cannot resolve appeals
        as_user("admin")
        r = enf.decide_appeal(ap, "Upheld", "Loading was brief and permitted")
        self.assertEqual(r["credit"], "500.00")
        self.assertEqual(enf.get_invoice(inc)["total"], "0.00")
        self.assertEqual(frappe.db.count("CPCP Incident Charge", {"incident": inc, "charge_class": "PARKING_VIOLATION"}), 1)  # original kept
        with self.assertRaises(frappe.ValidationError):
            enf.decide_appeal(ap, "Dismissed", "again")

    def test_other_household_cannot_appeal_or_read_invoice(self):
        inc = self._incident()
        frappe.set_user("Administrator")
        other_unit = frappe.db.get_value("CPCP Unit", {"estate": self.estate, "unit_label": "A2"})
        email = f"neighbor@{DOM}"
        if not frappe.db.exists("User", email):
            setup._user(email, "Neighbor", "Tmp-pass-12345!")
        if not frappe.db.exists("CPCP Role Assignment", {"user": email}):
            frappe.get_doc({"doctype": "CPCP Role Assignment", "user": email, "cpcp_role": "resident", "unit": other_unit,
                            "approved_by": "Administrator"}).insert()
        frappe.set_user(email)
        with self.assertRaises(frappe.PermissionError):
            enf.submit_appeal(inc, "not mine")
        with self.assertRaises(frappe.PermissionError):
            enf.get_invoice(inc)
