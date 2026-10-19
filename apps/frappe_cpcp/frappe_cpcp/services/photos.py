# SPDX-License-Identifier: Apache-2.0
"""Resident photo intake: validate, strip ALL embedded metadata, then store privately (PRD 34.2.5, AC-58).

The upload is never stored as received. It is decoded, orientation-corrected, flattened to RGB, size-limited and RE-ENCODED as a
fresh JPEG, which discards EXIF (including GPS, camera make/model, timestamps and thumbnails), ICC profiles, comments, XMP and any
trailing bytes appended to the file. Sanitisation happens before persistence and before any preview exists.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import io
import json

import frappe

MAX_INPUT_BYTES = 8 * 1024 * 1024
MAX_PIXELS = 36_000_000
MAX_EDGE = 1600
MAX_PHOTOS = 3
_MAGIC = (b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n")


class PhotoError(frappe.ValidationError):
    pass


def decode_list(photos_json: str | None) -> list[bytes]:
    """Parse a JSON list of base64 strings (data: URL prefixes tolerated)."""
    if not photos_json:
        return []
    try:
        items = json.loads(photos_json)
    except ValueError:
        raise PhotoError("Photos must be a JSON list") from None
    if not isinstance(items, list) or len(items) > MAX_PHOTOS:
        raise PhotoError(f"At most {MAX_PHOTOS} photos can be attached")
    out = []
    for b64 in items:
        if not isinstance(b64, str):
            raise PhotoError("Invalid photo")
        if "," in b64[:64]:
            b64 = b64.split(",", 1)[1]
        try:
            raw = base64.b64decode(b64, validate=True)
        except (binascii.Error, ValueError):
            raise PhotoError("A photo is not valid base64") from None
        out.append(raw)
    return out


def sanitize(raw: bytes) -> tuple[bytes, dict]:
    """Return (clean_jpeg_bytes, info). Raises PhotoError for anything that is not an acceptable JPEG/PNG."""
    from PIL import Image, ImageOps

    if not raw or len(raw) > MAX_INPUT_BYTES:
        raise PhotoError("A photo is empty or larger than 8 MB")
    if not raw.startswith(_MAGIC):
        raise PhotoError("Only JPEG or PNG photos are accepted")
    try:
        img = Image.open(io.BytesIO(raw))
        if img.format not in ("JPEG", "PNG"):
            raise PhotoError("Only JPEG or PNG photos are accepted")
        w, h = img.size
        if w * h > MAX_PIXELS:
            raise PhotoError("The photo has too many pixels")
        img.load()
    except PhotoError:
        raise
    except Exception:
        raise PhotoError("The photo could not be read") from None
    img = ImageOps.exif_transpose(img)  # apply the camera rotation, THEN drop the orientation tag with everything else
    if img.mode in ("RGBA", "LA", "P"):
        rgba = img.convert("RGBA")
        flat = Image.new("RGB", rgba.size, (255, 255, 255))
        flat.paste(rgba, mask=rgba.getchannel("A"))
        img = flat
    else:
        img = img.convert("RGB")
    img.thumbnail((MAX_EDGE, MAX_EDGE))
    img.info = {}  # nothing inherited from the source survives
    out = io.BytesIO()
    img.save(out, "JPEG", quality=82, optimize=True)  # no exif=/icc_profile=/comment= arguments: a fresh file
    data = out.getvalue()
    return data, {"width": img.size[0], "height": img.size[1], "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def private_file(name: str, data: bytes):
    """Create a PRIVATE File after the server's own checks (the caller may be a resident or an anonymous guest with no File permission)."""
    f = frappe.get_doc({"doctype": "File", "file_name": name, "content": data, "is_private": 1})
    f.insert(ignore_permissions=True)
    return f


def store(allegation: str, raws: list[bytes], *, source_mode: str) -> list[str]:
    """Sanitize every photo FIRST (all-or-nothing), then persist privately. Returns Attachment names."""
    from frappe_cpcp.services.common import to_db, utcnow

    cleaned = [sanitize(r) for r in raws]
    names = []
    for data, info in cleaned:
        f = private_file(f"report-{info['sha256'][:12]}.jpg", data)
        att = frappe.get_doc({"doctype": "CPCP Allegation Attachment", "allegation": allegation, "file_url": f.file_url, "sha256": info["sha256"],
                              "width": info["width"], "height": info["height"], "bytes": info["bytes"], "source_mode": source_mode,
                              "created_at": to_db(utcnow())}).insert(ignore_permissions=True)
        frappe.db.set_value("File", {"file_url": f.file_url}, {"attached_to_doctype": "CPCP Allegation Attachment", "attached_to_name": att.name})
        names.append(att.name)
    return names


def read_clean(attachment: str) -> dict:
    row = frappe.db.get_value("CPCP Allegation Attachment", attachment, ["file_url", "width", "height", "sha256"], as_dict=True)
    if not row:
        raise frappe.PermissionError("not permitted")
    content = frappe.get_doc("File", {"file_url": row.file_url}).get_content()
    if isinstance(content, str):
        content = content.encode("latin-1")
    if hashlib.sha256(content).hexdigest() != row.sha256:
        raise frappe.ValidationError("Photo integrity check failed")
    return {"attachment": attachment, "width": row.width, "height": row.height, "data_url": "data:image/jpeg;base64," + base64.b64encode(content).decode()}
