# Community Parking & Compliance Platform (CPCP)
## Product Requirements Document — Version 1.7 — Public Open-Source Repository, Community Development & Incident Consolidation Edition

**Date:** 19 October 2026 (v1.7 consolidation)  
**v1.7 note:** This file is the consolidated authoritative specification: all of v1.6 is preserved verbatim below, and **Section 60** (the Incident Consolidation, Duplicate Allegations and Repeat-Offender Lifecycle addendum, acceptance tests AC-D01..AC-D18) is appended. Where Section 60 conflicts with any earlier rule that uses a fixed plate-and-time window to decide whether reports describe the same event, Section 60 prevails. Copyright (c) 2026 Johnathan Lightfoot.  
**Status:** Proposed implementation specification for Claude; public **source-code** publication is authorized subject to mandatory ownership, license, privacy and secret-scan gates. Production deployment, real enforcement and app-store publication remain subject to separate authorization, jurisdiction review and store acceptance. Version 1.6 supersedes v1.5, retains AC-1 through AC-120 and all prior requirements, and introduces a public Apache-2.0 open-source delivery and governance model. **CPCP** is an internal working title only; no commercial name or trademark is adopted.  
**Product type:** Multi-organization, configurable B2B SaaS for residential-estate, HOA, condominium, and gated-community parking, access, and enforcement management  
**Primary market / reference deployment:** Ghana residential estate; designed to be localized for other jurisdictions  
**Proposed stack:** Frappe Framework custom application and isolated organization sites; centralized SaaS provisioning/control plane; responsive desktop web console; shared React/TypeScript mobile client with Capacitor-produced iOS and Android applications plus PWA fallback; MariaDB as Frappe's primary production database; Frappe Insights for BI where practical; Leaflet/GeoJSON for estate maps and heatmaps. Capacitor is the recommended candidate, subject to Phase 0 native-device proof of concept and licensing/security review.

---

## 1. Assignment to Claude

This is a **design, implementation, testing, and staging-verification assignment**, not an assessment-only or mockup-only exercise. Build a usable, production-quality custom application on the Frappe Framework. Prioritize reuse of mature Frappe capabilities and maintained open-source libraries over reinventing authentication, forms, permissions, workflows, invoicing, reporting, or maps.

Claude must:
1. Verify the supported Frappe version, dependencies, library licenses, deployment target, and existing infrastructure before coding.
2. Produce a short technical architecture and entity-relationship model, then implement vertical slices in the sequence in section 20.
3. Establish and maintain a **PUBLIC GitHub source repository** (`Exnav29/community-parking-compliance-platform` proposed, subject to verified ownership and repository-name availability), after passing the ownership, third-party licensing, privacy and secret-removal gates in Section 55. Publish only project-owned or authorized code and safe synthetic test data. Commit all application source and approved build/development artifacts to Git throughout development; push tested work to GitHub at each meaningful milestone. NEVER publish resident/visitor records, credentials, keys, production configuration, private evidence, photographs, backups or customer-specific data. Use **Apache License 2.0** for code authored under the project, subject to final ownership clearance.
4. Implement real data persistence, workflows, API validations, mobile and desktop user interfaces, tests, demo data, and documentation; no fake buttons or placeholder features represented as working.
5. Build and verify in an isolated development/staging environment; **do not activate live clamping, towing, charge collection, public registration, or production deployment without explicit authorization** and locally verified legal authority.
6. Produce an evidence-based handoff, including implementation status, screenshots, test results, unresolved dependencies, and a production readiness checklist.

Do not silently substitute a simplistic parking-space reservation app, spreadsheet, generic ERP screen, or static mockup for the product described below.

## 2. Executive Product Vision

Create a configurable, multi-organization SaaS platform for managing the relationships among **estates, units, residents, vehicles, visitors, parking zones, security officers, parking violations, evidence, warnings, clamping, towing, storage, fees, appeals, and compliance reporting**.

The product is built around one principle: **the goal is voluntary parking compliance and safe access, not fine revenue**. Ordinary violations should normally be identified, documented, communicated, and given a reasonable opportunity for correction before penalties. Safety-critical obstructions require immediate, lawful resolution rather than immobilization in place.

Desktop users manage records, policies, approvals, billing, disputes, maps, and analytics. Gatehouse and roaming security officers use a fast, mobile-first interface with camera, GPS, plate lookup, check-in/check-out, incident capture, and status updates. Authorized residents can submit **identified or anonymous suspected parking violation reports** to a security-only triage queue, request changes to their own household vehicles, see the status of their own reports, respond to their own verified incidents and submit appeals through a limited self-service portal. They **cannot browse the permanent resident registry or visitor log**.

### Product success outcomes
- Reliable, searchable, historical records of units, residents, vehicles, visitors, and violations.
- Security can identify who to contact for a plate within seconds, with proper authorization.
- Ordinary incidents can be resolved through documented warnings before fees are imposed.
- Safety obstructions can be escalated immediately, with evidence and oversight.
- All clamping, towing, impound, storage, invoice, payment, release, and appeal activity reconciles to a **single incident ID**.
- Management can see trends, repeat violations, compliance rates, and **GPS-based hotspot maps** at estate-road and zone level.
- Independently managed associations can subscribe to the same SaaS product, with strong tenant isolation, independent admins, configurable policies/forms/fees/branding, and centralized provisioning without rewriting application code.
- One shared branded mobile application can serve authorized users across organizations, with App Store, Google Play, and Samsung Galaxy Store submission readiness designed and tested from Phase 0.
- Role-specific resident, security officer, security manager, management, finance and auditor experiences use one audited authorization service; residents may **report concerns**, but only authorized security may **verify and open enforceable incidents**.

## 3. Boundaries, Decisions, and Assumptions

### Required in initial usable release
1. Estate setup, buildings/blocks/roads/units/zones and configurable rules.
2. Permanent resident and unit directory with historical occupancy and contact records.
3. Resident vehicle registration and lifecycle.
4. Visitor/contractor vehicle entry and exit register; host/unit association.
5. Mobile plate search and incident capture including photograph and **location snapshot plus map pin confirmation**.
6. Documented notification and warning process; customizable default **15-minute grace period** for ordinary violations.
7. Immediate-obstruction incident type and supervisor escalation.
8. Authorized clamping/towing/impound lifecycle and itemized penalty, towing and storage ledger.
9. Resident response/appeal process and audit trail.
10. Desktop graphical dashboards, downloadable reports, and estate hotspot map.
11. Role-based access, event logging, backups, staged deployment, automated test coverage.
12. SaaS organization onboarding and provisioning, tenant isolation, independent policy/fee/form configuration, plan entitlements and metering.
13. App-store-ready mobile architecture and distributable **iOS and Android native project builds** with camera, GPS, secure login, push notification handling and offline incident drafts. A web-only PWA is not sufficient.
14. Explicit role-based access control plus organization/estate/unit/record scoping, separate resident concern reporting and security verification, tightly controlled resident/visitor log access, security alert routing, read-only auditing and tested authorization on every API, file, dashboard and export.

### Configurable reference defaults, not universally applicable law
- Locale: Ghana; currency GHS (display **GH₵**); timezone **Africa/Accra**.
- Example standard violation penalty: **GH₵500**.
- Ordinary warning grace period: **15 minutes following verified notification**, not automatically 15 minutes after an unanswered call.
- Towing and storage: separate configured or verified provider amounts; **do not invent default fees**.
- Clamping and towing: methods of enforcement, not two automatic copies of the same parking penalty.
- Fine assessment, immobilization, towing, impound release, and mandatory payment are **disabled pending association approval and jurisdiction-specific legal signoff**.

### Explicit design choices
- Start with one estate pilot, but build an operational **SaaS foundation in v1**: organization signup/invitation, tenant provisioning, roles, plan entitlements, feature flags and safe independent configuration.
- Prefer **one isolated Frappe site per subscribing organization** as the default tenant boundary. An organization may administer one or multiple estates inside its own site, with per-estate scoping and inherited/overridden policies. Prove database/file/backup isolation and tenant-safe routing; do not treat Frappe Role Permissions alone as a sufficient cross-customer boundary.
- Use a custom Frappe app (DocTypes, server-side methods, workflows, reports), not a fork of core Frappe.
- Use a single shared **React/TypeScript application for mobile/security and optionally resident experiences, packaged via Capacitor to produce native iOS and Android apps** for Apple App Store, Google Play and Samsung Galaxy Store; support an installable PWA as a supplementary channel. Maintain a distinct desktop web management experience. Include Xcode/macOS or approved macOS CI in the build plan.
- **Do not submit a thin WebView wrapper.** Make native camera, explicit GPS capture, secure storage, system notifications and robust offline drafts real and useful. Native builds and submission assets are required in the delivery gates; publication requires developer accounts and separate approval.
- Frappe Insights can supply charts and dashboards; a **custom Leaflet/GeoJSON incident map and hotspot layer** is required for local estate geography, since country-level BI map types do not solve this use case.
- Mobile location access must be permission-based and event-triggered. **No continuous officer, resident, or vehicle tracking**.

## 4. Personas, Roles and Permission Principles — Mandatory v1.2

The system requires purpose-built user experiences and enforceable permissions, not merely different menus. **Default deny, least privilege, named user accounts, explicit organization/estate/household scope and backend authorization are mandatory.** Detailed actions and test cases appear in sections 28–32; those sections prevail over looser language inherited from v1.1.

| Role | Operational purpose | Data boundary and non-negotiable restrictions |
|---|---|---|
| SaaS Platform Administrator / Operator | Provision subscribing organizations, subscriptions, deployment, health and support | No routine tenant personal data, private registry, visitor log, case evidence or financial detail. Audited emergency-access process only. |
| Association Owner / Organization Administrator | Manage their organization's policies, estates, contracts, administrators, settings and oversight | Full authorized **organization** scope, not all SaaS tenants; immutable audits and legal enforcement gates cannot be overridden. |
| Management Company Administrator | Operate assigned organizations or estates: staff, registry, security, reporting, finance and configurations | Broad operational access **only under explicit delegated management contracts and scoped role grants**; no implicit access to other customers. Sensitive actions remain approval- and audit-controlled. |
| Estate Manager / Delegated Manager | Administer assigned estates and operations within organization-defined limits | No unauthorized cross-estate access or ability to alter organization-wide legal/safety controls. |
| Security Manager / Supervisor | Manage officers, both private registries, review resident reports, approve eligible enforcement and operational reports | Assigned estates only; cannot secretly remove evidence or adjust policy/fee tables; prevent self-approval and conflicts. |
| Security Officer | Check vehicles and visitors, access the two registries for duty, contact associated households, investigate resident reports, verify violations, capture evidence, issue approved warnings and execute authorized actions | Only assigned estates/shifts and legitimate operations; cannot change fees, approve disputed own cases, bulk export private registries or browse out-of-scope households. |
| Resident / Household Member | Submit suspected violations, check own reports, view approved anonymized community reports, request changes to own vehicles, respond/appeal own incidents | **No read/search/list/export access to the permanent resident/vehicle registry or visitor log**, even for their own unit; limited self-service projection of their own vehicle submissions is separate from those logs. |
| Auditor | View authorized read-only dashboards, approved records and immutable audit history | Cannot file concerns/violations, call residents, mutate data, approve actions, issue fines, change settings or export underlying PII by default. Special access to sensitive logs requires separately approved, expiring audit grant. |
| Finance Officer | Manage authorized charges, receipts, payment reconciliation, waivers/refunds with approvals and finance reporting | Minimum case/party information, no general visitor log access, no incident verification or enforcement authorization. |
| Association Board Observer (optional) | View approved strategic dashboards and board reports | Aggregated, redacted reports only unless separately delegated. |
| Towing / Impound Contractor (optional) | Fulfill assigned removal and storage tasks, provide receipts and confirmation | Only assigned jobs and minimum necessary data; never tenant-wide directories, appeals adjudication or fee policy changes. |

**Mandatory split:** A *resident concern* is a separate unverified object; a *verified violation incident* is an official case created or verified by an authorized security officer, with normal legal and policy gates. A resident's submission must never start a fine, warning countdown, tow, clamp, or payment request automatically. Management may supervise the process but must not be able to remove the audit trail.

**Authorization checks apply to desktop, Android, iOS, PWA, APIs, webhooks, background jobs, file downloads, analytics drill-through and exports.** A hidden button is not security. Access scope is bound to authenticated user membership and delegated grants, never to a user-supplied tenant ID, unit ID, or device flag. Deny-by-default when a membership is expired, suspended or ambiguous.

## 5. Core Entity and Relationship Model

Implement explicit linked Frappe DocTypes and migrations, with appropriate indexes, uniqueness rules, archival instead of destructive deletion, and effective-date history.

| Entity / DocType | Key attributes | Relationships |
|---|---|---|
| Organization / SaaS Tenant (control plane) | opaque tenant ID, display name, provisioning status, billing plan, trial/end dates, region, legal authority flags, primary admin | Owns isolated site; SaaS services and zero/minimal PII metadata only |
| Estate | id, organization site, name, address, jurisdiction, timezone, currency, map boundary, status | Owns units, roads, zones, config and users |
| Organization Configuration / Branding | tenant/site, display name, logo/theme, contacts, locale, modules, form-pack version, approved effective policy version | Organization, per-estate override references |
| Custom Field Definition | tenant/estate scope, target form, field code/type/label, validation, visibility, retention/sensitivity, required/optional, version | Form schema with structured values, versioned; no executable fields |
| SaaS Entitlement / Meter | organization, plan/feature, period, usage, limits, grace/suspension state, immutable events | Isolated from resident penalty accounting |
| Road / Zone | zone ID, type, restriction, geofence/polygon, signage, capacity, active dates | Estate; incidents; parking spaces |
| Building / Block | identifier, estate, address/label | Houses units |
| Unit | immutable id, display unit no., block, occupancy status, contact route | Residents, visitor sessions and registered vehicle links |
| Person / Resident | permanent person ID, name, authorized contact methods, active/inactive, privacy notice status | Memberships in one or more units, vehicle custodianship |
| Role Assignment / Delegated Access | user, organization/estate/unit scope, role, permission bundle, approved by, start/expiry, employment or management contract basis | Explicit grants; no cross-tenant inheritance |
| Resident Concern / Suspected Violation | immutable report ID, reporter identity (private), submitted plate text/description, location/photos, priority, triage status, created time | Security queue; may link to verified incident; distinct from enforcement case |
| Security Alert / Triage Assignment | resident concern ID, assigned estate/team/officer, urgency, notification/delivery status, acknowledgement, due time | Operational security inbox; supervisor escalation and handoff |
| Unit Membership | unit, person, owner/tenant/occupant/authorized host, start/end, verified by | Time-bounded relationships; multiple persons per unit |
| Vehicle | immutable vehicle ID, normalized plate, country, make, model, color, status | Resident registrations, visitor visits, incident records |
| Vehicle-Unit Association | vehicle, unit, permitted driver/custodian, role, start/end, status, evidence | Historical many-to-many relationship |
| Visitor Session | immutable session ID, minimal visitor identity if needed, vehicle/plate or no-vehicle mode, host unit, entry and departure UTC times, entry/exit gate and officer, authorization mode, occupancy/status, offline/sync timestamps, correction trail | Separate time-bounded visits; never a resident access record or permanent authorization; cross-gate checkout supported |
| Parking Rule | estate/zone, violation category, effective date, ordinary/emergency, warning rules, enforcement eligibility | Governs incidents; versioned policy |
| Violation Incident | immutable case ID, vehicle/plate snapshot, unit link if known, rule version, classification, status, officer, timestamps | Central parent of all activity below |
| Evidence | incident, photos, image integrity hash, time captured, GPS snapshot, uploader | Immutable originals with controlled viewing |
| Location Observation | device latitude/longitude, accuracy m, timestamp, source, officer confirmation, corrected vehicle pin, zone | Incident/evidence; immutable raw plus auditable correction |
| Contact / Notice Attempt | incident, channel, recipient reference, queued/sent/delivered/answered/acknowledged/failed, time | Determines if/when grace begins |
| Enforcement Action | incident, warning validation, approval, action type, operator, timestamps | Clamp, tow, cancellation, release, each with audit |
| Tow Job / Impound Record | provider, driver/truck, dispatch, collection photos, destination, yard arrival, release, storage period | Incident and vehicle; provider receipts |
| Fee Schedule | effective from/to, category, currency, rate, authorization and legal eligibility | Governs invoice calculation with versioning |
| Incident Charge | incident, charge class, quantity, unit price, source/provider, period, tax if applicable, approval | Once-only penalty, tow, storage, credit, adjustment |
| Invoice / Payment / Refund | identifiers, provider refs, status, amount, receipts, reconciliation | One or more charges; accounting audit |
| Appeal / Decision | incident, reason, attachments, appeal state, independent reviewer, outcome | Adjustment/refund/release as appropriate |
| Audit Event | actor, role, action, entity, before/after reference, time, reason, request ID | Append-only, scoped, retained and exportable |
| Sensitive Record Access Event | actor, role, estate, record type/ID, access reason/context, timestamp, result, API/request ID | Immutable log of registry lookup, visitor log read, attachment access and approved exports |
| Controlled Export / Auditor Access Grant | authorizer, recipient, scope, purpose, expiry, field masking, file token, download events | Time-limited access to specific approved reports or evidence; not blanket permissions |

**Critical relationship rules:** A resident concern may exist with no confirmed violation; security may verify a concern into **one linked violation incident** or close it as unsubstantiated. Unit, person, vehicle and visitor links must never be inferred from unverified free-text plates alone. One unit has many people and vehicles; one vehicle may be associated with multiple authorized units over time; visitor records are not permanent resident registrations; historical incident plate/unit/contact snapshots must remain accurate even when ownership changes; a violation may initially reference an unidentified vehicle and be linked later without overwriting its original observations. Plate alone is not a permanent identity and can be reused or mistyped. Duplicate active registrations and overlapping ownership associations require conflict resolution. Avoid exposing PII in report exports by default.

## 6. Administration: Estate, Resident, Unit and Vehicle Records

### 6.1 Estate setup
- During initial organization setup, authorized association owners configure their tenant independently (subject to section 24 controls); they must not require the platform operator to edit source code for routine policy changes.
- Admin creates estate profile, locale/currency/timezone, policy and fee schedule, gate(s), block(s), roads, parking zones, prohibited locations, parking spaces, emergency access corridors and map outline.
- Supports uploading an estate/site plan and calibrating/aligning it with a map if satellite/street imagery is inadequate.
- Define roles, staff, approval limits, contacts, visitor procedures, penalty/impound legal activation flags, and notification templates.
- Import existing units/residents/vehicles from validated CSV templates with dry-run preview, deduplication and rollback strategy.

### 6.2 Permanent resident register
- Create person records, associate with one or more units, set ownership/tenancy/occupancy/authorized-host status and effective dates.
- Capture only needed name, unit, phone/contact preferences, relevant emergency contacts where justified; do not require national ID or sensitive personal information as a default.
- Search by unit, occupant name (privileged), authorized phone, registered plate; mark records inactive, preserve history and audit changes.
- Unit history survives move-in, move-out, and changes to household/vehicle composition.

### 6.3 Resident vehicle registration
- Security or authorized residents can initiate registration; require unit and plate, relevant vehicle description and proof/verification as configurable.
- Officer can search normalized plate, confirm correct record, propose association, issue/print QR-coded parking permit if enabled. QR codes carry only opaque IDs, not personal information.
- Unit representative may request new vehicle/edit information; verify before activation under configured policy.
- Support revocation, expired permits, staff review, visitor mistaken for resident, plate change and reassignment with history.

### 6.4 Visitor / contractor log
- Fast security form: plate, vehicle category, host unit, purpose/category, entry time, optional minimum visitor name/contact, expected departure when appropriate, gate and recording officer.
- Link to existing vehicle record when known without automatically granting resident privileges or disclosing household details.
- Check in, mark temporary permission, notify host if configured, record check-out; exceptions for no vehicle, ride-hailing, delivery and emergency services.
- Visitor information collection must be proportionate and subject to privacy notices and retention policy; avoid compulsory capture of national ID or unnecessary identity documents.
- Gate screen must operate in a few taps and support fast plate reuse for repeat legitimate visits.

## 7. Mobile Security Workflow — Priority UX

A security officer opens the **store-distributed Android or iOS application** (or the fallback PWA), authenticates in a verified organization context, and sees four prominent actions:

**Check Vehicle · Register Visitor · Review Resident Reports · Report Violation · Active Cases**

### Search / identify vehicle
1. Enter or scan plate manually (camera-based OCR is optional later, not a dependency).
2. Display authorized match: resident or visitor status, relevant host unit, and a **Contact Household** action without unnecessary PII.
3. Unknown plates can be recorded and later reconciled.

### Review and investigate a resident-submitted concern
1. Security receives a new concern in an estate-scoped **Resident Reports** queue and optional on-duty push alert; only officers assigned to the estate can open it.
2. Officer reviews the reporter-submitted description, photographs and location without exposing the reporter to other residents or visitor records.
3. Officer accepts/assigns the task, visits or otherwise verifies the scene, and records findings. A report can be dismissed (with reason), resolved without formal enforcement, merged as a duplicate, or promoted to a verified incident with an auditable linkage.
4. Only authorized security (or expressly delegated incident verifiers) may promote to a formal incident. The original resident report and evidence remain unchanged; new officer evidence and rules are recorded separately.
5. Reporter receives a privacy-safe status update (e.g., Received, Under Review, Resolved, Not Substantiated), never the offending driver's identity, registration or contact details.

### Report an incident
1. Officer selects **Report Violation** and enters plate (or unknown), category, road/zone and short description.
2. Officer takes one or more photographs within the app; system logs device/server times and requests current GPS when capturing the first photo and/or on pressing **Capture Location**.
3. App shows map pin, **location accuracy (meters)**, capture age and estate/zone suggestion. Officer confirms the actual **vehicle position**, adjusts a draggable pin or selects zone if device reading represents the officer's location.
4. Required prompts prevent claiming GPS precision that has not been achieved. Save separate original device observation and corrected vehicle pin plus reason/source.
5. Officer submits incident. Server allocates unique case number and rule snapshot.
6. System finds the associated unit/person (or starts an unknown-vehicle identification task), supports a call via device dialer and logs outcome, and sends approved notifications where configured.
7. Standard cases proceed to a grace-period workflow **only after the qualifying contact milestone under estate policy**. Emergency/safety cases go to the urgent escalation workflow.
8. Officer can see a running countdown, notification status, escalation task and **Mark Corrected** action with optional follow-up photograph.

### GPS requirements — mandatory
- Request **event-triggered, foreground** browser/native location permission; browser PWA requires HTTPS, permission, and compatible device/browser. Native apps request only the minimal foreground location scope with platform-appropriate usage text. Do not request background location.
- Prefer a fresh reading (`maximumAge=0`), request high accuracy where available, and use a bounded timeout with retry. Never block an essential safety report solely because GPS is disabled or unavailable.
- Store latitude, longitude, accuracy in meters, observation time, capture source (`device`, `manual_pin`, `zone_only`), coordinates provenance, officer ID and incident reference. Optionally store photo-level location observations.
- Make accuracy explicit. **Illustrative UX thresholds only**, configurable: <=25 m “high”; 26–75 m “approximate”; >75 m “low—confirm location”. These are *not* guaranteed GPS tolerances or evidence of where a parked vehicle was located.
- Permit map pin placement, zone selection and reasoned correction; keep raw observations immutable and correction events in audit log.
- If photo has EXIF coordinates, treat as supplementary and untrusted, not authoritative; capture location in an explicit record and validate photo dates server-side. Preserve evidentiary original securely where justified; strip sensitive EXIF from ordinary UI thumbnails/exports.
- If outside geofence or far from estate, display warning and require verification/override with reason; do not fabricate or silently snap coordinates to property.
- **Never collect continuous or background location**, never disclose the officer’s historical movements to residents, and never publish precise location/PII via public dashboards.
- Ensure map and GPS work on target mobile devices in staging; create cases with manual location when denied, timed out, inaccurate, or offline, clearly labeling evidence quality.

## 8. Parking Violations, Warnings, and Escalation

### Incident categories
- Ordinary unauthorized parking / visitor-space misuse / expired permit / restricted area.
- Compound entrance, resident gate/driveway obstruction.
- Emergency route, fire access, ambulance access, major traffic obstruction.
- Other locally defined categories with severity, evidence and response SLA.

### Proposed state machine
`draft → recorded → identification_pending / contact_pending → notification_attempted → notified → grace_active → corrected_no_fee / escalation_pending → approved → clamped / tow_dispatched → impounded / released → resolved_closed`

