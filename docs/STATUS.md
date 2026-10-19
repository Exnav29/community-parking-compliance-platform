# Status (verified results, blockers, next steps)
Updated 2026-10-19 (second session).

## Test results (last full run, this date)
| Suite | Result |
|---|---|
| Core unit tests (pytest, no Frappe) | **73 passed** |
| Frappe integration on org-a (3 modules: integration 22, comms/enforcement 14, reports 6) | **42 passed** |
| Cross-tenant HTTP isolation (2 sites) | **8 passed** |
| Mobile (vitest) + `tsc -b` + production build | **9 passed**, typecheck clean, build OK |

## Feature status
| Area | State |
|---|---|
| Copyright owner confirmed (Johnathan Lightfoot), NOTICE updated | Implemented |
| Contact resolution, dialer outcome capture, server SMS (mock adapter), HMAC callbacks, notice clock | Implemented and verified (integration tests) |
| Enforcement actions, itemized charges (one penalty/incident), appeals, release never gated | Implemented and verified; **all legal gates OFF**, no live adapters |
| Dashboards, hotspot layers (verified vs unverified), thresholded resident summary | Implemented and verified (API) |
| Officer evidence photos (validated, server-hashed, private) | Implemented and verified |
| Mobile app screens (gate, triage, verify with map pin, case/contact, resident) | **Implemented, awaiting physical-device validation** (see docs/ANDROID_TESTING.md) |
| PRD v1.7 incident de-duplication / repeat-offender addendum | **BLOCKED: addendum text was not attached** (see below). Interim behavior: 4-hour same-plate clustering only. |
| Desktop management console | Not started |
| Backup/restore proof, SBOM/license CI, threat model & matrices docs, store-compliance matrix | Not started |
| Provider-mediated voice, real SMS provider | Blocked: provider/authorization decision |

## Blocker: PRD v1.7 addendum
The requested file was not in the message, `D:\Projects\CPCP`, `Downloads` or `D:\Projects`. Only PRD v1.6 exists. Acceptance tests are not fabricated; once the addendum is supplied it will be merged into `docs/spec/PRD_v1.7.md` and its 18 tests implemented before any live financial/enforcement work.


## Verified
- `apps/frappe_cpcp` core unit tests: **64 passed** (`python -m pytest`, local Python 3.11).
- Apache-2.0 LICENSE is byte-identical to the canonical text (sha256 cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30).
- Upstream versions/licenses checked (see docs/legal/THIRD_PARTY_LICENSES.md).
- Frappe v15.123.1 bench builds in Docker (frappe/bench image, Python 3.12).

- Frappe v15.123.1 dev stack with two sites (`org-a.localhost`, `org-b.localhost`); app installs, all 24 DocTypes import.
- **21 Frappe integration tests pass** on org-a (`bench --site org-a.localhost run-tests --app frappe_cpcp --module frappe_cpcp.tests.test_integration`): resident denied registry/visitor log (UI hooks, list, API), officer lookup minimal + logged, other-estate denial, visit lifecycle/idempotency/re-entry, anonymous intake without correlators + receipt, claim race, verify-and-create (separate incident, duplicate allegations join one incident), append-only + audit chain, expired/multi-role handling.
- **Cross-tenant HTTP isolation: 8 tests pass** (`tests/tenant-isolation`; needs `bash infra/dev/seed.sh` + `serve.sh`): session-cookie replay and Host-header swap against the other site fail, same plate resolves to each tenant's own unit, guests read nothing, different policies per tenant (15 min vs 10 min).
- **Mobile PoC** (`apps/mobile`, React 19 + TS + Capacitor 8): typecheck, 9 unit tests and production build pass; Android and iOS native projects generated; **GitHub CI builds an unsigned debug APK** (artifact `cpcp-debug-apk-unsigned`). NOT yet verified: install/run on a physical Android or iPhone, camera/GPS/keystore behavior on device, push notifications, iOS archive (needs macOS).
- CI on GitHub passes (core tests, lint, DocType regeneration check, secret scan).

## Not yet verified (do not assume)
- Backup/restore proof, physical-device tests, desktop UI, maps/heatmap, enforcement/finance/appeals (gated), notification adapters, control-plane provisioner UI, SBOM/license CI.

## Blockers
- No JDK/Android SDK on the dev machine: native Android build must run in CI or after installing the SDK.
- No macOS: iOS archive needs an authorized Mac/CI runner. No physical-device tests yet.
- Copyright holder name needs owner confirmation; PRD inclusion needs owner confirmation.
- Legal items (clamping/towing authority, Ghana DPA review, SMS/voice/payment providers) are external decisions.

## Next
1. Run migrations + Frappe integration tests on both sites; fix failures.
2. Two-site isolation tests; mobile PoC (React + Capacitor) with camera/GPS/secure storage.
3. Desktop console skeleton, maps, SBOM/license CI, branch protection.
