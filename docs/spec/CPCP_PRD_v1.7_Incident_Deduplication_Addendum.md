# CPCP PRD v1.7 — Incident Consolidation, Duplicate Allegations, and Repeat-Offender Lifecycle

**Status:** Proposed mandatory addendum to `docs/spec/PRD_v1.6.md`  
**Working product:** Community Parking & Compliance Platform (CPCP)  
**Owner:** Johnathan Lightfoot  
**Scope:** Frappe backend, resident reporting, security work queue, enforcement ledger, dashboards, mobile application, and API concurrency safeguards.  
**Priority:** P0 — correctness, financial fairness, safety, and security.  
**Supersedes:** Any previous rule that uses a fixed plate-and-time window as the sole or definitive test of whether two reports describe the same parking event. Preserve all other PRD v1.6 requirements.

## 1. Problem statement and fundamental rules

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

## 2. Conceptual records and relationships

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

## 3. Resident experience

**Scenario:** Resident B sees a vehicle that Resident A has already reported or that security is currently addressing.

- Accept Resident B's observation and preserve it as a distinct allegation; optionally attach additional photographs, pin, and urgency update. Do not discard genuine evidence.
- Before submission, a privacy-safe precheck MAY show a generic message such as, **“Security may already be reviewing a similar parking concern. You can add your observation to help.”** It MUST NOT reveal another reporter, resident name, phone, ownership, unit, plate from the registry, officer location, clamp details, or protected status.
- If confidence is insufficient, accept the allegation for security review instead of rejecting or silently combining it.
- After submission, return a distinct report receipt/reference and a neutral confirmation. If linked to an existing incident, do not disclose sensitive internal case identifiers or investigative state unless separately authorized.
- Anonymous submissions must keep the existing truly anonymous intake safeguards; **do not silently create durable device/user fingerprinting merely for deduplication**. Use submitted event attributes and backend operational evidence only, with minimization and transparent privacy practices.
- A resident must be able to flag an urgent new safety issue even when a related case exists. Such updates should escalate priority, not create a duplicate penalty.

## 4. Security officer and manager experience

- Triage queue presents one consolidated actionable incident or candidate cluster with **“3 independent reports”**, oldest report time, latest observation, location, evidence, urgency, and current assigned officer.
- Officer can inspect each report separately, see new evidence and allegation count, and choose **Link to Existing**, **Create Separate Incident**, **Needs Investigation**, or **Not Related**, with reason and audit trail. Officer must confirm identity/location when ambiguous.
- New reports arriving on an assigned incident appear as updates on the assigned officer's case; send an alert to the officer and appropriate manager when material or urgent. Avoid one new general claimable work item per duplicate report.
- Where an incident is already warned, clamped, tow ordered, impounded, or awaiting release, additional observations attach to it. The interface must prominently display **“Already being handled”** to authorized security, with the current enforcement state and no second action button unless policy specifically allows an independently justified action.
- When a clamp is photographed, the officer can record the observation and verify against the authoritative active clamp record; a clamp in a photograph **alone is not proof** it is the same incident, properly authorized, or still current.
- The security manager can merge or split cases when subsequent evidence resolves ambiguity. Require reason, authorized role, non-destructive link/reassignment operations, financial reconciliation/holds where needed, and immutable audit history. A merge MUST NOT hide a penalty that was already duplicated; it must flag it for review and lawful reversal, rather than silently deleting a ledger entry.

## 5. Matching and incident identity

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

## 6. State machine and end-of-episode evidence

Support, at minimum, `New/Candidate`, `Under Review`, `Verified/Open`, `Warning Active`, `Compliance Confirmed`, `Clamp Active`, `Tow Ordered`, `Towed/Impounded`, `Release Pending`, `Resolved/Closed`, and `Reopened for Review` (or equivalent separately modeled incident/enforcement states). State transitions must be explicit, tested and auditable.

A new offense requires evidence the prior event ended and that a new violation began. Acceptable evidence might include verified vehicle departure by security, confirmed removal, corroborated movement and re-parking, or another documented manager-approved determination. Payment or clamp removal by itself is not proof the obstructing vehicle left. Overnight timing or a new calendar date is not proof either.

Retain the ability to attach late reports, append evidence, amend classification through authorized review, and reopen for administrative correction without pretending the original event never occurred.

## 7. Race conditions, atomicity, and financial safety

Design for simultaneous resident submissions, simultaneous officer claims, mobile offline replay, provider callbacks, and concurrent incident conversions.

- Implement transactional **find-or-create active incident** with appropriate row/advisory locking or a database-enforced unique active identity/reservation mechanism compatible with the chosen Frappe/MariaDB deployment. Do not rely on a pre-insert SELECT alone or mutable process-local locks.
- Use stable client submission idempotency keys, and additional unique constraints/idempotency protections for case creation, incident–allegation links, work item ownership, enforcement action transitions, and charge creation.
- Guarantee one active owner/claim for an actionable case at a time; handle officer takeover with explicit lease expiry or manager reassignment. Prevent split-brain assignments when two reports arrive simultaneously.
- Ensure the transaction either links/creates the incident and associated work ownership atomically or rolls back. Send pushes/SMS through a transactional outbox so a retry does not create a second incident.
- Maintain server-generated, unique charge identifiers including incident, charge class and policy-defined discriminator; explicitly prohibit a second base violation penalty for the same incident, including after merge, tow or clamp escalation. Check payment webhook and refund idempotency.
- Where collision/matching is uncertain, create a **manual review candidate**, not two auto-billable violations.
- Validate the entire path via parallel HTTP/DB integration tests, not only pure unit tests.

## 8. Dashboards and metrics

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

## 9. Acceptance tests (mandatory)

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

## 10. Implementation instructions for Claude Code

1. Treat this addendum as a P0 refinement to PRD v1.6; integrate it as **PRD v1.7** in the repository, retaining all earlier requirements and tests. Keep a versioned changelog.
2. Begin with a gap assessment against existing `core/allegations.py`, `api/allegations.py`, `core/charges.py`, DocTypes, and integration tests. The current implementation has a plate-based four-hour cluster and an existing-incident lookup that are **not a sufficient lifecycle/concurrency guarantee**.
3. Design and implement the correct canonical incident model, database indexes, transaction boundaries, candidate matching, authorized reviewer overrides, single claim, episode close/reopen, reporter-safe user experience, and charge idempotency.
4. Create schema migrations that do not silently discard prior allegation/incident links and retain audit history.
5. Test all AC-D01..AC-D18 with unit, integration, concurrent submission and cross-tenant HTTP tests. Record exact pass/fail evidence in `docs/STATUS.md`.
6. Keep enforcement and payments disabled by default. Do not run actual clamping, towing, messages, fines, payment collection, or production deployment without explicit approvals.
7. After the change is integrated and tests pass, commit and push cleared source and documentation to the existing Apache-2.0 public GitHub repository, then **continue building the remaining approved product milestones**. Do not stop at this addendum.

**Copyright for original material owned by the project initiator:** Copyright © 2026 Johnathan Lightfoot. Preserve third-party and independent contributors' notices and rights.