Parallel subflows: `invoice_draft → invoice_issued → partially_paid / paid / adjusted / refunded`; `appeal_submitted → review → upheld / dismissed / partially_upheld`. Appeals and finance must not overwrite operational history.

### Warning and compliance safeguards
- Default 15-minute grace applies to **ordinary** violations starting from **verified contact/receipt per policy**; attempted, failed, sent, delivered and acknowledged are distinct statuses. No auto-penalty on an unanswered call.
- Template message identifies plate, violation, location, action, deadline, contact number and possible consequences.
- Manual calls record whom security spoke with, start/end times, response and officer; automated messages record provider IDs, delivery confirmation, errors and retries.
- Failure to reach responsible party creates **contact unresolved** case for supervisor handling under a separately published policy, not a fabricated notification event.
- Officer can mark correction, attach follow-up evidence, end case **without fine**.
- Enforcement needs eligibility check and separately authorized supervisor approval (unless legally required emergency procedure is predefined); log reason, rule version, legal authority flag and approver.
- Repeat violations can be flagged for management; no automatic higher penalties unless an effective, approved schedule explicitly authorizes them.

### Critical obstruction
- Prompt immediate contact and management escalation; applicable authorities/emergency services if needed.
- **Do not clamp a vehicle in place if that worsens an obstruction.** A legally authorized safe removal/tow may be appropriate.
- Grace may be shortened/bypassed only where approved emergency criteria apply and a reason is logged.
- Fees and release conditions remain subject to local law, provider agreements, association rules and documented appeal rights.

## 9. Clamping, Towing, Storage and Release

### Core rule
**Exactly one underlying parking-violation penalty is chargeable per qualifying incident.** Clamping, towing and storage are separate operational events; tow/storage charges are independently itemized, eligible only under approved fee schedules and actual service records. If a car is clamped and then towed, do not apply a second GH₵500 penalty.

### Clamping lifecycle
- Supervisor approves → security records clamp installed (time, identifier, photos, installer) → authorized release process → clamp removed (time, remover, evidence) → incident closed.
- Show eligible charge in resident and finance views; no officer cash collection outside approved, receipted process.

### Towing and impound lifecycle
- Approval / emergency override → dispatch provider → accepted/declined → arrival → vehicle condition photos and pickup timestamp → collected → impound destination and arrival → accumulated authorized storage → release instruction → retrieved/released timestamp and recipient confirmation → reconciliation.
- Record contractor, vehicle/truck, operator, provider reference, yard/location, chain of custody, service timestamps and itemized receipts.
- Storage calculation uses configured pricing basis, rounding, grace/no-charge window if authorized, actual impound start and stop events, timezone-safe timestamp handling, maximum/waiver rules, and versioned effective rates.
- Incorrect or disputed time entries require supervisor-approved adjustments. Never accrue storage beyond confirmed release/eligible stop event.
- Permit emergency release, independent review, and other lawful release procedures even if a dispute is open. **Do not build an unconditional vehicle-hold-until-paid rule** without validated legal authority.

## 10. Charge Engine, Invoicing, Payments and Appeals

### Charge categories
`PARKING_VIOLATION` (e.g., GH₵500), `TOW_SERVICE`, `STORAGE`, `OTHER_APPROVED_SERVICE`, `ADJUSTMENT_CREDIT`, `REFUND`. Each charge records incident ID, rate snapshot, legal eligibility, calculation basis, source, payee and tax treatment where applicable.

### Example calculations (illustrative only)
- Clamp after valid warning: 1 × GH₵500 = **GH₵500**.
- Tow after valid enforcement: GH₵500 + **authorized actual tow cost** + **authorized storage** = total. Example: GH₵500 + GH₵300 tow + GH₵100 storage = GH₵900 (tow/storage values are examples, not policy).
- Clamp followed by tow: **GH₵500 once**, plus independently valid tow/storage charges; no penalty duplication.

### Required controls
- Separate penalty, tow, storage and adjustments as itemized records and on printable/PDF invoices.
- Invoice numbers, partial payments, online/offline receipted payments, refund/waiver approvals, provider settlement/reconciliation, currency rounding rules, ledger and audit events.
- Ghana-appropriate payment adapter architecture with test/sandbox mode and configurable provider; do not assume a particular payment provider is available before verifying its terms and APIs. Secure payment callbacks, idempotent settlement and duplicate prevention.
- Idempotency keys per incident/charge type and duplicate webhook protection. Never silently charge a stored payment instrument or add unapproved fees.
- Customer sees amount, basis, evidence references, payment status, rights to contest and authorized release process. Suppress payment information from unauthorized guard screens.
- Appeals: time-limited configurable submission, independent reviewer, evidence access, documented decision, cancellation/recalculation/refund and resident notification. Processing of safety risks is separate from financial disputes.

## 11. Maps, Geospatial Analytics and Reporting — Mandatory

### Operational map
- Use a georeferenced estate footprint, roads, blocks, parking zones, entrances, emergency access lanes and restricted areas. Allow manual zones/polygons or aligned site-plan overlay where standard maps lack estate detail.
- Pins represent **confirmed vehicle location** with visible accuracy/provenance cues; allow authorized drill-down to case details and photographs.
- Select incident date range, violation type, severity, status, zone, repeat offenses, enforcement action, warning outcome and staff shift.
- Offer clusters, heatmap density, zone-by-zone counts, and before/after policy comparisons. Heatmap cells should avoid pinpointing household identities in broadly shared views.
- Correct for reporting bias: include incident counts and, when available, rates per vehicle entry/registered vehicle/parking capacity or patrol hours; do not infer causation from a density map alone.

### Dashboard requirements
1. Executive overview: total vehicles, registered resident vehicles, active visits, incidents, resolved with warnings, clamped, towed, unpaid invoices and pending appeals.
2. Compliance funnel: reported → reached/contacted → warned → voluntarily corrected → escalated → penalized; counts and rates with explicit denominators.
3. Incident trends: daily/weekly/monthly line charts, categories, severity and repeat offenders (restricted access).
4. Geographic analysis: estate map with interactive **incident markers, clusters and heatmap**; top road/zone hotspots.
5. Gate activity: arrivals, departures, visitors by day/hour, overstays and unmatched vehicles.
6. Operational performance: time to identify, contact, correct, approve, remove obstruction and close cases; overdue cases.
7. Finance: penalties vs tow vs storage invoiced/collected/outstanding, waived, refunded, service-provider reconciliations, with clear distinction between revenue and costs.
8. Fairness and quality: no-contact cases, warning adherence, overturned appeals, GPS capture quality, inconsistent enforcement, missing records.
9. Optional recurring management digest with aggregated anonymized statistics.

### Reports and exports
- Visual, filterable dashboards on desktop/tablet and simplified supervisor dashboard on mobile; drill-through with permitted scope.
- Table and chart export to CSV and printable PDF (XLSX where supported); optional scheduled email with access-controlled links, not PII-rich attachments by default.
- All metrics must use documented formulas, tested aggregation, date filters in estate local timezone and UTC-safe storage.
- Prefer Frappe Report Builder/Script Reports and Frappe Insights for business intelligence; build local heatmaps using Leaflet and a fit-for-purpose clustering/heatmap layer with vetted license.
- Charts must render meaningful empty states and large datasets without leaking precise household/visitor information.

## 12. Communications and Notifications

- Separate channels for call log, email and SMS; optional WhatsApp adapter only after suitable provider, opt-in/template/compliance verification.
- Distinguish **security-work-queue alerts** generated by unverified resident concerns from official notices to vehicle operators. Reporter-triggered security alerts never bypass security validation or start a fine/warning clock.
- Configurable per-estate warning and escalation templates, sender identity, language, delivery status and retry policy.
- Non-delivery and no-response visible to officer/supervisor. No false statement that a resident received a notice.
- Escalate urgent gate/emergency reports; do not treat WhatsApp or SMS as guaranteed instant delivery.
- Minimize notification contents; sensitive evidence and appeals accessible through authenticated portal links with expiration where appropriate.
- Configurable resident notification preferences cannot override essential legally required notices without legal review.

## 13. Resident Self-Service and Suspected-Violation Reporting — Revised v1.2

- Require verified resident login and active unit affiliation; any allowed multi-unit household access must be explicitly assigned, not guessed from a unit number. Show only a **self-service household projection**: requests, authorized household vehicle registrations, personal notifications, own cases/invoices and appeals. This is **not** access to the permanent resident/vehicle registry or visitor log.
- Residents may create a **suspected parking violation report** with configurable category, narrative, approximate location/map pin, optional vehicle plate typed manually, photos and urgency. Offer **Identified** reporting (privately record authenticated reporter ID and unit) or **Anonymous** reporting (no reporter identity, account, unit, or device identifier associated with the report). The latter requires a separately isolated anonymous intake flow and security/privacy controls specified in sections 34–37. No plate lookup, auto-fill of another household, visitor search or private vehicle ownership match in the resident UI or API.
- Submitting a report creates an **unverified Resident Concern**, immediately queues an alert to security for the assigned estate and records notification/acknowledgment state. It **must not** automatically generate an enforceable violation, fine, clamping/towing instruction, warning deadline or message to the alleged driver.
- Identified reporters can see their own report status (Received → Under Review → Resolved/Not Substantiated/Duplicate) and approved explanations; anonymous reporters cannot see reports in an account dashboard but may optionally check limited status using an unlinked secret receipt code, and any separately authorized incident information where they are an affected party. Residents cannot edit other residents' reports, assign officers or control official incident status. Retractions/corrections append an event rather than erase a received report.
- Give residents access to specifically **approved community reports**: aggregated counts, anonymized trends, delayed/blurred hotspot summaries where appropriate, and public policy documents. They may not drill into cases, export visitor/plate lists, identify reporters, see staff GPS traces, access live security patrol maps or obtain household-specific incident locations.
- Household members may submit vehicle registration/update requests; security/management verifies the authoritative registry change. Resident ability to view their own submitted vehicle card is a limited dedicated endpoint, **not generic resident-registry read permission**.
- Residents can respond to incidents involving their own verified household and appeal their own issued charges. Redact bystanders, visitor identities, raw staff location and irrelevant evidence before displaying any photo or case record.
- Use anti-spam/rate limits, deduplication, abuse reporting and security triage. A good-faith mistaken report is not treated as misconduct. Resident GPS is optional and capture must be event-triggered with clear consent and manual-location fallback.

## 14. User Experience and Accessibility

### Mobile/security design
- Purpose-built **store-installable Android/iOS application and compatible PWA**, not a shrunk Frappe administrator screen. Use mobile-platform conventions, safe areas, OS permission prompts, back navigation and useful native capabilities.
- Big tap targets, high-contrast accessible components, clear status labels and persistent context; functional in bright daylight and low bandwidth.
- Quick plate input, recent plates, unit search with minimal exposure, camera capture/compression and configurable location confirmation.
- Aim for primary check-in within ~30 seconds and incident capture within ~90 seconds under normal device/network conditions; validate targets with pilot users.
- Support screen reader basics, keyboard navigation for desktop, responsive layouts, helpful errors and recovery from browser refresh.

### Desktop/admin design
- Distinct navigation areas: Overview, Estate Map, Units, Residents, Vehicles, Visits, Violations, Enforcement, Finance, Appeals, Reports, Policies, Security, Settings.
- Avoid one giant scrolling admin page. Related functions grouped by section, details in subordinate screens, rich data tables, visual alerts and practical filters.

### Connectivity / offline
- Native mobile app and supplemental PWA must remain usable under intermittent connectivity. Native app must use vetted encrypted local storage and per-organization offline namespaces; PWA offline mode must degrade securely when platform storage guarantees differ. At minimum, securely queue **new, non-financial** visitor check-in and incident/evidence drafts when offline; display unsynced state and sync confirmation. Offline records are **provisional** until accepted by server.
- Do **not** authorize clamps/tows, confirm notice delivery, issue enforceable fines, take payment or release vehicles from an unsynced local record.
- Resolve conflicts/idempotency on reconnect; use secure storage, minimize local PII/photos and clear protected cached data on logout/expiry. Test lost signal mid-photo upload, duplicate submission, clock drift and sync ordering.
- If durable safe offline storage is infeasible in a particular browser, clearly degrade to a read-only/offline-draft mode rather than claiming full functionality.

## 15. Privacy, Security, Legal and Governance

- Ghana pilot requires locally informed review of the **Data Protection Act, 2012 (Act 843)** and applicable private property, clamping, towing, consumer/contract and payment rules; international deployments require local equivalents. This PRD does **not** assert that an estate inherently has authority to clamp, tow, or demand fees.
- Complete privacy notice, lawful basis assessment, collection minimization, purpose limitation, role permissions, consent/notice where relevant, retention and deletion schedule, controller/processor obligations and vendor contracts before real resident data ingestion.
- Strong authentication and authorization, role and record scope, per-estate isolation, secure session lifecycle, MFA for privileged users, encrypted transport, encrypted backup/storage where appropriate, rate limiting, CSRF and upload validation.
- Original violation evidence kept private, access logged, object hashing/integrity checks, append-only audit; changes expressed as superseding events rather than overwriting evidentiary originals.
- Private registries (permanent residents/vehicles and visitors) are separate protected data categories; officers/managers receive operational query access by assignment, residents receive **no direct registry DocType/report/API permission**, and auditors receive no raw data except separately authorized temporary scoped access. Record sensitive access and export attempts.
- Permission testing must include list queries, direct record IDs, filtered report endpoints, linked documents, print formats, private file URLs, image thumbnails, exported datasets, notifications, websocket events, cached mobile data and offline drafts.
- Do not publish incident maps showing personally identifying households. Audit export/downloads and prohibit public sharing of Frappe Insights dashboards containing private data.
- Redact plate numbers/contacts from public management summaries; ensure backups cover private attachments and database consistently, with tested restore.
- Legal and policy feature flags default **OFF** for actual fine collection, immobilization, towing and impound enforcement until signed authorization and local legal review.

## 16. Suggested Technical Architecture

- **Backend:** supported stable Frappe Framework release, Python DocTypes and server-side business services, native permissions/workflows/background jobs/scheduled tasks, REST API; default production MariaDB, Redis/worker as supported by deployment. Implement role permissions with DocPerm/permission levels/User Permissions plus consistent `permission_query_conditions` and `has_permission` hooks for estate/unit/record scope. Enforce action-specific policy checks in every whitelisted API and background handler; do not rely on client checks or assume `get_all` bypasses are safe.
- **Web frontend:** purpose-built responsive desktop organization admin, finance, board reporting and resident portal, communicating through server-validated Frappe APIs. Frappe Desk remains available to appropriately privileged operators but is not the only user experience.
- **Mobile frontend:** shared React/TypeScript mobile client, recommended Capacitor for maintained native iOS and Android projects, store artifacts and PWA fallback. Confirm feasibility with actual native camera/GPS/offline/push and app-review-relevant flows in Phase 0. Prefer shared domain/API contracts over sharing unsafe web session implementation. Do not package the Frappe Desk website as a bare native shell.
- **SaaS control plane:** independently secured organization registry, signup/invitation, provisioning jobs, subscription plans/entitlements, customer support controls, feature flags, staged migrations and monitoring. Store minimum organization metadata; do not centralize resident records or evidence. Site-bound service tokens and verified tenant discovery prevent cross-site routing by untrusted client-supplied hostnames.
- **Maps:** Frappe Geolocation field for stored point/map UI where useful; separate estate-specific Leaflet layer, GeoJSON polygons, coordinate snapshots, marker/heatmap/clustering extension. Respect mapping tile provider terms, budgets and offline behavior.
- **Analytics:** Frappe Report Builder/Script Reports plus optional installed Frappe Insights for dashboards. Do not depend on country/India-only map chart for intra-estate heatmaps.
- **Attachments:** protected Frappe private attachments or hardened S3-compatible private storage with signed access; image integrity and virus/content validation as appropriate.
- **Payment providers:** adapter interface; sandbox-only until gateway and fee/legal approvals verified.
- **Notifications:** queue-based adapter with provider receipt webhooks and retry/dead-letter monitoring; templates and audit.
- **Deployment:** isolated development/staging via maintained `frappe_docker` or approved hosting method, HTTPS, environment-managed secrets, daily backups and tested restore. Inventory authorized existing infrastructure before selecting live host. No implicit deployment onto unrelated production services.
- **Licensing:** document licenses/compatibility of Frappe (MIT), Frappe Insights, Leaflet, mapping layers, and any added libraries; do not copy unlicensed code from third-party repos.
- **Extensibility:** separate modules/service boundaries for policy, notifications, GIS, enforcement, billing and optional SaaS provisioning; versioned APIs and migrations.

### Data isolation strategy
Deploy one dedicated Frappe site **per subscribing organization**, with one or more estates as records inside that organization's site. Frappe sites have separate databases and files; each organization also needs isolated private attachments, jobs, cache keys, encryption configuration, backups and scoped credentials. Within an organization's site, validate estate/unit permissions server-side. Build automated tenant provisioning, suspension/reactivation, upgrades, backups, metering, exit/export and deletion from Phase 0. A shared global database may contain only minimal SaaS account/billing/operational metadata; no resident directory, raw incident evidence or full contacts. Any alternative shared-database design requires architecture review and an exhaustive cross-tenant isolation demonstration before approval.

## 17. Business Rules and Edge Cases

1. No fine if an ordinary violation is corrected within a properly measured warning period.
2. A failed/unanswered call alone is not an acknowledged warning; unresolved contact follows supervisor procedure.
3. High-risk obstructions permit justified immediate escalation, but never imply automatic unlimited towing authority.
4. Same plate may have multiple historical registrations; link immutable vehicle and occupancy history, never rewrite closed incidents.
5. Resident with multiple vehicles, one vehicle used by multiple units, move-out/ownership changes and visiting former resident must work.
5a. A resident allegation remains unverified until an authorized security verification step; neither a UI bug nor direct API call may transform a resident report into a fine, clamp/tow order or warning notice.
6. Visitor arriving without preregistration or with unknown host creates a safely restricted pending record.
7. Offline duplicate actions, repeat photo upload, retried payment webhook and simultaneous officers must not create duplicate incidents or fees inadvertently.
8. A vehicle initially clamped and later towed is assessed only one violation penalty per incident; permissible ancillary charges itemized.
9. Storage must not start before verified yard arrival or continue after approved stop/release boundary; support time/date transitions.
10. Authorized fee waiver, partial appeal, corrected vehicle identity, tow-cancelled-after-dispatch, and incorrect map pin require auditable reversals.
11. Residents may contest errors; appeals preserve evidence and cannot be resolved solely by the original enforcing officer.
11a. Resident reporting is estate-scoped and reporter-visible only; names of other households, private registries and visitor sessions are never returned in resident report suggestions, autocomplete or lookup endpoints.
11b. Auditors have no mutation capabilities, including assignments, comments on operational cases, report filing, permission changes, data edits or enforcement initiation; their access is explicitly scoped and recorded.
12. Emergency service access, lost connectivity, inaccurate GPS, location permission denied, camera failure and no-contact scenarios all need usable fallback processes.
13. An officer may be standing away from the car: separately record device observation and manually confirmed vehicle position; never assert GPS = vehicle position without confirmation.
14. All compliance percentages define numerator, denominator and exclusion of invalid/unverified incidents; money collected is not the primary success measure.

## 18. Nonfunctional Requirements and Service Targets

- **Performance:** server-side indexed plate search typical target <2 seconds under pilot load, incident save typical <3 seconds excluding photo uploads; validate on average Ghana mobile connectivity. Targets are provisional pending realistic benchmark.
- **Reliability:** queuing and retry for notices; failed payments and tow dispatches visible; resilient to short connectivity interruptions; backups tested with full restoration of private evidence.
- **Scale:** pilot sized for one estate with hundreds to thousands of units/vehicles and large historical incident sets; design indexes/pagination/aggregation and load-test against explicit assumptions.
- **Security:** no cross-unit/cross-estate access; no insecure direct object references; secrets only in server environment/secret manager; audit critical actions; retention configurable. **Privilege escalation, raw registry/visitor list disclosure, report drill-through and auditor mutation are release-blocking test failures.**
- **Maintainability:** standard custom Frappe app packaging, migrations, clean dependencies, no core monkey patches, tests, documented deployment and rollback procedures.
- **Interoperability:** exports and documented API for later gate hardware, OCR/ANPR, CCTV, payments, WhatsApp, and visitor QR passes; none are required for first launch.
- **Accessibility:** WCAG 2.2 AA as an implementation target where feasible, with practical security-officer usability testing.

## 19. Acceptance Criteria and Mandatory Demonstrations

Claude must demonstrate each outcome with real persisted data and test evidence.

**AC-01 Estate:** Create estate, gate, zones, units and fee/policy versions; change visible in UI, persistent after restart.

**AC-02 Resident registry:** Register two adults in one unit, migrate one to a new unit while preserving prior history; restrict unrelated resident access.

**AC-03 Vehicle:** Register two resident vehicles, link to correct unit; plate lookup by officer yields appropriate association without exposing unnecessary PII.

**AC-04 Visitor:** Register a visiting vehicle with unit/host, check in, locate active session at the exit gate and check out; complete entry/exit times, source gate/officer, derived duration and historical event trail remain queryable. See v1.5 cases AC-101 onward.

**AC-05 GPS and evidence:** Create incident from mobile camera; collect fresh GPS observation with timestamp and accuracy; manually confirm/adjust vehicle location; persist raw/corrected coordinates and reason; render correct marker on estate map. Demonstrate fallback with denied/inaccurate GPS and no fabricated data.

**AC-06 Warning:** A case receives a call attempt without answer: it must **not** automatically enter an acknowledged 15-minute grace window. Confirmed contact starts the applicable countdown; on-time correction closes without penalty.

**AC-07 Ordinary enforcement:** Valid notice + expired grace + approval permits policy-eligible clamping with photos and clamp identifier; one GH₵500 violation penalty example, no duplicated charge.

**AC-08 Safety obstruction:** Gate-blocking case escalates immediately; interface prioritizes clearing the obstruction. It must not default to clamping that worsens blockage.

**AC-09 Tow and storage:** Approved towing case records pickup/arrival/release, verified towing costs, storage calculation and itemized invoice; GH₵500 penalty once plus eligible tow/storage, accurate through adjusted timestamps and cancellation.

**AC-10 Payments:** Sandbox payment settlement, partial payment, receipt, refund/waiver and duplicate webhook retry without duplicate entries; prohibited live financial actions remain feature-flagged off.

**AC-11 Appeals:** Resident files appeal; independent approver decides; invoice adjusted/refunded as needed without deleting original evidence.

**AC-12 Reporting:** Live dashboard shows totals, trends, warning compliance, action breakdown and itemized finances; data matches incident ledger and filters.

**AC-13 Hotspots:** At least 20 seeded violations distributed across geofenced zones display as pins, clusters and heatmap; filtering by date, offense and zone updates map and counts. Blurred/approximate coordinates cannot misleadingly imply exact vehicle location.

**AC-14 Security:** Security officer cannot edit fee schedules or access other estate data; resident cannot enumerate other units; unauthorized API/download/report access denied.

**AC-15 Mobile usability:** Independently built Android and iOS app artifacts install on representative real devices; functional camera, map, foreground location permissions, platform push notifications, encrypted credential storage, readable layouts, reconnect handling and secure logout. PWA fallback also demonstrated. Real store publication is separately approved.

**AC-16 Offline:** Save an offline provisional incident, reconnect and upload exactly once; avoid offline enforcement/payment actions and test conflict/clock scenarios.

**AC-17 Audit:** Record actor, timestamp, decision, location correction and fee change with evidentiary audit chain; no ordinary user can silently erase it.

**AC-18 Resilience:** Restore staging backup including incident photos and invoices; verify migration, rollback, logging, alerting and error states.

**AC-19 Legal gating:** With enforcement feature flag off, no user can generate enforceable live clamp/tow/fine/payment action, including via API.

**AC-20 Reusability:** Provision a **second independent association tenant/site** with its own currency, grace period, fee schedule, forms, staff and branding without source changes. Each association may have more than one estate. Verify no cross-tenant data access or metadata leakage.

## 20. Delivery Plan and Milestone Gates

### Phase 0 — Discovery, architecture and app-store feasibility (no production actions)
- Confirm supported Frappe/Capacitor versions, native dependencies and licenses; inventory authorized repository, macOS build/CI, Android build, hosting, domains, payment and notification resources.
- Create architecture/ERD, SaaS tenant-boundary diagram, **action-by-role permission matrix, read/write/field sensitivity matrix, resident concern triage state machine**, API contracts, threat model, org/policy configuration schema, store-compliance matrix, risk register, wireframes and legal feature flags.
- Stand up **two separate isolated Frappe organizations/sites**, custom app scaffolding, organization control-plane skeleton, verified PUBLIC GitHub repo (only after pre-publication license, provenance, secret and privacy clearance), CI, healthchecks and backup/restore proof.
- Produce early **real native iOS and Android test builds**, verify tenant-specific secure login, camera, foreground GPS, credential storage, app lifecycle and offline draft sync on physical devices; prepare app-store submission-gap assessment.
- **Gate:** demonstrate that chosen mobile architecture is substantively functional and review-oriented, not a thin wrapper; approve SaaS tenancy and data model before extending it.

