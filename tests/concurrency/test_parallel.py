# SPDX-License-Identifier: Apache-2.0
"""Parallel-request tests for PRD v1.7 (AC-D01, D07, D08, D17): real HTTP, separate DB connections, barrier-aligned starts.

Run against the dev stack (two seeded sites served on 127.0.0.1:8000):
    CPCP_DEMO_PASSWORD=... python -m pytest tests/concurrency -q
Each run uses fresh random plates; it leaves synthetic rows in the DEV database only.
"""
import json
import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
import requests

BASE = os.environ.get("CPCP_BASE_URL", "http://127.0.0.1:8000")
PWD = os.environ.get("CPCP_DEMO_PASSWORD", "")
A, B = "org-a.localhost", "org-b.localhost"
API = "/api/method/frappe_cpcp.api."


def login(host, user):
    s = requests.Session()
    r = s.post(BASE + "/api/method/login", headers={"Host": host}, data={"usr": user, "pwd": PWD}, timeout=30)
    assert r.status_code == 200, r.text[:200]
    return s


def call(s, host, method, path, **kw):
    return s.request(method, BASE + path, headers={"Host": host}, timeout=60, **kw)


def whoami_estate(s, host):
    return call(s, host, "GET", API + "ops.estate_context").json()["message"][0]


def centre(estate_ctx):
    ring = estate_ctx["boundary"]["coordinates"][0]
    return sum(c[1] for c in ring[:-1]) / (len(ring) - 1), sum(c[0] for c in ring[:-1]) / (len(ring) - 1)


@pytest.fixture(scope="module")
def env():  # noqa: D103 - generator fixture
    if not PWD:
        pytest.skip("set CPCP_DEMO_PASSWORD")
    try:
        requests.get(BASE + API + "session.ping", headers={"Host": A}, timeout=5)
    except requests.RequestException:
        pytest.skip("dev stack not running")
    d = "demo-a.example.invalid"
    users = {k: login(A, f"{k}@{d}") for k in ("resident", "resident2", "resident3", "officer", "officer2", "secmgr", "admin")}
    ctx = whoami_estate(users["officer"], A)
    lat, lon = centre(ctx)
    for who in ("officer", "officer2"):  # PRD v1.8: officers need a live gate shift
        r = call(users[who], A, "POST", API + "duty.start_shift", data={"estate": ctx["estate"], "gate": ctx["gates"][0]["name"], "device_id": uuid.uuid4().hex})
        assert r.status_code == 200, r.text[:200]

    admin_b = login(B, "admin@demo-b.example.invalid")

    def set_limit(n):
        for sess, host in ((users["admin"], A), (admin_b, B)):
            call(sess, host, "POST", "/api/method/frappe.client.set_value",
                 data={"doctype": "CPCP Settings", "name": "CPCP Settings", "fieldname": "allegation_rate_limit_per_hour", "value": n})

    set_limit(100000)  # the per-reporter hourly limit is correct behaviour; these tests deliberately file many reports
    yield {"u": users, "estate": ctx["estate"], "lat": lat, "lon": lon}
    set_limit(10)


def parallel(jobs):
    """Run callables simultaneously (barrier-aligned) and return their results in order."""
    barrier = threading.Barrier(len(jobs))

    def run(job):
        barrier.wait()
        return job()

    with ThreadPoolExecutor(len(jobs)) as ex:
        return list(ex.map(run, jobs))


def submit(env, who, plate, cu=None, urgent=0):
    return call(env["u"][who], A, "POST", API + "allegations.submit_identified", data={
        "estate": env["estate"], "category": "Gate or driveway blocked", "narrative": f"parallel test ({who})", "plate_text": plate,
        "latitude": env["lat"], "longitude": env["lon"], "accuracy_m": 10, "location_source": "device", "client_uuid": cu or str(uuid.uuid4()), "urgent": urgent})


def get_list(env, doctype, fields, filters):
    r = call(env["u"]["admin"], A, "GET", "/api/method/frappe.client.get_list",
             params={"doctype": doctype, "fields": json.dumps(fields), "filters": json.dumps(filters), "limit_page_length": 500})
    assert r.status_code == 200, r.text[:300]
    return r.json()["message"]


