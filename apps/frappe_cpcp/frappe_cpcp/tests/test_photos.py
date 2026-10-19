# SPDX-License-Identifier: Apache-2.0
"""Resident photos: metadata stripped BEFORE persistence (AC-58), private storage, purpose-checked retrieval."""
import base64
import io
import json
import uuid

import frappe
from frappe.tests.utils import FrappeTestCase

from frappe_cpcp import setup
from frappe_cpcp.api import allegations as alg
from frappe_cpcp.api import duty
from frappe_cpcp.core import allegations as al
from frappe_cpcp.services import access, photos
from frappe_cpcp.services.common import utcnow

DOM = "demo-a.example.invalid"
SECRETS = (b"SecretMaker", b"SecretModel", b"Exif", b"GPS", b"2026:10:19", b"<script>", b"PhotoComment")


def as_user(k):
    frappe.set_user(f"{k}@{DOM}")


def exif_jpeg(extra: bytes = b"") -> bytes:
    from PIL import Image

    img = Image.new("RGB", (300, 200), (200, 30, 30))
    ex = Image.Exif()
    ex[0x010F], ex[0x0110], ex[0x0112], ex[0x0132] = "SecretMaker", "SecretModel", 6, "2026:10:19 10:00:00"  # make, model, orientation, timestamp
    gps = ex.get_ifd(0x8825)
    gps[1], gps[2], gps[3], gps[4] = "N", (5.0, 36.0, 18.0), "W", (0.0, 11.0, 6.0)
    buf = io.BytesIO()
    img.save(buf, "JPEG", exif=ex, comment=b"PhotoComment")
    return buf.getvalue() + extra


def b64(b: bytes) -> str:
    return base64.b64encode(b).decode()


