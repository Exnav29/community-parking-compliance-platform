# Status (verified results, blockers, next steps)
Updated 2026-10-19 (second session).

## Test results (last full run, 2026-10-19, after the v1.7 changes)
| Suite | Result |
|---|---|
| Core unit tests (pytest, no Frappe) | **80 passed** |
| Frappe integration on org-a: integration 22, comms/enforcement 14, reports 6, **dedup (AC-D01..D18 + variant) 19** | **61 passed** |
| Cross-tenant HTTP isolation (two sites) | **8 passed** |
| **Parallel HTTP concurrency** (`tests/concurrency`, 6 scenarios, barrier-aligned threads) | **6 passed; repeated 40 times in a row = 240 concurrent scenarios, 0 failures** |
| Mobile (vitest) + `tsc -b` + production build | **9 passed**, typecheck clean, build OK |

### PRD v1.7 acceptance tests (AC-D01..AC-D18)
All 18 are implemented and **pass** (serial, real DB and permission hooks: `apps/frappe_cpcp/frappe_cpcp/tests/test_dedup.py`; one extra test `d05b` covers resolved-without-departure). D07, D08 and D17 are additionally proven under **real parallel HTTP** (`tests/concurrency/test_parallel.py`).
| AC | Test | Result |
|---|---|---|
| D01 three reports, one incident, one penalty | `test_d01_*` | pass |
| D02 report after claim does not steal claim | `test_d02_*` (+ parallel claim race) | pass |
| D03 5+ hours / clamped still attaches | `test_d03_*` | pass |
| D04 overnight + shift change, one penalty | `test_d04_*` | pass |
| D05 leave then reoffend = new episode (and payment / clamp removal are not evidence) | `test_d05_*`, `d05b` | pass |
| D06 other location / uncertain plate -> review, no merge | `test_d06_*` | pass |
| D07 competing officers promote -> one incident | `test_d07_*` + parallel | pass |
| D08 duplicate client operation idempotent, separate reports kept | `test_d08_*` + parallel (6 at once) | pass |
| D09 clamp/tow active shows one status, nothing new started | `test_d09_*` | pass |
| D10 tow + storage separate lines, retries idempotent | `test_d10_*` | pass |
| D11 resident precheck/ack leak nothing | `test_d11_*` | pass |
| D12 anonymous links with no correlators | `test_d12_*` | pass |
| D13 merge/split non-destructive, duplicate penalty flagged and credited | `test_d13_*` | pass |
| D14 repeat offenders count episodes, not allegations | `test_d14_*` | pass |
| D15 late allegation links without charge; new episode still possible | `test_d15_*` | pass |
| D16 dashboards/maps not inflated | `test_d16_*` | pass |
| D17 no cross-estate / cross-organization matching | `test_d17_*` + parallel cross-tenant | pass |
| D18 urgent second report raises priority, no bypass | `test_d18_*` | pass |

**Defects found by these tests and fixed:** (1) unique-index violations raise `UniqueValidationError`, not `DuplicateEntryError`, so race losers returned HTTP 500; (2) plain reads after a lost race used an older snapshot and missed the winner's rows (now locking reads); (3) a lock-order inversion between promotion and arriving reports caused InnoDB deadlocks (now ordered, plus bounded retry); (4) Frappe link validation used a plain read and could reject a just-committed allegation (internal inserts skip it after locking reads). Design: `docs/architecture/INCIDENT_LIFECYCLE.md`.

## Feature status
| Area | State |
|---|---|
| Copyright owner confirmed (Johnathan Lightfoot); NOTICE, README, CONTRIBUTING updated | Implemented |
| PRD v1.7 consolidated (`docs/spec/PRD_v1.7.md`) | Done |
| Incident consolidation, duplicate allegations, episode lifecycle, repeat offenders (PRD section 60) | **Implemented and verified** (above) |
| Domain core (authorization matrix, visits, notice clock, charges, triage, audit chain, geo, episodes, matching) | Implemented and verified |
| Frappe app: 31 DocTypes, permission hooks, registry / visitor / allegation / incident / communications / enforcement / reports APIs | Implemented and verified (integration + isolation + concurrency) |
| Contact resolution, dialer outcome capture, server SMS (mock adapter), HMAC callbacks, notice clock | Implemented and verified |
| Enforcement, itemized charges (one penalty per episode), appeals | Implemented and verified; **all legal gates OFF**, no live adapters |
| Dashboards, hotspot layers (verified vs unverified), thresholded resident summary, repeat-offender report | Implemented and verified (API) |
| Mobile app (gate, triage, verify with map pin, case/contact, resident reporting, consolidated reports, end-episode) | **Implemented, awaiting physical-device validation** (`docs/ANDROID_TESTING.md`) |
| Two isolated organization sites; cross-tenant isolation | Verified (HTTP) |
| GitHub CI (core tests, lint, DocType regeneration check, secret scan, web build, unsigned debug APK) | Passing at last push |
| Desktop management console | Not started |
| Backup/restore proof, SBOM / license CI, threat model, permission & sensitivity matrices (docs), app-store compliance matrix | Not started |
| Real SMS / voice / payment providers | Blocked: provider and authorization decisions |
| iOS archive; physical-device tests | Blocked: need macOS and your phone |

## Known limits
* Matching uses plate and location; OCR confidence and visit-session history are not yet inputs. Movement of a vehicle between prohibited spots is resolved by reviewer (`review_candidate`, merge).
* Resident report photos (and EXIF stripping) are not implemented yet; officer evidence photos are.
* The dev DB accumulates synthetic rows from the HTTP tests (unique plates per run).
* The PWA/web build cannot persist offline drafts (by design); native only.

## Blockers
* No JDK/Android SDK locally (Android builds run in CI). No macOS for iOS.
* Legal items: clamping/towing authority, Ghana DPA review, SMS/voice/payment provider terms, AI-authorship question (see `docs/legal/OWNERSHIP_AND_PUBLICATION_CLEARANCE.md`).

## Next
1. Desktop management console (React web, server-enforced authorization) including a case-review screen for merge/split.
2. Threat model, permission/sensitivity matrices, store-compliance matrix; SBOM and license CI; backup/restore proof.
3. Android device test with the owner; fix findings.