### Phase 1 — SaaS onboarding, independent configuration, registry and visits
- Organization provisioning, account invitations, plan entitlements, subscription state, secure tenant selection, configurable org/estate branding, fields and policy versions.
- Estates, units, roads/zones, person/membership, vehicle and vehicle-unit registration, **v1.2 delegated roles/scopes and protected registry query APIs**, resident roles and protected visitor log. Implement resident concern submission and security-only triage inbox as a Phase 1 vertical slice.
- Native mobile security and desktop admin views; imports; search; tenant-separated test fixtures.
- **Gate:** AC-01 through AC-04, AC-20, AC-21 through AC-25, **AC-35 through AC-42**, plus role/registry/tenant isolation evidence.

### Phase 2 — Incident capture, camera, GPS, warnings
- Incident/evidence DocTypes, mobile GPS pin/correction, policies, contacts/notice state, ordinary and urgent path, notification adapters. Complete resident concern → security validation → verified incident linkage and resident-safe status updates.
- **Gate:** AC-05, AC-06, AC-08, **AC-43 through AC-47**, offline incident capture and location privacy tests.

### Phase 3 — Enforcement, finance and appeals
- Supervisor approvals, clamp/tow/yard chain of custody, penalty + tow + storage ledger, sandbox invoices/payments, refunds and appeals.
- **Gate:** AC-07, AC-09 through AC-11, AC-19, **AC-48 and AC-49**; legal flags remain off until approved.

### Phase 4 — Reporting, mobile distribution readiness and operational hardening
- Dashboard/report integration, estate heatmaps and geofenced zones, operations/finance dashboards, cross-tenant safe SaaS metrics, audits, offline recovery, QA, backup restoration and pilot training.
- Finalize Android app bundle/store build, signed Samsung-compatible package as required, and iOS archive/TestFlight submission candidate; confirm current SDK targets, permissions, privacy declarations, metadata, accessible demos and store review notes.
- **Gate:** AC-12 through AC-18, AC-20 through AC-34, **AC-35 through AC-54**; full multi-tenant role/security E2E suite, native device tests, store-readiness evidence and reproducible distribution assets.

### Phase 5 — Pilot, store submissions and production activation (separate approvals)
- Dry-run pilot using demo or authorized data, ideally two different organizations; resident/security onboarding; management review of rates, signage, legal powers, privacy notices and release policy.
- With separate permission and developer accounts, submit iOS to TestFlight/App Review and Android to Google Play testing/review and Samsung Seller Portal according to current rules; respond to actual reviewer feedback. **Store approval is external and cannot be promised.**
- Obtain explicit written production/legal go-live approval before importing real resident information or enabling enforcement, payments, provider dispatch, SaaS customer billing, public registration, or public store availability.
- Monitor pilot outcomes and revise workflow; never call staging or store-submission preparation a production deployment or approved listing.

## 21. Required Claude Deliverables

1. Verified **public GitHub repository** with cleared source, Apache-2.0 license, reproducible setup, sanitized synthetic fixtures, migrations, contributor docs and documented third-party licenses; exclude all private runtime data and secrets.
2. `ARCHITECTURE.md`, dependency list, version pinning, ERD and business process state diagrams.
3. Responsive desktop management application, a shared **role-adaptive native Android/iOS app** serving security, managers and residents, compatible PWA fallback, and scoped resident/auditor web experiences. Source, native project files, signing instructions and app-store submission packs included.
4. Real DocTypes, APIs, background jobs, workflow rules, RBAC, audit, evidence and reporting implementations, including distinct resident-report and verified-incident objects, resident-to-security alert routing, protected registry APIs, a complete permission matrix and automated negative authorization tests.
5. User-interface screenshots or screen recordings of the primary flows, including GPS map and heatmap.
6. Automated unit/integration/security/E2E tests plus representative device smoke tests, with commands and results.
7. Demo dataset featuring multiple units, residents, vehicles, visits, incidents, contacts, emergency obstruction, clamp, tow, storage, appeal and map hotspots.
8. Staging URL or reproducible startup instructions, documented environment assumptions, sandbox integrations and a tested restore/rollback procedure.
9. Operator guide for security, supervisors, finance, association owners, management companies, auditors and residents; SaaS provisioning/support/runbooks; implementation plan for real deployment.
10. Tenant-onboarding portal/configuration UI, SaaS architecture/tenant-isolation proof, plan/entitlement ledger, branded app-assets flow, and customer data export/offboarding guide.
11. Apple App Store, Google Play and Samsung Galaxy Store compliance matrix and submission checklists, packaged builds in staging, test-device evidence, review-demo credentials, privacy disclosures and privacy/account-deletion endpoints.
12. Final evidence report: **implemented / tested / staging-verified / blocked / deferred**, with precise outstanding issues. No unverified claims of deployment or integration success.

## 22. Questions Claude Should Resolve During Phase 0 (Without Stalling the Build)

These are configurable choices or approval gates, not reasons to stop basic scaffolding:
- Which authorized infrastructure/repository owner will host the isolated staging application?
- Which jurisdiction-specific organization has legal authority over clamping/towing and prescribed release procedures?
- Will the first estate require residents to use the self-service portal or will staff register everyone?
- What approved provider will send SMS/WhatsApp/email and process payment? Begin with mock/sandbox adapters.
- What are the approved towing and storage fee schedules and operational providers? Leave these unconfigured rather than inventing prices.
- Is an up-to-date estate site plan available? Implement manual zone map setup while awaiting it.
- What data retention and privacy notices have been approved for resident contacts, visitor logs, resident-submitted concerns, GPS and evidence?
- Which management company or association administrators are assigned to which organization/estates, and what auditor data-access scopes/expiration rules will be approved? Use least-privilege defaults meanwhile.
- What legal entity will own the SaaS brand, developer accounts, and app privacy policy? Do not block staging proof-of-concept if not yet chosen.
- Which supportable native build system and release pipeline will be used (local macOS or authorized cloud macOS runner)?
- What B2B SaaS subscription billing provider and association subscription tiers will be approved? Prototype sandbox entitlements without enabling live subscription charges.

## 23. Reference Documentation Verified During PRD Preparation

- Frappe Framework overview, DocTypes, permissions and reports: https://docs.frappe.io/framework/user/en/basics
- Frappe field types, Geolocation and map view: https://docs.frappe.io/framework/user/en/basics/doctypes/fieldtypes
- Frappe Geolocation/map customization: https://docs.frappe.io/framework/user/en/customize-geolocation-map
- Frappe REST API: https://docs.frappe.io/framework/user/en/api/rest
- Frappe site isolation: https://docs.frappe.io/framework/user/en/basics/sites
- Frappe Insights: https://docs.frappe.io/insights/introduction
- Frappe Insights geographic map-chart limits: https://docs.frappe.io/insights/charts/chart-types-explained
- PWA approach demonstrated by Frappe CRM: https://docs.frappe.io/crm/mobile-app-installation
- Web geolocation permissions and accuracy: https://developer.mozilla.org/en-US/docs/Web/API/Geolocation/getCurrentPosition
- Ghana Data Protection Commission: https://dataprotection.org.gh/


## 24. Multi-Organization SaaS Requirements — Mandatory v1.1

### 24.1 Product identity, tenancy and association hierarchy

The product is **one centrally maintained B2B SaaS offering**, not a separate code fork installed manually for every customer. Use this hierarchy:

`SaaS Platform → Organization / Association (isolated Frappe site) → Estate / Property (one or more) → Block / Road / Zone → Unit → Occupants / Vehicles / Visits / Incidents`.

An **organization tenant** means the HOA, estate management company or community association purchasing the service; a **residential tenant/occupant** means an individual who lives in a unit. Code, UI and documentation must not conflate them.

The platform owner manages customer subscriptions and operational health; each association controls its own units, membership, staff, policies, forms, branding and enforcement. An association may administer several estates, including estates in different permitted regions, but each estate retains its own legal eligibility, currency/timezone defaults where relevant, location boundary and policy version.

### 24.2 Onboarding and provisioning

- SaaS customer organization lifecycle: `lead/invited → trial/provisioning → active → past_due/grace → suspended_restricted → cancelling → export_pending → closed/deleted`, with administrator-approved overrides, audit and notices.
- Create tenant through an idempotent, restartable provisioner: reserve unique organization ID and slug; allocate Frappe site/database/private file scope; install the common custom app and migrations; initialize role/policy defaults; configure HTTPS DNS; seed primary admin securely; test site health; record status. Roll back safely or quarantine partial sites if provisioning fails.
- Default onboarding works by **platform invitation** or controlled association signup. Public signup, automatic payment collection or tenant activation need separate approval and anti-abuse controls.
- Tenant discovery via verified invite/organization code or verified email-domain association; users with multiple authorized associations can securely select/switch active organization. Never let client-submitted hostnames, tenant IDs or unit IDs grant access by themselves.
- Every API credential and auth token is bound to a specific audience/organization/site. On switching tenant, discard prior-site caches, offline drafts from active views and session context; re-authenticate or securely obtain a site-scoped token. Test token replay against other sites.
- Make account invitations, admin enrollment, password reset, MFA for privileged users, role revocation, account disabling and secure account recovery part of the core product.

### 24.3 Association-owned configuration without source-code changes

**v1.2 safety boundary:** Tenant-configurable fields, menus and policies may be *more restrictive* but must never override system-enforced residency/privacy boundaries, give residents access to private registry or visitor DocTypes, make auditors write-capable, broaden staff cross-tenant scope, or enable legal enforcement features without approval. Custom field definitions must use a controlled sensitivity classification and explicit backend-approved visibility, never arbitrary code or query execution.

Each organization owner can use a dedicated **Settings & Policy Studio** to change:

1. **Identity:** name, logo, support details, timezone, locale, language, permitted color theme and resident-facing templates.
2. **Community structure:** estate(s), gates, unit types, street/zone maps, parking allocations, visitor spaces and authorized vehicle classes.
3. **Parking policy:** offense catalog, zone applicability, severity, whether warning is required, proof of successful notification, 15-minute or other grace duration, repeat-offense approach, reminders, safe escalation matrix, supervisor approval level, ordinary vs emergency resolution and appeals deadlines.
4. **Fees:** GHS or association/jurisdiction-appropriate currency; fine amount, clamping release rules, tow service and impound/storage pricing method, rates, caps, late/waiver policies, taxes, refund/appeal controls and financial approval levels. Separate fee payer/payee and effective dates. **No automatic legal authority from merely changing settings.**
5. **Registration forms:** configurable optional/required *allowlisted* fields for residents, vehicles, visitors, contractors and violation observations; field label, type, help text, visibility, validation, choices, retention and export behavior.
6. **Operations:** visitor gate rules, officer shifts/assignments, security escalation contacts, who may contact whom, notification channels/templates/language and approved integration providers.
7. **Reporting:** saved report filters, custom view columns, dashboard presets, schedules and sanitized export templates.
8. **Entitlement settings:** association plan features and limits are assigned by SaaS operator; organization owners may enable or disable eligible modules only **within purchased and legally authorized entitlements**.

**Custom-fields safety rules:** The configuration engine supports text, number, date/time, selector, boolean, validation regex from a safe restricted subset, attachment reference and relationship reference; constrain lengths/options/types. Never allow organizations to write or upload executable Python/JavaScript/SQL or arbitrary Frappe scripts, custom code, privileged permission expressions, untrusted HTML or dynamic server-side hooks. Additional fields are managed as typed, versioned metadata plus structured extension values with server-side validation, indexed fields where justified, import/export compatibility and automatic mobile/web form rendering. Every field has sensitivity classification, access matrix, default visibility and retention. Forbid discriminatory or unnecessary data collection by default; highly sensitive new fields require platform review or should be unavailable. Changing a required field cannot retroactively invalidate past records.

### 24.4 Policy Studio: draft → preview → approval → activation

- Every policy/rate/form change begins as a **draft version**; show change diff and interactive preview, including an example clamped/towed case and expected invoice calculation.
- Verify it against platform-level safety rules, legal activation flags, allowed bounds/roles, local governing approval evidence and the association's approved policy effective date.
- Require configurable separation of duties for fee increases, emergency towing rules, private data field requirements and enforcement activation. At least one independent approver for high-impact changes.
- Permit future-dated publication and deliberate emergency rollback. Preserve historic versions in append-only audit; never recalculate old incidents using newly published fee schedules unless a specifically authorized adjustment is made.
- Each incident records the exact effective policy, field schema, fee rates, warning rule and timezone used when it was opened. Claimed legal authority is not validated simply because an owner checks a box.
- Provide safe policy templates (reference Ghana / generic HOA) as **examples**, never default to live clamping or fines. Associations must explicitly configure and certify local requirements before those workflows can be activated by the platform operator under documented authorization.

### 24.5 SaaS plans, subscriptions and two separate money systems

There are **two separate financial ledgers**:

- **SaaS subscription billing:** what an association pays the platform for a subscription (plan, billed period, seats, estates, optional modules, invoicing, metered usage, credit, collection status).
- **Estate enforcement accounting:** what a vehicle operator may legally owe **the association or approved provider** for an incident (one underlying penalty, towing, storage, waiver/refund, release).

Do not combine, net or mix these balances, merchant accounts or reconciliation reports. No implicit transfer of resident penalty money to the SaaS operator. Implement separate account ownership, payment provider adapters, authorization checks, receipts, payouts/settlements, taxes and audit logs; choose live providers only after authorization and commercial/legal review.

SaaS plan packaging: trial, basic and advanced can be seeded as **configurable examples**, not a finalized price list. Potential entitlements: number of estates/units, registered vehicles, security seats, retention tiers, report exports, map heatmaps, SMS/WhatsApp allowance, finance integrations and API access. Billing/metering must be accurate and idempotent, with admin visibility, grace and safety preserving suspension behavior. **Suspension must not strand legally required incident evidence, appeals or vehicle release access.**

For native-store B2B customers, initially handle association subscription purchase through appropriate **web-based business contracting/invoicing**, with the mobile app used primarily by authorized existing users. **Do not add prompts or links inside the store apps that route users to prohibited external purchase methods.** Before adding any in-app purchase, upgrade, resident fee payment, or checkout flow to native apps, assess and document Apple, Google and Samsung payment rules **separately**, distinguishing B2B software subscriptions from lawful payments for real-world towing/parking-related services. Do not assume that one exception applies universally.

### 24.6 Tenant isolation, lifecycle and support

- Isolate each association's database, private attachments, caches/queues, backups, secrets, logs and exports. Apply estate, unit and role scoping within each site.
- Control-plane operator can view aggregate customer health, subscriptions, usage and support events with no resident PII by default. Access to tenant personal data requires legitimate documented purpose, tenant permission where appropriate, time-bound break-glass, MFA and full audit.
- Tenant-scoped credentials, signing keys where appropriate, expiring private file links, rate limits and storage quotas; no globally shared direct file buckets/filenames without strong partitioning.
- Automated site updates with staged rollout, migration compatibility checks, tenant-by-tenant backup and rollback strategy, and clear incident communication.
- Export customer-owned data in documented machine-readable formats with media manifest, permissions checks, audit and completion confirmation. Support termination with data retention/deletion according to contract and law; preserve legal-hold evidence only with appropriate justification, access controls and documented retention limits.
- Platform-level analytics must avoid mixing or exposing an association's raw data to other customers. Benchmarks across organizations require clear agreement, aggregation and privacy thresholding; disable by default.

## 25. Native Mobile and App Marketplace Compliance — Mandatory v1.1

### 25.1 Target distribution channels and architecture

- **Apple App Store (iOS):** independently buildable, signed iOS project; native iOS bundle archive, TestFlight trial distribution (when authorized), final App Store Connect submission pack.
- **Google Play (Android):** signed release Android App Bundle as required by current Play rules, closed/internal testing track (when authorized), Play Console release pack.
- **Samsung Galaxy Store (Android):** use the common Android application source and produce Samsung-accepted release format and signing/package identity; prepare Seller Portal metadata and run Samsung-specific review/prelaunch testing. Verify current format/country/target-API requirements at release time; do not assume Google Play acceptance implies Galaxy Store acceptance.
- **Desktop:** browser-based administration and graphical analytics. PWA remains a low-friction alternative, not the only mobile deliverable.

One branded mobile app should support staff/residents across authorized associations via secure organization discovery and server-delivered branding. Avoid creating a separately compiled native binary for each estate or associating a tenant's name with an app package ID. All organizations share the same versioned native client and compatible Frappe API contract.

**Recommended frontend:** React/TypeScript + Capacitor, chosen for common web/mobile components and access to native iOS/Android functionality. The team must validate that the chosen Capacitor SDK/plugin versions are maintained, support required current store SDK targets and are license compatible. If a native-device proof fails materially, propose an explicit alternative (e.g. React Native/Expo or Flutter) with migration cost before finalizing. Avoid coupling product business rules to a specific native plugin.

### 25.2 Meaningful native functionality (no empty website wrapper)

Build and demonstrate all supported features, not merely link to a responsive website:

- In-app camera capture for violation/vehicle evidence with secure upload queue, image integrity metadata and app lifecycle safety.
- Foreground location permission and capture when the officer documents a violation; visible accuracy and corrected vehicle pin. No background tracking/permission request by default.
- OS-native permission education and graceful denied/revoked permission fallback.
- Device-keystore/keychain-backed secure credential storage, biometric reauthentication only if implemented securely, secure logout and remote device/session revocation.
- Native push registration/permissions and notification navigation to authorized incident records; secret incident details must not appear on lock screens by default.
- Offline encrypted **provisional** capture of visitor/check-in and incident/photo drafts, with clear pending/failed/synced indicators, idempotent retry and strong per-organization isolation. No offline final monetary or coercive enforcement action.
- App-native lifecycle handling: background/foreground, interruption during capture/upload, connection changes, deep links, back button, permissions returning from settings and native navigation behavior.
- Responsive high-contrast, large-target field workflow, accessibility labels, dynamic text sizes and usable dark/light appearance as appropriate.
- Demo/reviewer mode with synthetic data permitting representative role-based features without production PII or real enforcement.

### 25.3 Security and privacy baseline

Adopt **OWASP MASVS** as a security verification baseline, plus Frappe backend/API tests. Threat-model malicious or lost security phones, session theft, reverse engineering, untrusted photos, GPS spoofing, shared devices, deep-link abuse, notification leaks, insecure local caches and cross-tenant token replay.

- Least privilege: location **while in use** only, camera only when requested, notifications with opt-in. Do not request unnecessary contacts, Bluetooth, nearby devices, background location or broad photo-library access.
- Store resident names, telephone numbers, plates and photographs only as necessary. Use encrypted device data stores, OS secure credential APIs and automatic expiration/eviction. Disallow sensitive data in logs, crash analytics, clipboard, screenshots in sensitive screens where justified, and unrestricted OS backups where feasible.
- Enforce TLS and secure API authentication; tokens must not be embedded in app binaries, local web assets, public maps, URL query strings or push contents. Server authorizes every action even when client UI hides it.
- Validate uploaded file type/size/content and safely handle EXIF; require evidence integrity audit and server-time corroboration. Client-supplied GPS is evidence of a reported observation, not proof of actual vehicle position.
- Provide in-app accessible privacy policy, terms/support contact, disclosure of collection/use of location/camera/evidence, retention/deletion and documented third-party data processors.
- If users can create accounts, provide Apple-required in-app initiation of account deletion and Google-required in-app **and web** account deletion pathways as applicable. Define how personal account deletion coexists with independently lawfully retained incident evidence/financial records, using deidentification and access limits as legally advised; avoid promising deletion of lawfully retained records without checking obligations.
- Maintain accurate Apple privacy nutrition labels, Google Play Data safety form, Samsung privacy/security declarations and native permission descriptions. Verify third-party SDK data practices and any Apple privacy manifest requirements for included SDKs.
- Complete dependency, license, SAST/SCA, mobile package analysis, API penetration tests, secret scans, device security verification and privacy review before external submission.

### 25.4 Store review and release operations

**v1.2 reviewer requirement:** Provide test accounts for Resident, Security Officer, Security Manager and Management Administrator with synthetic data, plus a permitted read-only Auditor profile where review needs it. Demonstrate meaningful role-specific functionality and clearly worded camera/location permissions. No app-store demo profile may expose real resident or visitor records.

- Maintain **three separate store readiness checklists** with links to current official requirements. Recheck policy and target-SDK deadlines before every public submission; rules can change.
- Apple: meaningful standalone utility beyond repackaged web content, complete reviewer demo credentials for all relevant roles, accurate metadata/screenshots, explanation of authorized organizational use, privacy policy, account deletion flows, no broken features and current platform SDK/compliance settings. App Review has discretion; this PRD cannot guarantee approval.
- Google Play: policy-accurate Data safety disclosures, privacy policy, account deletion where required, current target API and testing eligibility, least-privilege runtime permissions, functioning tester credentials and pre-launch report fixes.
- Samsung: Samsung Seller Portal enrollment, country eligibility, accepted signed Android package, image/text metadata, Samsung distribution/review requirements, testing on applicable Galaxy devices and independent release approval.
- Supply icons, splash screens, version names/build numbers, release notes, localization placeholders, screenshot sets, reviewer role accounts, synthetic demo organization, support URL, legal URLs, release artifact checksums and reviewer instructions.
- Use CI to build/release unsigned test artifacts by default; use protected store credentials, organization-controlled signing keys and segregated approval-only signing pipelines for release. iOS release requires authorized macOS/Xcode build infrastructure or a trusted macOS CI service.
- Maintain crash/ANR and privacy-safe mobile diagnostics, staged rollouts, rollback response, release channel version gating, upgrade compatibility for older clients and critical server policy changes.
- **Publication requires distinct explicit owner authorization, store accounts and provider review.** Staging build success alone cannot be represented as app-store acceptance.

## 26. New v1.1 Acceptance Criteria and Demonstrations

**AC-21 SaaS onboarding:** Provision two independent organizations from a central operations console; both receive separately isolated Frappe site/database/private file scopes, unique admins, backups and working tenant routing. Failed provision retries are idempotent and audited.

**AC-22 Multi-estate association:** Organization A manages Estate 1 and Estate 2 without code changes. Estate administrators cannot access an estate unless granted; Association B sees no records or metadata from A.

**AC-23 Configuration:** Organization A changes its ordinary warning from 15 to 10 minutes in a newly approved future policy; Organization B remains at 15. New A incidents use 10 after activation while previously opened incidents retain their original policy snapshot.

**AC-24 Form designer:** Organization A adds a validated optional visitor field and a required resident-vehicle field without a code deployment; both render correctly in native Android/iOS and web views, respect permissions/retention, and survive upgrades. Association B is unchanged.

**AC-25 Fee and escalation studio:** Two associations configure different penalties, towing/storage rates, escalation contacts, approval levels and appeals deadlines. The simulator shows both an ordinary warning case and urgent tow case, without enabling live collection, and historic invoices remain immutable.

**AC-26 Plan and billing separation:** Association subscription invoice and a resident's authorized parking incident invoice appear in distinct ledgers, with distinct payee and reconciliation. Subscription suspension cannot delete case evidence or make a legally required vehicle release impossible.

**AC-27 Tenant attack tests:** Attempts to replay an auth token against another tenant, tamper with hostname/header/organization ID, enumerate private file URLs, switch tenant with offline data present or access a different tenant's notification/exports all fail safely; record test evidence.

**AC-28 Native build:** Produce reproducible iOS project/archive candidate through approved macOS environment and signed/staging Android app candidate. Confirm both are actual installable apps, not just browser launchers. Verify app lifecycle and versioning on physical iPhone and Android device.

**AC-29 Mobile native features:** Demonstrate camera capture, foreground GPS with explicit permissions and accuracy, pin correction, secure token storage, push notification registration/handling and manual-location fallback on native Android and iOS, with all data associated to correct organization.

**AC-30 Offline safety:** Disconnect on a device, save incident and photo as an encrypted draft, switch organization or logout, confirm data cannot leak to another association, reconnect and upload once; offline clamp/tow authorization and payment remain unavailable.

