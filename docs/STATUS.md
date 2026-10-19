# Status (verified results, blockers, next steps)
Updated 2026-10-19 (second session).

## Test results (last full run, 2026-10-19, after the v1.8 changes)
| Suite | Result |
|---|---|
| Core unit tests (pytest, no Frappe) | **88 passed** (includes the purpose rules in `core/pbac.py`) |
| Frappe integration on org-a: integration 22, comms/enforcement 14, reports 6, dedup (AC-D01..D18) 19, PBAC-01..20 + extras 22, **resident photos 5** | **88 passed** |
| Cross-tenant HTTP isolation (two sites) | **8 passed** |
| **Privacy over HTTP** (`tests/privacy`: Desk/REST/search/print/export, forged purposes, journal visibility, cross-tenant journals, device revocation) | **16 passed** |
| Parallel HTTP concurrency (6 scenarios; earlier repeated 40x = 240 runs with 0 failures) | **6 passed** |
| Mobile (vitest) + `tsc -b` + production build | **12 passed**, typecheck clean, build OK |

### PRD v1.8 acceptance tests (PBAC-01..PBAC-20)
All 20 are implemented and **pass** (`apps/frappe_cpcp/frappe_cpcp/tests/test_pbac.py`; PBAC-04/05/12/14/15/19/20 also over real HTTP in `tests/privacy`; PBAC-18 also in the mobile unit tests).
| PBAC | What is proven | Result |
|---|---|---|
| 01 | Unassigned/off-duty officer gets nothing and the denial is journaled; on-duty gate answers carry no names/numbers/history; bare unit lookups are rate-limited | pass |
| 02 | Off-shift, ended and **expired** shifts are denied and journaled | pass |
| 03 | Other estate, other gate, or a shift in another estate (officer assigned to both) is denied and journaled | pass |
| 04 | Desk lists, forms, autocomplete and routes for Person, Membership, Vehicle, Association, Visitor Session, Visit Event are closed to officers (DocPerm + hooks + request guard) | pass |
| 05 | Forged purpose, case id, gate id or unit never grant access | pass |
| 06 | Unit-first returning-visitor check-in still works (unit + plate hint -> confirm), minimum fields only | pass |
| 07 | An assigned case reveals only that case's masked contact actions; the number goes to the assignee only and is journaled | pass |
| 08 | A claim or another case cannot be used to look up an unrelated plate or unit | pass |
| 09 | Reassignment or closure revokes access immediately | pass |
| 10 | Allowed, denied and no-match are all journaled with the required fields; the hash chain verifies | pass |
| 11 | A denial survives exception + rollback; a journal outage **fails closed** | pass |
| 12 | Browse / search / suggestion / evidence / report / export / print paths are guarded and audited, including direct Frappe calls | pass |
| 13 | The journal holds no phone numbers, names, narratives, reporter identity or raw plates | pass |
| 14 | Officers cannot edit, delete or view access records or dashboards; auditors are read-only; managers see officer activity only | pass |
| 15 | Manager, admin and platform-Administrator access is journaled and visible to independent reviewers | pass |
| 16 | Break-glass: reason, one unit, short expiry, notified, independent review, daily cap, not transferable | pass |
| 17 | Review signals: scoped, idempotent, sent to reviewers and not the person, no automatic action | pass |
| 18 | No directory endpoint exists; suggestions capped at 3; device drafts refuse personal/directory data and expire (vitest) | pass |
| 19 | No cross-tenant disclosure: session replay and journals per site, over HTTP against both demo sites | pass |
| 20 | A revoked device or suspended user loses sensitive APIs immediately, even with a screen left open | pass |

**Defects found by these tests and fixed:** journal reads for rate limits could miss out-of-band commits (now a fresh connection); an empty case reference could match a record (now never); the request guard passed `purpose` twice; the outbox rejected reviewer roles; journal-based limits persisted into test reruns (fixtures now self-clean and use unique device ids). Design: `docs/security/PRIVACY_PBAC.md`. Matrix: `docs/security/PERMISSION_MATRIX.md` (generated from code, checked in CI).

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