class TestPhotos(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        frappe.set_user("Administrator")
        cls.seed = setup.seed_demo("a")
        e = next(iter(cls.seed["estates"].values()))
        cls.estate, cls.gate = e["name"], e["gate"]
        frappe.db.set_single_value("CPCP Settings", "allegation_rate_limit_per_hour", 100000)
        for who in ("officer", "officer2"):
            frappe.db.sql("update `tabCPCP Gate Shift` set status='Ended', active_key=NULL where user=%s and status='On Duty'", (f"{who}@{DOM}",))
        as_user("officer")
        duty.start_shift(cls.estate, cls.gate, "photo-" + uuid.uuid4().hex[:6])
        frappe.set_user("Administrator")

    @classmethod
    def tearDownClass(cls):
        frappe.set_user("Administrator")
        frappe.db.set_single_value("CPCP Settings", "allegation_rate_limit_per_hour", 10)
        super().tearDownClass()

    def tearDown(self):
        frappe.set_user("Administrator")

    def test_sanitize_removes_every_embedded_identifier(self):
        from PIL import Image

        raw = exif_jpeg(extra=b"<script>alert(1)</script>")
        self.assertTrue(any(s in raw for s in (b"SecretMaker", b"Exif")))  # the fixture really carries metadata
        clean, info = photos.sanitize(raw)
        for s in SECRETS:
            self.assertNotIn(s, clean, s)
        im = Image.open(io.BytesIO(clean))
        self.assertEqual(dict(im.getexif()), {})
        self.assertNotIn("exif", im.info)
        self.assertEqual(im.size, (200, 300))  # orientation was APPLIED, then the tag dropped
        self.assertEqual(info["width"], 200)
        self.assertEqual(len(info["sha256"]), 64)

    def test_png_with_alpha_and_hostile_inputs(self):
        from PIL import Image

        buf = io.BytesIO()
        Image.new("RGBA", (50, 50), (0, 0, 0, 0)).save(buf, "PNG")
        clean, _ = photos.sanitize(buf.getvalue())
        self.assertTrue(clean.startswith(b"\xff\xd8\xff"))  # always re-encoded as JPEG
        big = io.BytesIO()
        Image.new("RGB", (7000, 7000)).save(big, "PNG")
        with self.assertRaises(photos.PhotoError):
            photos.sanitize(big.getvalue())  # too many pixels (decompression-bomb guard)
        for bad in (b"hello", b"", b"GIF89a....", b"\xff\xd8\xff" + b"x" * 20):
            with self.assertRaises(photos.PhotoError):
                photos.sanitize(bad)
        with self.assertRaises(photos.PhotoError):
            photos.decode_list(json.dumps([b64(b"x")] * 4))  # at most three photos

    def test_identified_report_stores_only_clean_private_photos(self):
        as_user("resident")
        r = alg.submit_identified(self.estate, "Unsafe parking", "photo test", str(uuid.uuid4()),
                                  photos_base64=json.dumps([b64(exif_jpeg()), b64(exif_jpeg())]),
                                  latitude=5.605, longitude=-0.185, accuracy_m=10, location_source="device")
        atts = frappe.get_all("CPCP Allegation Attachment", filters={"allegation": r["reference"]}, fields=["name", "file_url", "sha256", "source_mode"])
        self.assertEqual(len(atts), 2)
        for a in atts:
            f = frappe.get_doc("File", {"file_url": a.file_url})
            self.assertEqual(f.is_private, 1)
            self.assertEqual(f.attached_to_doctype, "CPCP Allegation Attachment")
            data = f.get_content()
            data = data.encode("latin-1") if isinstance(data, str) else data
            for s in SECRETS:
                self.assertNotIn(s, data)
        n = frappe.db.count("CPCP Parking Allegation")
        with self.assertRaises(frappe.ValidationError):  # a bad photo fails the whole report BEFORE anything is written
            alg.submit_identified(self.estate, "Unsafe parking", "bad photo", str(uuid.uuid4()), photos_base64=json.dumps([b64(b"not an image")]))
        self.assertEqual(frappe.db.count("CPCP Parking Allegation"), n)

    def test_anonymous_report_photos_are_clean_and_unlinked(self):
        frappe.set_user("Administrator")
        code = al.community_code(frappe.conf.get("cpcp_anon_signing_key").encode(), self.estate, int(utcnow().timestamp() // (7 * 86400)))
        frappe.set_user("Guest")
        res = alg.submit_anonymous(self.estate, code, "Unsafe parking", "anon photo", photos_base64=json.dumps([b64(exif_jpeg())]))
        frappe.set_user("Administrator")
        ref = frappe.db.get_value("CPCP Allegation Receipt", {"receipt_id": res["receipt_id"]}, "allegation")
        att = frappe.get_all("CPCP Allegation Attachment", filters={"allegation": ref}, fields=["name", "file_url", "owner", "source_mode"])[0]
        self.assertEqual((att.owner, att.source_mode), ("Guest", "Anonymous"))
        f = frappe.get_doc("File", {"file_url": att.file_url})
        self.assertEqual(f.owner, "Guest")  # no account is attached to the file either
        data = f.get_content()
        data = data.encode("latin-1") if isinstance(data, str) else data
        self.assertNotIn(b"Exif", data)
        al.assert_anonymous_clean(frappe.get_doc("CPCP Parking Allegation", ref).as_dict())

    def test_only_the_assigned_on_duty_officer_can_view_and_it_is_journaled(self):
        as_user("resident")
        r = alg.submit_identified(self.estate, "Unsafe parking", "view photo", str(uuid.uuid4()), photos_base64=json.dumps([b64(exif_jpeg())]))
        wi = frappe.get_all("CPCP Security Work Item", filters={"allegation": r["reference"]}, pluck="name")[0]
        as_user("resident")
        with self.assertRaises(frappe.PermissionError):
            alg.allegation_photos(r["reference"])
        as_user("officer")
        alg.claim_work_item(wi)
        got = alg.allegation_photos(r["reference"])
        self.assertEqual(len(got), 1)
        self.assertTrue(got[0]["data_url"].startswith("data:image/jpeg;base64,"))
        rows = access.query("select * from `tabCPCP Sensitive Access Event` where record_type='Allegation Photo' and actor=%s order by seq desc limit 1",
                            (f"officer@{DOM}",))
        self.assertEqual((rows[0]["result"], rows[0]["category"]), ("Allowed", "restricted_safety"))
        as_user("officer2")  # not assigned and not on duty
        with self.assertRaises(frappe.PermissionError):
            alg.allegation_photos(r["reference"])
        as_user("officer")  # no Desk/REST path to the attachment records either
        self.assertFalse(frappe.has_permission("CPCP Allegation Attachment", "read"))
        with self.assertRaises(frappe.PermissionError):
            frappe.get_list("CPCP Allegation Attachment")