**AC-31 Store-compliance audit:** Evidence matrix maps current Apple/Google/Samsung policies to implemented code, user screens, permissions, reviewer credentials, screenshots, privacy policy and declarations, package formats and outstanding owner actions. Mark any requirement untested or pending honestly.

**AC-32 Deletion/privacy:** User with an eligible self-created account can initiate deletion in app and via web where required; a lawful-retention record is handled transparently without exposing unrelated tenant information. Exports, device caches and scheduled deletion are tested.

**AC-33 SaaS upgrade/migration:** Deploy new custom app version and field metadata migration to two sites, preserving individual policies and databases; test rollback/backup restore and compatibility of an older still-supported mobile client.

**AC-34 Distribution candidate:** Supply separate Apple TestFlight/App Store Connect, Google Play, and Samsung Galaxy Store submission packs including verified signing pipeline, correct package IDs, build artifacts where accounts permit, metadata, demo organization, reviewer credentials and known blockers. Do not claim store acceptance unless each store actually approved it.

## 27. v1.1 Reference Sources and Review Notes

- Frappe multisite architecture (separate sites/databases/files): https://docs.frappe.io/framework/user/en/basics/sites and https://docs.frappe.io/framework-git/administration/multitenancy-domains
- Capacitor native runtime and iOS/Android/web build guides: https://capacitorjs.com/docs and https://capacitorjs.com/docs/getting-started and https://capacitorjs.com/docs/getting-started/environment-setup
- Apple App Review Guidelines (4.2 minimum functionality; 3.1.3 enterprise/companion app billing; 5.1 privacy): https://developer.apple.com/app-store/review/guidelines/
- Apple reviewer demo account requirements: https://developer.apple.com/help/app-review/before-submitting-for-review/complete-review
- Apple account deletion guidelines: https://developer.apple.com/help/app-review/guideline-reference/5-1-1-account-deletion
- Google Play Developer Program Policies, privacy/Data safety/account deletion: https://support.google.com/googleplay/android-developer/answer/18258653
- Google Play payments policy guidance: https://support.google.com/googleplay/android-developer/answer/10281818
- Samsung Galaxy Store Distribution Guide: https://developer.samsung.com/galaxy-store/distribution-guide.html
- Samsung submission/review: https://developer.samsung.com/galaxy-store/galaxy-store-developer-api/content-publish-api/submit-app.html
- OWASP Mobile Application Security Verification Standard: https://mas.owasp.org/MASVS/

**Version notes:** v1.1 supersedes v1.0. All original registry, resident/unit/vehicle linking, visitors, GPS/photo evidence, warning, clamp/tow/storage, appeals, reporting, confidentiality and legal-safety requirements remain in effect. Added organization-level SaaS, configuration studio, subscription/billing segregation, native build readiness, three-store release compliance, and extended test gates.



## 28. Mandatory v1.2 Authorization Matrix and Separation of Duties

The matrix below is normative. It defines the maximum baseline abilities in a user's **assigned organization/estate scope**. Tenant administrators may restrict these further. They may not grant powers forbidden by platform privacy and security rules. Permission codes: **R** = read, **C** = create, **U** = update/operate, **A** = approve/authorize, **V** = read-only approved aggregate view, **—** = no access, **G** = only with separately approved, time-limited grant, **S** = only self/household or assigned case. A role named "Full Access" means authorized business operations, **not** unrestricted database, secret, audit-delete or other tenant access.

| Capability | Mgmt company / Org admin | Security manager | Security officer | Resident | Auditor | Finance | Tow provider |
|---|---|---|---|---|---|---|---|
| Estate, units and authorized occupancy records | R/C/U | R | R (duty scope) | — | R/G | — | — |
| **Permanent resident + vehicle registry** | R/C/U | R/C/U | R/C/U (operational, no bulk export) | **—** | G (approved, read-only) | — | — |
| **Visitor entry / exit log** | R/C/U | R/C/U | R/C/U | **—** | G (approved, read-only) | — | — |
| Own household vehicle *request/card* (not registry access) | R/C/U | R/C/U | R/C/U | S: R/C/U request only | — | — | — |
| Submit suspected parking report | C | C | C | **C: identified, or anonymous via isolated intake** | **—** | — | — |
| View/triage resident reports | R/C/U | R/C/U/A | R/C/U assigned | S: identified own status; anonymous receipt-only | G: read-only | — | — |
| Verify allegation → official incident | R/C/U (authorized) | R/C/U | R/C/U | **—** | **—** | — | — |
| Capture officer evidence, GPS and case notes | R/C/U | R/C/U | R/C/U assigned | S: original submission only | G: read-only | minimum billing data | S: assigned task only |
| Call responsible resident / log contact | R/C/U | R/C/U | R/C/U | **—** | **—** | — | — |
| Issue standard warning (subject to policy) | R/C/U | R/C/U | R/C/U | **—** | **—** | — | — |
| Approve clamp/tow escalation | A (independent approver) | A (eligible independent approver) | — | **—** | **—** | — | — |
| Execute authorized clamp / tow dispatch | R/C/U | R/C/U | R/C/U assigned action | **—** | **—** | — | S: assigned job update |
| Change estate policies / fees / escalation | R/C/U/A, two-step approval | — | — | — | — | — | — |
| Generate/modify charge ledger and invoices | R/C/U/A per limits | R minimal status | R minimal status | S: own invoice read | G read-only | R/C/U | S: own service charge claims |
| Post receipts / refunds | R/C/U/A per controls | — | — | S: receipt read | G read-only | R/C/U per limits | S: provider receivable status |
| Submit case appeal | R/C (on behalf, tracked) | — | — | S: own case | — | — | — |
| Resolve appeal / void penalty | A (independent reviewer) | — unless delegated | — | — | — | R/U finance execution after approval | — |
| Approved aggregate community dashboards | R | R | R limited | **V** | **V** | R finance scope | — |
| Detailed operational incident reports | R | R | R assigned | S: own case only | G read-only | R restricted | S: assigned task |
| View audit history / data-access log | R | R own team | S: own actions | S: own report activity | R approved scope | R own finance | S own job |
| Create/edit organization users and grant access | R/C/U/A (scoped) | Staff assignment proposal only | — | — | — | — | — |
| Raw PII / visitor registry export | G, explicit purpose and audit | G, explicit approval | **—** | **—** | G, time-limited | **—** | **—** |
| Edit/delete immutable enforcement/evidence audit | **—** | **—** | **—** | **—** | **—** | **—** | **—** |

**Additional roles:** Estate Managers are management-role subsets restricted to appointed estates. Board Observers have access to approved aggregate dashboards only. SaaS Platform Administrators are outside this tenant-data matrix and have **no routine access**; their exceptional access is a separate, dual-authorized and logged break-glass procedure.

**Multiple simultaneous roles:** Effective access is determined from authenticated membership, organization/estate/unit assignment, active shift/contract where relevant, resource classification, explicit grants and deny rules. If one person is both a resident and an officer, they must use a clearly indicated role context; an officer role is never activated through the resident context, and conflicts are logged and controlled. An auditor-only account must never inherit edit privileges through a default Frappe role or organization configuration. Restrict creation and elevation of privileged users with dual control where feasible.

**Sensitive registries:** Security Officers and Security Managers may access and search the current and historically relevant permanent resident/vehicle register and the visitor register **for their assigned estate and operational purposes**. This meets the requirement that security can identify a household and contact it. The product should present only necessary identity, unit, vehicle and approved contact fields in the operational search view, provide a `Call Host / Resident` action, and log lookup attempts. Do not force staff to browse a broad resident directory when a plate-based result is sufficient; do not disable necessary legitimate registry functions.

## 29. Resident Report → Security Alert → Verification Workflow

### 29.1 Resident mobile and web reporting interface

Create a `Report Parking Concern` action on resident home screens. Include category, narrative, optional photo(s), map point/road/zone, optional manually entered plate text and `Emergency access currently obstructed?` indicator. In Identified mode only, capture the authenticated reporter/household privately; in Anonymous mode, use the separate identity-unlinked intake path specified in section 34. Never allow resident searches to resolve plate ownership, host unit or visitor identity. Do not display other residents' reports, except approved aggregate summaries. Default GPS to an explicit one-time action (not background tracking); allow location correction and manual zone fallback.

### 29.2 State machine and evidentiary boundary

`Draft (resident-local) → Submitted → Received by Security → Assigned / Under Review → [Verified and Linked to Official Incident | Resolved without Violation | Not Substantiated | Duplicate / Merged | Withdrawn with history] → Closed`.

Only authorized security may set investigation and verification outcomes. For a verified report, generate a **separate official Violation Incident** with its own immutable ID, rule snapshot, officer identity, verification time and officer-collected evidence. Cross-reference the resident concern ID; never silently rewrite what the resident originally alleged. Security is responsible for contact calls, appropriate warning starts, further investigation and lawful enforcement. No automated financial consequence or driver notice from a resident allegation alone.

### 29.3 Alert delivery and task assignment

Upon server acceptance of a report, atomically create an estate-scoped security task and durable notification-outbox event. Route in-app alert/push to available assigned officers and the security manager, with priority rules that an association can configure **within non-overridable safety boundaries**. Track pending/delivered/opened/acknowledged/assigned/escalated states separately; allow assignment or claim-lock to avoid multiple officers treating the same concern as different incidents. Push failures must not lose the durable task. Avoid disclosing resident reporter PII on lock-screen notifications. Provide shift handoff, missed-alert escalation and a management view of response times; alert-time targets remain estate-configurable and tested.

Urgent reports are immediately highlighted for on-duty security and may escalate to supervisors. Urgency stated by a resident is **not** itself proof of an emergency or authority to tow; officers independently verify and follow the approved safety procedure.

### 29.4 Resident feedback, abuse controls and analytics

Show reporter-safe status updates with receipt ID and timestamps, generic resolution text and an optional feedback mechanism **for identified reporters**. For anonymous reports, provide only a voluntary, unlinked receipt-code status check, and never promise direct follow-up when no return channel was provided. Limit repeated submissions/spam, rate limit photos and attachments, validate MIME/malware, and provide duplicate detection; retain a route for good-faith reports. Make `reports submitted`, `reports verified`, `unsubstantiated`, `time to security acknowledgement`, `time to resolution` separately countable and filterable. Prevent report-count inflation from merged duplicates. Never expose the reporter's name, host/unit, photos containing bystanders, complete license plate, exact GPS point or alleged driver's identity in neighborhood-facing charts.

## 30. Privacy Protection and Frappe Authorization Implementation

### 30.1 Implementation requirements

- Use **per-organization Frappe sites** for tenant data isolation and explicitly authorized per-estate/per-unit access within each site. No user-supplied organization ID, `Host` header, URL slug, local storage value or mobile build property may confer tenant rights.
- Define dedicated minimal Frappe roles and DocPerm levels; **never assign Frappe `Administrator` (superuser) or unrestricted `System Manager` to tenant management-company, estate, security, auditor, finance or resident users**. Then use **User Permissions**, `permission_query_conditions` for list/report counts and `has_permission` for individual-document access. A list filter without a matching document-level check is unacceptable; both must deny unauthorized deep links. Apply action-specific checks to whitelisted RPC/API methods, custom reports, direct file access and exports. Never expose unrestricted `get_all`, unguarded SQL or `ignore_permissions=True` to client-supplied identifiers.
- Implement a **central authorization service** tested against the role/action/resource/scope matrix; use server-authoritative permissions to return a filtered navigation manifest to clients. UI must reflect permissions, but API enforcement independently rejects unauthorized operations and writes auditable forbidden-action events.
- Distinguish classified data: `PUBLIC_AGGREGATE`, `SELF_HOUSEHOLD`, `STAFF_OPERATIONAL`, `SENSITIVE_RESIDENT_REGISTRY`, `SENSITIVE_VISITOR_LOG`, `RESTRICTED_EVIDENCE`, `FINANCIAL`, `IMMUTABLE_AUDIT`. Tenant-custom fields inherit the containing record's classification or a stricter classification; associations cannot label a sensitive phone/name/plate field as public.
- Scope sensitive data to the **least necessary operational context**: assigned estate, active role, approved purpose and optional shift. Officer can look up plate and reach the responsible household; resident cannot discover ownership through search/autocomplete, generic API error differences, shared media URLs, public maps or notifications.
- Default no bulk registry exports. Any special approved export must specify purpose, case/estate scope, authorized recipient, expiry and watermark/traceable job, with masked fields by default; signed URLs expire, downloads are counted and audited. Native app offline storage must not contain complete resident/visitor directories.
- Store all authenticating identities in individually assigned accounts; enable MFA for supervisors, managers, finance and auditors, strong session/token controls, remote session revocation, restrictive service accounts and short-lived credentials. Prohibit shared security logins. Where offline dispatch is needed, only previously authorized provisional drafts can be written offline; no privileged action based on stale credentials.
- Enforce separation of duties: author of evidence cannot secretly alter originals; an enforcement action needs the correct independent approval; fee schedule activation/waiver/refund approval and appeal adjudication have distinct authority paths; auditor is always read-only; the system operator cannot modify a tenant audit chain.

### 30.2 Protected views and auditability

Provide two *independently protected* registers, `Resident / Registered Vehicles` and `Visitor Check-in / Check-out`, with security-specific operational screens and manager-only administrative screens. Residents receive dedicated household `My Vehicle Requests` and `My Reports` endpoints, not repackaged access to either log.

Log reads of protected registries, search terms where proportionate, record opens, attachment views, denied attempts, authorized bulk exports, changes, and break-glass access. Audit logs must be tamper-evident with independent retention/backup and limited auditor query rights; privacy-preserving logs should avoid reproducing entire resident records in log payloads. Define practical retention by record category and local legal review, including visitor log deletion schedules and legal-hold constraints.

### 30.3 Privacy-safe reports and map layers

Partition reports into **private operational**, **management/audit**, and **resident-approved aggregate** datasets. A resident-facing dashboard should use delayed or grouped zone totals and configurable minimum aggregation thresholds; if there are too few incidents in a zone/time window, suppress the cell or widen the region/time period to avoid identifying a single household or vehicle. No resident drill-through to raw incident IDs, reporter names, plates, security-call history, live patrol/officer GPS, visitor movements or exact compound gates. Auditor read-only views must use an approved dataset; sensitivity and cross-estate scope remain independently enforced for dashboards, SQL/BI connections, scheduled reports and downloadable exports.

## 31. Role-Specific Applications, Administration and Operations

### 31.1 Primary surfaces

| Surface | Default landing modules | Explicitly excluded |
|---|---|---|
| Management web / tablet | Overview, estate/unit/vehicle and visitor registers, security queues, case approvals, enforcement, billing, policies, user roles, analytics, auditing | Cross-tenant content unless explicitly assigned; deletion of immutable audit |
| Security Manager mobile/web | Security queue, officer assignments, both registries, urgent issues, warnings, compliance, enforcement approvals, team reporting | Unapproved policy or fee edits, hidden audit alteration |
| Security Officer mobile | Check Vehicle, Check-in Visitor, Resident Reports, Patrol/Report Violation, Assigned Cases, Contact Household | Finance changes, registry bulk exports, administrator settings |
| Resident mobile/web | Report a Concern, My Reports, My Household Vehicle Requests, My Cases/Appeals, Approved Community Reports | Resident vehicle registry, visitor log, security queues, operational heatmap drill-through |
| Auditor web/tablet | Approved Dashboards, Audit History, Scoped Case/Financial Review (if granted), Access Review | Add/Edit/Delete, report concern, contacts, approvals, operations, unrestricted exports |
| Finance web | Incident Charges, Towing/Storage Reconciliation, Payments, Refund Requests, Financial Reports | Security case verification, unrelated personal-directory browsing |
| Tow contractor task portal | Assigned Dispatches, Arrival/Condition, Storage and Release Record | Community directories, fee schedule administration, unrelated jobs |

### 31.2 Provisioning, permission changes and user lifecycle

- Association administrator invites security officers/managers, residents, auditors, finance users and delegated management companies; every invitation verifies destination and estate/household association. Residents cannot self-assign a unit by merely knowing an address or unit number.
- Staff accounts bind to employment/contract scope and date; support automated/management-triggered deactivation, revocation, temporary delegation, emergency removal and lost-device logout. Audit role additions/removals; require privileged authorization and optional dual control for sensitive grants.
- Distinguish SaaS platform operator, association owner, and external management service provider. A management company working for several associations needs **separate contractual grants and tenant-bound sessions**. Do not merge organization databases or expose cross-tenant consolidated PII to simplify operations.
- Include a read-only auditor onboarding template with approved dashboard/report scope, expiry and strong authentication. Elevated audit access to raw registry or visitor data is exceptional and scoped, never the auditor's baseline role.
- Associate each delivered screen, component and action with a documented permission identifier and an API authorization test. Unauthorized users see appropriate 403/404 without presence leakage; accessible screens show clear read-only states rather than deceptive edit controls.

## 32. New v1.2 Acceptance Criteria and Mandatory Adversarial Tests

**AC-35 Role provisioning:** Create and assign Management Company Admin, Security Manager, Security Officer, Resident, Auditor and Finance Officer to two organizations and three estates; demonstrate correct navigation and verified scope from browser and native apps.

**AC-36 Registry privacy:** Resident cannot access resident/registered-vehicle directory or visitor logs via UI, API, URL ID guessing, list/query, autocomplete, report, export, attachment or direct download; prove with automated negative tests. Resident can still see their **own vehicle application card** through a dedicated scoped endpoint.

**AC-37 Security operations:** Officer can search current resident/vehicle and visitor registrations only within assigned estates, register and check out a legitimate visitor, link host unit, contact the right household and record the call. Reads and contact operations are logged. No bulk private-data export.

**AC-38 Security manager:** Supervisor can view officer queues, both protected registers, assign tasks, approve eligible enforcement and view team metrics without editing fee rules or immutable photos.

**AC-39 Management delegated scope:** Management agency has all authorized operations within assigned organization/estate, but cannot reach an association it does not manage, even by cross-tenant login, guessed document ID or header substitution. Management does not bypass legal go-live gates.

**AC-40 Auditor is non-mutating:** Read-only auditor may open granted dashboards/case/audit records but cannot create resident reports, official incidents, contacts, notifications, grants, invoices, approvals, data changes or exports without additional explicit grant. Validate direct POST, PATCH, DELETE, RPC, background-task and offline sync endpoints.

**AC-41 Finance separation:** Finance user can reconcile assigned incident charges, provider receipts and authorized refunds but cannot browse visitor directory, independently verify offenses or authorize a clamp/tow.

**AC-42 Expired/revoked roles:** Role expiration, estate reassignment, contract termination, user suspension and device revocation invalidate new API access, push channels and sensitive cached/offline data as designed. Session/role switching cannot mix data from old organizations or accounts.

**AC-43 Resident report submission:** Resident submits an identified or genuinely anonymous suspected violation with optional photo, GPS/manual pin and plate text. Server creates an unverified concern, not an official incident; identified reporter can view own status and anonymous reporter can use an unlinked receipt code only if saved. See AC-55–AC-68.

**AC-44 Alert to security:** Submission reliably creates a durable estate-specific alert and assignment, sends app/push to on-duty officers, records acknowledgement and retries failures without duplicate incidents or revealing reporter identity on a locked phone.

**AC-45 Security verification boundary:** Officer verifies a valid report and promotes it into a separate official incident with traceable link, rule version and officer evidence; unsubstantiated/duplicate reports close with reason. Resident cannot trigger the promotion by API tampering.

**AC-46 Reporter visibility:** Identified resident sees only their own report status and permitted resolution notes; anonymous submission is never added to any user account history and may only expose limited receipt-code status. Neither can view who was contacted or the alleged driver's identity, or enumerate other reporters or reports. Changing resident unit assignment adjusts access prospectively without exposing prior unrelated units.

**AC-47 Abuse and privacy safety:** Rate limiting, photo validation, duplicate detection, false-urgency handling, security alert escalation and manual GPS fallback work. No unsolicited enforcement action is generated from a suspicious or incomplete submission.

**AC-48 Enforcement segregation:** Security officer may document/action an approved tow but cannot self-approve an action requiring a manager. Reporter submission alone cannot start a warning timer or produce penalty; emergency override demands privileged audit and legal feature gate.

**AC-49 Fee/audit governance:** Management approvals, invoice amendments, refunds and appeals are independently logged; one incident carries only one core violation fine. Auditor sees authorized read-only financial/audit data; no one can rewrite original photos or silently delete the history.

**AC-50 Filtered dashboards:** Resident only sees approved anonymized counts and delayed/coarse hotspots. Attempt to use Frappe Insights, filter parameters, geolocation, chart drill-through or report download to expose private case/visitor/resident data fails.

**AC-51 Native UI by role:** Same App Store-ready build provides fully functional but different landing/navigation/action sets for resident, officer and supervisor; role switching and organization switching revalidate authentication and scoped offline storage.

**AC-52 Access logging and export governance:** Protected registry searches, visitor log accesses, case evidence, attempted unauthorized API calls and approved PII exports appear in a tamper-evident audit. Special auditor registry access requires a grant with reason, independent approval, minimal fields and expiration.

**AC-53 SaaS customizations cannot weaken security:** Association configures custom resident/visitor fields, fee tables and dashboard visibility without granting resident direct register access, auditor write access, cross-tenant access, public PII maps or illegal enforcement activation, including through custom scripts/imports.

**AC-54 End-to-end scenario:** Resident sees car blocking a gate → files identified or anonymous report/photo/location → both security officer and security manager notified → officer claims and investigates → one-action conversion creates linked verified incident, preserving original submission and using officer evidence → officer links authorized plate/unit and contacts host → validated warning/emergency action follows configured lawfully enabled policy → clamping or tow (if authorized), itemized fee/storage → resident or obligated party appeals → authorized auditor reviews read-only evidence and management sees privacy-safe charts. Demonstrate success/failure/denied-access branches with two tenants and both iOS/Android builds.

## 33. References and Version Notes for v1.2

Verified Frappe security implementation references (review against the selected supported version during Phase 0):

- Frappe permission model, DocPerm and Administrator/System Manager privilege implications: https://docs.frappe.io/framework-git/security/permission-model
- Frappe `permission_query_conditions` and `has_permission` for list and document scope: https://docs.frappe.io/framework-git/security/permission-query-conditions
- Frappe permission enforcement and code-level pitfalls (`get_list` vs `get_all` and `ignore_permissions`): https://docs.frappe.io/framework-git/server-side/permissions-in-code
- Frappe users, roles and per-field permission levels: https://docs.frappe.io/framework/user/en/basics/users-and-permissions
- Optional Frappe v16+ custom permission types (only if verified compatible): https://docs.frappe.io/framework/permission-types

**Version notes:** Version 1.2 supersedes v1.1 and retains all requirements for Frappe-based SaaS tenancy, native iOS/Android and desktop delivery, app-store design, resident/unit/vehicle linking, visitor check-ins, GPS/geographic heatmaps, warnings, clamping, towing, storage, charges, payments and appeals. It adds: formal management company/security officer/security manager/resident/auditor/finance roles; separate resident suspected-violation reporting and security alert triage; non-mutating auditor access; hard boundaries around both private vehicle/resident and visitor logs; explicit action/resource scope; role-specific navigation; access auditing; **20 additional acceptance criteria (AC-35–AC-54)** and staged delivery gates. Requirements in sections 28–32 take precedence wherever an older paragraph might imply broader rights.




---

## 34. Mandatory v1.3 Resident Allegation Intake: Identified and Anonymous

**Priority and precedence:** Sections 34–37 are binding v1.3 additions and override any prior v1.0–v1.2 sentence that requires every resident report to be tied to an authenticated account, stores a reporter identity for an anonymous report, or suggests security can automatically penalize an alleged offender. A report is an **allegation** until independently verified by an authorized officer.

### 34.1 Two explicit reporter modes

The resident reporting form must open with a privacy choice; never silently default to anonymous or imply that an identified report is public.

| Setting | **Identified report** | **Anonymous report** |
|---|---|---|
| Reporter attribution | Verified resident identity, membership and unit stored in restricted metadata | No reporter name, account ID, unit link, login token, phone number or persistent device identifier linked to submission |
| Who can see identity | Only designated authorized staff who demonstrably require it for follow-up; not the accused resident, general security alert, neighborhood dashboard or contractors | Nobody in the normal application because no identity is collected or stored with the report |
| Follow-up | Security may request clarification and return private status through in-app notification or approved contact methods | No direct follow-up or push notification unless the person separately opts into a return channel; a secret receipt can allow a limited *pull* status check |
| My Reports | Visible only to the reporting user/authorized household policy where appropriate; not a public feed | **Not** shown in account's My Reports, household profile, push history or audit view as an attributed submission |
| Photos and location | Optional one-time GPS, adjustable vehicle pin, photos | Same optional fields, but with extra privacy warning and metadata stripping |
| Case processing | Same official security triage and verification standards | Same standards: anonymous reports must not be disregarded by default, or treated as proof without officer verification |

