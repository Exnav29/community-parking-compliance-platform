# Threat model (living document; PRD 15, 25.3, 61.2)

Scope: Frappe backend per organization site, React/Capacitor mobile apps, desktop console (planned), SaaS control plane (skeleton). Method: asset -> actor -> abuse case -> control -> evidence (test) -> residual risk. "Evidence" names a test that currently passes unless marked **gap**.

## Assets (by sensitivity)
Resident/household identity and contacts; visitor movements; vehicle-to-household links; reporter identity (identified reports); anonymous-report unlinkability; evidence photos and GPS; enforcement ledger and appeals; the access journal itself; per-site secrets; device sessions.

## Actors
Curious or retaliatory insider (security officer); compromised or malicious manager/admin; resident abusing the report channel; outsider guessing endpoints; lost/shared phone; other tenant; platform operator; malicious contributor/dependency.

## Abuse cases
| # | Abuse case | Controls | Evidence |
|---|---|---|---|
| T1 | Officer browses units out of curiosity | No standing registry/visitor-log permission; gate answers need a live shift, return <= 3 plate-level candidates, no names/numbers/dates; plate-hint narrowing; hourly ceilings; journal + review signals | PBAC-01, 02, 06; `test_pbac01b` |
| T2 | Officer uses returning-visitor suggestions to reconstruct a household's visitors | Capped, undated, no counts; bare lookups have a stricter ceiling and raise a signal | PBAC-06, 17 |
| T3 | Off-shift / wrong gate / wrong estate officer | Shift, gate, estate, device and account re-checked server-side on every call; shift expires on the server | PBAC-02, 03, 20 |
| T4 | Real case used as a pretext to browse | Case access only for the current assignee, only the case's own plate/unit; reassignment or closure revokes immediately | PBAC-07, 08, 09 |
| T5 | Bypass via Frappe Desk, REST, autocomplete, export, print | No DocPerm for officers; `permissions` hooks; request guard names every sensitive doctype; export/print denied for all roles | PBAC-04, 12 (+ HTTP) |
| T6 | Manager/admin snooping | Allowed for administration but always journaled; independent reviewers (auditor, org admin; managers see only officers); privileged-volume signal | PBAC-15, 17 |
| T7 | Denied attempt erased by rollback | Journal on a separate connection, committed at once; fail closed if unwritable; hash chain; append-only model | PBAC-10, 11, 14 |
| T8 | Journal tampering | Hash chain + `verify_chain`; purge only via a contiguous, anchored retention job | PBAC-10; `test_retention_*` |
| T9 | Break-glass abuse | One unit, contacts only, <= 60 min, 3/day cap, reason, instant notification, independent review, overdue-review signal | PBAC-16, 17 |
| T10 | Lost phone / shared device / stolen credentials | `revoke_device`, `suspend_user`, session clearing; offline drafts hold no directory data, expire in 72 h, wiped on sign-out; native keystore | PBAC-18, 20 (+ HTTP) |
| T11 | Duplicate reports inflate penalties or start parallel enforcement | Episode identity (unique active key), single claim, live-action uniqueness, idempotent charges | AC-D01..D18, concurrency x40 |
| T12 | Race conditions (simultaneous reports/claims/promotions) | Unique-key find-or-create, locking reads, lock order, deadlock retry | `tests/concurrency` |
| T13 | Anonymous reporter deanonymised by the system | Separate unauthenticated path, no session/IP/device stored, `assert_anonymous_clean`, photos stripped of EXIF **before** persistence, receipt secret stored only as scrypt hash | `test_d12`, `test_photos` |
| T14 | Hostile image upload | Magic-byte check, size and pixel caps, full re-encode (drops polyglot/trailing bytes), private storage, hash verification on read | `test_photos` |
| T15 | Cross-tenant access | Site-per-organization; session replay and Host swap fail; journals per site | isolation (8) + PBAC-19 HTTP |
| T16 | Fine/clamp/tow/payment activated without authority | Legal flags default OFF, need approval reference; release/cancel never payment-gated; emergency never clamped | AC-19, enforcement tests |
| T17 | Provider webhook forgery/replay | HMAC per site, idempotency key, monotonic status | comms tests |
| T18 | Supply-chain compromise | SBOMs, licence policy, Dependabot, secret scanning, pinned actions policy | CI; **open advisories** in `DEPENDENCY_FINDINGS.md` |
| T19 | Reporter identity misuse by staff | Manager-only reveal with reason, journaled; hidden by default | `test_reveal_reporter_*` |
| T20 | Notification leakage | Minimal payloads (no plate/phone/name/unit) | outbox payload tests |

## Residual risks and gaps (honest list)
* **G1** An on-duty officer legitimately gets small gate-level answers for any unit of their estate; mitigated by minimisation, ceilings, journaling and review, not eliminated.
* **G2** Database administrators can alter rows; detection (hash chain) rather than prevention. Deployment must separate roles, encrypt backups and restrict DB access. **gap: not yet in infrastructure templates.**
* **G3** The native dialer exposes the dialled number to the assigned officer's phone; provider-mediated calling is not enabled.
* **G4** Upstream Python advisories in Frappe's dependency tree are open (see `DEPENDENCY_FINDINGS.md`).
* **G5** No external penetration test, MASVS assessment or device-level security test yet. **gap**
* **G6** GPS spoofing and photo authenticity: client data is treated as an observation, never proof; officer verification is required.
* **G7** Desktop console not built; when it is, it must reuse these APIs and add no direct-DocType listing of sensitive records.
* **G8** TLS, WAF, CDN and proxy logging for the anonymous route are a deployment concern; until reviewed, the UI label stays "Confidential" (`anonymous_label_verified` = 0).
* **G9** Rate limits for the anonymous route are per-estate buckets only (no per-person tracking by design), so a determined outsider with the community code can fill the bucket.
