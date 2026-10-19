# SPDX-License-Identifier: Apache-2.0
"""The management console is only a client: this proves what the SERVER allows each role to load for every console page.

    bash infra/dev/seed.sh && bash infra/dev/serve.sh && (cd apps/web && npm run build) && bench build --app frappe_cpcp
    CPCP_DEMO_PASSWORD=... python -m pytest tests/console -q
"""
import json
import os

import pytest
import requests

BASE = os.environ.get("CPCP_BASE_URL", "http://127.0.0.1:8000")
PWD = os.environ.get("CPCP_DEMO_PASSWORD", "")
HOST, DOM = "org-a.localhost", "demo-a.example.invalid"
API = "/api/method/frappe_cpcp.api."


def login(key):
    s = requests.Session()
    r = s.post(BASE + "/api/method/login", headers={"Host": HOST}, data={"usr": f"{key}@{DOM}", "pwd": PWD}, timeout=30)
    assert r.status_code == 200, r.text[:200]
    return s


def get(s, path, **params):
    return s.get(BASE + path, headers={"Host": HOST}, params=params, timeout=60).status_code


@pytest.fixture(scope="module")
def env():
    if not PWD:
        pytest.skip("set CPCP_DEMO_PASSWORD")
    try:
        requests.get(BASE + API + "session.ping", headers={"Host": HOST}, timeout=5)
    except requests.RequestException:
        pytest.skip("dev stack not running")
    users = {k: login(k) for k in ("admin", "secmgr", "auditor", "officer", "resident", "finance")}
    # the estate every non-admin demo role is assigned to (the org-wide admin may also see extra estates created by other tests)
    estate = users["secmgr"].get(BASE + API + "ops.estate_context", headers={"Host": HOST}).json()["message"][0]["estate"]
    return users, estate


def rest(doctype, fields="[\"name\"]"):
    return "/api/resource/" + doctype, {"fields": fields, "limit_page_length": 1}


def calls(estate):
    return {
        "overview": (API + "reports.dashboard", {"estate": estate}),
        "cases": (API + "incidents.list_cases", {"estate": estate}),
        "queue": (API + "allegations.triage_queue", {"estate": estate}),
        "map": (API + "reports.hotspots", {"estate": estate}),
        "visitors_now": (API + "visitors.active_visitors", {"estate": estate}),
        "people": rest("CPCP Person"), "units": rest("CPCP Unit"), "vehicles": rest("CPCP Vehicle"), "visits": rest("CPCP Visitor Session"),
        "roles": rest("CPCP Role Assignment"), "shifts": rest("CPCP Gate Shift"), "policies": rest("CPCP Policy Version"),
        "ar_search": (API + "access_review.search", {}), "ar_summary": (API + "access_review.summary", {}), "ar_flags": (API + "access_review.flags", {}),
        "ar_emerg": (API + "access_review.pending_emergency_reviews", {}), "ar_chain": (API + "access_review.verify_chain", {}),
        "ar_audit": (API + "access_review.verify_audit_chain", {}), "ar_export": (API + "access_review.export_log", {}),
    }


# expected HTTP status family per role and console call: True = allowed (200), False = refused (401/403)
EXPECT = {
    "admin": {k: True for k in ("overview", "cases", "queue", "map", "visitors_now", "people", "units", "vehicles", "visits", "roles", "shifts", "policies",
                                "ar_search", "ar_summary", "ar_flags", "ar_emerg", "ar_chain", "ar_audit", "ar_export")},
    "secmgr": {"overview": True, "cases": True, "queue": True, "map": True, "visitors_now": True, "people": True, "units": True, "vehicles": True, "visits": True,
               "roles": False, "shifts": True, "policies": True, "ar_search": True, "ar_summary": True, "ar_flags": True, "ar_emerg": True, "ar_chain": True,
               "ar_audit": True, "ar_export": False},
    "auditor": {"overview": True, "cases": False, "queue": False, "map": False, "visitors_now": False, "people": False, "units": False, "vehicles": False,
                "visits": False, "roles": False, "shifts": False, "policies": False, "ar_search": True, "ar_summary": True, "ar_flags": True, "ar_emerg": True,
                "ar_chain": True, "ar_audit": True, "ar_export": False},
    "officer": {"cases": False, "map": True, "people": False, "vehicles": False, "visits": False, "roles": False, "shifts": False, "policies": False,
                "ar_search": False, "ar_summary": False, "ar_flags": False, "ar_emerg": False, "ar_chain": False, "ar_audit": False, "ar_export": False},
    "resident": {"overview": False, "cases": False, "queue": False, "map": False, "visitors_now": False, "people": False, "vehicles": False, "visits": False,
                 "roles": False, "shifts": False, "policies": False, "ar_search": False, "ar_summary": False, "ar_flags": False, "ar_export": False},
    "finance": {"overview": True, "queue": False, "people": False, "vehicles": False, "visits": False, "roles": False, "shifts": False,
                "ar_search": False, "ar_summary": False, "ar_flags": False, "ar_export": False},
}


@pytest.mark.parametrize("role", list(EXPECT))
def test_each_console_call_is_allowed_or_refused_by_the_server(env, role):
    users, estate = env
    wrong = []
    for name, want in EXPECT[role].items():
        path, params = calls(estate)[name]
        code = get(users[role], path, **params)
        ok = code == 200
        if ok != want or (not want and code not in (401, 403)):
            wrong.append(f"{role}:{name} expected {'200' if want else '401/403'} got {code}")
    assert not wrong, "\n".join(wrong)


def test_console_is_served_by_frappe_from_the_same_origin():
    if not PWD:
        pytest.skip("set CPCP_DEMO_PASSWORD")
    r = requests.get(BASE + "/assets/frappe_cpcp/web/index.html", headers={"Host": HOST}, timeout=20)
    if r.status_code == 404:
        pytest.skip("console not built (cd apps/web && npm run build; bench build --app frappe_cpcp)")
    assert r.status_code == 200 and "CPCP Management Console" in r.text
    js = [p for p in r.text.split('"') if p.endswith(".js") and "/assets/" in p]
    assert js and requests.get(BASE + js[0], headers={"Host": HOST}, timeout=20).status_code == 200


def test_officer_cannot_reach_management_apis_even_with_a_valid_session(env):
    users, estate = env
    for path, params in ((API + "incidents.merge_incidents", {}), (API + "duty.revoke_device", {}), (API + "access_review.run_detection", {})):
        r = users["officer"].post(BASE + path, headers={"Host": HOST}, data={"source": "x", "target": "y", "reason": "r", "user": "u"}, timeout=30)
        assert r.status_code in (401, 403), f"{path} -> {r.status_code}"
