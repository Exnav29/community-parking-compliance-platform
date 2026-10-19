# SPDX-License-Identifier: Apache-2.0
"""Black-box tenant-isolation tests over HTTP (AC-20, AC-22, AC-27, AC-117).

Needs the dev stack running with both sites seeded and `bench serve` on 127.0.0.1:8000:
    bash infra/dev/bootstrap.sh && bash infra/dev/seed.sh && bash infra/dev/serve.sh
    CPCP_DEMO_PASSWORD=... python -m pytest tests/tenant-isolation -q
Skipped automatically when the stack is not reachable.
"""
import os

import pytest
import requests

BASE = os.environ.get("CPCP_BASE_URL", "http://127.0.0.1:8000")
PWD = os.environ.get("CPCP_DEMO_PASSWORD", "")
A, B = "org-a.localhost", "org-b.localhost"


def call(host, method, path, session=None, **kw):
    s = session or requests.Session()
    return s, s.request(method, BASE + path, headers={"Host": host}, timeout=20, **kw)


def login(host, user):
    s, r = call(host, "POST", "/api/method/login", data={"usr": user, "pwd": PWD})
    assert r.status_code == 200, r.text[:200]
    return s


@pytest.fixture(scope="module", autouse=True)
def _stack():
    if not PWD:
        pytest.skip("set CPCP_DEMO_PASSWORD (the password used by the seed)")
    try:
        requests.get(BASE + "/api/method/frappe_cpcp.api.session.ping", headers={"Host": A}, timeout=5)
    except requests.RequestException:
        pytest.skip("dev stack not running")


def test_each_site_reports_its_own_org():
    sa = login(A, "officer@demo-a.example.invalid")
    sb = login(B, "officer@demo-b.example.invalid")
    wa = call(A, "GET", "/api/method/frappe_cpcp.api.session.whoami", session=sa)[1].json()["message"]
    wb = call(B, "GET", "/api/method/frappe_cpcp.api.session.whoami", session=sb)[1].json()["message"]
    assert wa["organization"] == "org-a" and wb["organization"] == "org-b"


def test_session_cookie_replay_against_other_site_fails():
    sa = login(A, "officer@demo-a.example.invalid")
    sid = sa.cookies.get("sid")
    assert sid
    s2 = requests.Session()
    s2.cookies.set("sid", sid)
    r = call(B, "GET", "/api/method/frappe_cpcp.api.session.whoami", session=s2)[1]
    assert r.status_code in (401, 403), r.text[:200]


def test_host_header_swap_does_not_change_tenant_data():
    sa = login(A, "officer@demo-a.example.invalid")
    # Same cookie, other Host => other site => unauthenticated.
    r = call(B, "GET", "/api/method/frappe_cpcp.api.registry.lookup_plate", session=sa, params={"estate": "EST-00001", "plate": "ZZ1001-26"})[1]
    assert r.status_code in (401, 403)


def _on_duty(session, host):
    ctx = call(host, "GET", "/api/method/frappe_cpcp.api.ops.estate_context", session=session)[1].json()["message"][0]
    r = call(host, "POST", "/api/method/frappe_cpcp.api.duty.start_shift", session=session,
             data={"estate": ctx["estate"], "gate": ctx["gates"][0]["name"], "device_id": os.urandom(6).hex()})[1]
    assert r.status_code == 200, r.text[:200]


def test_same_labels_are_independent_per_tenant():
    sa = login(A, "officer@demo-a.example.invalid")
    sb = login(B, "officer@demo-b.example.invalid")
    _on_duty(sa, A)
    _on_duty(sb, B)
    for host, user in ((A, "admin@demo-a.example.invalid"), (B, "admin@demo-b.example.invalid")):  # journal-based plate limit: allow this test's calls
        adm = login(host, user)
        call(host, "POST", "/api/method/frappe.client.set_value", session=adm,
             data={"doctype": "CPCP Settings", "name": "CPCP Settings", "fieldname": "plate_lookups_per_hour", "value": 100000})
    ra = call(A, "GET", "/api/method/frappe_cpcp.api.registry.lookup_plate", session=sa, params={"estate": "EST-00001", "plate": "ZZ1001-26"})[1]
    assert ra.json()["message"]["match"] == "resident_vehicle"
    rb = call(B, "GET", "/api/method/frappe_cpcp.api.registry.lookup_plate", session=sb, params={"estate": "EST-00001", "plate": "ZZ1001-26"})[1]
    # The same fictitious plate exists in both tenants, but each answers from its OWN registry.
    assert ra.json()["message"]["unit"] == "A1"
    assert rb.status_code == 200 and rb.json()["message"]["unit"] == "101"


def test_resident_http_denied_registry():
    s = login(A, "resident@demo-a.example.invalid")
    r = call(A, "GET", "/api/method/frappe_cpcp.api.registry.lookup_plate", session=s, params={"estate": "EST-00001", "plate": "ZZ1001-26"})[1]
    assert r.status_code == 403
    r = call(A, "GET", "/api/resource/CPCP Vehicle", session=s)[1]
    assert r.status_code in (403, 404)
    r = call(A, "GET", "/api/resource/CPCP Visitor Session", session=s)[1]
    assert r.status_code in (403, 404)


def test_policies_differ_between_tenants():
    sa = login(A, "admin@demo-a.example.invalid")
    sb = login(B, "admin@demo-b.example.invalid")
    pa = call(A, "GET", "/api/method/frappe.client.get_list", session=sa, params={"doctype": "CPCP Policy Version", "fields": '["grace_minutes","violation_penalty"]'})[1].json()["message"]
    pb = call(B, "GET", "/api/method/frappe.client.get_list", session=sb, params={"doctype": "CPCP Policy Version", "fields": '["grace_minutes","violation_penalty"]'})[1].json()["message"]
    assert pa[0]["grace_minutes"] == 15 and pb[0]["grace_minutes"] == 10


def test_guest_cannot_read_anything_sensitive():
    for host in (A, B):
        for path in ("/api/resource/CPCP Vehicle", "/api/resource/CPCP Parking Allegation", "/api/resource/CPCP Visitor Session"):
            assert call(host, "GET", path)[1].status_code in (401, 403)


def test_anonymous_status_is_generic_for_unknown_receipt():
    r = call(A, "POST", "/api/method/frappe_cpcp.api.allegations.anonymous_status", data={"receipt_id": "R-NOPE", "secret": "x"})[1]
    assert r.status_code == 200 and r.json()["message"] == {"found": False}
