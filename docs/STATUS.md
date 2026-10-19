# Status (verified results, blockers, next steps)
Updated 2026-10-19.

## Verified
- `apps/frappe_cpcp` core unit tests: **64 passed** (`python -m pytest`, local Python 3.11).
- Apache-2.0 LICENSE is byte-identical to the canonical text (sha256 cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30).
- Upstream versions/licenses checked (see docs/legal/THIRD_PARTY_LICENSES.md).
- Frappe v15.123.1 bench builds in Docker (frappe/bench image, Python 3.12).

- Frappe v15.123.1 dev stack with two sites (`org-a.localhost`, `org-b.localhost`); app installs, all 24 DocTypes import.
- **21 Frappe integration tests pass** on org-a (`bench --site org-a.localhost run-tests --app frappe_cpcp --module frappe_cpcp.tests.test_integration`): resident denied registry/visitor log (UI hooks, list, API), officer lookup minimal + logged, other-estate denial, visit lifecycle/idempotency/re-entry, anonymous intake without correlators + receipt, claim race, verify-and-create (separate incident, duplicate allegations join one incident), append-only + audit chain, expired/multi-role handling.
- **Cross-tenant HTTP isolation: 8 tests pass** (`tests/tenant-isolation`; needs `bash infra/dev/seed.sh` + `serve.sh`): session-cookie replay and Host-header swap against the other site fail, same plate resolves to each tenant's own unit, guests read nothing, different policies per tenant (15 min vs 10 min).
- CI on GitHub passes (core tests, lint, DocType regeneration check, secret scan).

## Not yet verified (do not assume)
- Backup/restore proof, mobile PoC, desktop UI.

## Blockers
- No JDK/Android SDK on the dev machine: native Android build must run in CI or after installing the SDK.
- No macOS: iOS archive needs an authorized Mac/CI runner. No physical-device tests yet.
- Copyright holder name needs owner confirmation; PRD inclusion needs owner confirmation.
- Legal items (clamping/towing authority, Ghana DPA review, SMS/voice/payment providers) are external decisions.

## Next
1. Run migrations + Frappe integration tests on both sites; fix failures.
2. Two-site isolation tests; mobile PoC (React + Capacitor) with camera/GPS/secure storage.
3. Desktop console skeleton, maps, SBOM/license CI, branch protection.
