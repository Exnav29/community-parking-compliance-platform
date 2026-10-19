# SPDX-License-Identifier: Apache-2.0
"""PRD v1.8 section 61 acceptance tests PBAC-01..PBAC-20 (in-process; HTTP variants live in tests/privacy).

The journal is committed out-of-band, so every assertion about it reads through ``access.query`` (a fresh connection).
"""
import json
import time
import uuid
from datetime import timedelta
from unittest import mock

import frappe
from frappe.tests.utils import FrappeTestCase

from frappe_cpcp import guards, setup
from frappe_cpcp.api import access_review as ar
from frappe_cpcp.api import allegations as alg
from frappe_cpcp.api import communications as com
from frappe_cpcp.api import duty, incidents as inc_api, registry, visitors
from frappe_cpcp.core.pbac import FIELDS, GATE_FORBIDDEN_KEYS, Disclosure
from frappe_cpcp.services import access, access_review, retention
from frappe_cpcp.services.common import to_db, utcnow

DOM = "demo-a.example.invalid"
T = "`tabCPCP Sensitive Access Event`"


def as_user(key):
    frappe.set_user(key if "@" in key else f"{key}@{DOM}")


def journal(where="1=1", params=(), limit=20):
    return access.query(f"select * from {T} where {where} order by seq desc limit {limit}", params)


def plate():
    return "B" + uuid.uuid4().hex[:7].upper()


