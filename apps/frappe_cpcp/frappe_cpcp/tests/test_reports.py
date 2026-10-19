# SPDX-License-Identifier: Apache-2.0
"""Dashboards, hotspots, community summaries and operational reads (AC-12, AC-13, AC-50)."""
import json
import uuid

import frappe
from frappe.tests.utils import FrappeTestCase

from frappe_cpcp import setup
from frappe_cpcp.api import allegations as alg
from frappe_cpcp.api import ops, reports

DOM = "demo-a.example.invalid"


def as_user(key):
    frappe.set_user(f"{key}@{DOM}")


class TestReports(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        frappe.set_user("Administrator")
        frappe.db.sql("delete from `tabCPCP Role Assignment` where user in (%s, %s)", (f"finance@{DOM}", f"auditor@{DOM}"))
        cls.seed = setup.seed_demo("a")
        cls.estate = next(iter(cls.seed["estates"].values()))["name"]
        cls.gate = next(iter(cls.seed["estates"].values()))["gate"]
        from frappe_cpcp.api import duty
        for who in ("officer", "officer2"):  # PRD v1.8: gate work needs a live shift
            frappe.set_user(f"{who}@demo-a.example.invalid")
            duty.start_shift(cls.estate, cls.gate, f"test-device-{who}")
        frappe.set_user("Administrator")
        frappe.db.set_single_value("CPCP Settings", "allegation_rate_limit_per_hour", 10000)
        # a handful of verified incidents at varied pins plus one unverified allegation (AC-13 seed, scaled down)
        for i in range(6):
            as_user("resident")
            r = alg.submit_identified(cls.estate, "Unsafe parking", "seed", str(uuid.uuid4()), plate_text=f"H{i}{uuid.uuid4().hex[:5]}",
                                      latitude=5.601 + i * 0.001, longitude=-0.185, accuracy_m=10, location_source="device")
            wi = frappe.get_all("CPCP Security Work Item", filters={"allegation": r["reference"]}, pluck="name")[0]
            as_user("officer")
            alg.claim_work_item(wi)
            alg.verify_and_create_violation(r["reference"], f"HS{i}00{i}", uuid.uuid4().hex, 5.601 + i * 0.001, -0.185, 12)
        as_user("resident")
        alg.submit_identified(cls.estate, "Gate or driveway blocked", "unverified one", str(uuid.uuid4()), latitude=5.608, longitude=-0.186, accuracy_m=30, location_source="manual_pin")

    @classmethod
    def tearDownClass(cls):
        frappe.set_user("Administrator")
        frappe.db.set_single_value("CPCP Settings", "allegation_rate_limit_per_hour", 10)
        super().tearDownClass()

    def tearDown(self):
        frappe.set_user("Administrator")

    def test_dashboard_has_denominators_and_separates_allegations(self):
        as_user("secmgr")
        d = reports.dashboard(self.estate)
        self.assertGreaterEqual(d["allegations"]["submitted"], 7)
        self.assertGreaterEqual(d["verified_incidents"]["total"], 6)
        cr = d["allegations"]["conversion_rate"]
        self.assertEqual(cr["denominator"], d["allegations"]["submitted"])
        self.assertIn("unverified", d["allegations"]["note"].lower())
        self.assertNotIn("finance", d)  # security manager sees no money
        self.assertIn("caveat", d["visitors"])

    def test_finance_section_only_for_finance_and_admin(self):
        as_user("finance")
        self.assertIn("finance", reports.dashboard(self.estate))
        as_user("admin")
        self.assertIn("finance", reports.dashboard(self.estate))
        as_user("officer")
        self.assertNotIn("finance", reports.dashboard(self.estate))

    def test_hotspots_two_layers_with_accuracy_and_filters(self):
        as_user("secmgr")
        h = reports.hotspots(self.estate)
        self.assertGreaterEqual(len(h["verified_incidents"]["points"]), 6)
        self.assertGreaterEqual(len(h["allegations"]["points"]), 1)
        self.assertIn("UNVERIFIED", h["allegations"]["label"])
        p = h["verified_incidents"]["points"][0]
        self.assertIn(p["tier"], ("high", "approximate", "low - confirm location"))
        none = reports.hotspots(self.estate, classification="Emergency")
        self.assertEqual(none["verified_incidents"]["points"], [])
        self.assertTrue(reports.hotspots(self.estate, classification="Ordinary")["verified_incidents"]["points"])
        # no reporter identity anywhere in the map payloads
        blob = json.dumps(h)
        self.assertNotIn("resident@", blob)
        self.assertNotIn("reporter_user", blob)

    def test_resident_gets_only_thresholded_aggregates(self):
        as_user("resident")
        s = reports.community_summary(self.estate)
        blob = json.dumps(s)
        for forbidden in ("INC-", "HS", "lat", "plate", "resident@"):
            self.assertNotIn(forbidden, blob)
        for z in s["zones"]:  # either >= K or the suppression text; never a small exact count
            self.assertTrue(isinstance(z["count"], str) or z["count"] >= 5)
        with self.assertRaises(frappe.PermissionError):
            reports.hotspots(self.estate)
        with self.assertRaises(frappe.PermissionError):
            reports.dashboard(self.estate)

    def test_auditor_needs_grant_for_incident_maps(self):
        as_user("auditor")
        with self.assertRaises(frappe.PermissionError):
            reports.hotspots(self.estate)
        self.assertIn("allegations", reports.dashboard(self.estate))  # aggregate view only

    def test_estate_context_and_active_cases(self):
        as_user("officer")
        ctx = ops.estate_context()
        self.assertEqual(len(ctx), 1)
        self.assertTrue(ctx[0]["gates"])
        cases = ops.active_cases(self.estate)
        self.assertTrue(cases)
        inc = ops.incident_detail(cases[0]["incident"])
        self.assertEqual(inc["location"]["note"].startswith("Officer-confirmed"), True)
        as_user("resident")
        with self.assertRaises(frappe.PermissionError):
            ops.active_cases(self.estate)
        with self.assertRaises(frappe.PermissionError):
            ops.incident_detail(cases[0]["incident"])