**Material privacy limitation:** "Anonymous" must never be marketed as an absolute, forensic impossibility of identification. Timing, CCTV, distinctive descriptions/photos, infrastructure/provider network logs and voluntary disclosures can sometimes reveal identity. The application must truthfully explain its technical anonymity boundary, retention, and unavoidable service-provider or legally compelled disclosures. If source IP addresses, cookies, session identifiers, request-tracing IDs or device identifiers are retained in a way that permits association with a submission, the interface must **not** label that implementation genuinely anonymous. In that case the feature is "Confidential/identity hidden from staff" until technical remediation and privacy verification are complete.

### 34.2 Anonymous capture architecture

1. The resident app provides a **Submit anonymously** choice. Selecting it must leave authenticated resident context and launch a truly separate, identity-unlinked intake session. Do not carry the resident's access token, cookies, user ID, unit ID, push token, advertising ID, device fingerprint, original URL query state or analytics visitor ID into that flow. Do not submit first under a logged-in session and later erase the identity; that is not the same as anonymous intake.
2. Associate the submission with an **estate** using a privacy-reviewed access mechanism such as an association-specific anonymous reporting URL/QR code with rotating access control, or a deliberately designed unlinkable credential. Do **not** derive estate selection from an individual resident's login, user-specific invitation or household identifier. The choice of solution must be documented, tested against abuse, and workable from iOS, Android and web.
3. Public anonymous endpoints must be protected against outside submissions and abuse with privacy-preserving rate limits, attachment caps, malware checks, duplicate suppression, and/or an accessible CAPTCHA or scoped community code. Avoid permanent IP-based tracking or identity-based abuse controls that defeat the anonymity promise; disclose unavoidable transient security telemetry.
4. Minimize reverse-proxy, gateway, application, WAF, CDN, analytics, crash, third-party notifications and database logs capable of correlating report traffic to account or device. Document concrete settings, retention, access, and testing; do not promise that third-party infrastructure performs no logging without verification.
5. Strip photographic EXIF and other embedded author/device/location metadata from **resident** uploads **before persistence and before creating thumbnails**. Capture only the explicitly submitted vehicle location and photo itself as incident data. Display a warning that recognizable people, cars, doors and landmarks inside an image may still identify the reporter; offer crop/blur where feasible. Preserve file integrity/hashes on the sanitized image. Officer-collected official evidence is governed separately by chain-of-custody requirements.
6. Anonymous reports must not record household association or be exposed through account-specific dashboards, search history, resident notifications or export functions. Authorized staff may investigate the *allegation and vehicle*, not investigate who filed it absent a separately governed legal/safety process.
7. Provide an optional high-entropy **receipt ID plus secret lookup token** shown once at submission and downloadable/copiable. Store only a salted/slow-hashed verification value or equivalently secure token digest; prevent enumeration and replay. The anonymous reporter may view a minimal, privacy-safe status page by presenting the secret. Losing the secret means there is no recovery through resident lookup. There is no obligation to offer direct messages or requests for clarification.
8. If an anonymous reporter voluntarily supplies a callback email or telephone number, explicitly relabel the submission **Contactable confidential** (not truly anonymous), segregate that contact data from security-wide queues, capture consent, and allow removal under an appropriate retention policy. This does not require collecting a resident/unit identity.
9. Privacy notices must be localized per jurisdiction, and the store-distributed app must accurately declare collected data, permissions, tracking behavior and any optional location/photo access. Never request continuous background GPS for reporting.

### 34.3 Mandatory allegation form

The report form shall be concise and mobile-first, with configurable association-specific fields that cannot compromise privacy or tenant segregation:

- Choose **Identified / Anonymous** with clear, plain-language privacy consequences.
- Select alleged issue: gate or driveway blocked, roadway obstruction, unsafe parking, unauthorized space, emergency access, other (policy-configurable).
- Enter narrative and optional visible plate characters **manually**; never permit resident lookup of registries or plate-to-unit ownership.
- Pin the suspected vehicle on a map; optionally capture one-time GPS and display accuracy plus an adjustable pin, or choose a road/zone manually. Reporting device GPS is not claimed to be the actual vehicle location unless verified.
- Attach optional photographs, with consent explanation and the anonymous-mode metadata controls above.
- Mark **urgent access/emergency concern**, accompanied by instruction to contact estate emergency/security numbers directly in an active emergency; do not imply app response substitutes for emergency services.
- Review report details, choose Submit, receive a reference number, and (if anonymous) separately receive the optional one-time secret status token.
- Upon success, report is saved as **UNVERIFIED / SUBMITTED**, with no fine, enforcement order, official warning, or lookup disclosed to the reporter.

### 34.4 Minimal data model and classification

Create or extend Frappe DocTypes with tenant/estate-level scope and restrictive permissions:

- `Parking Allegation`: immutable allegation ID; tenant/estate; public-safe category; narrative; alleged plate text; submission timestamp; location source/accuracy/pin/zone; priority claim; anonymous/identified classification; triage state and disposition; dedup cluster; report version and policy snapshot as appropriate. `reporter_user` and `reporter_unit` **nullable and absent** in anonymous mode; never fill these from headers, session or later plate matches.
- `Allegation Attachment`: sanitized resident photograph, upload hash, file validation, access classification; never public URLs.
- `Allegation Receipt`: cryptographically random one-time anonymous status secret with independently protected verification and short-lived/limited queries; store no reverse user/account mapping.
- `Security Work Item` and `Notification Outbox`: durable estate-scoped tasks and delivery state; security alert identity fields contain no anonymous or unneeded reporter PII.
- `Allegation Review Event`: append-only officer assignment, inspection, findings, classification and disposition history. Do not alter original alleged facts.
- `Official Violation Incident`: separate immutable incident ID with foreign-key/link to `Parking Allegation` (allow multiple separate allegations linked to a single verified real-world violation when justified); reviewer/officer ID; verified plate, unit or visitor link (if authorized), physical location, evidence, verified rule/version and decision history. No official violation exists solely because a report was submitted.
- `Officer Evidence`: separately captured, timestamped officer photographs, GPS observation, *confirmed vehicle map pin*, accuracy, visual inspection and tamper-evident digest. Never merge a resident's submission into an officer attestation.

Do not copy or denormalize identified reporter information into ordinary incident list views, officer push alerts, accused-person notices, payment records, graphs or report exports. Use restricted, separately auditable fields only if follow-up requires it.

## 35. v1.3 Security Officer and Security Manager Workflow

### 35.1 Dual notification and durable intake

1. An accepted report creates the allegation record, an estate-scoped **Security Work Item**, and a durable notification-outbox event in one atomic transaction (or equivalent transactional-outbox design). This operation is idempotent under repeat form submissions and retries.
2. Notify **on-duty Security Officers assigned to that estate** and the **Security Manager** through in-app alerts. Send approved push notifications where enabled. The manager must be informed even if an officer is not currently online. No reporter identity, complete plate, photo or exact residential address on lock-screen banners.
3. The queue shows claim status, age, category, coarse location, reported urgency and acknowledgement. Officers may **Claim / Begin Investigation**; use atomic locking to prevent duplicate, concurrent conversion or duplicate enforcement.
4. If no assigned officer acknowledges within the estate-configured response target, escalate to the manager with a separate durable escalation event; preserve after-hours/shift handover. A failed push notification never loses the work item. In an emergency, the app clearly states that the alert is not guaranteed immediate dispatch.
5. Security Manager can oversee assignment, prioritize, reassign, review substantiation and audit officer progress. A Security Officer may investigate and verify within an assigned estate, but cannot approve manager-controlled clamping or towing using this workflow.

### 35.2 One-action conversion: *Allegation → Official Violation*

Officer opens allegation and sees resident-submitted narrative, images, reported coordinates/map pin, issue type and optionally the confidential identified-reporter details only when explicitly allowed for a documented follow-up purpose. The default screen hides reporter identity.

- Officer physically visits or otherwise follows an approved verification process and records their **own** current observations, GPS or corrected vehicle position, photographs and violated published rule. Resident evidence can guide the investigation but does not replace officer verification.
- Officer may **Verify & Create Violation**; this is a single guided action that pre-populates appropriate editable fields from the allegation and links its original report, avoiding redundant data entry. Pre-filled resident-supplied facts remain visibly **Unverified Resident Allegation** until an officer independently attests to them.
- Server validates role, estate, active assignment, submitted evidence, rule, duplicate check and policy conditions **before** committing. On success, create an independent Official Violation Incident ID and immutable cross-reference, preserving all original report/attachments and review history. Never promote by changing the original allegation's record type or overwriting its content.
- If multiple residents report the same parked vehicle/event, merge/associate those allegations under one verified incident **without duplicate core penalties**. Record each source allegation and separate notification/receipt appropriately. Concurrent officers and retries must not create duplicate billable incidents.
- Officer may instead choose **Not Substantiated**, **Resolved Before Verification**, **No Violation**, **Duplicate/Merged**, **Further Investigation** or **Escalate Safety Emergency**, with factual reason and traceable timestamp. None of these outcomes triggers a penalty automatically.
- From the verified incident, **Security—not the reporting resident—**uses authorized resident/vehicle and visitor logs to locate the relevant host/driver, performs contact calls, sends the configured warning, and records contact success/failure. After the applicable period, manager approval and legal checks govern clamping, towing, storage and itemized fees. For blocked gates or emergency access, safely prioritize authorized removal over clamping in place.

### 35.3 Status and communication rules

- **Identified reports:** Reporters receive confidential receipt and basic state updates (Received, Assigned, In Review, Verified/Action Taken, Resolved, Not Substantiated) using their authorized app view or approved channels; security may request additional details. Never disclose the alleged driver's identity, household affiliation, complete plate, private visitor logs or enforcement staff notes.
- **Anonymous reports:** No automatic callback, named account notification or "My Reports" entry. Show optional read-only, generic state information via saved secret receipt; no bidirectional conversation by default. When security needs clarification but no return channel exists, indicate internally **Follow-up unavailable: anonymous report** and continue verification using independent evidence.
- Association administrators may customize wording, report categories, manager escalation windows and notification templates, but may not make anonymous reporting secretly identifiable, expose protected logs to residents, generate automatic penalties, or bypass security verification.

### 35.4 Reporting and dashboards

Provide management-only dashboards and appropriately redacted auditor views for `Allegations by source (identified vs anonymous)`, `Pending triage`, `Officer acknowledgement SLA`, `Time to verification`, `Conversion rate`, `Not substantiated`, `Duplicate/merged`, `Validated violations`, `Warning compliance`, and `Violation GPS hotspots`. Separate *allegation* heatmaps from **verified violation** heatmaps by explicit labels; anonymous reporter locations must not be plotted. Only show the explicitly claimed vehicle pin, suitably aggregated/delayed for resident-facing visuals. Avoid publishing sparse data that identifies individual complainants.

## 36. v1.3 Role-Specific Interface and Privacy Constraints

| Actor | Required screen/behavior | Prohibited behavior |
|---|---|---|
| Resident (identified) | `Report Concern`, own confidential report history, optional replies, approved community aggregates | Browse other reports, plate registration/visitor logs, officer contacts, case investigation details |
| Resident (anonymous flow) | Separated non-authenticated reporting form, privacy notice, optional secret receipt-status lookup | Attach identity/session/household metadata, show submission under signed-in resident account, promise direct follow-up |
| Security Officer | Incident queue + alerts, claim/investigate, view allegation/evidence, `Verify & Create Violation`, authorized plate-to-unit lookup, documented warning/contact | Change report author's original claims, charge directly from allegation, self-approve manager-only enforcement, unrestricted reporter-directory browsing |
| Security Manager | All estate security queue, real-time SLA, assignment/reassignment, officer approvals within approved policy, evidence/violation review | Unlogged identity lookups, tenant-crossing access, rewriting submitted evidence |
| Management Company Admin | Scoped configuration, policy and category design, authorized reports and appeals, approval controls and performance dashboards | Reconfigure away anonymity, override immutable audit or access unrelated estates |
| Auditor | Approved read-only inspection and redacted dashboards; exceptional access only through time-limited, independently approved grants | Modify allegations, notify persons, verify or convert a report, authorize fees or enforce |
| SaaS Platform Operator | Cross-tenant operational health, subscription, feature flags and aggregate uptime | Routine access to raw allegation photographs, identities, visitor/resident registries or private incident locations |

App-store distribution requirement: camera and GPS access must be contextual and permissioned, with clear purpose strings, an explicit manual-location alternative, no background location requirement for allegations, accessibility of anonymous mode, truthful data collection declarations, and documented privacy policy/retention terms for Apple/Google/Samsung review. In-App sign-in behavior must not accidentally attach tokens to anonymous intake requests.

## 37. New v1.3 Acceptance Tests — Required Before Pilot

**AC-55 — Reporting mode selection:** Resident chooses Identified or Anonymous; interface accurately explains what is stored, who sees it, follow-up limits and potential metadata disclosures. No dark patterns.

**AC-56 — Identified report:** Authenticated resident submits an allegation with narrative, optional manually entered plate, photographs and pin; identity stored only in appropriate restricted fields; another resident cannot view or search the report.

**AC-57 — Anonymous true-separation test:** Starting from an authenticated mobile session, submit anonymously and demonstrate that the submission request, report, audit record, attachment, outbox, app analytics and user history have no identity/account/household/device correlator. Review server/CDN/WAF/reverse-proxy logging and disclose any residual linkability; if it remains, disable the anonymous label until fixed.

**AC-58 — Anonymous photos:** Upload resident photo containing EXIF geotag/device metadata. Confirm original identifying metadata never persists in resident-allegation storage or previews, and that explicit vehicle-location input is retained separately and correctly.

**AC-59 — Anonymous receipt:** Generated unpredictable code permits only generic status retrieval; account login cannot recover report ownership; wrong code fails without leaking existence; absence/loss of code means no follow-up, explained before submission.

**AC-60 — Security + manager notification:** One report triggers durable work item and separate delivery attempts to on-duty assigned officers and security manager. Retry/offline/push failure leaves one allegation and one active work item, not duplicates.

**AC-61 — Officer claim & investigation:** Two officers attempting to claim simultaneously yield one valid assignment. Officer can open original allegation, visit scene, confirm GPS/zone/photo and preserve the resident's original unverified statements.

**AC-62 — One-action conversion:** Authorized officer selects Verify & Create Violation, system pre-populates useful report fields yet requires officer verification/evidence, and creates a *new linked* immutable official case. Original report remains unchanged and all changes are audit logged.

**AC-63 — Rejected, resolved and duplicate allegations:** Officer can mark Not Substantiated, Resolved Without Violation or Duplicate/Merged with reason; no warnings, fees, clamping or towing are automatically generated. Multiple resident allegations cannot yield duplicate penalties for a single incident.

**AC-64 — Subsequent enforcement:** Following conversion, authorized security searches registry/visitor information, calls the proper contact, records delivery/response, follows warning or safety exception and manager approval, then issues only lawful configured charges. Reporter cannot perform those actions.

**AC-65 — Anonymous follow-up boundary:** Anonymous submission creates no message, push or report history in any resident account. When no receipt is saved, no return channel exists; internal interface accurately says follow-up unavailable. Voluntary contact request is reclassified as Contactable Confidential.

**AC-66 — Location and mapping:** Resident GPS defaults off until explicit request; officer captures independent observations. Charts distinguish unverified allegation density from verified incident hotspots, and resident-facing charts suppress precise household and reporter data.

**AC-67 — Security of attachments and reports:** Unauthenticated deep links, document guessing, cross-tenant access, forged role headers, direct file URLs, exports, cached mobile files, push previews and offline resynchronization do not disclose identified reporter or anonymous link data. Auditor role remains non-mutating.

**AC-68 — End-to-end mobile demonstration:** On physical Android and iOS devices, demonstrate both reporting modes, security + manager alerts, one-action verified-case creation, read-only receipt/status, and role-based denial tests. Include privacy and app-store data collection checklist evidence.

## 38. Delivery Instructions and v1.3 Change Log

Claude must extend, not replace, all earlier requirements: multi-tenant Frappe SaaS; configurable management policies and fees; resident/unit/vehicle history; gate visitor registry; native-store-ready Android/iOS and desktop experience; GPS and verified-hotspot reporting; finance including one core violation penalty plus lawful clamp/tow/storage lines; management approvals; appeals; audit and least-privilege roles. **Implement v1.3 sections 34–37 as first-class scoped Phase 1/2 features**, not a later optional enhancement. Demo the full report-to-verified-case flow early with two isolated tenants. No production go-live, towing activation, live penalty collection or claim of store approval without separate authorization and verification.

**Version 1.3 additions:** Identified-vs-anonymous selection; non-identifying intake and honest privacy guarantees; safe photo handling and optional receipt-code tracking; durable alerts to officers *and* manager; security-assigned onsite verification; one-action allegation conversion into an independent linked official case using prefill rather than repeated paperwork; status separation and no unauthorized follow-up; anonymized source analytics; **14 additional acceptance criteria (AC-55–AC-68)**.

---

## 39. v1.4 Mandatory Design Philosophy and Operations Model

**The system should do the remembering, searching, linking, notifying, documenting and calculating; the officer should confirm facts and take authorized actions.** This version is a first-class refinement to the existing PRD, not a replacement. Where earlier text suggests a generic visitor form or merely manually logging calls, this section and following sections supersede it with explicit operator interactions and communications integrity requirements.

- First priority: the gatehouse officer can check in a returning visitor without retyping a plate, phone number, vehicle description or household record.
- Second priority: a responding officer can verify a resident allegation, open the resulting violation record, find an authorized host/driver contact, call or SMS within the case, and document the outcome without leaving the workflow.
- Third priority: supervisors can demonstrate when contact was attempted, whether anyone was reached, what was communicated and when, which policy governed the warning, and why clamping or towing was subsequently authorized.
- Operate on entry-level Android devices with modest memory, variable connectivity, gloves/sunlight, inconsistent charging, shared shift hardware and varying staff digital literacy. Do not assume the officer has an always-on desktop, reliable data plan, perfect GPS or comfort with lengthy forms.
- Require native iOS/Android store-ready applications as previously established, but pilot gatehouse UX on inexpensive Android hardware used by real officers. Functional equivalence is required; screens may adapt to form factor.
- Do not use a device's personal call log or SMS database as the system of record.

## 40. v1.4 Fast Gatehouse Visitor Entry and Repeat-Visit Matching

### 40.1 Mandatory entry flow

1. Officer opens `Gate / Check In`. The app defaults to assigned estate and active gate/shift, not a free-text estate field.
2. Officer chooses the fast lookup method: **Unit**, **Plate**, or **Scan Plate** (scan only if reliable OCR prototype is approved; manual lookup works without camera/OCR).
3. **Unit-first**: Enter `A1` (or select from recent/authorized unit suggestions). Show only relevant vehicle entries permitted for this gate officer: current resident registrations plus the **minimum necessary prior visitor-vehicle candidates** historically associated with visits to that unit, marked distinctly as `Resident Vehicle` or `Previously Visited`. Show recognizable plate, optional make/color, and an abbreviated last-visit indicator (e.g. `Visited before`, optionally date), not an unrestricted visitor activity history.
4. Officer selects a suggested plate, confirms it is the vehicle present and confirms **visiting this unit today**. System must never presume that historic association authorizes current entry or auto-check in without confirmation.
5. **New vehicle**: Officer enters the plate (keyboard adapted to local plate format but able to accept foreign/unusual plates), optional category/make/color, host unit, and as few other required fields as the association's approved policy permits. Visitor phone is optional unless approved as necessary; host's verified contact is an available default route. Prepopulate gate, guard and check-in timestamp.
6. Officer taps prominent `Confirm Entry`; show saved receipt and optional privacy-safe host notification. Time of actual entry must be distinguished from creation time and from offline-synced server time.
7. If a visit is still active for the same vehicle and estate, offer `View Active Visit` instead of blindly opening a second overlapping session; allow manager-mediated override where appropriate.
8. Provide `Check Out`, `Vehicle Not Found`, `No Plate`, `Pedestrian / Delivery`, and `Wrong Unit` exception routes. Make required departure capture configurable; avoid creating permanent phantom visits.
9. On exit, security can find active visits using plate, unit, recent arrivals or a compact activity list. Confirmation records the departure through the controlled lifecycle defined in **section 50**. An earlier visit must not be overwritten, and a resident driving out must not be misclassified as a departing visitor.

### 40.2 Correct modeling for repeat visitors

- `Vehicle` is not equal to `Visitor`, and `Visitor` is not equal to `Unit`. Use `Visitor Session` for each dated arrival and `Prior Visit Suggestion / Derived Vehicle-Unit Visit History` as an **index of past sessions**, not a permanent authorization link.
- One plate may visit several units, one unit may receive many plates, a resident might rent or change cars, and a ride-hailing car may visit multiple units in the same day. Never hard-code one-to-one relationship or automatically make a prior visitor a resident.
- Normalized plate is a **search key and candidate**, not conclusive legal ownership. Support plate collision/typo review; plate photo is optional and proportionate.
- When the officer types `A1`, return only the vehicle suggestions authorized by the officer's estate/gate assignment; do not return visitor names, other host addresses, full visit history, phone numbers, photo IDs or unrelated unit activity by default.
- Display human-readable attributes to avoid picking the wrong car with similar plates. Implement confidence labeling for OCR and a compulsory plate confirmation before registration or citation.
- Define sensible association-specific history/retention windows; expired or purged visitor histories must not persist indefinitely in auto-suggestion caches.
- Visitor check-in must provide appropriate notice about collection, purpose and retention of plate and unit information; no requirement to upload Ghana Card, national ID, passport or face photography by default.

### 40.3 Friction and measurable usability targets

- Returning vehicle check-in target: **three primary actions after selecting/entering unit**; benchmark **under 15 seconds** in a controlled usability test once the screen is ready; not a claim that real estate operations always meet it.
- New vehicle check-in target: **under 45 seconds** under suitable connectivity with minimal approved fields; measure using trained and first-time officers on entry-level Android phones.
- Prefer a numeric/unit keypad, large high-contrast tap targets, recent valid values, inline search, auto-capitalization and plate-format hints (non-blocking for foreign plates), clear success sounds/vibration where accessible, and one-screen forms with a progress indicator only when needed.
- No giant dropdown of all residents; no repeated sign-in per visitor; no keyboard requirement for values that can be selected. Association customization cannot force long forms into the `Express Check-In` path without a visible management warning and validation of impacts.
- Add demo/simulation mode with synthetic data for training. Never use real residents/visitors in demonstration accounts.

### 40.4 Optional future enhancement: host-pre-registered visitor invitations

- An authenticated resident may optionally pre-register an expected visit for **their own unit only** with anticipated arrival window, vehicle plate if known, category and a revocable opaque QR/pass token. Security must still confirm current host, actual vehicle, entry, and validity before checking in; an invitation is not an absolute right of access.
- Pre-registration should be **additive, not mandatory**. Walk-in visitors and low-tech households must still be admitted under estate policy without a phone/app. Avoid imposing visitor account creation or collecting unnecessary visitor contact details.
- Invitations auto-expire, are revocable, are tenant/unit scoped, cannot disclose historical visitor movement to residents, and never imply permanent vehicle/resident enrollment.
- Put this behind a per-association feature flag after the low-typing gatehouse core is stable; do not defer express returning-visitor check-in while building it.

## 41. v1.4 Contact Resolution and Reachability — Violation Workflow

### 41.1 Allegation-to-violation-to-contact sequence

1. Resident submits identified or anonymous allegation under v1.3. Security team and manager receive the scoped alert.
2. An on-duty authorized officer claims it, goes on site, captures independent photo/GPS observations and verifies or rejects the allegation.
3. Tapping **`Verify & Create Violation`** preserves the original allegation and produces a linked, official violation with all reuse-safe fields prefilled, with corrections and newly added evidence clearly attributed to the officer.
4. System attempts to resolve the observed plate to an **active visitor session at this estate first when relevant**; also checks current resident registration and historical/ambiguous candidates, clearly labeling confidence and temporal validity.
5. Show a `Contact Responsible Party` panel using a **server-authorized projection** of minimum operationally necessary contact fields, not a raw list of all residents or an entire visitor directory.
6. For an active visitor: show confirmed host unit and **current host contact(s)**; show visitor phone only if legitimately captured and authorized for enforcement communications. For resident vehicle: show active vehicle-to-unit registrations and authorized primary/backup contact(s). Unknown/ambiguous match: `No Verified Match` and a guided escalation path; officer must not assume a plate match proves who was driving.
7. Contacts are numbered by association-configured routing order: (a) on-site driver/visitor if reliable, (b) verified unit/household contact, (c) backup household contact, (d) duty supervisor. Officer can choose a permitted contact without copying the number to another app.
8. Each call/SMS/push/email attempt is attached to the immutable violation ID, contact resolution snapshot, officer, shift, and policy version, with strict permission checks.
9. Officer records whether the vehicle moved, moved late, requires assistance, is disputing identity, or remains obstructing; app computes next permitted action and any supervisor approval.
10. Emergency obstructing access overrides ordinary waiting only under approved safety procedure. Do not clamp an obstruction in place if that worsens the obstruction; lawful immediate removal may be appropriate.

