# Community Parking & Compliance Platform (CPCP)
## PRD v1.8 Addendum — Resident Safety, Purpose-Based Access and Sensitive-Record Audit

**Date:** 19 October 2026  
**Status:** Proposed, mandatory security and privacy addition to PRD v1.7.  
**Applies to:** Frappe backend, desktop management console, React/Capacitor mobile apps, gatehouse, security workflow, SaaS organization sites, background jobs, reporting, and audit infrastructure.  
**Project copyright for original owned contributions:** Copyright © 2026 Johnathan Lightfoot. Apache-2.0 remains unchanged, with independent and third-party rights preserved.  
**Priority:** Security foundation, to be implemented before production deployment or provisioning real resident data. Compatible implementation can proceed in development while v1.7 incident deduplication is completed.

### 1. Objective and non-negotiable principle

Prevent casual, curious, retaliatory, or malicious browsing of resident and visitor information by any user, including otherwise authorized security personnel. **Possession of a security role is not, by itself, sufficient authorization to access a particular household's sensitive records.** Sensitive data access must be limited to the minimum necessary for a **server-verified, current operational purpose** and recorded in a tamper-evident access history. Protection applies equally to all residents, including vulnerable individuals, and does not rely on the officer's good intentions.

A logged-but-otherwise-unrestricted directory is **not** an acceptable implementation.

### 2. Threat model to address

- Officer searches Unit A2 out of curiosity and learns the occupant's identity, phone number, vehicles, guests, attendance, or patterns of movement.
- Officer uses the returning-visitor suggestion feature to reconstruct which vehicles regularly visit a household.
- Employee who is off shift, at the wrong gate, or assigned to another estate searches residents.
- Officer opens a real incident as a pretext to browse unrelated households or contacts.
- Officer with valid read access uses Frappe DocType list/record, report, search, export, API, mobile cached data or a background process to bypass the sanctioned workflow.
- Manager or administrator accesses sensitive records without a legitimate management purpose and avoids independent scrutiny.
- Failed/denied requests disappear from audit records because the same database transaction is rolled back.
- A lost or shared device exposes locally cached contact details, histories, GPS, or photographs.

### 3. Data classification and permissible disclosure

Classify at least the following separately, with default-deny rules:

1. **Public/aggregated:** community-level delayed statistics with small-cell suppression; never individual occupancy or movements.
2. **Operational minimum:** valid/invalid plate match; unit identifier; vehicle description and entry eligibility; minimal visit status.
3. **Sensitive personal:** resident and visitor names, contact numbers, household membership, visit history, personal photos, contact preferences.
4. **Restricted safety information:** granular in/out patterns, location history, emergency contact details, sensitive allegations and reporter identity.
5. **Restricted legal/finance/audit:** enforcement evidence, fines, appeals, privileged exports and access trails.

Prohibit routine display of resident names, household member lists, phone numbers, visitor history or occupancy patterns in general gatehouse searches. No general-purpose resident directory for security officers; no unrestricted visitor-history browser. Keep protected information out of push payloads and client logs.

### 4. Purpose-based authorization (PBAC) layered over RBAC

The server must evaluate all of the following **for each sensitive request**: organization and estate isolation; active individual user account; current role; current shift/gate or authorized assignment when applicable; requested capability; targeted record; **verifiable operational purpose and active case/visit/work-item reference**; field-level disclosure; and any necessary time-limited approval. Never trust a client-supplied purpose string, case ID, or unit ID as sufficient proof. Validate the referenced record and its relationship to the user, role, target and stage.

Permitted normal purposes:

- **Gate check-in / checkout:** A legitimate, active gate workflow by the on-duty officer. Unit-first entry remains fast, but exposure must be minimal; do not return a full resident directory or complete visit history merely from entering a unit. Prefer unit + observed plate (camera scan or partial/manual plate), matching a pre-approved visit, or other low-friction second discriminator. Return one or a minimal set of relevant candidates without resident names. Historical candidate lists must be constrained, rate-limited, audited and carefully reviewed for privacy.
- **Assigned allegation/incident:** Officer must hold a valid claim/assignment to the case, and the vehicle-to-unit/host relationship must be verified server-side. Present only actionable contact methods and fields needed to resolve the case.
- **Contact host/responsible person:** Where possible, expose a server-mediated **Call Host** or **Send SMS** action rather than general raw contact details. If the app launches the native dialer and necessarily exposes a number, disclose that limitation explicitly; do not promise contact-number confidentiality in that mode.
- **Supervisor investigations / corrections:** Scoped access to a specific approved investigation, appeal, safety concern or record correction, with reasons and approvals as applicable.
- **Emergency access (break-glass):** Only for genuine time-sensitive safety events; scope to the relevant estate, household/incident, and minimum fields; require a recorded reason, short expiry, conspicuous log and supervisory review. Do not let break-glass become a general-purpose bypass.