### Other verified results
| Item | Result |
|---|---|
| **Backup and restore** (`bash infra/dev/backup_restore_check.sh`): back up org-a with private files, restore into a NEW site, compare | **RESTORE VERIFIED**: 21 doctype counts, access-journal chain (2026 rows), audit chain (1895 rows), ledger totals and the SHA-256 digest of the private file are identical. See `docs/deployment/BACKUP_RESTORE.md` for what is NOT yet proven |
| **Resident photos with EXIF stripping** | Fixture with EXIF GPS, camera make/model, timestamp, comment and a trailing script: none survive in the stored file; orientation applied; PNG alpha flattened; non-images, 7000x7000 bombs and a 4th photo rejected; a bad photo fails the whole report before any write; anonymous photos owned by Guest |
| **SBOM + licence policy** | 188 components (backend environment + mobile production) checked; policy OK with 16 reasoned exceptions (`docs/legal/license-exceptions.json`; 8 of them are 'metadata missing' entries a maintainer should confirm before redistributing any built image) |
| **Vulnerability scan** | npm production dependencies: **0 vulnerabilities**. **Python packages inside Frappe's pinned tree have OPEN advisories** (pyjwt, werkzeug, oauthlib, pypdf, weasyprint, pdfkit): not fixed, not exploitable through CPCP's own paths as far as assessed, must be resolved before any pilot. See `docs/security/DEPENDENCY_FINDINGS.md` |

## Feature status
| Area | State |
|---|---|
| Copyright owner confirmed (Johnathan Lightfoot); NOTICE, README, CONTRIBUTING updated | Implemented |
| PRD v1.7 consolidated (`docs/spec/PRD_v1.7.md`) | Done |
| Incident consolidation, duplicate allegations, episode lifecycle, repeat offenders (PRD section 60) | **Implemented and verified** (above) |
| Domain core (authorization matrix, purpose rules, visits, notice clock, charges, triage, audit chain, geo, episodes, matching) | Implemented and verified |
| **PRD v1.8 purpose-based access: shifts/devices, durable hash-chained access journal, request guard, access review + signals, break-glass, retention** | **Implemented and verified** |
| Frappe app: 35 DocTypes, permission hooks, registry / visitor / allegation / incident / communications / enforcement / reports APIs | Implemented and verified (integration + isolation + concurrency) |
| Contact resolution, dialer outcome capture, server SMS (mock adapter), HMAC callbacks, notice clock | Implemented and verified |
| Enforcement, itemized charges (one penalty per episode), appeals | Implemented and verified; **all legal gates OFF**, no live adapters |
| Dashboards, hotspot layers (verified vs unverified), thresholded resident summary, repeat-offender report | Implemented and verified (API) |
| Mobile app (gate, triage, verify with map pin, case/contact, resident reporting, consolidated reports, end-episode) | **Implemented, awaiting physical-device validation** (`docs/ANDROID_TESTING.md`) |
| Two isolated organization sites; cross-tenant isolation | Verified (HTTP) |
| GitHub CI (core tests, lint, DocType regeneration check, secret scan, web build, unsigned debug APK) | Passing at last push |
| Desktop management console (including the Access Review dashboard UI) | Not started (APIs ready) |
| Permission matrix (generated) and privacy/PBAC design docs | Done (`docs/security/`) |
| Threat model, app-store compliance matrix, backup/restore procedure, dependency findings | Done (`docs/security/THREAT_MODEL.md`, `docs/deployment/`); store matrix is PREPARATION only |
| SBOM + licence policy + audit + Dependabot in CI | Implemented (`supply-chain` job; workflow not yet seen running) |
| Resident report photos with EXIF stripping | **Implemented and verified**; mobile screens updated, awaiting device validation |
| Real SMS / voice / payment providers | Blocked: provider and authorization decisions |
| iOS archive; physical-device tests | Blocked: need macOS and your phone |

## Known limits
* Matching uses plate and location; OCR confidence and visit-session history are not yet inputs. Movement of a vehicle between prohibited spots is resolved by reviewer (`review_candidate`, merge).
* The dev DB accumulates synthetic rows from the HTTP tests (unique plates per run).
* The PWA/web build cannot persist offline drafts (by design); native only.

## Blockers
* No JDK/Android SDK locally (Android builds run in CI). No macOS for iOS.
* Legal items: clamping/towing authority, Ghana DPA review, SMS/voice/payment provider terms, AI-authorship question (see `docs/legal/OWNERSHIP_AND_PUBLICATION_CLEARANCE.md`).

## Next
1. Desktop management console (React web) including the Access Review dashboard and case review (merge/split).
2. Resolve the open Python advisories in staging; account deletion flow; tenant export/offboarding; external penetration test and MASVS review (G5 in the threat model).
3. Android device test with the owner; fix findings.