### 41.2 Contact resolution edge cases

- Several adults attached to unit A1; one may be primary and another backup. Respect verified reachability, authorization and contact preferences.
- Resident phone changed, person moved, vehicle transferred, visitor visiting different host today, shared/borrowed vehicle, and incomplete check-out must not route warning silently to a stale person. Provide `Incorrect Contact`, `Wrong Plate`, `Wrong Host`, `Unknown Driver` and supervised correction flows.
- No current valid contact: log `Unable to identify contact` and escalate; never invent an acknowledgment or backdate a warning.
- Calling phone numbers is limited to authorized on-duty security. Residents cannot derive a neighbor's phone number via case/lookup/export/API, even from their own submitted allegations.
- Support Ghana `+233` E.164 normalization and international numbers while preserving the source string for audit; do not assume every number is Ghanaian or that a specific operator/carrier is always available.

## 42. v1.4 In-App Telephony, SMS and Provable Communication Timeline

### 42.1 Two legitimate call modes; do not misrepresent duration

**Mode A — Basic native dialer fallback (initial supported mode):**

- Officer taps `Call` beside an authorized contact; app securely deep-links to the platform dialer with the number and writes a `Call Initiated / Dialer Open Requested` event with local and server times and officer identity.
- Once the officer returns to the app, present large one-tap outcomes: `Answered`, `No Answer`, `Busy`, `Wrong Number`, `Could Not Place Call`, `Callback Requested`, `Other`. Allow a short optional note or a canned phrase.
- A phone dialer open event is **not evidence that a call connected**. The app must not claim an automatically verified connected call, provider outcome or duration; if officer enters approximate duration manually, label it `Officer-entered estimate — unverified`.
- Do not request restricted personal call-log/SMS-reading permissions just to reconstruct calls. Avoid permissions that would undermine Apple, Google Play or Samsung review.

**Mode B — Integrated provider-mediated voice calling (target capability / Phase 0 feasibility spike):**

- Provide an approved organization-funded voice provider integration that originates calls through a managed voice service or approved bridge, minimizing display of private phone numbers where possible.
- Store provider call ID, number dialed in secured fields, initiation/ringing/answer/end timestamps, duration, connection status, provider error, officer identity, cost, and callback signatures. Use **provider-supplied verified duration**, not device-generated estimates.
- Confirm the selected provider supports the required Ghana outbound numbers, caller identification, acceptable per-minute rates, local legal/regulatory requirements and testable call-status callbacks before choosing it. Do not claim a chosen vendor supports Ghana without verification.
- Audio recording is **disabled by default**, requires separate policy and lawful notification/consent where relevant. Never infer permission to record because the officer initiated an app call.
- If provider-mediated calls fail or network is offline, fall back to standard dialer and manual outcome logging. Record provenance (`verified-provider`, `officer-reported`, `requested-only`).

### 42.2 SMS must be sent through backend provider adapters

- Officer chooses `Send SMS`, sees a preapproved and policy/version-controlled message template populated with case number, plate (minimized/masked where practicable), location/zone, requested move-by time **only after a valid start is established**, and security contact route. Officer previews recipient and text before explicit send.
- Route through tenant-scoped server-side SMS gateway, e.g. a locally validated Ghana SMS API. Do not depend on personal device SMS permissions or an officer using their own number.
- Store `Message Created`, `Queued`, `Provider Accepted`, `Sent` (if reported), `Delivered` (if reported), `Failed`, `Unknown`, `Acknowledged` and/or `Replied` **as distinct states**. Delivery ≠ read/acknowledgment; sent ≠ delivered; unverified delivery must be reported as such.
- Immutable message snapshot: exact text sent, language, policy/template version, recipient reference, masked number in ordinary UI, encrypted accessible full number where necessary, initiator, provider ID, source, local/UTC time and provider delivery receipts. Support duplicate webhook delivery without duplicate SMS charges/sends.
- Support template languages configured per association; pilot with clear, plain English and evaluate local language options through resident/security testing rather than automatically translating legal notices.
- Rate-limit per case/contact and provider cost quotas to prevent repeated harassment or runaway SMS spending; require reason/approval for exceptional retries. Prevent confidential allegation reporter data from appearing in notices.

### 42.3 Notification and warning clock authority

- Association policy engine explicitly defines permitted notice channels, proof required for `notification established`, when the countdown begins, and when an unsuccessful contact escalates to supervisor. Default must favor **answered call with officer-confirmed warning**, documented explicit acknowledgment or another legally reviewed equivalent—not an unanswered call, unconfirmed outgoing attempt or merely queued SMS.
- A provider `Delivered` SMS alone must not silently imply the driver read or acknowledged it. Its treatment for formal notice must follow the association's published and legally reviewed policy; system UI must expose the basis.
- Time calculations occur on the server in UTC, with association-local presentation (`Africa/Accra` for pilot). Device time drift, offline outbox, daylight changes abroad, queued SMS and delayed delivery receipts must not falsely expire a warning.
- Each warning record includes `notice_method`, `proof_basis`, `notice_effective_at`, `grace_minutes`, `deadline`, `rule_version`, `notification_attempt_ids`, and `override_reason`/approver when applicable.
- If contact fails, provide `Notify Security Manager`, `Try Authorized Backup`, `Record No Verified Contact`; the app must not silently start a GH₵500 penalty timer.
- Emergency obstruction protocol may supersede the ordinary countdown for immediate, lawful removal. Warning/contact history remains in case and is never erased.

### 42.4 Example warning template (configurable)

> Community Security: Vehicle [PLATE] is parked in a restricted area at [ZONE]. Please move it immediately. For assistance call [SECURITY NUMBER]. Case [CASE ID]. Enforcement may follow under the published estate policy once applicable notice and escalation requirements are met.

No dynamic promised deadline should be inserted until the notice clock is actually established. Template variables must be escaped, limit sensitive data in lock-screen previews, and avoid threatening action without lawful authority.

## 43. v1.4 Officer-First Mobile Screens and Shortcuts

Mandatory screens and key actions (role and active estate/shift gated):

| Screen | Essential content and actions | Optimization |
|---|---|---|
| Gate Home | `Check In`, `Check Out`, `Find Vehicle`, `Incidents`, shift badge, offline indicator | Large five-tap-or-less routes, recent unit/plate suggestions |
| Visitor Check-In | `Unit` search, `Previously Visited`, `New Vehicle`, confirm gate/entry | Unit-first and plate-first lookup, return visitor in roughly 3 actions |
| Active Visits | Plates by gate, host unit, entry age, check-out, ambiguous duplicates | Current-status first, filter instead of typing |
| Allegation Queue | Priority, zone, photo thumbnail, age, manager escalation, `Claim` | No resident identity leakage or unrelated private info |
| Verify Allegation | Resident evidence distinctly labeled, independent photo/GPS, `Verify & Create Violation`, reject reason | Prefilled incident, preserve original immutable allegation |
| Violation Contact | Associated vehicle and confirmed host, `Call`, `Send SMS`, `Record Outcome`, `No Match` | One-action contacts, automated timeline, no needless directory browsing |
| Active Enforcement | Warning clock and proof, action permission, supervisor approval, move confirmed, authorized tow | No false countdown or unauthorized fee/clamp/tow |
| Shift Handover | Open contacts, unresolved incidents, unreachable hosts, active visitors, pending sync | Clear ownership across shifts, prevent abandoned work |
| Supervisor | Staff assignment, urgent queue, duplicates, overrides, authorizations, SLAs | Exception-oriented and audit-ready |

- Enforce field minimization. Administrative Frappe Desk screens are not acceptable substitutes for the designed security mobile screens.
- Use text **plus** icons, not icon-only critical actions. Strong contrast, visible focus, large labels, and low-reading-load, one-task-per-screen designs. Do not rely exclusively on red/green or color to communicate status.
- Offer guided first-time training and a 60-second contextual demonstration for new officers. Training must be available offline where feasible, with screenshots and simple language.
- Shared devices: per-officer login or shift PIN reauthentication with auditable real identity, biometric if appropriate/available, short automatic session timeout, locked-device protections and remote session revocation. Never share one group account among all guards.
- Voice dictation may be explored only as opt-in; do not require it or send private details to an undisclosed transcription service. No mandatory data-hungry background sync.

## 44. v1.4 Offline, Shift Changes, Device Reliability and Operational Continuity

### 44.1 Offline-first constraints

- Allow provisional check-in, check-out draft, incident notes, evidence photo and GPS observation offline with encrypted per-estate local queue. Never represent an unsynced record as committed or legally enforceable.
- Before offline use, securely cache a **minimum scoped operational subset** of active units and vehicle suggestions for assigned gate/shift, subject to association approval. Avoid offline caching the full resident and visitor directory or all phone numbers. Sensitive contact lookup should require online access unless narrowly authorized, time-limited and encrypted.
- On reconnection, synchronize idempotently (client-generated UUID and unique business constraints), preserve original captured time and server-accepted time, reconcile conflicts and show clear `Pending Sync`, `Synced`, `Needs Review` states.
- A stale offline visitor session must not create an overlapping active check-in. Stale or offline warning drafts must never automatically start a timer or trigger clamping/towing/payment.
- Photos should be resized for network cost while preserving encrypted evidentiary originals or an auditable high-quality copy and integrity information under policy; verify that auto-compression does not destroy critical plate readability. Delay nonessential uploads when network is weak.
- Detect low battery/data mode where platform allows, and provide printable/fallback incident reference instructions for prolonged outages (manual register to be reconciled, never fabricate timestamps).

### 44.2 Shift and management continuity

- Explicit `Start Shift` / `End Shift`, assigned post/gate, manager escalation and outstanding items. Handover shows claimed concerns, pending notices, unreachable contacts, unresolved obstructions, active impound cases, unsynced drafts and long-stay visitor sessions.
- Prevent cases from silently remaining owned by an off-duty officer. Supervisor reassigns based on shift and timeouts with audit and push fallback.
- High urgency events require a visible, acknowledged alert and escalation to manager; push notifications alone do not count as successful officer acknowledgment.
- Provide daily supervisor briefing and an exception dashboard covering missing visitor checkout, uncontactable hosts, clock anomalies, failed SMS, duplicate plates, mismatched registry and missing audit evidence.

## 45. v1.4 Extended Data Model and API Contracts

Add these explicit Frappe DocTypes/linked models to section 5, or map them to existing compatible DocTypes with documented uniqueness and permission behavior:

| Entity | Required fields / relationships |
|---|---|
| Gate Shift | estate, gate, officer, start/end, on-duty status, assignment and handover history |
| Visitor Vehicle Suggestion Index | estate, host unit, vehicle ref, derived allowed history count/last permitted visit, expiration/retention policy, suggestion source and confidence; **no permanent authorization semantics** |
| Visitor Session (extended) | vehicle, current host unit, entry/exit, category, privacy-notice state, gate/officer, provisional/offline ID, sync state, duplicate resolution |
| Contact Directory Projection | estate, contact source ref, active unit membership, role as primary/backup/visitor contact, masked/full number field policy, freshness/verification and valid-from/to |
| Contact Resolution Snapshot | incident, selected authorized contact, current relationship and match basis, resolution status, time, officer, alternate candidate and reviewer |
| Communication Attempt | case ID, contact ref, role/shift, channel, provider ID, destination (encrypted), source, initiated_at, status, outcome, duration with verified/provenance flag, error, template snapshot and cost |
| Communication Event | immutable child events for accepted/sent/delivered/answered/completed/failed/acknowledged, provider original timestamp, ingestion timestamp, webhook signature validation and idempotency key |
| Warning Notice | policy version, method, delivery/acknowledgment basis, effective_at, server deadline, grace time, supervisor override and immutable references |
| Device / Offline Queue | authorized device, user and gate, queued UUID, payload type, created_on_device, server_received, sync/checksum status, expiry and wipe state (never stored unencrypted) |
| Shift Handover | duty group, outgoing/incoming officer, case refs, active visits, unresolved contact action, manager acknowledgement, due times |
| Performance / UX Telemetry | aggregate only: check-in time, tap count, visit-match type, failed validations, offline/sync latency, non-PII; privacy review required |

Mandatory domain services / typed APIs:
- `lookup_visits_for_unit(unit_id, estate_context, shift_context)` returns minimal scoped candidate vehicle summaries.
- `check_in_visitor()` and `check_out_visitor()` are idempotent and tenant/gate scoped.
- `resolve_violation_contacts(case_id)` returns allowed contacts under caller role; does not expose full household registry.
- `initiate_call(case_id, contact_id, mode)` validates rights and returns a correlation ID and truthful capabilities.
- `record_call_outcome()` verifies officer and authorized case; distinguishes self-reported outcome from provider-verified duration.
- `send_case_sms(case_id, template_version, contact_id)` is server-side, idempotent and budget-controlled; logs exact message before submission.
- `ingest_provider_callback()` verifies cryptographic callback authenticity, server-scopes tenant/provider and deduplicates events.
- `establish_notice_clock()` is server-authoritative, requires configured evidence and returns an auditable deadline.
- `handoff_shift()`, `reassign_case()` and `reconcile_offline_visit()` enforce supervisor rules and audit.

Use Frappe role permissions AND estate/document-level hooks AND field projection controls for every workflow; no generic `frappe.get_all`/`ignore_permissions=True` on caller-directed private data without equivalent explicit authorization. UI hiding alone is never sufficient.

## 46. v1.4 More Requirements We Might Otherwise Miss

1. **Host verification and emergency contact tree.** Primary and secondary contact per unit, opt-in preferences, number re-verification, emergency/security desk number, and clear failed-contact escalation.
2. **Non-vehicle entrants.** Walk-ins, delivery riders, motorcycles, tradespeople, taxis, ride-hailing and shared commercial vehicles need appropriate fast paths without falsely assigning drivers to households permanently.
3. **Visitor checkout anomalies.** Re-entry, vehicle already inside, missing departure, overnight visitor, wrong host and manager correction. Model current presence separately from historic visit counts.
4. **False allegations, retaliation and duplicates.** Separate triage identity from cited vehicle, detect duplicate reports without deanonymization, allow officer rejection with reasons, prevent sanctions based on allegation alone, and protect private reporter details.
5. **Vehicle/plate mismatch.** Plate scanning error, transfer, borrowed car, foreign plates or same plate history: require human confirmation and show conflict warnings.
6. **Actual incident lifecycle.** Photo, GPS, verified incident, notice attempts, clock, compliance, enforcement authorization, clamp/tow, yard intake, itemized invoice and storage, release, appeal, refund and closure must remain one auditable case.
7. **Time and evidence integrity.** Tamper-evident immutable records, image hashes, UTC server time, device-captured time, source provenance, duplicate protection and clear corrections rather than rewriting original events.
8. **Permission safety for outsourced managers.** A property management company may administer several estates; access and reports are explicitly assigned by tenant and estate. No general SaaS-wide resident database.
9. **Payment methods practical for Ghana.** Include configurable Ghana Mobile Money and bank/card payment adapter options, but prove provider support and lawful collection before release; official receipts, reconciliation and separation from SaaS subscription revenue.
10. **Data protection obligations.** Validate Ghana Data Protection Act 2012 Act 843 requirements, role of controllers/processors, registration, privacy notice, purpose limitation, retention/deletion and vendor data-processing terms. Avoid collecting unneeded visitor identifiers. Require local legal approval for fees, towing and release prerequisites.
11. **Security incident and lost-device response.** Fast revoke, remote cache wipe on reconnect, device inventory, per-officer authentication, backups, audit review and compromised credential runbook.
12. **Affordability and adoption.** Device and data costs, per-SMS/voice cost ceilings, first-use training, field testing on actual gate hardware, simple bilingual/localized templates if tested and approved, and web-based fallback for desktops.
13. **Service quality reporting.** Plot check-in time percentiles, notification success, incident closure/verification, officer response time, rejected allegations, repeat hotspots and appeal reversals. Exports must be redacted by role.
14. **Legal release exception.** Do not leave emergency access blocked solely because the user disputes a charge or has not paid; enforce only lawful release/collection procedures and preserve appeal/payment-under-protest possibilities.
15. **Device location trust.** A photograph's GPS is camera position, not necessarily precise vehicle position. Allow officer pin confirmation, record accuracy and distinguish onsite-verified from resident-supplied allegation coordinates. No continuous guard tracking by default.
16. **Policy changes over time.** Historical cases hold snapshot of policy/version/rates. Tenant-customizable fields and fees cannot loosen core security, anonymity, authorization or audit rules.

## 47. v1.4 Reporting: Gate, Contact, and Operational Performance

In addition to all original dashboards and hotspot maps, management may filter by estate, gate, month, shift, staff group, offense zone and reporting channel (within permitted privacy scope):

- Visits by hour/day/gate, average/median/95th-percentile check-in time and returning-vs-new check-in mix.
- Number and rate of stale active sessions, check-out completion, duplicate plate collisions and erroneous unit corrections.
- Allegations received → officer acknowledged → verified → contact identified → notice established → corrected → escalated → released, with conversion rates and median step durations.
- Communication funnel: attempted calls, officer-reported answers, provider-verified connects, verified durations if provider integration active; SMS accepted, delivered, failed and explicit acknowledgment. Never conflate these.
- Percentage of warnings corrected during grace, notice clock exceptions, contacts not reached and repeat violations.
- Hotspot map combining confirmed violation **zone**, location accuracy and incident severity, with unverified allegations on a separate labeled layer. Do not publish exact visit histories or household contacts to residents.
- Enforcement invoices by charge class (base GH₵500 default, tow, storage, offsets), appeals, refunds and collected-vs-outstanding, always under the estate's published fee policy.
- Staff and shift analytics should support training and operational accountability, not covert monitoring; discuss legitimate purpose and notice.

## 48. v1.4 New Acceptance Tests — Required Before Pilot (AC-69 to AC-100)

**AC-69 — Unit-first repeat check-in:** Officer enters `A1`; sees only scoped prior-visit candidate plates and vehicle summaries, selects returning vehicle, confirms current host, checks in without reentering redundant data. Usability test records action count and completion time.

**AC-70 — Plate-first and new vehicle:** Search by plate returns correct authorized current or historic candidates; unmatched plate opens minimal new check-in form prefilled with estate/gate/officer/date; repeat entry preserved as separate visitor session.

**AC-71 — Never implicit visitor authorization:** Previously visiting a unit does not auto-authorize a new visit or create permanent residency status; active-session conflict triggers review.

**AC-72 — Multi-unit/multi-driver vehicle:** One vehicle legitimately visits units A1 and B2; current host is selected explicitly, and historic visit to B2 is not used to contact A1 in an A1 incident.

**AC-73 — Wrong/stale records:** Resident moves out and changes phone; contacting vehicle incident does not route to expired household association. Ambiguous plate requires confirmation.

**AC-74 — Unauthorized visitor-history lookup:** Resident, unrelated estate officer, auditor without scope and SaaS admin cannot enumerate returning-visitor plates, contacts or host/visit correlations via UI, API, report, autocomplete or offline cache.

**AC-75 — Privacy of suggestions:** Gate officer sees minimum plate/make/color/visit hint, not full historic movement profile. Visiting unit A1 does not reveal B2's past visit.

**AC-76 — No-car and mixed visitor types:** Walk-in, motorbike, delivery rider and hired taxi can be checked in without fictitious private registration; appropriate checkout works.

**AC-77 — OCR confidence and correction:** Misread plate must be confirmed/corrected before persistent association or citation; poor camera does not prevent manual check-in.

**AC-78 — Full allegation conversion-to-contact:** Resident allegation is claimed, independently verified, converted with preserved original evidence, matched to current visit or resident registration, and provides valid `Call`/`SMS` actions without second data entry.

**AC-79 — Contact choice:** Multiple resident contacts (primary/backup) and optional visitor contact are labeled; officer sees role and last verification and selects lawful route, not all community phone numbers.

**AC-80 — Native basic dialer truthfulness:** `Call` launches iOS/Android native dialer and records a requested/attempted action, not fictional connected status. Returning officer selects documented outcome. No automatic call duration is fabricated.

**AC-81 — Provider integrated calling:** If provider feature activated, verify webhook call ID/status, answered/end events, actual duration, provider cost and signature; incorrect/replayed webhook does not alter another tenant's records. Feature disabled if pilot Ghana voice support fails.

**AC-82 — SMS content and status:** Authorized officer previews server-side templated message and sends once; case records exact content and intended recipient and follows provider `Accepted/Sent/Delivered/Failed/Unknown` separately. Simulated callback duplicates do not duplicate charges or messages.

**AC-83 — SMS authorization:** Resident, auditor, off-duty officer or unrelated estate officer cannot send violation SMS or access full number/history even by direct API call.

**AC-84 — Grace clock control:** Neither unanswered call nor merely queued, submitted, or delivered-unacknowledged SMS begins a countdown by default. A verified policy-defined notice event establishes exact server deadline.

**AC-85 — Unreachable contact escalation:** Wrong number, no answer, SMS failed and expired guest contact lead to supervised next action with accurate timeline, not automatic penalty.

**AC-86 — Emergency obstruction:** Gate blocked with emergency: documented prompt contact and authorized safe removal path; no clamp trapping vehicle, no inaccurate 15-minute countdown, no double base penalty.

**AC-87 — Cross-device messages:** On phone and desktop, a manager can inspect the same case's contact timeline; exact message accessible only under appropriate permissions and sensitive details are masked otherwise.

**AC-88 — Check-in offline:** At low/no connectivity, encrypted draft check-in is recorded as provisional and later synced once; active visit conflicts get `Needs Review` instead of silent overwrite.

**AC-89 — Device clock drift:** Officer phone time off by 20 minutes cannot backdate or prematurely expire legal warning. Server authoritative clock applies when notice is established.

**AC-90 — Offline protected data:** Unauthorized person cannot extract full visitor/contact directory from shared phone. Offline cache expires/is estate scoped and is cleared on role, device or tenant change.

**AC-91 — Shift handover:** Officer ends shift with unresolved verified case; security manager receives handover, reassigns to incoming officer; notification history and prior assignments persist.

**AC-92 — Priority acknowledgement:** Urgent confirmed concern remains actionable when push fails; dashboard and escalation prove actual officer/manager acknowledgment separately from attempted notification.

**AC-93 — Low-literacy UX:** Test 3–5 representative gate officers on a low/midrange Android device; identify confusion and iterate. Screen readability, big actions, clear error messages and minimal typing demonstrated.

**AC-94 — Visitor duration:** Returning visitor, first-time visitor and checkout flows meet agreed pilot UX budgets or have documented performance blockers and mitigation; no false speed claim without testing.

**AC-95 — Ghana phone normalization:** `024...`, `+23324...` and valid international format normalize appropriately without breaking displayed/verifiable contact values; invalid/wrong number handled gracefully.

**AC-96 — Duplicate/suspicious plate:** Two simultaneous check-ins or incidents for same plate at one estate trigger expected conflict handling; never issue duplicate GH₵500 fees for one case.

**AC-97 — Finance and lawful release:** Fee engine itemizes one base violation penalty plus authorized tow/storage lines, ensures no duplicates and supports receipt, appeal and emergency access procedure.

**AC-98 — Ghana privacy safeguards:** Sample visitor collection notice, controlled retention, registered controller responsibilities and DPC compliance checklist exist; data remains role-scoped and access audited. Do not assert legal compliance solely on code/tests.

**AC-99 — Telephony store review:** iOS/Android builds declare only relevant permissions; Android uses dial intent, server-side messaging and provider callbacks, not unauthorized SMS/call-log permissions. Verify Apple/Google/Samsung submission requirements and documented privacy declarations.

**AC-100 — End-to-end demonstration:** On physical low-cost Android plus iPhone and desktop, demonstrate check-in repeat visitor at A1, anonymous resident allegation, security officer claim, on-site verification, case conversion, contact lookup, dialer outcome and server SMS, policy-compliant warning, timely move/no penalty, and separately approved escalation with itemized enforcement charges. Include a second isolated tenant with different policy/fees and demonstrate no cross-tenant disclosure.