Generic dropdown selections or self-declared reasons do not grant access on their own. If there is no legitimate, active record or workflow, deny the request rather than merely logging it.

### 5. Access-control implications for the existing code

Review and refactor these existing paths (names are current as of the Oct 19 snapshot):

- `apps/frappe_cpcp/frappe_cpcp/core/authz.py`: estate-scoped `resident_registry` and `visitor_log` permissions currently permit broad `R` access to security officers. Introduce purpose- and resource-scoped capability decisions.
- `apps/frappe_cpcp/frappe_cpcp/permissions.py`: `has_permission`, `permission_query_conditions` and Frappe Desk direct-DocType access must not accidentally permit list browsing or direct record access that bypasses a purpose check. Deny general-purpose browsing to ordinary officers; route protected lookups through dedicated APIs.
- `apps/frappe_cpcp/frappe_cpcp/api/registry.py`: `lookup_plate` and `lookup_visits_for_unit` currently log minimal lookups, but must also require and validate a gate, case or supervisor purpose and limit returned fields.
- `apps/frappe_cpcp/frappe_cpcp/services/audit.py`: improve sensitive-access logging so it covers all approved and denied access paths, and persists reliably on authorization failure.

Changes should preserve legitimate rapid gatehouse check-in, visitor checkout, resident-vehicle contact and case investigation. Do not break v1.7 incident linking/concurrency safety.

### 6. Mandatory access-event journal

Every actual or attempted sensitive operation, including **success, denial and no-match results**, must be recorded at the point of access. Cover single records, record lists, search/autocomplete, sensitive report generation, downloads/exports, print, bulk APIs, data corrections, emergency overrides, contact reveals, and sensitive evidence access. Avoid treating navigation events or ordinary aggregate metrics as equal to individual-record exposure.

At minimum record:

- Server timestamp in UTC; authenticated individual actor ID; active role and organization/estate scope.
- Authenticated session and pseudonymous device/workstation identifier, when legitimately available; duty shift and gate or assignment.
- Action and requested capability (search, view, contact, history, export, etc.).
- Target unit/vehicle/visit/case **identifier or safely derived token**, where available; for textual searches store a one-way hashed/normalized term rather than raw resident details.
- Validated purpose and its associated work-item/visit/incident ID (or failed-purpose reason).
- Decision: allowed, denied, no-match, or emergency grant; reason code; field category or disclosure level; correlation/request ID.
- Any supervisor grant and subsequent review outcome.

Do **not** copy full contact numbers, visitor names, report content, photos, or other sensitive source data into the logs. Protect audit access from security officers and unaudited administrators. Configure retention, access review, and deletion under a documented privacy schedule, with appropriate legal review.

**Durability:** Never silently lose denied-access events because an HTTP exception rolls back the main Frappe database transaction. Design a transactional/out-of-band durable audit approach and test rollback behavior. If the mandatory audit mechanism is unavailable, fail closed for sensitive access, except for a narrowly defined and independently recorded emergency process.

### 7. Detection, oversight and accountability

Create an **Access Review** interface for appropriately authorized association management, privacy/safety reviewers and auditors (auditors read-only). A security officer must not be able to remove or amend their own access traces. Independent reviewers must be able to investigate access by security managers and association admins too.

Surface actionable anomalies such as:

- Searches outside assigned shift, gate, estate or case.
- Multiple different units or households accessed within a short period.
- Repeated lookups of the same household without case/visit justification.
- High-volume suggestion/history searches, bulk exports, repeated denied lookups.
- Contact/identity reveals with no successful matching operational workflow.
- Emergency break-glass requests or grants.

Thresholds should be configurable, privacy-preserving and resistant to false positives. Alert designated reviewers, not the person being investigated. An alert is a review signal, not proof of misconduct. Establish a fair documented investigation and response process.

### 8. User experience for officers and residents