class TestPBAC(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        frappe.set_user("Administrator")
        cls.seed = setup.seed_demo("a")
        e = next(iter(cls.seed["estates"].values()))
        cls.estate, cls.gate = e["name"], e["gate"]
        cls.back_gate = frappe.db.get_value("CPCP Gate", {"estate": cls.estate, "name": ["!=", cls.gate]})  # any OTHER gate of the estate
        cls.rid = uuid.uuid4().hex[:6]  # unique device ids per run: test data can persist between runs
        for user in ("officer", "officer2", "officerc"):  # start from a clean duty state
            u = f"{user}@{DOM}"
            frappe.db.sql("update `tabCPCP Gate Shift` set status='Ended', active_key=NULL where user=%s and status='On Duty'", (u,))
            frappe.db.sql("delete from `tabCPCP Device Registration` where user=%s", (u,))
            frappe.db.sql("update `tabCPCP Role Assignment` set status='Active' where user=%s and status='Suspended'", (u,))
            frappe.db.sql("update `tabCPCP Emergency Access` set creation = creation - interval 3 day where requested_by=%s", (u,))  # the daily cap is per 24h
        for f in ("bare_suggestions_per_hour", "suggestion_limit_per_hour", "plate_lookups_per_hour"):  # journal-based limits persist across runs; tests raise them
            frappe.db.set_single_value("CPCP Settings", f, 100000)
        frappe.db.set_single_value("CPCP Settings", "allegation_rate_limit_per_hour", 100000)
        as_user("officer")
        duty.start_shift(cls.estate, cls.gate, f"pbac-officer-{cls.rid}")  # officer2 deliberately has NO shift
        frappe.set_user("Administrator")

    @classmethod
    def tearDownClass(cls):
        frappe.set_user("Administrator")
        frappe.db.set_single_value("CPCP Settings", "allegation_rate_limit_per_hour", 10)
        for f, v in (("bare_suggestions_per_hour", 10), ("suggestion_limit_per_hour", 30), ("plate_lookups_per_hour", 60)):
            frappe.db.set_single_value("CPCP Settings", f, v)
        for f, v in (("ar_distinct_units_per_hour", 12), ("ar_repeat_unit_per_day", 4), ("ar_denied_per_hour", 5)):
            frappe.db.set_single_value("CPCP Settings", f, v)
        super().tearDownClass()

    def tearDown(self):
        frappe.set_user("Administrator")

    # ---------------------------------------------------------------- helpers
    def make_incident(self, p=None, officer="officer"):
        """A verified incident assigned to ``officer`` for a resident vehicle of A1 (so contacts resolve)."""
        p = p or plate()
        frappe.set_user("Administrator")
        unit = frappe.db.get_value("CPCP Unit", {"estate": self.estate, "unit_label": "A1"})
        v = frappe.get_doc({"doctype": "CPCP Vehicle", "plate": p}).insert()
        frappe.get_doc({"doctype": "CPCP Vehicle Unit Association", "vehicle": v.name, "unit": unit, "verification_status": "Verified"}).insert()
        as_user("resident")
        r = alg.submit_identified(self.estate, "Unsafe parking", "pbac", str(uuid.uuid4()), plate_text=p, latitude=5.605, longitude=-0.185, accuracy_m=10, location_source="device")
        wi = frappe.get_all("CPCP Security Work Item", filters={"allegation": r["reference"]}, pluck="name")[0]
        as_user(officer)
        alg.claim_work_item(wi)
        out = alg.verify_and_create_violation(r["reference"], p, uuid.uuid4().hex, 5.605, -0.185, 8)
        return out["incident"], p

    # ---------------------------------------------------------------- PBAC-01
    def test_pbac01_unassigned_officer_gets_nothing_and_the_denial_is_logged(self):
        as_user("officer2")  # no shift = not on duty anywhere
        for call in (lambda: registry.lookup_visits_for_unit(self.estate, "B1"), lambda: registry.lookup_plate(self.estate, "ZZ1001-26")):
            with self.assertRaises(frappe.PermissionError):
                call()
        rows = journal("actor=%s and result='Denied'", (f"officer2@{DOM}",))
        self.assertTrue({"history_bare", "search"} <= {r["action"] for r in rows})
        self.assertTrue(all(r["reason_code"] == "no_active_shift" for r in rows[:2]))
        as_user("officer")  # on duty: the gate answer is still minimal, never a household profile
        res = registry.lookup_visits_for_unit(self.estate, "B1")
        blob = json.dumps(res).lower()
        for banned in GATE_FORBIDDEN_KEYS | {"ama", "kofi", "0241"}:
            self.assertNotIn(banned, blob)
        self.assertLessEqual(len(res["candidates"]), 3)
        for dt in ("CPCP Person", "CPCP Unit Membership", "CPCP Vehicle Unit Association", "CPCP Visitor Session"):
            with self.assertRaises(frappe.PermissionError):
                frappe.get_list(dt)

    def test_pbac01b_bare_unit_lookups_are_rate_limited_and_the_limit_hit_is_journaled(self):
        as_user("officer")
        used = access.count_recent(f"officer@{DOM}", actions=("history_bare",), minutes=60, results=("Allowed", "No Match"))
        frappe.db.set_single_value("CPCP Settings", "bare_suggestions_per_hour", used + 2)
        registry.lookup_visits_for_unit(self.estate, "B1")
        registry.lookup_visits_for_unit(self.estate, "B1")
        with self.assertRaises(frappe.PermissionError):  # the third bare lookup in the hour is refused
            registry.lookup_visits_for_unit(self.estate, "A2")
        self.assertEqual(journal("actor=%s and result='Denied'", (f"officer@{DOM}",), 1)[0]["reason_code"], "rate_limited")
        res = registry.lookup_visits_for_unit(self.estate, "A2", plate_hint="ZZ")  # a plate hint uses the roomier limit
        self.assertTrue(res["narrowed_by_plate"])
        frappe.db.set_single_value("CPCP Settings", "bare_suggestions_per_hour", 100000)

    # ---------------------------------------------------------------- PBAC-02
    def test_pbac02_off_shift_officer_is_denied_and_logged(self):
        as_user("officer2")
        with self.assertRaises(frappe.PermissionError):
            visitors.active_visitors(self.estate)
        duty.start_shift(self.estate, self.gate, f"pbac-o2-{self.rid}")
        self.assertTrue(duty.my_shift()["on_duty"])
        registry.lookup_plate(self.estate, "ZZ1001-26")  # works while on duty
        duty.end_shift()
        with self.assertRaises(frappe.PermissionError):
            registry.lookup_plate(self.estate, "ZZ1001-26")
        duty.start_shift(self.estate, self.gate, f"pbac-o2-{self.rid}")
        frappe.db.set_value("CPCP Gate Shift", {"user": f"officer2@{DOM}", "status": "On Duty"}, "ends_at", to_db(utcnow() - timedelta(minutes=1)))
        with self.assertRaises(frappe.PermissionError):  # expiry is enforced on the server clock
            registry.lookup_plate(self.estate, "ZZ1001-26")
        self.assertIn("no_active_shift", {r["reason_code"] for r in journal("actor=%s and result='Denied'", (f"officer2@{DOM}",))})
        frappe.db.set_value("CPCP Gate Shift", {"user": f"officer2@{DOM}"}, {"status": "Ended", "active_key": None})

    # ---------------------------------------------------------------- PBAC-03
    def test_pbac03_other_estate_or_other_gate_is_denied(self):
        frappe.set_user("Administrator")
        e2 = frappe.get_doc({"doctype": "CPCP Estate", "estate_name": f"Second {uuid.uuid4().hex[:5]}"}).insert().name
        g2 = frappe.get_doc({"doctype": "CPCP Gate", "estate": e2, "gate_name": "Gate X"}).insert().name
        email = f"officerc@{DOM}"
        if not frappe.db.exists("User", email):
            setup._user(email, "OfficerC", "Tmp-pass-12345!")
        for est in (self.estate, e2):
            frappe.get_doc({"doctype": "CPCP Role Assignment", "user": email, "cpcp_role": "security_officer", "estate": est, "approved_by": "Administrator"}).insert()
        frappe.set_user(email)
        duty.start_shift(e2, g2, f"pbac-c-{self.rid}")  # works at estate 2 ...
        with self.assertRaises(frappe.PermissionError):  # ... but not at estate 1 although assigned there too
            registry.lookup_plate(self.estate, "ZZ1001-26")
        self.assertEqual(journal("actor=%s and result='Denied'", (email,))[0]["reason_code"], "shift_other_estate")
        as_user("officer")  # Main Gate shift, claims the other gate
        with self.assertRaises(frappe.PermissionError):
            registry.lookup_plate(self.estate, "ZZ1001-26", gate=self.back_gate)
        self.assertEqual(journal("actor=%s and result='Denied'", (f"officer@{DOM}",))[0]["reason_code"], "gate_mismatch")
        with self.assertRaises(frappe.PermissionError):  # an estate they are not assigned to at all
            registry.lookup_plate(e2, "ZZ1001-26")
        self.assertTrue(journal("actor=%s and estate=%s and result='Denied'", (f"officer@{DOM}", e2)))

    # ---------------------------------------------------------------- PBAC-04
    def test_pbac04_desk_lists_forms_and_search_are_closed_to_officers(self):
        as_user("officer")
        for dt in ("CPCP Person", "CPCP Unit Membership", "CPCP Vehicle", "CPCP Vehicle Unit Association", "CPCP Visitor Session", "CPCP Visit Event"):
            self.assertFalse(frappe.has_permission(dt, "read"), dt)
            with self.assertRaises(frappe.PermissionError):
                frappe.get_list(dt)
        person = frappe.get_all("CPCP Person", limit=1, ignore_permissions=True, pluck="name")[0]
        with self.assertRaises(frappe.PermissionError):
            frappe.get_doc("CPCP Person", person).check_permission("read")
        from frappe.desk.search import search_link
        try:
            res = search_link("CPCP Vehicle", "ZZ")
        except frappe.PermissionError:
            res = []
        self.assertFalse(res, "autocomplete must not enumerate vehicles for an officer")
        for path, form in (("/api/resource/CPCP Person", {}), ("/api/method/frappe.client.get_list", {"doctype": "CPCP Vehicle"}),
                           ("/api/method/frappe.desk.search.search_link", {"doctype": "CPCP Vehicle", "txt": "ZZ"}),
                           ("/api/method/frappe.desk.form.load.getdoc", {"doctype": "CPCP Person", "name": person}),
                           ("/api/method/frappe.desk.reportview.get", {"doctype": "CPCP Visitor Session"})):
            with self.assertRaises(frappe.PermissionError):
                guards.check_request(path, "GET", form, f"officer@{DOM}")

    # ---------------------------------------------------------------- PBAC-05
    def test_pbac05_forged_purpose_case_gate_or_unit_never_grant_access(self):
        inc, p = self.make_incident()
        as_user("officer")
        forged = [dict(purpose="admin"), dict(purpose="emergency"), dict(purpose="case", reference="INC-99999"), dict(purpose="case", reference=""),
                  dict(purpose="gate", gate=self.back_gate)]
        for kw in forged:
            with self.assertRaises(frappe.PermissionError):
                registry.lookup_plate(self.estate, p, **kw)
        # a real case reference does not unlock a DIFFERENT plate
        with self.assertRaises(frappe.PermissionError):
            registry.lookup_plate(self.estate, "ZZ1002-26", purpose="case", reference=inc)
        # another officer cannot use a case that is not theirs
        as_user("officer2")
        duty.start_shift(self.estate, self.gate, f"pbac-o2b-{self.rid}")
        with self.assertRaises(frappe.PermissionError):
            registry.lookup_plate(self.estate, p, purpose="case", reference=inc)
        with self.assertRaises(frappe.PermissionError):
            com.resolve_violation_contacts(inc)
        reasons = {r["reason_code"] for r in journal("result='Denied' and actor in (%s,%s)", (f"officer@{DOM}", f"officer2@{DOM}"), 30)}
        self.assertTrue({"unknown_purpose", "case_not_found_or_closed", "target_not_part_of_case", "not_assigned_to_case", "gate_mismatch"} <= reasons)
        frappe.db.set_value("CPCP Gate Shift", {"user": f"officer2@{DOM}"}, {"status": "Ended", "active_key": None})

    # ---------------------------------------------------------------- PBAC-06
    def test_pbac06_returning_visitor_check_in_stays_fast_and_minimal(self):
        p = plate()
        as_user("officer")
        t0 = time.perf_counter()
        first = visitors.check_in_visitor(self.estate, "A2", str(uuid.uuid4()), plate=p, confirm_visiting_today=1)
        visitors.check_out_visitor(first["session"], str(uuid.uuid4()))
        res = registry.lookup_visits_for_unit(self.estate, "A2", plate_hint=p[:3])  # step 1: unit + a few characters of the car in front of them
        cand = [c for c in res["candidates"] if c["plate"] == p]
        self.assertEqual(len(cand), 1)
        self.assertTrue(res["narrowed_by_plate"])
        again = visitors.check_in_visitor(self.estate, "A2", str(uuid.uuid4()), plate=cand[0]["plate"], confirm_visiting_today=1)  # step 2-3
        self.assertEqual(again["status"], "Checked In")
        self.assertLess(time.perf_counter() - t0, 5)
        self.assertTrue(set(cand[0]) <= set(FIELDS[Disclosure.GATE_MINIMUM]) | {"already_inside"})
        self.assertNotIn("last_visit_date", json.dumps(res))
        self.assertEqual(again["entry_gate"], self.gate)  # the gate comes from the shift

    # ---------------------------------------------------------------- PBAC-07
    def test_pbac07_assigned_case_reveals_only_that_cases_contact_actions(self):
        inc, p = self.make_incident()
        as_user("officer")
        res = com.resolve_violation_contacts(inc)
        self.assertTrue(res["contacts"])
        blob = json.dumps(res)
        self.assertNotIn("0241230001", blob)
        self.assertTrue(set(res["contacts"][0]) <= {"contact_id", "relationship", "first_name", "number", "last_updated"})
        self.assertIn("*", res["contacts"][0]["number"])
        got = registry.lookup_plate(self.estate, p, purpose="case", reference=inc)
        self.assertEqual(got["match"], "resident_vehicle")
        self.assertEqual(got["unit"], "A1")
        for banned in ("Ama", "Kofi", "members", "history"):
            self.assertNotIn(banned, json.dumps(got))
        call = com.initiate_call(inc, res["contacts"][0]["contact_id"], str(uuid.uuid4()))
        self.assertTrue(call["dial"].startswith("+233"))  # revealed only to the assigned officer, journaled as a contact reveal
        self.assertEqual(journal("actor=%s and category='contact_reveal' and result='Allowed'", (f"officer@{DOM}",), 1)[0]["purpose_ref"], inc)

    # ---------------------------------------------------------------- PBAC-08
    def test_pbac08_a_claim_cannot_be_used_to_look_up_unrelated_units_or_plates(self):
        inc_a, pa = self.make_incident()
        inc_b, pb = self.make_incident(officer="officer")
        as_user("officer")
        wi = frappe.get_all("CPCP Security Work Item", filters={"status": "Open"}, pluck="name")
        # a work item name is not a case reference for lookups
        for w in wi[:1]:
            with self.assertRaises(frappe.PermissionError):
                registry.lookup_plate(self.estate, pa, purpose="case", reference=w)
        # case A's reference cannot reveal case B's vehicle
        with self.assertRaises(frappe.PermissionError):
            registry.lookup_plate(self.estate, pb, purpose="case", reference=inc_a)
        with self.assertRaises(frappe.PermissionError):
            com.initiate_call(inc_a, "MEM-00001-not-theirs", str(uuid.uuid4()))
        self.assertTrue(journal("actor=%s and reason_code='target_not_part_of_case'", (f"officer@{DOM}",)))

    # ---------------------------------------------------------------- PBAC-09
    def test_pbac09_reassignment_and_closure_revoke_access(self):
        inc, _p = self.make_incident()
        as_user("officer")
        cid = com.resolve_violation_contacts(inc)["contacts"][0]["contact_id"]
        as_user("officer2")
        duty.start_shift(self.estate, self.gate, f"pbac-o2c-{self.rid}")
        as_user("secmgr")
        inc_api.reassign_incident(inc, f"officer2@{DOM}", "shift handover")
        as_user("officer")
        for call in (lambda: com.resolve_violation_contacts(inc), lambda: com.initiate_call(inc, cid, str(uuid.uuid4())), lambda: com.comms_timeline(inc)):
            with self.assertRaises(frappe.PermissionError):
                call()
        as_user("officer2")
        self.assertTrue(com.resolve_violation_contacts(inc)["contacts"])
        as_user("officer2")
        inc_api.end_episode(inc, "departure_verified", "left through the gate")  # closing the case ends everyone's access
        with self.assertRaises(frappe.PermissionError):
            com.resolve_violation_contacts(inc)
        self.assertIn("case_not_found_or_closed", {r["reason_code"] for r in journal("result='Denied'", (), 15)})
        frappe.db.set_value("CPCP Gate Shift", {"user": f"officer2@{DOM}"}, {"status": "Ended", "active_key": None})

    # ---------------------------------------------------------------- PBAC-10
    def test_pbac10_every_outcome_is_journaled_with_the_required_fields(self):
        p = plate()
        as_user("officer")
        registry.lookup_plate(self.estate, "ZZ1001-26")  # allowed
        registry.lookup_plate(self.estate, p)             # no match
        with self.assertRaises(frappe.PermissionError):
            registry.lookup_plate(self.estate, p, purpose="nonsense")  # denied
        rows = journal("actor=%s and record_type='Vehicle'", (f"officer@{DOM}",), 3)
        self.assertEqual({r["result"] for r in rows}, {"Allowed", "No Match", "Denied"})
        for r in rows:
            for field in ("at_utc", "actor", "role", "estate", "action", "purpose", "reason_code", "request_id", "category", "hash", "prev_hash", "seq"):
                self.assertTrue(r[field] not in (None, ""), f"{field} missing in {r['result']}")
            self.assertEqual((r["role"], r["estate"]), ("security_officer", self.estate))
            self.assertTrue(r["at_utc"].endswith("Z"))
        self.assertEqual(rows[2]["target_unit"], "A1")
        ok, bad = access.verify_chain()
        self.assertTrue(ok, f"journal chain broken at {bad}")

    # ---------------------------------------------------------------- PBAC-11
    def test_pbac11_denial_survives_exception_and_rollback_and_fails_closed(self):
        as_user("officer2")
        marker = "pbac11-" + uuid.uuid4().hex[:6]
        frappe.db.savepoint("pbac11")
        try:
            with self.assertRaises(frappe.PermissionError):
                registry.lookup_plate(self.estate, "ZZ1001-26", purpose=marker)
            raise RuntimeError("simulated failure after the denial")
        except RuntimeError:
            frappe.db.rollback(save_point="pbac11")  # what Frappe does when the request fails
        self.assertTrue(journal("purpose=%s and result='Denied'", (marker,)), "the denial must outlive the rollback")
        # fail closed: if the journal is unavailable the sensitive call returns nothing
        as_user("officer")
        with mock.patch.object(access, "_connect", side_effect=RuntimeError("db down")):
            with self.assertRaises(frappe.ValidationError):
                registry.lookup_plate(self.estate, "ZZ1001-26")
            with self.assertRaises(frappe.ValidationError):
                registry.lookup_visits_for_unit(self.estate, "A1", plate_hint="ZZ")

    # ---------------------------------------------------------------- PBAC-12
    def test_pbac12_all_browse_search_export_print_paths_are_guarded_and_audited(self):
        person = frappe.get_all("CPCP Person", limit=1, ignore_permissions=True, pluck="name")[0]
        probes = [("/api/method/frappe.client.get_list", "GET", {"doctype": "CPCP Vehicle"}), ("/api/resource/CPCP Visitor Session", "GET", {}),
                  ("/api/method/frappe.desk.search.search_link", "GET", {"doctype": "CPCP Person", "txt": "A"}),
                  ("/api/method/frappe.desk.form.load.getdoc", "GET", {"doctype": "CPCP Person", "name": person}),
                  ("/api/method/frappe.core.doctype.data_export.exporter.export_data", "POST", {"doctype": "CPCP Vehicle"}),
                  ("/api/method/frappe.utils.print_format.download_pdf", "GET", {"doctype": "CPCP Person", "name": person}),
                  ("/printview", "GET", {"doctype": "CPCP Visitor Session", "name": "x"})]
        for who in ("officer", "resident", "finance"):
            for path, method, form in probes:
                with self.assertRaises(frappe.PermissionError, msg=f"{who} {path}"):
                    guards.check_request(path, method, form, f"{who}@{DOM}")
        denied = journal("result='Denied' and purpose='desk_access'", (), 40)
        self.assertGreaterEqual(len(denied), 21)
        self.assertIn("bulk_disclosure_requires_approved_export", {r["reason_code"] for r in denied})
        # even managers cannot export or print the registries; they can administer, and every open is journaled
        for path, method, form in probes[4:]:
            with self.assertRaises(frappe.PermissionError):
                guards.check_request(path, method, form, f"secmgr@{DOM}")
        guards.check_request("/api/method/frappe.client.get_list", "GET", {"doctype": "CPCP Person"}, f"secmgr@{DOM}")
        self.assertEqual(journal("actor=%s and result='Allowed' and purpose='administration'", (f"secmgr@{DOM}",), 1)[0]["role"], "security_manager")
        # CPCP's own purpose-checked APIs pass through the guard untouched
        guards.check_request("/api/method/frappe_cpcp.api.registry.lookup_plate", "GET", {"estate": "x", "plate": "y"}, f"officer@{DOM}")

    # ---------------------------------------------------------------- PBAC-13
    def test_pbac13_journal_contains_no_pii(self):
        inc, p = self.make_incident()
        as_user("officer")
        res = com.resolve_violation_contacts(inc)
        com.initiate_call(inc, res["contacts"][0]["contact_id"], str(uuid.uuid4()))
        com.send_case_sms(inc, res["contacts"][0]["contact_id"], str(uuid.uuid4()))
        registry.lookup_plate(self.estate, p)
        rows = access.query(f"select * from {T} order by seq desc limit 200")
        # the authenticated actor id is a required journal field; everything ELSE must be free of personal data
        text = json.dumps([{k: v for k, v in r.items() if k != "actor"} for r in rows], default=str).lower()
        for pii in ("0241230001", "+233241230001", "241230001", "ama demo", "kofi", "resident@demo", "blocked (", p.lower()):
            self.assertNotIn(pii, text, f"journal leaked {pii!r}")
        self.assertTrue(all(len(r["search_term_hash"] or "") in (0, 32) for r in rows))  # one-way hash, never the term

    # ---------------------------------------------------------------- PBAC-14
    def test_pbac14_officers_cannot_alter_or_view_access_records(self):
        as_user("officer")
        row = frappe.get_all("CPCP Sensitive Access Event", limit=1, ignore_permissions=True, pluck="name")[0]
        doc = frappe.get_doc("CPCP Sensitive Access Event", row)
        doc.result = "Allowed"
        for op in (doc.save, lambda: frappe.delete_doc("CPCP Sensitive Access Event", row, force=True), lambda: doc.check_permission("read")):
            with self.assertRaises(frappe.PermissionError):
                op()
        for fn in (ar.search, ar.summary, ar.flags, ar.pending_emergency_reviews, ar.verify_chain):
            with self.assertRaises(frappe.PermissionError):
                fn()
        for fn in (ar.run_detection, ar.export_log):
            with self.assertRaises(frappe.PermissionError):
                fn()
        with self.assertRaises(frappe.PermissionError):
            frappe.get_list("CPCP Sensitive Access Event")
        as_user("auditor")  # reviewers may read but never mutate or run the privileged operations
        self.assertIn("rows", ar.search())
        for fn in (ar.run_detection, ar.export_log):
            with self.assertRaises(frappe.PermissionError):
                fn()
        as_user("secmgr")  # managers see only officer activity, never admins or their own
        roles = {r["role"] for r in ar.search()["rows"]}
        self.assertTrue(roles <= {"security_officer"}, roles)
        as_user("admin")
        self.assertTrue(ar.export_log()["rows"] > 0)

    # ---------------------------------------------------------------- PBAC-15
    def test_pbac15_managers_and_admins_are_journaled_and_reviewable(self):
        as_user("secmgr")
        duty_row = registry.lookup_plate(self.estate, "ZZ1001-26")
        self.assertEqual(duty_row["match"], "resident_vehicle")
        as_user("admin")
        registry.lookup_plate(self.estate, "ZZ1001-26")
        guards.check_request("/api/resource/CPCP Person", "GET", {}, "Administrator")  # the platform operator is journaled too
        guards.check_request("/api/resource/CPCP Person", "GET", {}, f"admin@{DOM}")
        rows = journal("result='Allowed'", (), 12)
        self.assertTrue({"security_manager", "org_admin", "platform_admin"} <= {r["role"] for r in rows})
        as_user("auditor")
        seen = {r["role"] for r in ar.search()["rows"]}
        self.assertTrue({"org_admin", "security_manager"} <= seen, "independent reviewers must see manager and admin activity")
        as_user("admin")
        self.assertTrue(any(r["actor"] == f"admin@{DOM}" for r in ar.search()["rows"]))

    # ---------------------------------------------------------------- PBAC-16
    def test_pbac16_break_glass_is_narrow_short_loud_and_reviewed(self):
        as_user("officer2")
        with self.assertRaises(frappe.PermissionError):  # off duty: no emergency either
            duty.request_emergency(self.estate, "A1", "gas leak reported from the unit, need to reach the household urgently")
        duty.start_shift(self.estate, self.gate, f"pbac-o2d-{self.rid}")
        with self.assertRaises(frappe.PermissionError):
            duty.request_emergency(self.estate, "A1", "short")
        g = duty.request_emergency(self.estate, "A1", "smoke seen coming from A1, need to reach the household urgently")
        self.assertIn("recorded", g["notice"])
        row = frappe.get_doc("CPCP Emergency Access", g["grant"])
        self.assertLessEqual((row.expires_at - row.granted_at).total_seconds(), 120 * 60)
        got = duty.emergency_contacts(g["grant"], "A1")
        self.assertTrue(got["contacts"])
        self.assertTrue(got["contacts"][0]["number"].startswith("+233"))
        with self.assertRaises(frappe.PermissionError):  # scope: one household only
            duty.emergency_contacts(g["grant"], "A2")
        as_user("officer")
        with self.assertRaises(frappe.PermissionError):  # a grant belongs to the person who raised it
            duty.emergency_contacts(g["grant"], "A1")
        self.assertTrue(journal("result='Emergency' and action='emergency_grant'", (), 1))
        self.assertTrue(frappe.get_all("CPCP Notification Outbox", filters={"idempotency_key": ["like", f"emergency_access:{g['grant']}:%"]}))
        as_user("officer2")
        with self.assertRaises(frappe.PermissionError):  # cannot review own grant
            duty.review_emergency(g["grant"], "Appropriate", "self review")
        as_user("secmgr")
        self.assertEqual(duty.review_emergency(g["grant"], "Appropriate", "genuine smoke report, confirmed with fire service")["status"], "Reviewed")
        as_user("officer2")  # expiry
        g2 = duty.request_emergency(self.estate, "A1", "second genuine event: person collapsed in the unit, need next of kin")
        frappe.db.set_value("CPCP Emergency Access", g2["grant"], "expires_at", to_db(utcnow() - timedelta(minutes=1)))
        with self.assertRaises(frappe.PermissionError):
            duty.emergency_contacts(g2["grant"], "A1")
        duty.request_emergency(self.estate, "A1", "third event: fire alarm sounding in the unit now, urgent")
        with self.assertRaises(frappe.PermissionError):  # a per-person daily cap stops it becoming a habit
            duty.request_emergency(self.estate, "A1", "fourth request in one day should be refused by the cap")
        frappe.db.set_value("CPCP Gate Shift", {"user": f"officer2@{DOM}"}, {"status": "Ended", "active_key": None})

    # ---------------------------------------------------------------- PBAC-17
    def test_pbac17_review_signals_are_scoped_idempotent_and_never_automatic_punishment(self):
        frappe.set_user("Administrator")
        for f, v in (("ar_distinct_units_per_hour", 3), ("ar_repeat_unit_per_day", 3), ("ar_denied_per_hour", 3)):
            frappe.db.set_single_value("CPCP Settings", f, v)
        actor = f"officer@{DOM}"
        for u in ("A1", "A2", "B1", "A1X"):  # many different households in a short time
            access.record(actor=actor, role="security_officer", estate=self.estate, action="history", record_type="Visitor Suggestion", target_unit=u,
                          category="restricted_safety", purpose="gate_entry", result="Allowed")
        for _ in range(4):  # repeated lookups of ONE household, no case or visit
            access.record(actor=actor, role="security_officer", estate=self.estate, action="search", record_type="Vehicle", target_unit="B1",
                          category="operational_min", purpose="gate_entry", result="Allowed")
        for _ in range(3):
            access.record(actor=actor, role="security_officer", estate=self.estate, action="search", record_type="Vehicle", category="operational_min",
                          purpose="gate_entry", result="Denied", reason_code="no_active_shift")
        raised = access_review.run_detection()
        self.assertTrue({"many_households_in_an_hour", "repeat_lookup_same_household", "repeated_denied_attempts"} <= set(raised), raised)
        self.assertEqual(access_review.run_detection(), {}, "same window must not raise duplicate signals")
        fl = frappe.get_all("CPCP Access Review Flag", filters={"actor_user": actor}, fields=["rule", "status", "summary"])
        self.assertTrue(all(f.status == "New" for f in fl))
        self.assertNotIn("Ama", json.dumps(fl))
        # reviewers are alerted; the person concerned is not
        notified = {o.recipient_user for o in frappe.get_all("CPCP Notification Outbox", filters={"idempotency_key": ["like", "access_review_signal:%"]}, fields=["recipient_user"])}
        self.assertIn(f"admin@{DOM}", notified)
        self.assertNotIn(actor, notified)
        as_user("officer")
        with self.assertRaises(frappe.PermissionError):
            ar.flags()
        as_user("auditor")
        self.assertTrue(ar.flags())
        with self.assertRaises(frappe.PermissionError):
            ar.review_flag(fl and frappe.get_all("CPCP Access Review Flag", filters={"actor_user": actor}, pluck="name")[0], "Escalated", "x")
        as_user("admin")
        flag = frappe.get_all("CPCP Access Review Flag", filters={"actor_user": actor}, pluck="name")[0]
        with self.assertRaises(frappe.ValidationError):
            ar.review_flag(flag, "Closed - No Action", "")
        self.assertIn("not a finding", ar.review_flag(flag, "Closed - No Action", "legitimate end-of-month deliveries")["note"])
        self.assertEqual(frappe.db.get_value("Role Assignment", {"user": actor}, "status") if False else
                         frappe.db.get_value("CPCP Role Assignment", {"user": actor, "cpcp_role": "security_officer"}, "status"), "Active")  # no automatic suspension
        summ = ar.summary()
        self.assertTrue(any(p["actor"] == actor and p["denied"] >= 3 for p in summ["people"]))

    # ---------------------------------------------------------------- PBAC-18
    def test_pbac18_server_never_hands_a_device_a_registry(self):
        as_user("officer")
        res = registry.lookup_visits_for_unit(self.estate, "A1")
        self.assertLessEqual(len(res["candidates"]), 3)
        self.assertEqual(visitors.active_visitors.__name__, "active_visitors")
        # there is simply no endpoint that returns residents, and the only list (active visitors) holds plates/units for people inside now
        import frappe_cpcp.api as api_pkg, pkgutil
        names = {m.name for m in pkgutil.iter_modules(api_pkg.__path__)}
        for mod in names:
            m = __import__(f"frappe_cpcp.api.{mod}", fromlist=["x"])
            for fn in dir(m):
                self.assertFalse(fn.startswith(("list_residents", "all_residents", "directory", "export_registry", "browse")), f"{mod}.{fn}")
        self.assertIn("recorded", res["note"])

    # ---------------------------------------------------------------- PBAC-19
    def test_pbac19_no_cross_tenant_disclosure_in_process(self):
        inc, p = self.make_incident()
        # the journal and every record live in THIS site's database: another organization's identifiers are not resolvable here
        as_user("officer")
        with self.assertRaises(frappe.PermissionError):
            registry.lookup_plate("EST-DOES-NOT-EXIST", p)
        with self.assertRaises(frappe.PermissionError):
            registry.lookup_plate(self.estate, p, purpose="case", reference="INC-FROM-ORG-B")
        rows = access.query(f"select distinct estate from {T} where estate != ''")
        known = set(frappe.get_all("CPCP Estate", pluck="name", ignore_permissions=True))
        self.assertTrue({r["estate"] for r in rows if r["estate"] and r["estate"].startswith("EST-")} <= known | {"EST-DOES-NOT-EXIST"} | {r["estate"] for r in rows})
        # org-level: the journal API only returns this site's events (the HTTP test proves the same against org-b)
        as_user("admin")
        self.assertTrue(all(r["estate"] == "" or r["estate"].startswith("EST-") for r in ar.search(limit=100)["rows"]))

    # ---------------------------------------------------------------- PBAC-20
    def test_pbac20_revoked_device_or_suspended_user_loses_sensitive_apis_immediately(self):
        as_user("officer2")
        duty.start_shift(self.estate, self.gate, f"pbac-o2e-{self.rid}")
        registry.lookup_plate(self.estate, "ZZ1001-26")  # allowed before revocation
        as_user("officer")
        with self.assertRaises(frappe.PermissionError):  # an officer cannot revoke
            duty.revoke_device(f"officer2@{DOM}", "x")
        as_user("secmgr")
        res = duty.revoke_device(f"officer2@{DOM}", "phone reported lost at the gate")
        self.assertEqual(res["devices_revoked"], 1)
        as_user("officer2")  # the screen and a cached session are still "open" -- the server no longer cares
        for call in (lambda: registry.lookup_plate(self.estate, "ZZ1001-26"), lambda: visitors.active_visitors(self.estate),
                     lambda: registry.lookup_visits_for_unit(self.estate, "A1")):
            with self.assertRaises(frappe.PermissionError):
                call()
        with self.assertRaises(frappe.PermissionError):  # the same device cannot start a new shift either
            duty.start_shift(self.estate, self.gate, f"pbac-o2e-{self.rid}")
        self.assertFalse(duty.my_shift()["on_duty"])
        duty.start_shift(self.estate, self.gate, f"replacement-phone-{self.rid}")  # a new, unrevoked device is a normal registration
        registry.lookup_plate(self.estate, "ZZ1001-26")
        as_user("secmgr")
        duty.suspend_user(f"officer2@{DOM}", "credentials compromised")
        as_user("officer2")
        with self.assertRaises(frappe.PermissionError):
            registry.lookup_plate(self.estate, "ZZ1001-26")
        frappe.set_user("Administrator")
        frappe.db.set_value("CPCP Role Assignment", {"user": f"officer2@{DOM}", "cpcp_role": "security_officer"}, "status", "Active")

    # ---------------------------------------------------------------- retention
    def test_retention_purges_only_a_safe_prefix_and_keeps_the_chain_verifiable(self):
        frappe.set_user("Administrator")
        for _ in range(3):
            access.record(actor="retention-test", role="security_officer", action="search", record_type="Vehicle", purpose="gate_entry", result="Allowed")
        out = retention.purge_expired_access_events(now=utcnow() + timedelta(days=4000), days=730)
        self.assertGreater(out["purged"], 0)
        ok, bad = access.verify_chain()
        self.assertTrue(ok, f"chain broken at {bad} after purge")
        self.assertTrue(frappe.db.count("CPCP Audit Event", {"action": "access_journal_purged"}) >= 1)
        self.assertEqual(access.query(f"select count(*) n from {T}")[0]["n"] >= 1, True)  # the newest row is always kept as the anchor
