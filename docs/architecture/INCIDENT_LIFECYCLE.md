# Incident consolidation, duplicate allegations and repeat offenders (PRD v1.7, section 60)

## 1. Gap assessment (before this change)
| Area | Finding |
|---|---|
| Matching | A same-plate **4-hour window** (`_dedup_cluster`) decided whether reports belonged together. A clamped or impounded car reported 5+ hours later started a second cluster. |
| Work ownership | `CPCP Security Work Item` was **one per allegation** (unique on `allegation`), so every duplicate report created another claimable item and a second officer could start a parallel case. |
| Incident identity | "Is there already an incident?" was a plain `SELECT` followed by an insert. **No database constraint** prevented two incidents for one vehicle; two concurrent promotions could both create one. |
| Links | Allegations were child rows with no join reason, confidence, actor or uniqueness. |
| Enforcement | Nothing stopped a second clamp or tow proposal on the same episode. The base penalty was protected by a unique `idempotency_key` only. |
| Episode end | No concept. A new calendar day or a closed ticket could silently make the next report a "new" case. |
| Metrics | Dashboards counted allegations and incidents but did not separate linked duplicates. |

## 2. Model
* **Incident == parking episode.** `active_key = hash(estate | normalized plate)` is a **UNIQUE** column that is non-NULL only while the episode has not *positively* ended. That is the database-enforced "one live episode per vehicle per estate".
* **Work item == one actionable case** with a UNIQUE `cluster_key` while open (same estate+plate). Allegations join it as child rows (`CPCP Work Item Allegation`). One claim, with a lease (`claim_lease_hours`) and manager reassignment.
* **Allegation** stays an immutable intake record. Linking is a separate row (`CPCP Incident Allegation Link`) with `link_state` (Auto Candidate, Confirmed, Rejected, Late, Merged from, Split out), `join_reason`, `matcher_confidence`, `linked_by`, `linked_at` and a unique `link_key` (`incident:allegation`).
* **No active key** (no or unreadable plate) means the report can never be auto-merged or auto-billed. It becomes a review work item that points at the nearest active case for comparison.
* **Elapsed time is not an input to matching.** See `core/matching.py` (there is no time field) and tests.

## 3. Lifecycle (`core/episodes.py`)
`New/Candidate -> Under Review -> Verified/Open -> Warning Active -> (Compliance Confirmed | Clamp Active -> Tow Ordered -> Towed/Impounded) -> Release Pending -> Resolved/Closed -> Reopened for Review`.
Illegal jumps raise. States `Warning Active`, `Clamp Active`, `Tow Ordered`, `Towed/Impounded`, `Release Pending` are **"already being handled"**: later reports enrich the case and the UI shows that banner; a second clamp/tow cannot be proposed.

**What ends an episode** (`end_episode`): `departure_verified`, `removal_confirmed`, `movement_corroborated`, `manager_determination` release the vehicle identity (a later offense becomes a new episode). `resolved_without_departure` closes the case but **keeps** the identity. `payment`, `clamp_removed`, `new_day`, `overnight`, `shift_change` are rejected as evidence. A live clamp/tow must be released first (managers may override with a determination).

## 4. Concurrency rules (MariaDB / InnoDB REPEATABLE READ)
1. **Unique-key find-or-create.** INSERT inside a savepoint; a unique violation (`UniqueValidationError` *or* `DuplicateEntryError`) means another request won.
2. **Locking reads after a conflict.** The winner is read with `SELECT ... FOR UPDATE`. A plain read may come from an older snapshot and miss a row committed a moment ago (this was found and fixed by the parallel tests).
3. **Lock order: work item first, then incident.** Prevents the deadlock between a verifier (holding the work item, inserting the incident key) and an arriving report (gap-locking the incident key, wanting the work item).
4. **Retry.** `@deadlock_retry` re-runs a whole mutating request if InnoDB picks it as a deadlock victim. All guarded paths are idempotent (client UUIDs, unique keys).
5. **Idempotency keys:** allegation `client_uuid`; work item `cluster_key`; link `link_key`; live enforcement action `active_key` (`incident:type`); charge `idempotency_key` (`incident:class:discriminator`); outbox `idempotency_key`; provider events `event_key`.
6. **Transactional outbox.** Notifications are rows written in the same transaction; delivery is a separate retried concern.
7. Reads inside critical sections that decide *membership or counts* use locking reads (`members_of`, `locked_count`, `locked_get`).

## 5. Manager operations (all non-destructive, reasoned, audited)
`merge_incidents` (re-links reports as *Merged from*, frees the source key, **flags both incidents if two base penalties exist** and never deletes a ledger line), `credit_duplicate_penalty` (adds an `ADJUSTMENT_CREDIT`), `split_incident` (moves reports to a fresh review work item), `reassign_work_item` / `reassign_incident`, `reopen_episode`.

## 6. Resident and anonymous privacy
`precheck_similar` takes **location only** (never a plate, so it cannot probe which vehicles are being handled), returns an identical shape every time and a generic sentence. Submission acknowledgements never include incident IDs, units, officers or enforcement state. Linking uses submitted attributes and server evidence only; anonymous allegations gain no device, user or IP correlator (`assert_anonymous_clean`, tested).

## 7. Metrics
Dashboards separate: allegations (identified vs anonymous *submissions*, never "people"), unique incidents, verified violations, duplicate reports linked, executed enforcement actions by type, distinct base penalties (finance roles only), repeat vehicles (distinct verified episodes; merged-away and appeal-upheld incidents excluded) and median first-response time. Hotspot pins are one per episode; complaint intensity is a separate layer.

## 8. Migration
`patches/v1_7_incident_lifecycle.py` backfills episode status, `plate_hash`, counts, `active_key` (the first live incident per vehicle keeps the key; duplicates are flagged for review, never auto-merged), link states and work-item member rows. No prior link or history is removed.

## 9. Known limits
* Matching is plate-and-location based; OCR confidence and visit-session history are not yet inputs.
* The vehicle-moved-between-prohibited-locations case relies on the reviewer (`review_candidate`, `merge`); there is no automatic movement timeline yet.
* Payment-webhook idempotency is covered at the core level (`apply_payment_once`); no live payment endpoint exists (gated).