- Officers should see purpose-focused screens: **Check In**, **Check Out**, **My Assigned Cases**, **Contact Host**—not **Browse All Residents** or **Visitor History**.
- On-duty gate check-in should require few taps. Context and purpose should be automatically drawn from the validated workflow, without repeated form typing.
- A valid assigned case should let the officer resolve it efficiently, including contacting an authorized host without opening the household's complete profile.
- Residents must not access other households' sensitive records or audit trails. Resident views of their own household data, and any optional privacy/access-history request, require carefully scoped authentication and privacy review; do not automatically disclose investigative details.
- The UI should clearly tell staff that access to sensitive information is recorded, without implying that logging replaces access restrictions.

### 9. Mobile, offline and SaaS safeguards

- No bulk resident directory, visitor history or sensitive exports on ordinary security devices.
- Cache only the minimum workflow-specific data needed for approved offline actions, with encrypted device storage, short lifetimes, explicit sync conflict rules, sign-out/session expiry cleanup and lost-device revocation. Never treat stale offline data as authority to reveal new sensitive details.
- No passwords, full phone numbers, personal details, photos or identities in push notifications, analytics SDK events, crash diagnostics or ordinary logs.
- On-duty/assigned status and access grants must expire on the server; app navigation hiding does not constitute authorization.
- Preserve per-organization Frappe site isolation; management companies administering multiple estates must only reach organizations/estates they are explicitly assigned to.
- Review records, rights, audit retention and lawful processing requirements for Ghana and future jurisdictions before real customer data is introduced.

### 10. Required tests (PBAC-01 through PBAC-20)

- **PBAC-01:** Unassigned officer searches an arbitrary unit: no resident names, numbers or visit history returned; denied attempt logged.
- **PBAC-02:** Off-shift officer tries a sensitive lookup: denied and logged.
- **PBAC-03:** Officer at Gate A attempts access to another estate/gate without assignment: denied and logged.
- **PBAC-04:** Normal officer's Frappe Desk DocType list and detail routes cannot browse `CPCP Person`, vehicle association, visitor session, memberships or history without server-verified purpose.
- **PBAC-05:** API and direct request attempts with a forged `purpose`, `case_id` or `gate_id` do not grant access.
- **PBAC-06:** Legitimate unit-first returning-visitor check-in still works quickly and returns only minimal necessary candidate data.
- **PBAC-07:** Plate/case lookup for officer's active assigned violation reveals an authorized contact action but not unrelated household data.
- **PBAC-08:** Claimed work item cannot be used to look up an unrelated unit or plate.
- **PBAC-09:** Case re-assignment or closure revokes unnecessary access and invalidates stale grants/tokens.
- **PBAC-10:** All allowed, denied and no-match sensitive searches have reliable access-event entries with server time, actor, role, scope, target/purpose references, decision and request ID.
- **PBAC-11:** Audit of a denied lookup survives an API exception and DB rollback.
- **PBAC-12:** General browse/search, suggestion lookup, evidence fetch, sensitive report, export and print paths are guarded and audited, including unauthorized direct Frappe calls.
- **PBAC-13:** Audit entries contain no raw contact data, reporter identity, personal photos or unnecessary PII.
- **PBAC-14:** Ordinary security officers cannot edit/delete access records, erase denials or view unrestricted access-review dashboards.
- **PBAC-15:** Security-manager and association-admin sensitive access is also subject to review and log coverage.
- **PBAC-16:** Emergency break-glass has required scope, reason, limited lifetime and independent review; no unlimited bypass.
- **PBAC-17:** Excessive distinct-unit lookups and repeated targeted lookups generate correctly scoped reviewer alerts, with reasonable controls against false positives.
- **PBAC-18:** Offline device cannot reveal entire registries, and local sensitive data is protected and expires/wipes as specified.
- **PBAC-19:** No cross-tenant disclosure through desktop, mobile, API, exports, logs or background jobs; negative tests against both demo sites.
- **PBAC-20:** A device/session revoked during or after a shift can no longer use sensitive lookup APIs, even if screens or cached session data remain open.

### 11. Definition of done and handoff

This addendum is complete only after: architectural mapping to concrete entry points; threat model and data classification updates; implemented server-side purpose checks; all 20 tests (or documented defensible test decomposition) passing with integration coverage; audit-retention and review plan; Android test plan updates; and an accurate `docs/STATUS.md`. Protect against regressions to previously passing gate, allegation, deduplication and tenant-isolation tests. All code and public docs must be secret-scanned and kept free of genuine resident/customer data. Do not activate live enforcement or deploy production without separate authorization. Integrate this as the next cumulative PRD version rather than replacing v1.7.
