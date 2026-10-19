# SPDX-License-Identifier: Apache-2.0
"""PRD v1.8 purpose-based access: black-box HTTP tests (PBAC-04, 05, 12, 14, 19, 20).

Real requests through Frappe's whole stack (before_request guard, DocPerm, hooks, APIs) against BOTH seeded demo sites:
    bash infra/dev/bootstrap.sh && CPCP_DEMO_PASSWORD=... bash infra/dev/seed.sh && bash infra/dev/serve.sh
    CPCP_DEMO_PASSWORD=... python -m pytest tests/privacy -q
"""
import json
import os
import uuid

import pytest
import requests

BASE = os.environ.get("CPCP_BASE_URL", "http://127.0.0.1:8000")
PWD = os.environ.get("CPCP_DEMO_PASSWORD", "")
A, B = "org-a.localhost", "org-b.localhost"
API = "/api/method/frappe_cpcp.api."
DA, DB = "demo-a.example.invalid", "demo-b.example.invalid"
SENSITIVE = ["CPCP Person", "CPCP Vehicle", "CPCP Visitor Session", "CPCP Unit Membership", "CPCP Vehicle Unit Association", "CPCP Visit Event"]


def login(host, user):
    s = requests.Session()
    r = s.post(BASE + "/api/method/login", headers={"Host": host}, data={"usr": user, "pwd": PWD}, timeout=30)
    assert r.status_code == 200, r.text[:200]
    return s


def call(s, host, method, path, **kw):
    return s.request(method, BASE + path, headers={"Host": host}, timeout=60, **kw)


def estate_ctx(s, host):
    return call(s, host, "GET", API + "ops.estate_context").json()["message"][0]


def start_shift(s, host, ctx, device=None):
    r = call(s, host, "POST", API + "duty.start_shift", data={"estate": ctx["estate"], "gate": ctx["gates"][0]["name"], "device_id": device or uuid.uuid4().hex})
    assert r.status_code == 200, r.text[:300]
    return r.json()["message"]


@pytest.fixture(scope="module")
def env():
    if not PWD:
        pytest.skip("set CPCP_DEMO_PASSWORD")
    try:
        requests.get(BASE + API + "session.ping", headers={"Host": A}, timeout=5)
    except requests.RequestException:
        pytest.skip("dev stack not running")
    users = {k: login(A, f"{k}@{DA}") for k in ("officer", "officer2", "secmgr", "admin", "auditor", "resident")}
    ctx = estate_ctx(users["officer"], A)
    limits = ("plate_lookups_per_hour", "suggestion_limit_per_hour", "bare_suggestions_per_hour")

    def set_limits(vals):
        for f, v in zip(limits, vals):
            call(users["admin"], A, "POST", "/api/method/frappe.client.set_value", data={"doctype": "CPCP Settings", "name": "CPCP Settings", "fieldname": f, "value": v})

    set_limits((100000,) * 3)  # the journal-based limits are covered by their own tests; these tests make many calls
    start_shift(users["officer"], A, ctx)
    yield {"u": users, "ctx": ctx, "estate": ctx["estate"]}
    set_limits((60, 30, 10))


def admin_events(env, **params):
    r = call(env["u"]["admin"], A, "GET", API + "access_review.search", params={"limit": 500, **params})
    assert r.status_code == 200, r.text[:300]
    return r.json()["message"]["rows"]


@pytest.mark.parametrize("path,params", [
    ("/api/resource/CPCP Person", {}),
    ("/api/resource/CPCP Vehicle", {}),
    ("/api/resource/CPCP Visitor Session", {}),
    ("/api/method/frappe.client.get_list", {"doctype": "CPCP Unit Membership"}),
    ("/api/method/frappe.client.get_count", {"doctype": "CPCP Vehicle Unit Association"}),
    ("/api/method/frappe.desk.reportview.get", {"doctype": "CPCP Visit Event", "fields": '["name"]'}),
    ("/api/method/frappe.desk.search.search_link", {"doctype": "CPCP Vehicle", "txt": "ZZ"}),
    ("/api/method/frappe.desk.form.load.getdoc", {"doctype": "CPCP Person", "name": "PER-00001"}),
    ("/api/method/frappe.utils.print_format.download_pdf", {"doctype": "CPCP Person", "name": "PER-00001"}),
    ("/api/method/frappe.core.doctype.data_export.exporter.export_data", {"doctype": "CPCP Vehicle"}),
])
def test_pbac04_12_officer_cannot_browse_search_print_or_export(env, path, params):
    r = call(env["u"]["officer"], A, "GET", path, params=params)
    assert r.status_code in (401, 403), f"{path} -> {r.status_code}: {r.text[:200]}"
    body = r.text.lower()
    for leak in ("ama demo", "kofi", "0241230001", "zz1001", "zz 1001"):
        assert leak not in body


def test_pbac12_every_denied_desk_attempt_is_in_the_journal_and_visible_to_reviewers(env):
    marker = "/api/resource/CPCP Person"
    call(env["u"]["officer"], A, "GET", marker)
    rows = admin_events(env, actor_user=f"officer@{DA}", result="Denied")
    assert any(r["purpose"] == "desk_access" and r["record_type"] == "Person" for r in rows)
    assert all(r["role"] == "security_officer" for r in rows if r["purpose"] == "desk_access")