## 49. Delivery Gates, Phase Assignment and v1.4 Change Log

**Phase 0 additional spikes (first):**
1. Prototype `Unit → Prior Vehicle → Confirm Entry` and `Verified Case → Resolve Contact → Call / SMS` on entry-level Android hardware. Test with prospective Ghana security officers before locking UI components.
2. Verify Android/iOS native dialer limitations and prohibition on relying on restricted call-log/SMS reading. Test call-provider alternatives for Ghana and compare connection reliability/cost; implement honest manual-outcome fallback either way.
3. Verify Ghana SMS provider webhook delivery support and data-processing terms, opt-out/transactional classification, costs, sender ID and SMS failure/retry behavior; mock adapters until live authorization.
4. Define approved notice-evidence threshold and emergency legal procedure with association counsel; avoid hard-coded legal assumptions.
5. Establish provisional per-tenant retention defaults and Ghana DPC compliance owner/data controller/processor responsibilities. Support offline encrypted cache and shift device management proof of concept.

**Phase 1 priorities:** estate/unit/resident/vehicle authority; secure gate mobile UI; repeat-visit suggestion index and visitor-session lifecycle; scoped contact projection; shift assignments; provisional offline check-ins and conflicts.

**Phase 2 priorities:** allegation-to-violation conversion; photo/GPS; case contact panel; native dialer with truthful outcomes; server-side SMS with status evidence; server notice-clock rules; off-duty escalation.

**Phase 3 priorities:** optional provider-mediated voice; approved enforcement actions; tow/impound/fee/appeals workflows with charge reconciliation, staff handover and manager oversight.

**Phase 4/5:** operational analytics, role-permission adversarial tests, device UX and store readiness, pilot training and incident-response operations. Store publication or live penalty collection remains gated by separate permission and jurisdiction verification.

**Implementation order is flexible only where dependencies are honored.** Architecture decisions must support multi-association SaaS from day one, independent policies/fees, tenant isolation, role boundaries, truthful communications and audit evidence. Do not build heavy generalized customizable admin forms before proving the fast unit-first gatehouse UX and case contact workflow are usable on physical phones.

### Supporting references for Claude to independently verify

- Google Play: `https://support.google.com/googleplay/android-developer/answer/16558241` and `https://support.google.com/googleplay/android-developer/answer/10208820` (restricted SMS/call-log permissions).
- Android dial intents: `https://developer.android.com/guide/components/intents-common`.
- Apple tel links: `https://developer.apple.com/library/archive/featuredarticles/iPhoneURLScheme_Reference/PhoneLinks/PhoneLinks.html`.
- Ghana Data Protection Commission: `https://dpc.gov.gh/for-organisations/`; Ghana Data Protection Act, 2012: `https://ghalii.org/akn/gh/act/2012/843/eng%402012-05-18`.
- Frappe permissions: `https://docs.frappe.io/framework-git/security/permission-query-conditions`.
- Ghana messaging API example (vendor verification necessary): `https://arkesel.com/developer-api/ghana/`.

**Version 1.4 additions:** mandatory unit-first returning visitor check-in; quick new-visitor minimal fields and checkout; historical association privacy; case-centric active host/contact resolution; dialer vs provider calling modes and honest duration provenance; server-side SMS exact content and delivery-state audit; authorized warning clocks; Ghana-friendly officer usability; offline and shift handover safety; new operational dashboards; 32 new acceptance tests AC-69 through AC-100.

---

## 50. v1.5 Mandatory Visitor Checkout and Presence Accounting

**This section is authoritative where previous visitor-checkout text was underspecified.** The system shall track a **visit as a time-bounded session**, not merely mark a vehicle as a visitor. A new visit starts when entry is recorded and ends when an officer confirms the vehicle or pedestrian visitor has left. A previous visit does not authorize subsequent entry.

### 50.1 Distinguish residents from temporary visitors

1. **Resident vehicle:** The permanent `Resident / Registered Vehicle` association confirms entitlement under an estate's parking and gate access rules. A resident's ordinary entrance or exit **does not require a visitor session or a checkout**. An estate may separately enable lawful resident traffic events, but those are a distinct opt-in feature and must not inflate visitor occupancy.
2. **Visitor vehicle:** Each actual arrival creates a new `Visitor Session` tied to current destination unit, vehicle reference or plate snapshot, estate, entry gate and guard, and actual entry time. That session stays `Checked In` until a verified checkout or documented authorized correction.
3. **Different host today:** A returning plate may visit a different unit. Use today's confirmed host, not last visit's host, and do not reveal other units' visit history through ordinary lookup.
4. **Mixed/ambiguous classification:** A registered resident may be driving for a visitor, a resident can visit another estate, and a rideshare/taxi vehicle can serve several households. Officer confirms visit purpose. Do not automatically link a plate to a unit on ambiguous identity or treat ordinary resident movement as a guest visit.
5. **Non-vehicle entries:** Pedestrians, motorcycles, bicycles, delivery riders and contractors may use appropriate session categories where the association has a legitimate need to track them. No invented plates or excessive identification fields.

### 50.2 Official checkout — fast officer flow

The gatehouse application's home screen prominently offers **Check In** and **Check Out**, not a buried menu.

1. On approach to exit, officer taps `Check Out`; app defaults to the currently assigned estate, gate and signed-in officer.
2. Display `Visitors Currently Inside` with a prominent plate or unit search, most recent arrivals and limited identifying vehicle details (plate, type/color, host unit, entry time). No unrelated resident contact directory appears.
3. Officer searches or selects a visitor session (optional camera-assisted plate recognition, always with officer confirmation). If there are multiple matching sessions, display an explicit resolution choice; never silently select one.
4. Verify that the actual departing vehicle or person matches the active visit; display a clear **Confirm Exit** action. No phone call, resident approval or full re-registration should ordinarily be required for legitimate departure.
5. Server atomically closes **that visit session only** and records actual `exit_at`, `exit_gate`, `exit_officer`, `exit_method`, `recorded_at`, original entry information, and a durable `Visitor Exit Event`. Duration is calculated from actual entry/exit timestamps and shown in minutes or hours.
6. A success state removes the session from the active visitor queue while retaining its immutable history. A subsequent arrival opens a **new visit**, not a reversal of checkout.
7. Target: one selection and one confirmation after the visitor is identified; benchmark ordinary checkout **within 10–15 seconds** on representative Ghana gatehouse Android hardware. Record actual pilot results rather than claiming a guaranteed duration.

**Example:** Visitor plate `GR 1234-25` enters Unit A1 at **2:00 PM**, exits via the same or another estate gate at **3:00 PM**. The original session remains in history with `14:00 entry`, `15:00 exit`, `60 minutes`, appropriate gate IDs and the distinct officers who recorded each event. If the visitor returns at 4:00 PM, this is a separate session.

### 50.3 Explicit visit status machine

`Expected (optional pre-registration) → Pending Authorization → Checked In → Checked Out`.

Exception states: `Awaiting Sync` (local-only provisional draft), `Exit Unconfirmed` (credible departure but insufficient verification), `Needs Supervisor Review` (collision, inconsistent event, missed checkout), `Cancelled/Voided` (with reason and history).

- Entry and exit state changes are enforced server-side in a transactional service; clients cannot set arbitrary final states via unrestricted DocType writes.
- A session can be checked out **only once**; repeated scans/taps/network retries are idempotent. Double checkout or conflicting gates must not create competing exits.
- A currently checked-in plate appearing for another arrival triggers `Already Inside` and a review/reconciliation prompt, not another silent active visit. Permit documented exceptions for shared registration numbers or plate errors through supervisor review.
- An estate may set expected departure or authorized overnight flags, but expiry alone **never proves physical departure**. Don't auto-check out on midnight, shift end or a configurable stay duration.
- Track `physical_presence_confidence` or equivalent (`Confirmed In`, `Confirmed Out`, `Unknown/Unverified`) separately from the administrative state when accuracy is uncertain. The active queue and occupancy reports must clearly distinguish confirmed and uncertain records.

### 50.4 Multiple entry/exit gates and staff shifts

- A visitor may enter Gate 1 and leave Gate 2. Both gates must read the same estate-scoped active sessions after synchronization. Do not require exit at the original entry gate.
- Log distinct entry officer, exit officer, shift and device, including reasoned manual correction. Preserve all events across shift changes.
- Checkouts are authorized for the user's **assigned estate** and permitted gate(s), not all SaaS tenants or all estates managed by the same company.
- Shift handover highlights `Visitors Still Inside`, stale sessions, `Exit Unconfirmed`, offline checkout drafts and irregular events. Officers must not lose active visitor status because their shift ended.

### 50.5 Offline and low-connectivity checkout

- If offline, the device may capture a **provisional checkout** with local timestamp, gate, officer, UUID and optional evidence, stored in an encrypted device queue; show `Pending Sync` and never falsely claim that the shared estate registry has been updated.
- Upon reconnection, transmit idempotently. Store both `observed_at_device` and `received_at_server` with provenance, avoiding substitution of sync time for observed departure time.
- If another officer already closed the session or a conflicting event exists, do not silently overwrite; route to conflict review with evidence.
- Devices should have a visible connection state and brief contingency instructions (paper fallback register reconciled by a supervisor) for prolonged outages.

### 50.6 Missed checkout, corrections and reasonable safeguards

- `Overdue / Long Visit` thresholds configurable by organization, estate, visitor type and permitted overnight stays; generate a **review reminder**, not an automatic allegation, fine, proof of unlawful presence, or automatic checkout.
- Officer may flag `Possibly Departed`; a supervisor can record `Exit Unconfirmed` or a corrected departure with required reason, basis, approver and original versus corrected timestamps. Estimated time must be labeled **estimated**, not represented as a verified gate event.
- Security can find and correct `Wrong Plate`, `Wrong Unit`, `Wrong Visit`, mistaken resident/visitor classification and accidental checkout through append-only correction events and relevant approvals. Original evidence and event history remain available to authorized reviewers.
- Respect site access and personal freedom: no automatic physical detention, barriers, exit denial or impound because a visit lacks checkout or because a visitor has an unrelated allegation or invoice. Any exception requires explicit lawful authority and separate operational policy.
- A visitor may be dropped off by a taxi and leave on foot; avoid tying every person session exclusively to a vehicle. Where an estate tracks both, link travel/visit records without falsely implying the driver and passengers departed together.

## 51. v1.5 Mobile Screens, Data Fields and Access Control

### 51.1 Mobile security screens

| Screen | Minimum interaction | Notes |
|---|---|---|
| Gate Home | Large `Check In`, `Check Out`, `Active Visitors`, `Find Vehicle` | Optional offline indicator, shift/gate and incident alert badge |
| Active Visitors | Search by plate or destination unit; recently admitted list; visitor count | Active/uncertain separated; minimal details; filter to assigned estate |
| Quick Checkout | Plate, vehicle description, unit, entry time; `Confirm Exit` | One confirmation; error/collision handling; no redundant forms |
| Exit Confirmation | Success, actual time, duration, recording gate and officer | New arrival later starts new session |
| Supervisor Exceptions | Overdue, unverified, wrong plate, duplicate events, correction approval | Review/evidence/notes with append-only audit trail |
| Management Gate Analytics | Gate entries/exits by hour, visitor duration, active visits, missed checkouts | Scope-controlled, privacy-preserving export |

### 51.2 Required visit-session and event fields

**Visit Session:** `session_id` (opaque immutable), `tenant_id/estate_id`, `visitor_category`, `vehicle_id nullable`, `plate_snapshot nullable`, `host_unit_id`, `entry_at_utc`, `entry_gate_id`, `entry_officer_id`, `authorization_basis`, `status`, `exit_at_utc nullable`, `exit_gate_id nullable`, `exit_officer_id nullable`, `exit_method`, `duration_seconds computed nullable`, `estimated_time_flag`, `sync_state`, `version`, `created_at`, `updated_at`.

**Visit Event (append-only):** `event_id`, `session_id`, `event_type` (`ENTRY`, `EXIT`, `EXIT_CORRECTION`, `VOID`, `REOPEN_REVIEW`), `actor`, `gate`, `device`, `observed_at_utc`, `server_received_at_utc`, `source`, `request_id/idempotency_key`, `reason`, `reviewed_by`, `prior_value_hash/ref` and `new_value_ref`. Keep event history even when materialized session status changes.

**Visitor/vehicle registration** persists independently from these sessions. Multiple historical sessions may reference the same registered vehicle and host unit; they must not reuse the same immutable session ID.

Use estate-local timezone **only for display and reporting buckets**. Store canonical instants in UTC, along with timestamp provenance, so reports remain correct if an organization changes its timezone or another estate is in a different country.

### 51.3 Security and privacy constraints

