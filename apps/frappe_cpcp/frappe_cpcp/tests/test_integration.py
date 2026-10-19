# SPDX-License-Identifier: Apache-2.0
"""Frappe integration tests: real DB, real permission hooks, real APIs. Run per site:

    bench --site org-a.localhost run-tests --app frappe_cpcp --module frappe_cpcp.tests.test_integration
"""
import uuid
from datetime import timedelta

import frappe
from frappe.tests.utils import FrappeTestCase

from frappe_cpcp import setup
from frappe_cpcp.api import allegations as alg_api
from frappe_cpcp.api import registry, session, visitors
from frappe_cpcp.core import allegations as al
from frappe_cpcp.core.authz import Role
from frappe_cpcp.permissions import get_actor, has_permission
from frappe_cpcp.services.audit import verify_audit_chain
from frappe_cpcp.services.common import utcnow


def as_user(key):
    frappe.set_user(f"{key}@{DOM}")


DOM = "demo-a.example.invalid"


class TestCPCP(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        frappe.set_user("Administrator")
        cls.seed = setup.seed_demo("a")
        cls.estate = next(iter(cls.seed["estates"].values()))["name"]
        cls.gate = next(iter(cls.seed["estates"].values()))["gate"]

    def tearDown(self):
        frappe.set_user("Administrator")

    # ---- legal gates ------------------------------------------------------------------------
    def test_gates_default_off_and_need_reference(self):
        s = frappe.get_single("CPCP Settings")
        self.assertFalse(any(s.get(f) for f in ("fine_assessment_enabled", "clamping_enabled", "towing_enabled", "payment_collection_enabled")))
        s.clamping_enabled = 1
        s.legal_approval_reference = ""
        with self.assertRaises(frappe.ValidationError):
            s.save()
        frappe.db.rollback()

    # ---- AC-36 / AC-14: resident cannot touch registries -----------------------------------
    def test_resident_cannot_access_registry_or_visitor_log(self):
        as_user("resident")
        for dt in ("CPCP Vehicle", "CPCP Person", "CPCP Visitor Session", "CPCP Unit Membership"):
            self.assertFalse(frappe.has_permission(dt, "read"), dt)
            with self.assertRaises(frappe.PermissionError):
                frappe.get_list(dt)
        with self.assertRaises(frappe.PermissionError):
            registry.lookup_plate(self.estate, "ZZ 1001-26")
        with self.assertRaises(frappe.PermissionError):
            visitors.active_visitors(self.estate)
        with self.assertRaises(frappe.PermissionError):
            registry.lookup_visits_for_unit(self.estate, "A1")

    def test_navigation_manifest_per_role(self):
        as_user("resident")
        nav = session.whoami()["navigation"]
        self.assertNotIn("resident_registry", nav)
        self.assertNotIn("visitor_log", nav)
        self.assertIn("submit_report", nav)
        as_user("officer")
        self.assertIn("visitor_log", session.whoami()["navigation"])

    # ---- AC-03 / AC-37: officer lookup is minimal and logged -----------------------------------
    def test_officer_lookup_minimal_and_logged(self):
        as_user("officer")
        before = frappe.db.count("CPCP Sensitive Access Event")
        r = registry.lookup_plate(self.estate, "zz1001-26")
        self.assertEqual(r["match"], "resident_vehicle")
        self.assertEqual(r["unit"], "A1")
        self.assertFalse({"phone", "name", "full_name", "email"} & set(r) | {"phone", "name"} & set(r.get("vehicle", {})))
        self.assertGreater(frappe.db.count("CPCP Sensitive Access Event"), before)
        self.assertEqual(registry.lookup_plate(self.estate, "QQ9999")["match"], "none")

    def test_officer_cannot_reach_other_estate(self):
        frappe.set_user("Administrator")
        other = frappe.get_doc({"doctype": "CPCP Estate", "estate_name": f"Other {uuid.uuid4().hex[:6]}"}).insert().name
        as_user("officer")
        with self.assertRaises(frappe.PermissionError):
            registry.lookup_plate(other, "ZZ1001-26")
        denied = frappe.get_all("CPCP Sensitive Access Event", filters={"result": "Denied", "estate": other})
        self.assertTrue(denied)

    # ---- visitors: AC-04, AC-101, AC-102, AC-105, AC-106 ---------------------------------------
    def _checkin(self, plate, unit="A1", **kw):
        return visitors.check_in_visitor(self.estate, unit, str(uuid.uuid4()), plate=plate, gate=self.gate,
                                         confirm_visiting_today=1, **kw)

    def test_visit_lifecycle_idempotency_and_duplicates(self):
        as_user("officer")
        plate = f"VV{uuid.uuid4().int % 9000 + 1000}"
        key = str(uuid.uuid4())
        a = visitors.check_in_visitor(self.estate, "A1", key, plate=plate, gate=self.gate, confirm_visiting_today=1)
        again = visitors.check_in_visitor(self.estate, "A1", key, plate=plate, gate=self.gate, confirm_visiting_today=1)
        self.assertTrue(again["replayed"])
        self.assertEqual(a["session"], again["session"])
        with self.assertRaises(frappe.DuplicateEntryError):  # same plate already inside
            self._checkin(plate)
        self.assertEqual(len(visitors.active_visitors(self.estate, plate=plate)), 1)
        self.assertEqual(registry.lookup_plate(self.estate, plate)["match"], "active_visitor")
        out_key = str(uuid.uuid4())
        out = visitors.check_out_visitor(a["session"], out_key, gate=self.gate)
        self.assertEqual(out["status"], "Checked Out")
        self.assertEqual(out["presence"], "Confirmed Out")
        self.assertIsNotNone(out["duration_minutes"])
        self.assertTrue(visitors.check_out_visitor(a["session"], out_key, gate=self.gate)["replayed"])
        with self.assertRaises(frappe.DuplicateEntryError):  # second, different exit
            visitors.check_out_visitor(a["session"], str(uuid.uuid4()), gate=self.gate)
        self.assertEqual(visitors.active_visitors(self.estate, plate=plate), [])
        b = self._checkin(plate)  # AC-104: re-entry is a NEW session
        self.assertNotEqual(b["session"], a["session"])
        self.assertEqual(frappe.db.count("CPCP Visit Event", {"session": a["session"]}), 2)

    def test_resident_vehicle_exit_needs_no_visitor_session(self):
        as_user("officer")
        before = frappe.db.count("CPCP Visitor Session")
        registry.lookup_plate(self.estate, "ZZ1001-26")
        self.assertEqual(frappe.db.count("CPCP Visitor Session"), before)

    def test_unit_first_suggestions_are_scoped_and_not_authorization(self):
        as_user("officer")
        plate = f"UF{uuid.uuid4().int % 9000 + 1000}"
        s = self._checkin(plate, unit="A2")
        visitors.check_out_visitor(s["session"], str(uuid.uuid4()), gate=self.gate)
        a2 = registry.lookup_visits_for_unit(self.estate, "A2")["candidates"]
        a1 = registry.lookup_visits_for_unit(self.estate, "A1")["candidates"]
        self.assertIn(plate, [c["plate"] for c in a2])
        self.assertNotIn(plate, [c["plate"] for c in a1])  # AC-75: A2's history is not shown for A1
        self.assertTrue(all("phone" not in c and "name" not in c for c in a2))

    def test_checkout_unknown_session_is_forbidden_not_not_found(self):
        as_user("officer")
        with self.assertRaises(frappe.PermissionError):
            visitors.check_out_visitor("does-not-exist", str(uuid.uuid4()))

    def test_auditor_cannot_mutate(self):
        as_user("auditor")
        with self.assertRaises(frappe.PermissionError):
            self._checkin("AU1234")
        with self.assertRaises(frappe.PermissionError):
            registry.lookup_plate(self.estate, "ZZ1001-26")  # no grant -> no read
        with self.assertRaises(frappe.PermissionError):
            alg_api.submit_identified(self.estate, "Unsafe parking", "x", str(uuid.uuid4()))

    # ---- allegations: AC-43..AC-47, AC-57, AC-59..AC-63 ----------------------------------------
    def _report(self, plate="RP4321", mode="identified"):
        if mode == "identified":
            as_user("resident")
            return alg_api.submit_identified(self.estate, "Gate or driveway blocked", "Car blocking the gate", str(uuid.uuid4()),
                                             plate_text=plate, latitude=5.605, longitude=-0.185, accuracy_m=12, location_source="device", urgent=1)

    def test_identified_report_is_unverified_and_has_no_consequences(self):
        r = self._report()
        a = frappe.get_doc("CPCP Parking Allegation", r["reference"])
        self.assertEqual(a.mode, "Identified")
        self.assertEqual(a.state, al.State.RECEIVED.value)
        self.assertEqual(frappe.db.count("CPCP Violation Incident", {"verified_by": ["is", "set"]}) , frappe.db.count("CPCP Violation Incident"))
        wi = frappe.get_all("CPCP Security Work Item", filters={"allegation": a.name}, fields=["status", "claimed_by"])
        self.assertEqual(len(wi), 1)
        self.assertEqual(wi[0].status, "Open")
        recips = {o.recipient_role for o in frappe.get_all("CPCP Notification Outbox", filters={"work_item": ["like", "SWI-%"]}, fields=["recipient_role", "payload_minimal"])}
        self.assertTrue({"security_officer", "security_manager"} <= recips)
        payload = frappe.get_all("CPCP Notification Outbox", fields=["payload_minimal"], limit=1, order_by="creation desc")[0].payload_minimal
        self.assertNotIn("RP4321", payload)
        self.assertNotIn("resident@", payload)
        as_user("resident")
        self.assertIn(r["reference"], [x["reference"] for x in alg_api.my_reports()])
        self.assertFalse(frappe.has_permission("CPCP Parking Allegation", "read"))

    def test_report_idempotent_on_client_uuid(self):
        as_user("resident")
        k = str(uuid.uuid4())
        a = alg_api.submit_identified(self.estate, "Unsafe parking", "dup test", k)
        b = alg_api.submit_identified(self.estate, "Unsafe parking", "dup test", k)
        self.assertTrue(b["replayed"])
        self.assertEqual(a["reference"], b["reference"])

    def test_anonymous_report_has_no_correlators_and_receipt_works(self):
        frappe.set_user("Administrator")
        key = frappe.conf.get("cpcp_anon_signing_key").encode()
        epoch = int(utcnow().timestamp() // (7 * 86400))
        code = al.community_code(key, self.estate, epoch)
        frappe.set_user("Guest")
        with self.assertRaises(frappe.ValidationError):
            alg_api.submit_anonymous(self.estate, "WRONGCODE", "Unsafe parking", "x")
        res = alg_api.submit_anonymous(self.estate, code, "Unsafe parking", "Anon blocked road", plate_text="AN0001")
        self.assertIn("secret", res)
        frappe.set_user("Administrator")
        rec = frappe.get_doc("CPCP Allegation Receipt", {"receipt_id": res["receipt_id"]})
        a = frappe.get_doc("CPCP Parking Allegation", rec.allegation)
        self.assertEqual(a.mode, "Anonymous")
        self.assertEqual(a.owner, "Guest")
        al.assert_anonymous_clean(a.as_dict())
        self.assertFalse(a.reporter_user or a.reporter_unit)
        self.assertNotIn(res["secret"], (rec.salt + rec.verifier))
        frappe.set_user("Guest")
        self.assertTrue(alg_api.anonymous_status(res["receipt_id"], res["secret"])["found"])
        self.assertEqual(alg_api.anonymous_status(res["receipt_id"], "wrong"), {"found": False})
        self.assertEqual(alg_api.anonymous_status("R-NOPE", "x"), {"found": False})
        as_user("resident")  # not in any account history
        self.assertNotIn(a.name, [x["reference"] for x in alg_api.my_reports()])
        with self.assertRaises(frappe.ValidationError):  # authenticated sessions may not use the anonymous route
            alg_api.submit_anonymous(self.estate, code, "Unsafe parking", "signed in")

    def test_triage_claim_race_and_verification(self):
        r = self._report(plate="RC7777")
        wi = frappe.get_all("CPCP Security Work Item", filters={"allegation": r["reference"]}, pluck="name")[0]
        as_user("resident")
        with self.assertRaises(frappe.PermissionError):
            alg_api.claim_work_item(wi)
        with self.assertRaises(frappe.PermissionError):
            alg_api.triage_queue(self.estate)
        as_user("officer")
        q = alg_api.triage_queue(self.estate)
        item = next(x for x in q if x["work_item"] == wi)
        self.assertNotIn("reporter", " ".join(item))  # projection has no reporter fields
        alg_api.claim_work_item(wi)
        # a second claimant (the manager) loses the race
        as_user("secmgr")
        with self.assertRaises(frappe.DuplicateEntryError):
            alg_api.claim_work_item(wi)
        # officer verifies: needs the claim, officer evidence, in-boundary location
        as_user("officer")
        before_narrative = frappe.db.get_value("CPCP Parking Allegation", r["reference"], "narrative")
        with self.assertRaises(frappe.ValidationError):
            alg_api.verify_and_create_violation(r["reference"], "RC7777", "", 5.605, -0.185, 8)  # no evidence hash
        with self.assertRaises(frappe.ValidationError):
            alg_api.verify_and_create_violation(r["reference"], "RC7777", "abc123", 40.0, 10.0, 8)  # outside geofence
        v = alg_api.verify_and_create_violation(r["reference"], "RC7777", "e3b0c44298fc1c149afbf4c8996fb924", 5.605, -0.185, 8)
        self.assertTrue(v["created"])
        inc = frappe.get_doc("CPCP Violation Incident", v["incident"])
        self.assertEqual(inc.status, "recorded")
        self.assertEqual(inc.verified_by, f"officer@{DOM}")
        self.assertEqual(frappe.db.get_value("CPCP Parking Allegation", r["reference"], "narrative"), before_narrative)
        self.assertEqual(frappe.db.get_value("CPCP Parking Allegation", r["reference"], "state"), al.State.VERIFIED.value)
        # a second allegation about the same plate joins the SAME incident (no duplicate penalty path)
        r2 = self._report(plate="RC7777")
        wi2 = frappe.get_all("CPCP Security Work Item", filters={"allegation": r2["reference"]}, pluck="name")[0]
        as_user("officer")
        alg_api.claim_work_item(wi2)
        v2 = alg_api.verify_and_create_violation(r2["reference"], "RC7777", "feedbeef", 5.605, -0.185, 8)
        self.assertFalse(v2["created"])
        self.assertEqual(v2["incident"], v["incident"])

    def test_reject_outcome_requires_reason_and_creates_nothing(self):
        r = self._report(plate="NS1111")
        wi = frappe.get_all("CPCP Security Work Item", filters={"allegation": r["reference"]}, pluck="name")[0]
        as_user("officer")
        alg_api.claim_work_item(wi)
        with self.assertRaises(frappe.ValidationError):
            alg_api.close_allegation(r["reference"], "Not Substantiated", "")
        n = frappe.db.count("CPCP Violation Incident")
        alg_api.close_allegation(r["reference"], "Not Substantiated", "Vehicle gone, nothing observed")
        self.assertEqual(frappe.db.count("CPCP Violation Incident"), n)

    def test_reveal_reporter_is_manager_only_and_reasoned(self):
        r = self._report(plate="RV1212")
        as_user("officer")
        with self.assertRaises(frappe.PermissionError):
            alg_api.reveal_reporter(r["reference"], "need to ask a follow up question")
        as_user("secmgr")
        with self.assertRaises(frappe.ValidationError):
            alg_api.reveal_reporter(r["reference"], "short")
        self.assertEqual(alg_api.reveal_reporter(r["reference"], "clarify location with reporter")["reporter_user"], f"resident@{DOM}")

    # ---- immutability / audit / roles -----------------------------------------------------------
    def test_append_only_and_audit_chain(self):
        frappe.set_user("Administrator")
        ev = frappe.get_all("CPCP Audit Event", limit=1)
        self.assertTrue(ev)
        d = frappe.get_doc("CPCP Audit Event", ev[0].name)
        d.actor = "mallory"
        with self.assertRaises(frappe.PermissionError):
            d.save()
        with self.assertRaises(frappe.PermissionError):
            frappe.delete_doc("CPCP Audit Event", ev[0].name, force=True)
        ok, bad = verify_audit_chain()
        self.assertTrue(ok, f"audit chain broken at {bad}")

    def test_system_manager_cannot_hold_tenant_role(self):
        frappe.set_user("Administrator")
        with self.assertRaises(frappe.ValidationError):
            frappe.get_doc({"doctype": "CPCP Role Assignment", "user": "Administrator", "cpcp_role": "org_admin"}).insert()

    def test_multiple_roles_require_explicit_context(self):
        frappe.set_user("Administrator")
        u = f"officer@{DOM}"
        if not frappe.db.exists("CPCP Role Assignment", {"user": u, "cpcp_role": "resident"}):
            unit = frappe.db.get_value("CPCP Unit", {"estate": self.estate}, "name")
            frappe.get_doc({"doctype": "CPCP Role Assignment", "user": u, "cpcp_role": "resident", "unit": unit,
                            "approved_by": "Administrator"}).insert()
        frappe.set_user(u)
        from frappe_cpcp.permissions import RoleContextRequired
        with self.assertRaises(RoleContextRequired):
            get_actor()
        self.assertEqual(get_actor(role_context="security_officer").role, Role.SECURITY_OFFICER)
        with self.assertRaises(frappe.PermissionError):
            get_actor(role_context="org_admin")  # cannot select a role that is not held
        frappe.set_user("Administrator")
        frappe.db.set_value("CPCP Role Assignment", {"user": u, "cpcp_role": "resident"}, "status", "Revoked")

    def test_expired_assignment_denied(self):
        frappe.set_user("Administrator")
        name = frappe.db.get_value("CPCP Role Assignment", {"user": f"officer@{DOM}", "cpcp_role": "security_officer"})
        frappe.db.set_value("CPCP Role Assignment", name, "valid_until", (utcnow() - timedelta(days=1)).date())
        as_user("officer")
        with self.assertRaises(frappe.PermissionError):
            registry.lookup_plate(self.estate, "ZZ1001-26")
        frappe.set_user("Administrator")
        frappe.db.set_value("CPCP Role Assignment", name, "valid_until", None)

    def test_has_permission_hook_false_for_guest(self):
        frappe.set_user("Guest")
        doc = frappe.get_doc("CPCP Estate", self.estate)
        self.assertFalse(has_permission(doc, "read", "Guest"))