def test_pbac05_forged_purpose_case_and_gate_do_not_grant_access(env):
    s, e = env["u"]["officer"], env["estate"]
    for params in ({"purpose": "admin"}, {"purpose": "case", "reference": "INC-99999"}, {"purpose": "case", "reference": ""}, {"purpose": "gate", "gate": "GATE-FAKE"}):
        r = call(s, A, "GET", API + "registry.lookup_plate", params={"estate": e, "plate": "ZZ1001-26", **params})
        assert r.status_code == 403, f"{params} -> {r.status_code} {r.text[:200]}"
    other = call(s, A, "GET", API + "registry.lookup_plate", params={"estate": "EST-NOT-MINE", "plate": "ZZ1001-26"})
    assert other.status_code == 403
    ok = call(s, A, "GET", API + "registry.lookup_plate", params={"estate": e, "plate": "ZZ1001-26"})
    assert ok.status_code == 200
    blob = json.dumps(ok.json()["message"]).lower()
    for banned in ("ama", "kofi", "phone", "0241", "members", "history"):
        assert banned not in blob


def test_pbac14_officers_cannot_touch_or_review_the_journal(env):
    s = env["u"]["officer"]
    for path in (API + "access_review.search", API + "access_review.summary", API + "access_review.flags", API + "access_review.verify_chain"):
        assert call(s, A, "GET", path).status_code == 403, path
    assert call(s, A, "GET", "/api/resource/CPCP Sensitive Access Event").status_code in (401, 403)
    admin = env["u"]["admin"]
    row = admin_events(env)[0]
    name = call(admin, A, "GET", "/api/method/frappe.client.get_list", params={"doctype": "CPCP Sensitive Access Event", "fields": '["name"]', "limit_page_length": 1}).json()["message"][0]["name"]
    for method, extra in (("PUT", {"data": json.dumps({"result": "Allowed"})}), ("DELETE", {})):
        r = call(admin, A, method, f"/api/resource/CPCP Sensitive Access Event/{name}", **extra)
        assert r.status_code in (403, 417, 500) and r.status_code != 200, f"{method} {r.status_code}"  # append-only even for admins
    assert row["request_id"]


def test_pbac15_manager_access_is_allowed_but_journaled(env):
    r = call(env["u"]["secmgr"], A, "GET", "/api/resource/CPCP Person", params={"limit_page_length": 1})
    assert r.status_code == 200
    mine = [x for x in admin_events(env, actor_user=f"secmgr@{DA}") if x["purpose"] == "administration"]
    assert mine and mine[0]["result"] == "Allowed" and mine[0]["role"] == "security_manager"
    for path in ("/api/method/frappe.utils.print_format.download_pdf", "/api/method/frappe.core.doctype.data_export.exporter.export_data"):
        assert call(env["u"]["secmgr"], A, "GET", path, params={"doctype": "CPCP Person", "name": "PER-00001"}).status_code == 403


def test_pbac19_cross_tenant_session_and_journal_isolation(env):
    sid = env["u"]["officer"].cookies.get("sid")
    other = requests.Session()
    other.cookies.set("sid", sid)
    r = call(other, B, "GET", API + "registry.lookup_plate", params={"estate": "EST-00001", "plate": "ZZ1001-26"})
    assert r.status_code in (401, 403)
    adm_b = login(B, f"admin@{DB}")
    rows_b = call(adm_b, B, "GET", API + "access_review.search", params={"limit": 500}).json()["message"]["rows"]
    assert all(not x["actor"].endswith(DA) for x in rows_b), "org-a identities must never appear in org-b's journal"
    rows_a = admin_events(env)
    assert all(not x["actor"].endswith(DB) for x in rows_a)
    # org-b officer is not on shift: the same sensitive call is denied there too
    ob = login(B, f"officer@{DB}")
    call(ob, B, "POST", API + "duty.end_shift")  # make sure this officer is not on duty in org-b
    assert call(ob, B, "GET", API + "registry.lookup_plate", params={"estate": estate_ctx(ob, B)["estate"], "plate": "ZZ1001-26"}).status_code == 403


def test_pbac20_revocation_stops_a_logged_in_phone_immediately(env):
    o2 = login(A, f"officer2@{DA}")
    ctx = env["ctx"]
    start_shift(o2, A, ctx, device="phone-to-revoke-" + uuid.uuid4().hex[:6])
    assert call(o2, A, "GET", API + "registry.lookup_plate", params={"estate": ctx["estate"], "plate": "ZZ1001-26"}).status_code == 200
    r = call(env["u"]["secmgr"], A, "POST", API + "duty.revoke_device", data={"user": f"officer2@{DA}", "reason": "phone lost at the gate"})
    assert r.status_code == 200, r.text[:300]
    after = call(o2, A, "GET", API + "registry.lookup_plate", params={"estate": ctx["estate"], "plate": "ZZ1001-26"})
    assert after.status_code in (401, 403)
    assert call(o2, A, "GET", API + "visitors.active_visitors", params={"estate": ctx["estate"]}).status_code in (401, 403)
    again = login(A, f"officer2@{DA}")  # fresh login works, but the revoked device cannot start a shift, so nothing sensitive opens
    assert call(again, A, "GET", API + "registry.lookup_plate", params={"estate": ctx["estate"], "plate": "ZZ1001-26"}).status_code == 403