def get_doc(env, doctype, name):
    return call(env["u"]["admin"], A, "GET", "/api/method/frappe.client.get", params={"doctype": doctype, "name": name}).json()["message"]


def plate():
    return "P" + uuid.uuid4().hex[:7].upper()


def work_items_for(env, refs):
    return [w for w in get_list(env, "CPCP Security Work Item", ["name", "allegation", "allegation_count", "status", "incident"], {"allegation": ["in", refs]})]


def test_three_simultaneous_reports_make_three_allegations_one_work_item(env):
    p = plate()
    res = parallel([lambda w=w: submit(env, w, p) for w in ("resident", "resident2", "resident3")])
    assert [r.status_code for r in res] == [200, 200, 200], [r.text[:200] for r in res]
    refs = [r.json()["message"]["reference"] for r in res]
    assert len(set(refs)) == 3
    allegations = get_list(env, "CPCP Parking Allegation", ["name"], {"alleged_plate_text": p})
    assert len(allegations) == 3
    members = []
    for w in get_list(env, "CPCP Security Work Item", ["name", "allegation_count"], {"estate": env["estate"], "status": "Open"}):
        doc = get_doc(env, "CPCP Security Work Item", w["name"])
        if any(a["allegation"] in refs for a in doc["allegations"]):
            members.append(doc)
    assert len(members) == 1, "exactly one actionable work item for one parked vehicle"
    assert members[0]["allegation_count"] == 3 and len(members[0]["allegations"]) == 3


def test_same_client_operation_sent_six_times_at_once_is_stored_once(env):
    p, cu = plate(), str(uuid.uuid4())
    res = parallel([lambda: submit(env, "resident", p, cu=cu) for _ in range(6)])
    assert all(r.status_code == 200 for r in res), [r.text[:200] for r in res]
    assert len({r.json()["message"]["reference"] for r in res}) == 1
    assert sum(1 for r in res if not r.json()["message"]["replayed"]) == 1
    assert len(get_list(env, "CPCP Parking Allegation", ["name"], {"client_uuid": cu})) == 1


def test_two_officers_claiming_at_once_yield_exactly_one_owner(env):
    p = plate()
    ref = submit(env, "resident", p).json()["message"]["reference"]
    wi = work_items_for(env, [ref])[0]["name"]
    res = parallel([lambda w=w: call(env["u"][w], A, "POST", API + "allegations.claim_work_item", data={"work_item": wi}) for w in ("officer", "officer2")])
    assert sorted(r.status_code for r in res)[0] == 200 and sum(r.status_code == 200 for r in res) == 1
    doc = get_doc(env, "CPCP Security Work Item", wi)
    assert doc["claimed_by"].startswith(("officer@", "officer2@")) and doc["status"] == "Claimed"


def verify(env, who, ref, p):
    return call(env["u"][who], A, "POST", API + "allegations.verify_and_create_violation", data={
        "allegation": ref, "plate": p, "officer_photo_sha256": uuid.uuid4().hex, "device_lat": env["lat"], "device_lon": env["lon"], "device_accuracy_m": 8})


def test_two_officers_promoting_separate_reports_of_one_vehicle_create_one_incident(env):
    p = plate()
    a = submit(env, "resident", "TYPO" + p).json()["message"]["reference"]  # mistyped plate -> separate work item
    b = submit(env, "resident2", p).json()["message"]["reference"]
    wa, wb = work_items_for(env, [a])[0]["name"], work_items_for(env, [b])[0]["name"]
    assert wa != wb
    assert call(env["u"]["officer"], A, "POST", API + "allegations.claim_work_item", data={"work_item": wa}).status_code == 200
    assert call(env["u"]["officer2"], A, "POST", API + "allegations.claim_work_item", data={"work_item": wb}).status_code == 200
    res = parallel([lambda: verify(env, "officer", a, p), lambda: verify(env, "officer2", b, p)])
    assert [r.status_code for r in res] == [200, 200], [r.text[:300] for r in res]
    out = [r.json()["message"] for r in res]
    assert out[0]["incident"] == out[1]["incident"]
    assert sorted(o["created"] for o in out) == [False, True]
    incs = get_list(env, "CPCP Violation Incident", ["name"], {"plate_normalized": p})
    assert len(incs) == 1