- Only authorized security officers, security managers and appropriately assigned management may view estate-scoped active visitor sessions; auditors are read-only within specific approved scopes. Residents cannot browse active visitors, plate histories or the visitor log for any unit (including another resident's unit).
- Never use a globally searchable SaaS plate index accessible across organizations. Cross-tenant identifiers are meaningless outside their tenancy unless lawful narrow-purpose integrations are explicitly approved.
- Officers can perform operational checkout for their estate but cannot erase historical sessions, bulk-export resident and visitor data or rewrite timestamps. Supervisors have specifically granted correction permissions, distinct from normal checkout privileges.
- Configurable collection and retention policy covers visit records, plate images, plate-to-unit suggestion history, device caches and exports; do not retain information indefinitely merely because it supports autocomplete.

## 52. v1.5 Dashboards and Operational Analytics

Add interactive dashboard cards and appropriately permissioned graphical reports for:

- **Currently inside:** active visitor vehicles and tracked non-vehicle visitors, by gate, unit/zone when authorized, type, duration bracket, and `uncertain/needs review` distinct from confirmed occupancy.
- **Visit flow:** arrivals and departures by hour/day/week, entry vs exit gate, visit volume trends, repeat versus first-time visit sessions.
- **Visit duration:** median, 90th percentile, maximum and distributions, excluding unconfirmed/estimated durations from verified-duration statistics or labeling them separately.
- **Visit closeout:** same-day checkout percentage, stale sessions, missed departures, open overnight sessions, double-tap/conflict events, time-to-resolution.
- **Gate officer workflow:** median time to complete actual checkout, retries, offline sync delay and error categories used for training—not covert individual performance surveillance.

The active visitor total is an **operational estimate based on recorded arrivals and departures**, not a guaranteed real-time census of all persons on the property. Resident traffic and untracked pedestrian movement are outside the visitor-vehicle count. Show missing-checkout caveats when relevant.

## 53. v1.5 Required Acceptance Tests and Claude Delivery Instructions

**AC-101 — Routine checkout:** Session checked in at 14:00 and confirmed out at 15:00 yields 60-minute verified duration, clear entry/exit audit metadata, and disappears from active list without losing history.

**AC-102 — Resident separation:** Registered resident vehicle departing normally does not create or close a guest session; visitor check-in is an explicit event even if a car historically belongs to a resident.

**AC-103 — Cross-gate departure:** Visitor arrives at Gate A, exits at Gate B, and remains one closed session with both accurate gates/officers.

**AC-104 — Re-entry:** Same visitor vehicle returns after checkout: create a fresh visit-session ID; prior visit remains unchanged.

**AC-105 — Duplicate and concurrent checkout:** Two devices attempt checkout simultaneously; exactly one authorized final exit event is committed, retries are idempotent and officer receives truthful current status.

**AC-106 — No matching visit:** Attempt checkout for an unknown plate; no invented historical visit or false exit record is created. Authorized exception workflow is available.

**AC-107 — Long or overnight stay:** Overnight visits do not auto-check out at midnight, threshold expiry or shift change; overdue flag triggers review only.

**AC-108 — Missed exit and supervisor correction:** Supervisor can record an estimated departure with reason, source and full append-only trail, displaying estimated/unverified status; ordinary officer cannot silently backdate.

**AC-109 — Offline provisional departure:** Officer records exit offline; UI shows pending sync. On recovery, exact observed and server receipt times remain distinct, conflict handling runs and duplicate exit is prevented.

**AC-110 — Wrong plate or unit correction:** Approved correction retains original plate/unit and correcting actor/reason, prevents leaking prior-unit visit data and does not alter unrelated vehicle sessions.

**AC-111 — Privacy and role isolation:** Resident user, unrelated gate officer, unauthorized auditor and SaaS admin cannot enumerate private visitor sessions through screen, API, search, export or cached data; assigned security can access only current estate.

**AC-112 — Multiple visitor types:** Pedestrian, motorcycle, ride-hail/drop-off and contractor workflows can close applicable sessions without inventing plates or assuming all passengers share one departure.

**AC-113 — Visit state confidence:** Verified checkouts count as `Confirmed Out`; estimated or unmatched exits are distinctly labeled and excluded from unqualified verified-duration reporting.

**AC-114 — Shift handover:** New guard sees authenticated estate's active/stale visitor queue; shift change doesn't close sessions or mutate original entry officer.

**AC-115 — Usability on entry-level Android:** Pilot shows an ordinary returning visitor checkout in one selection plus confirmation after identifying session; measure time, mis-taps, text entry and errors. Target 10–15 seconds, improve design if not attained.

**AC-116 — Analytics correctness:** Sample 14:00–15:00 visit, overnight visit, cross-gate exit and unconfirmed exit appear in the correct active/closed counts, graphs and filters without falsely claiming physical occupancy certainty.

**AC-117 — Multi-tenant isolation:** Same plate and unit labels in two unrelated estates produce independent sessions, events, policy views and reporting; no cross-tenant discovery or synchronization.

**AC-118 — External safety boundary:** Lack of checkout, disputed invoice or open violation never by itself enables a gate lock, resident/visitor detention, or automatic impound; prohibited controls absent and auditable.

**AC-119 — Event and timezone integrity:** Device capture, server receipt and organization-local displayed timestamps remain unambiguous; edits do not alter original historical exit evidence.

**AC-120 — End-to-end scenario:** Show real-device run: known visitor arrives at A1 at 14:00, check-in, active list presence, exit at another gate at 15:00, 60-minute duration, no active session, supervisor report updated, same plate's second arrival separate, and resident vehicle exits without visitor checkout. Include interrupted-network reconciliation and adverse access test.

**Required build priority:** Implement session/event data model, fast active visitor view, scoped one-confirmation checkout and cross-gate concurrency handling alongside the fast visitor check-in work in **Phase 1**. Offline sync, forgotten checkout, exception handling and visit dashboards must be exercised before an operational pilot. Retain all Phase 0 legal and app-store proof-of-concept gates from v1.4.

**Change summary:** Version 1.5 adds first-class resident-versus-visitor separation; explicit arrival/exit state machine; quick checkout and active visitor queue; multiple-gate departures; tamper-evident event and duration provenance; offline checkout; missed exits and supervisor corrections; role-safe reporting; and 20 additional acceptance tests (AC-101 through AC-120). All previously specified requirements and tests remain in force unless explicitly superseded here.

**End of preserved v1.5 requirements; v1.6 additions follow below.**


---

## 54. v1.6 Project Identity, Folder and Repository — Mandatory

**Internal working title:** **Community Parking & Compliance Platform (CPCP)**. This is a descriptive engineering codename, not a legally cleared brand. **Do not** label the iOS/Android app or SaaS product `EstateFlow` or another existing commercial name without separate name/trademark/app-store review. Final brand, package IDs, store display names, domains and trademark policies remain configurable decisions; choose collision-resistant provisional reverse-domain IDs only after confirming control of the relevant domain.

**Suggested Windows workspace:** `D:\Projects\CPCP` if `D:\Projects` is the user's chosen folder; the user will create it and open it in VS Code with Claude Code. Respect any actual user-provided filesystem path. Do not assume permission to inspect other projects.

**Proposed public GitHub remote:** `https://github.com/Exnav29/community-parking-compliance-platform` **only after it is actually created and verified**. Do not present this as an existing live link beforehand. Owner must be confirmed; if not accessible, obtain authorization or produce repeatable local setup instructions. Do not silently publish in a different personal or organization account.

The project consists of custom Frappe back-end app, mobile/desktop clients, documentation, infrastructure-as-code **without secrets**, synthetic fixtures, tests, and contributing materials. Maintain a clear monorepo layout or justify separate open repos, preserving automated builds and linking exact tested commits. Do not add closed proprietary code into the public repo by accident.

## 55. v1.6 Public Open-Source License and Contribution Governance — Mandatory

### 55.1 Chosen default license

- All **original, copyright-cleared** custom code intended for this public project shall be released under **Apache License, Version 2.0** (`SPDX-License-Identifier: Apache-2.0`). Add an exact, unmodified `LICENSE` file from the official Apache Software Foundation source. Keep mandatory third-party notices and a `NOTICE` file when applicable; include SPDX headers and copyright attribution where appropriate. Do not substitute a nonstandard summary for the legal license text.
- Why: Apache-2.0 permits use, modification, distribution and commercial products, includes an explicit patent grant, and supports paid hosting/services. A commercial SaaS can operate a publicly licensed codebase; tenant customer information, deployment credentials and billing accounts are **not** open-source code.
- **Deliberate tradeoff:** Apache-2.0 does *not* require downstream hosted operators to make their changes publicly available. If the owner later wants reciprocal sharing of hosted modifications, evaluate AGPLv3 and legal/contributor implications **before public releases**; do not unilaterally switch the license after external contributions.
- Verify legal ownership before license attachment: written permission or rights assignment for commissioned/employee work where needed, prior proprietary project code, purchased templates, images, fonts, UI assets, and any third-party snippets. Do not relicence components owned by others. Name the correct copyright holder only after owner confirmation; do not assume a company owns all code without evidence. Contributors retain their rights subject to licensed contributions.
- Frappe Framework is MIT-licensed; confirm the exact pinned code and dependency notices. ERPNext uses GPLv3; its inclusion/distribution or other copyleft code can affect the licensing of combined works. Prefer Frappe Framework and independently compatible permissive components; any ERPNext or GPL/AGPL dependency must undergo a documented compatibility/distribution review. Publish an SBOM and automated license inventory; fail a publication gate on unknown or incompatible source/licenses.
- Source-code license, brand/trademark permissions, privacy obligations, patent rights, and app-store distribution terms are distinct. The open-source license does not give access to any association's live data, private tenant site or branded store account.

### 55.2 Contributor-friendly public repository

Create and keep accurate:

1. `README.md`: project mission, who it is for, screenshots **only of synthetic demo data**, architecture, requirements, local development, safe demo, quick start, supported Frappe/mobile versions, current maturity/status and roadmap. Avoid unsupported 'production ready' claims.
2. `LICENSE`: full Apache-2.0 text; `NOTICE` if needed; per-package `THIRD_PARTY_NOTICES` / license inventory and dependency lockfiles.
3. `CONTRIBUTING.md`: setup, conventions, tests, lint/typecheck, schema migrations, PR process, API stability expectations, UX/accessibility requirements and security/privacy constraints. Explain the Apache-2.0 inbound=outbound contribution model and ask contributors to certify rights using a lightweight **Developer Certificate of Origin (DCO)** with signed-off commits, unless owner chooses a reviewed alternative.
4. `CODE_OF_CONDUCT.md`: standard conduct expectations, contact and escalation, respectful treatment of contributors.
5. `SECURITY.md`: confidential vulnerability disclosure contact, supported versions, patch policy, no public disclosure of exploit or production access details before remediation.
6. Issue and pull-request templates: bug reports with **redacted** logs, feature requests, security report redirect, checklist for tests, documentation, privacy, license inventory and backward compatibility.
7. `CHANGELOG.md`, semantic versioning or documented alternate policy, tagged releases, automated build/release workflow, maintainers/ownership file (e.g. `CODEOWNERS`) and a technical design/ADR directory.
8. Local development tooling (`compose.yaml` or Frappe Bench scripts where appropriate), `.env.example` with placeholder values only, `.gitignore`, synthetic seed/fixture data and optional local-only test harnesses.
9. GitHub Discussions (optional) and a public project roadmap with privacy-safe issues to invite community development.

**All code produced for CPCP** is version-controlled in Git and pushed to its verified PUBLIC GitHub repository at meaningful completed checkpoints. Drafts can remain in the local working tree until tests and public-safety checks pass. Never interpret 'all code' as permission to publish secret files, unlicensed third-party code, real customer data or vulnerable raw logs. Do not silently exclude essential product logic from public source without an explicit approved open-core plan.

### 55.3 GitHub governance and reliable collaboration

- Prefer protected `main` via supported branch rulesets or equivalent: PR reviews where available, CI required checks, no force-push, no unreviewed changes to payments/auth/tenancy/enforcement, and CODEOWNERS review on sensitive subsystems. Verify available GitHub plan features; document any unavailable controls and practical compensating checks.
- CI on commits and PRs: Python/Frappe tests, TypeScript build/typecheck, ESLint/static analysis, migrations and compatibility checks, role and cross-tenant authorization tests, SAST, dependency vulnerability scan, SBOM/license analysis, secret scanning, basic accessibility checks. Mobile store builds and signed artifacts require isolated release environments; use platform-held secrets, not source files.
- Dependabot or equivalent for supported ecosystems, issue triage and contributor acknowledgement, automated PR/branch checks, release tags, signed checksums where practicable and a documented emergency vulnerability hotfix process.
- Restrict GitHub Actions token permissions to minimum, pin third-party actions to reviewed immutable revisions where possible, require approval for untrusted fork workflows, avoid executing untrusted PR code with production secrets or privileged runners, and prohibit production data in CI.
- Open access to source does **not** imply open access to hosted SaaS accounts, production systems, tenant records, backend administrative endpoints or developer signing credentials.

## 56. v1.6 Public Repository Privacy, Security and Publication Gates

### 56.1 Mandatory pre-publication review

Before the first public push and before every public release, Claude must:

1. Inspect staged files **and full Git history to be published** for secrets, keys, access tokens, passwords, production `.env`, Frappe `site_config.json`, mobile signing certificates, credentials, payment-provider keys and internal network secrets. A `.gitignore` alone does not remove previously committed secrets. Use established automated detectors plus targeted manual checks. Rotate/revoke any accidentally exposed credential and remove it from public history through an approved process; do not proceed while unresolved.
2. Inspect all data and assets for **real** resident names, house/unit identifiers tied to people, license plates, phone numbers, visit times, GPS coordinates, violation photographs, allegations, reporter identities, financial transactions, security logs, customer exports, browser screenshots, database dumps, backups or estate diagrams that identify private properties. Use deliberately fictitious plates/units/people, simulated map coordinates and synthetic invoices. No public sensitive data even for 'debugging'.
3. Confirm copyright/source ownership, all third-party license rights, dependency inclusion rules and package notices. Do not republish a previous commercial repository or private integration simply because this project is open source.
4. Ensure infrastructure configuration is safe for public release: use documented templates/placeholders for domains, queues, storage, identity, databases, payment and SMS/voice providers. Keep environment-specific values in an external secrets store; exclude live operations, tenant backups and app-signing material.
5. Confirm no plaintext API credentials in mobile client bundles, URL parameters, screenshots, commit messages, CI logs, artifacts or generated documentation.
6. Run and preserve evidence of scans, build/tests and one maintainer approval before flipping an existing repository public or pushing sensitive changes. Public visibility is **irreversible for previously exposed information** even if later deleted; do not rely on later cleanup.

### 56.2 Public-code versus private-runtime boundary

**Public:** project source; migrations; safe synthetic fixtures; generic policies/templates; sanitized examples; infrastructure templates; technical docs; issue templates; tests; generated API schemas with no confidential endpoints; general architectural patterns.

**Private runtime:** live resident and visitor registries; officer/resident phone numbers; real license-plate histories; individual allegation records; anonymous-report tokens; photographs and precise vehicle GPS; case correspondence; phone/SMS content; payment and towing data; user access logs; production keys/secrets; association-specific customizations derived from private data; backups; app signing identities.

This is a strict data/publication boundary, not a reason to omit all source code from the repository.

### 56.3 Compliance and release boundaries

- Publishing open-source code is authorized, but **production deployment, live security monitoring, collection of fines, clamping/towing activation and public app-store submissions are NOT automatically authorized**. Respect existing PRD safety gates.
- App-store compliant builds from open source are allowed. Separate each platform's published privacy policy, data deletion mechanisms, package identifiers, store account access and release-signing keys from publicly visible code.
- New contributors must not receive tenant operational access merely because their PR was merged. Offer isolated synthetic/demo environments only.

## 57. v1.6 Recommended Repository Layout (Illustrative)

```text
CPCP/
  README.md
  LICENSE
  NOTICE                      # when attribution notices are required
  CONTRIBUTING.md
  CODE_OF_CONDUCT.md
  SECURITY.md
  CHANGELOG.md
  CODEOWNERS                  # or .github/CODEOWNERS
  .gitignore
  .env.example
  .github/
    workflows/               # CI, security, license checks
    ISSUE_TEMPLATE/
    PULL_REQUEST_TEMPLATE.md
  apps/
    frappe_cpcp/              # custom Frappe DocTypes, workflows, migrations, tests
    mobile/                   # Capacitor iOS/Android React client source
    web/                      # desktop portal source, if separately hosted
  packages/
    shared/                   # API contracts, UI types and common components
  infra/
    templates/                # safe example deployment manifests only
  docs/
    architecture/
    decisions/
    privacy/
    deployment/
  tests/
    integration/
    tenant-isolation/
    security/
  demo/
    synthetic-fixtures/      # fictitious names, plates, units, coordinates
```

Claude may change the structure to fit Frappe/Bench conventions, but must explain deviations and keep all maintained code accessible and discoverable in Git. A framework checkout from upstream is not to be vendored into this repository without need and license review.

## 58. v1.6 Mandatory Acceptance Tests (AC-121 through AC-136)

**AC-121 — Public repo verified:** Repository exists at the authorized GitHub account with PUBLIC visibility, an accessible initial commit and correct remote URL; report its verified URL and commit SHA, or report exact authorization blocker without inventing success.

**AC-122 — Open-source license:** Apache-2.0 `LICENSE` is complete; project metadata contains `Apache-2.0`, copyright ownership approved, per-package notices accurate.

**AC-123 — Secret/history safety:** Automated and manual scans of full publishable history, working tree and PR artifacts show no live secrets, keys, customer records or sensitive files; log safe scan output and any remediations.

**AC-124 — Synthetic data:** A fresh outside clone can load demonstrative visitors/vehicles/violations without real Ghana estate PII or identifiable real coordinates; fixture generation is documented and repeatable.

**AC-125 — Contribution path:** A new contributor can clone, install prerequisites, start a local demo and run meaningful tests using `README.md` and `CONTRIBUTING.md` without SaaS production access.

**AC-126 — Third-party licensing:** Machine-generated dependency inventory and human-reviewed exceptions ensure compatible rights, accurate attribution, and no unauthorized proprietary/copyleft contamination of Apache-licensed original work.

**AC-127 — CI on public fork PR:** Untrusted pull request runs tests with read-only/minimum permissions and no access to production secrets, customer data or publish credentials.

**AC-128 — Role and tenant security gates:** Cross-tenant and role-misuse tests from prior versions run in CI and prevent merging changes that accidentally expose resident/visitor registries or anonymous reporter identity.

**AC-129 — Changes appear publicly:** Every tested build delivered to user is traceable to a public commit/tag; no essential application feature exists only on an untracked workstation.

**AC-130 — Build reproducibility:** Fresh clone builds Frappe app and desktop/mobile source on documented environments; iOS signing requirements or macOS dependencies are accurately noted, not misrepresented as cross-platform turnkey signing.

**AC-131 — Vulnerability policy:** `SECURITY.md` documents a private responsible-disclosure route; public GitHub issues do not require vulnerability details.

**AC-132 — Correct rights boundary:** Public repository disclosure cannot expose live tenant state, precise private GPS, visitor SMS/phone logs, uploaded photos, billing credentials or app-signing material; verify with simulated adversarial access.

**AC-133 — Attribution and community docs:** README contains current status/maturity and safe screenshots; required notices, code of conduct, contribution procedure and changelog are included.

**AC-134 — Public/production separation:** A merged public PR cannot trigger production deployment, app-store submission, live enforcement activation or production migration absent independent authorized release approval.

**AC-135 — GitHub governance:** Mainline review, supported branch/ruleset checks, role ownership and workflow least-privilege are documented and verified to the extent the owner plan permits; gaps are surfaced honestly.

**AC-136 — Commercial SaaS and public source:** Demonstrate that open-source code can run against a local synthetic multi-organization demo while real organization's credentials, data, payment merchant accounts and policy configurations remain private, scoped and separately provisioned.

## 59. v1.6 Instructions to Claude Code and Change Log

**Begin in the user's designated VS Code project folder.** Inspect the PRD; confirm current upstream Frappe, React, Capacitor and license dependencies; define architecture, repo scaffold, GitHub publication checklist and a minimal local runnable demo. Establish the public repo only after the ownership, secret and privacy gates. Commit work often, verify CI, and push safe tested code at each phase. Invite contributions from day one; preserve carefully documented API and data migrations to avoid breaking community adopters.

**Do not claim GitHub creation, license clearance, CI completion, real-device tests, production readiness or app-store publication unless actually verified.** If authorization/connectivity prevents public repo creation, prepare safe local commits and provide exact steps/blockers; do not fall back to a private repository against the stated requirement without specific new approval.

**Version 1.6 change summary:** working CPCP identity and folder; publicly accessible GitHub repo rather than previous private-repo requirement; Apache-2.0 with ownership and license checks; contributor onboarding; GitHub governance and security automation; strict open-source/runtime data boundary; 16 new acceptance criteria AC-121 through AC-136. All prior requirements AC-1 through AC-120 remain in force except the v1.5 instruction to use a private repo, now superseded.

**End of PRD v1.6 content (preserved).**


---

## 60. v1.7 Incident Consolidation, Duplicate Allegations, and Repeat-Offender Lifecycle — Mandatory (P0)

**Status:** Mandatory addendum integrated into PRD v1.7 (originally `docs/spec/CPCP_PRD_v1.7_Incident_Deduplication_Addendum.md`). Owner: Johnathan Lightfoot. Priority P0 — correctness, financial fairness, safety and security. Supersedes any rule that uses a fixed plate-and-time window as the sole or definitive test of whether two reports describe the same parking event.

### 60.1 Problem statement and fundamental rules

Several residents may independently report the same illegally parked vehicle. A second report must neither generate an additional verified violation nor cause another warning, clamp, tow order, or base violation penalty for the **same physical parking episode**. Each genuine report must nevertheless be retained, linked to the common incident when appropriate, and accounted for in reporting. A separate offense occurring after the first parking episode ends may result in a new incident and permitted new enforcement, even with the same plate and location.

**Non-negotiable invariants:**

1. **One physical parking episode → one canonical incident** once validated. The incident can hold multiple independent allegations and evidence items.
2. **One verified episode → no more than one base parking-violation penalty for the applicable offense** under the adopted policy. Repeated submissions, app retries, competing officers, clamping followed by towing, or webhook retries must not duplicate that charge.
3. **One allegation → its own immutable intake record**, submission reference, consent/anonymity mode, timestamp, narrative, optional plate, zone, photo, location, and status; linking an allegation never overwrites or deletes its original evidence.
4. **Only authorized security verifies** an allegation or determines whether two allegations represent the same event. Resident-submitted material alone must never create a fine, clock, clamp, or tow action.
5. **Operational work is consolidated**: when a matching case is already assigned or under investigation, the next allegation enriches that same case and notifies the responsible officer/manager appropriately without opening an independent enforcement workflow.
6. **Episode continuity beats elapsed time**: an open, under-review, warned, clamped, tow-ordered, impounded, or unresolved vehicle stays attached to the same episode, including across shifts and days, until a documented end-of-episode determination. A fixed four-hour window cannot override this.
7. **Repeat offenders are tracked through distinct episodes**, not repeat allegations. A car that actually departs and later commits a new violation can have a new incident with a new policy-governed consequence.
8. **Security, privacy, multi-tenancy, and financial authorization apply at every layer**. Nothing in deduplication permits residents to browse or infer private resident/visitor logs, another reporter's identity, vehicle ownership, live enforcement details, or records from a different estate/tenant.

### 60.2 Conceptual records and relationships

- **Allegation**: an immutable resident- or security-submitted observation with its own reference; many allegations may reference one canonical incident. Allow anonymous and identified intake as already specified.
- **Incident / Parking Episode**: a canonical case representing a specific vehicle's continuous parking event at a particular location, with state, normalized vehicle identifier (when verified), estate, zone, location evidence, first-known observation, last-known presence, claimed/assigned officer, and end-of-episode evidence. Incident creation must be possible from security patrol without any resident allegation.
- **Incident–Allegation Link**: explicit association including join reason, matcher confidence, verification status, actor, time, audit references, and whether the attachment was automatic candidate linkage or confirmed linkage; prevent duplicate links.
- **Vehicle Identity**: prefer a confirmed vehicle registry ID or normalized verified plate; preserve the raw plate, OCR confidence, and uncertainty. Never assume an uncertain/missing plate is a definitive match.
- **Location Identity**: verified estate plus zone/road/entrance/unit frontage and geographic coordinates with accuracy; consider GPS uncertainty and manually corrected pins.
- **Security Work Item**: one active case assignment, escalation clock, and claim lock for a canonical incident or candidate cluster; allegations can continue to arrive without generating parallel enforcement ownership.
- **Evidence / Observations**: multiple reporter and officer photos, GPS pins, observations of whether the vehicle moved or remained, timestamps, and custody/audit history.
- **Enforcement Action**: warning, clamp, tow, impound, release and corrective actions, each linked to the canonical incident with durable provider/staff identifiers and state transitions.
- **Charge Ledger**: itemized, idempotent base penalty, authorized towing cost, verified storage periods, credits, refunds, and settlements, all attached to the same incident.
- **Repeat-Offender History**: derived from distinct verified incidents, not number of resident allegations; apply policy and appeal outcomes when counting repeats.

Claude should review existing 24 DocTypes and extend existing schema with additive migrations, not parallel duplicate models unless necessary. Preserve immutable raw observations and historic records.

### 60.3 Resident experience

**Scenario:** Resident B sees a vehicle that Resident A has already reported or that security is currently addressing.

- Accept Resident B's observation and preserve it as a distinct allegation; optionally attach additional photographs, pin, and urgency update. Do not discard genuine evidence.
- Before submission, a privacy-safe precheck MAY show a generic message such as, **“Security may already be reviewing a similar parking concern. You can add your observation to help.”** It MUST NOT reveal another reporter, resident name, phone, ownership, unit, plate from the registry, officer location, clamp details, or protected status.
- If confidence is insufficient, accept the allegation for security review instead of rejecting or silently combining it.
- After submission, return a distinct report receipt/reference and a neutral confirmation. If linked to an existing incident, do not disclose sensitive internal case identifiers or investigative state unless separately authorized.
- Anonymous submissions must keep the existing truly anonymous intake safeguards; **do not silently create durable device/user fingerprinting merely for deduplication**. Use submitted event attributes and backend operational evidence only, with minimization and transparent privacy practices.
- A resident must be able to flag an urgent new safety issue even when a related case exists. Such updates should escalate priority, not create a duplicate penalty.

### 60.4 Security officer and manager experience

- Triage queue presents one consolidated actionable incident or candidate cluster with **“3 independent reports”**, oldest report time, latest observation, location, evidence, urgency, and current assigned officer.
- Officer can inspect each report separately, see new evidence and allegation count, and choose **Link to Existing**, **Create Separate Incident**, **Needs Investigation**, or **Not Related**, with reason and audit trail. Officer must confirm identity/location when ambiguous.
- New reports arriving on an assigned incident appear as updates on the assigned officer's case; send an alert to the officer and appropriate manager when material or urgent. Avoid one new general claimable work item per duplicate report.
- Where an incident is already warned, clamped, tow ordered, impounded, or awaiting release, additional observations attach to it. The interface must prominently display **“Already being handled”** to authorized security, with the current enforcement state and no second action button unless policy specifically allows an independently justified action.
- When a clamp is photographed, the officer can record the observation and verify against the authoritative active clamp record; a clamp in a photograph **alone is not proof** it is the same incident, properly authorized, or still current.
- The security manager can merge or split cases when subsequent evidence resolves ambiguity. Require reason, authorized role, non-destructive link/reassignment operations, financial reconciliation/holds where needed, and immutable audit history. A merge MUST NOT hide a penalty that was already duplicated; it must flag it for review and lawful reversal, rather than silently deleting a ledger entry.

### 60.5 Matching and incident identity

Matching must be a two-stage process: **candidate discovery** followed by **server-authoritative linking or officer confirmation**.

**Candidate features (configurable):** organization and estate; verified or alleged normalized plate; relevant unit/gate/parking zone; officer-confirmed vehicle identity; spatial proximity adjusted for GPS accuracy; same/compatible rule and condition; observation timestamp; active incident state; prior visit session; historical movement/departure evidence. A plate/time match alone is never conclusive. Same vehicle + same location + unresolved episode is a strong candidate even after many hours.

**Boundary conditions:**

- Vehicle remains clamped overnight: same incident until the episode's end is confirmed.
- Vehicle leaves and returns at the same location within 30 minutes: new episode if departure/re-entry is reliably verified.
- Vehicle moves from one prohibited location to another: security determines whether the physical episode and applicable policy treat this as continuation or a distinct event; preserve movement timeline and do not automatically issue a second base penalty.
- Same plate in two separate locations simultaneously: raise a mismatch/possible plate misread or duplicate-plated vehicle exception; do not blindly merge.
- Plate absent, obscured, or OCR inconsistent: use zone/time/location candidates; require officer verification.
- A complaint after closure may refer to earlier conduct: allow a **late allegation** to link to the prior incident with an audit marker, or open a genuine new event after confirmed departure. Do not use time elapsed since closure as the only rule.
- An incident that is marked resolved without positive evidence of departure should not automatically qualify as a new billable episode for the same vehicle and location.

No fully automatic match may assess penalties; association policy controls final classification and officer/manager approvals.

### 60.6 State machine and end-of-episode evidence

Support, at minimum, `New/Candidate`, `Under Review`, `Verified/Open`, `Warning Active`, `Compliance Confirmed`, `Clamp Active`, `Tow Ordered`, `Towed/Impounded`, `Release Pending`, `Resolved/Closed`, and `Reopened for Review` (or equivalent separately modeled incident/enforcement states). State transitions must be explicit, tested and auditable.

A new offense requires evidence the prior event ended and that a new violation began. Acceptable evidence might include verified vehicle departure by security, confirmed removal, corroborated movement and re-parking, or another documented manager-approved determination. Payment or clamp removal by itself is not proof the obstructing vehicle left. Overnight timing or a new calendar date is not proof either.

Retain the ability to attach late reports, append evidence, amend classification through authorized review, and reopen for administrative correction without pretending the original event never occurred.

### 60.7 Race conditions, atomicity, and financial safety

Design for simultaneous resident submissions, simultaneous officer claims, mobile offline replay, provider callbacks, and concurrent incident conversions.

- Implement transactional **find-or-create active incident** with appropriate row/advisory locking or a database-enforced unique active identity/reservation mechanism compatible with the chosen Frappe/MariaDB deployment. Do not rely on a pre-insert SELECT alone or mutable process-local locks.
- Use stable client submission idempotency keys, and additional unique constraints/idempotency protections for case creation, incident–allegation links, work item ownership, enforcement action transitions, and charge creation.
- Guarantee one active owner/claim for an actionable case at a time; handle officer takeover with explicit lease expiry or manager reassignment. Prevent split-brain assignments when two reports arrive simultaneously.
- Ensure the transaction either links/creates the incident and associated work ownership atomically or rolls back. Send pushes/SMS through a transactional outbox so a retry does not create a second incident.
- Maintain server-generated, unique charge identifiers including incident, charge class and policy-defined discriminator; explicitly prohibit a second base violation penalty for the same incident, including after merge, tow or clamp escalation. Check payment webhook and refund idempotency.
- Where collision/matching is uncertain, create a **manual review candidate**, not two auto-billable violations.
- Validate the entire path via parallel HTTP/DB integration tests, not only pure unit tests.

### 60.8 Dashboards and metrics

Report distinct counts clearly, without inflating enforcement or revenue:

- Number of **allegations** (including identified versus anonymous where safe).
- Number of **unique incidents/episodes**.
- Number of **verified violations**.
- Number of **enforcement actions**, by type.
- Number and value of **distinct assessed base penalties**, towing charges and storage charges.
- Number of duplicate/related allegations **linked to existing incidents**.
- Locations with the most **unique verified incidents**, with an optional separate layer showing complaint intensity.
- Recidivism/repeat-offender counts based only on distinct verified episodes and lawful, policy-defined windows.
- Median security first-response time and time to resolve.

Never describe anonymous submissions as coming from distinct people if the system cannot verify individual identity. Residential public dashboards must be aggregate, privacy-preserving and resistant to small-cell reidentification.

### 60.9 Acceptance tests (mandatory) — AC-D01 to AC-D18

**AC-D01:** Three separate reports, same plate/location/continuous episode, create three allegations but only one canonical verified incident and one base penalty.

**AC-D02:** A second report submitted after an officer claims a case attaches to the case without stealing the claim or launching a second enforcement workflow.

**AC-D03:** A report 5+ hours after an initial report attaches to a still-open/clamped/towed episode despite the previous four-hour match window.

**AC-D04:** An overnight clamped/impounded vehicle has one base penalty despite reports across midnight and a shift change.

**AC-D05:** A vehicle verified to leave, then return and reoffend within the earlier four-hour window may create a second incident when security confirms a distinct episode.

**AC-D06:** Same plate, different location or uncertain GPS/plate does not auto-merge without validated continuity; reviewer gets candidate comparison and safe resolution.

**AC-D07:** Two officers concurrently promoting separate allegations for the same underlying incident yield one canonical incident, one active actionable work item, no duplicated charge and audit evidence of each submission.

**AC-D08:** Multiple simultaneous residents submitting over an unreliable network do not create duplicate reports for the same client operation; genuinely separate reports remain preserved.

**AC-D09:** A clamp-active or tow-active case displays a single active enforcement status to authorized staff; duplicate reports do not create new clamp/tow orders or new base penalties.

**AC-D10:** Towing and storage costs add as authorized distinct line items to the same episode, without recreating the original penalty; webhook retries are idempotent.

**AC-D11:** Resident duplicate checks and acknowledgements reveal no other reporter identity, private plate registry, resident unit/phone, security assignment details, or cross-tenant data.

**AC-D12:** Anonymous allegations link correctly with no newly introduced identity correlators, while remaining individually preserved.

**AC-D13:** Authorized manager merge/split requires reason, preserves complete history, and reconciles or flags duplicate charges for review without silent deletion.

**AC-D14:** Repeat-offender history counts separate verified incidents, not the number of allegations attached to a case.

**AC-D15:** A late allegation may be linked to a closed episode without generating a new charge; a later genuinely distinct episode can still be filed.

**AC-D16:** Dashboard totals distinguish allegations, incidents, violations, enforcement actions and financial charges; map incident hotspots are not inflated by multiple reports.

**AC-D17:** Under simultaneous cross-estate or cross-organization submissions, no data, incident, candidate cluster, or match can cross the authorized boundary.

**AC-D18:** An urgent second report can increase the priority of the existing case without bypassing manager approvals or creating duplicate enforcement.

### 60.10 Implementation instructions for Claude Code

1. Treat this addendum as a P0 refinement to PRD v1.6; integrate it as **PRD v1.7** in the repository, retaining all earlier requirements and tests. Keep a versioned changelog.
2. Begin with a gap assessment against existing `core/allegations.py`, `api/allegations.py`, `core/charges.py`, DocTypes, and integration tests. The current implementation has a plate-based four-hour cluster and an existing-incident lookup that are **not a sufficient lifecycle/concurrency guarantee**.
3. Design and implement the correct canonical incident model, database indexes, transaction boundaries, candidate matching, authorized reviewer overrides, single claim, episode close/reopen, reporter-safe user experience, and charge idempotency.
4. Create schema migrations that do not silently discard prior allegation/incident links and retain audit history.
5. Test all AC-D01..AC-D18 with unit, integration, concurrent submission and cross-tenant HTTP tests. Record exact pass/fail evidence in `docs/STATUS.md`.
6. Keep enforcement and payments disabled by default. Do not run actual clamping, towing, messages, fines, payment collection, or production deployment without explicit approvals.
7. After the change is integrated and tests pass, commit and push cleared source and documentation to the existing Apache-2.0 public GitHub repository, then **continue building the remaining approved product milestones**. Do not stop at this addendum.

**Copyright for original material owned by the project initiator:** Copyright © 2026 Johnathan Lightfoot. Preserve third-party and independent contributors' notices and rights.


**Version 1.7 change summary:** one physical parking episode maps to one canonical incident; every allegation is preserved and linked; episode continuity (not elapsed time) decides identity; end-of-episode requires positive evidence; database-enforced active-identity and idempotency constraints; single active claim with lease; manager merge/split without silent ledger deletion; repeat offenders counted from distinct verified episodes; 18 new acceptance tests AC-D01..AC-D18. All earlier requirements and AC-1..AC-136 remain in force.

**End of PRD v1.7.**