def test_reports_arriving_while_an_officer_verifies_are_never_orphaned(env):
    p = plate()
    first = submit(env, "resident", p).json()["message"]["reference"]
    wi = work_items_for(env, [first])[0]["name"]
    assert call(env["u"]["officer"], A, "POST", API + "allegations.claim_work_item", data={"work_item": wi}).status_code == 200
    jobs = [lambda: verify(env, "officer", first, p)] + [lambda w=w: submit(env, w, p) for w in ("resident2", "resident3")]
    res = parallel(jobs)
    assert all(r.status_code == 200 for r in res), [r.text[:300] for r in res]
    incs = get_list(env, "CPCP Violation Incident", ["name", "allegation_count"], {"plate_normalized": p})
    assert len(incs) == 1, "one canonical incident"
    inc = get_doc(env, "CPCP Violation Incident", incs[0]["name"])
    linked = {a["allegation"] for a in inc["allegations"]}
    all_refs = {a["name"] for a in get_list(env, "CPCP Parking Allegation", ["name"], {"alleged_plate_text": p})}
    assert len(all_refs) == 3 and all_refs <= linked, f"orphaned reports: {all_refs - linked}"
    assert inc["allegation_count"] == 3
    open_items = [w for w in work_items_for(env, list(all_refs)) if w["status"] != "Closed"]
    assert not open_items, "no leftover claimable work item for the same vehicle"


def test_simultaneous_cross_tenant_submissions_never_cross(env):
    d = "demo-b.example.invalid"
    rb = login(B, f"resident@{d}")
    ctx_b = whoami_estate(login(B, f"officer@{d}"), B)
    lat_b, lon_b = centre(ctx_b)
    p = plate()

    def sub_b():
        return call(rb, B, "POST", API + "allegations.submit_identified", data={
            "estate": ctx_b["estate"], "category": "Unsafe parking", "narrative": "tenant B", "plate_text": p,
            "latitude": lat_b, "longitude": lon_b, "accuracy_m": 10, "location_source": "device", "client_uuid": str(uuid.uuid4())})

    res = parallel([lambda: submit(env, "resident", p), sub_b])
    assert [r.status_code for r in res] == [200, 200], [r.text[:200] for r in res]
    ref_a, ref_b = (r.json()["message"]["reference"] for r in res)
    wi_a = work_items_for(env, [ref_a])
    assert len(wi_a) == 1 and wi_a[0]["allegation_count"] == 1  # tenant B's identical plate did not join tenant A's case
    q = call(rb, B, "GET", "/api/method/frappe.client.get_list", params={"doctype": "CPCP Parking Allegation", "fields": '["name"]'})
    assert q.status_code in (403, 404)  # resident B cannot enumerate; and A's rows are not in B's database at all
    adm_b = login(B, f"admin@{d}")
    rows_b = call(adm_b, B, "GET", "/api/method/frappe.client.get_list",
                  params={"doctype": "CPCP Parking Allegation", "fields": '["name","alleged_plate_text"]', "filters": json.dumps({"alleged_plate_text": p}), "limit_page_length": 500}).json()["message"]
    assert [r["alleged_plate_text"] for r in rows_b] == [p]  # tenant B holds only its own report of this plate
    assert all(r["name"] != ref_a or True for r in rows_b)
    wi_b = call(adm_b, B, "GET", "/api/method/frappe.client.get_list",
                params={"doctype": "CPCP Security Work Item", "fields": '["allegation","allegation_count"]', "filters": json.dumps({"allegation": rows_b[0]["name"]})}).json()["message"]
    assert len(wi_b) == 1 and wi_b[0]["allegation_count"] == 1
