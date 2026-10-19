# Resident privacy and purpose-based access (PRD v1.8, section 61)

**Principle:** a security role is not authorization to see a household. Sensitive reads need a *server-verified, current operational purpose*, return the *minimum* fields, and are *journaled durably before data is returned*.

## 1. Entry-point map (every door, and what guards it)
| Door | Before v1.8 | Now |
|---|---|---|
| Frappe Desk lists/forms, `/api/resource`, `frappe.client.*`, reportview, search/autocomplete | Officers had DocPerm read on Person, Vehicle, Visitor Session, Membership… | Officers have **no** DocPerm on any sensitive doctype; `permissions.has_permission` / `query_conditions` deny; and `guards.before_request` denies + journals on **every** request that names one (defense in depth) |
| Export / print / PDF / email / share of sensitive doctypes | blocked only by DocPerm flags | denied for **every** role by the request guard (`bulk_disclosure_requires_approved_export`) and journaled |
| `registry.lookup_plate` | any officer of the estate | `gate` purpose: live shift, matching gate, hourly ceiling; `case` purpose: assigned open case and **that case's own plate**; any other purpose → denied |
| `registry.lookup_visits_for_unit` (returning visitor) | up to 10 candidates with last-visit dates | max 3 candidates, **no dates/counts/names**, narrowed by a plate hint; bare unit lookups have a stricter hourly ceiling and are flagged when high-volume |
| `visitors.check_in/out/active_visitors` | any officer of the estate | live shift required; the gate comes from the shift, never from the client |
| `communications.*` (contacts, call, SMS, timeline) | any officer of the estate | the officer must be the case's **current assignee**, case open, on duty; numbers are masked; the dialer number is revealed only to the assignee and journaled as a contact reveal |
| `ops.active_cases`, `incident_detail` | all cases in the estate | "my assigned cases" only for officers |
| Triage queue / open report | any officer of the estate | on duty required; reporter identity still manager-only with a reason |
| Manager / admin / platform Administrator | unlogged | allowed for administration but **always journaled** (`purpose=administration`), visible to independent reviewers |
| Mobile offline cache | drafts | drafts only; **refuses** names, phones, contacts, members, history, candidates; 72 h expiry; wiped on sign-out; one namespace per organization; native keystore only |
| Push / SMS payloads | minimal | unchanged (no plate, unit, phone, name); tested |

## 2. The access journal (`CPCP Sensitive Access Event`)
* **Durable:** written on a **separate DB connection** and committed immediately (`services/access.py`), so a denial survives the request's rollback (test PBAC-11). If the journal cannot be written the operation **fails closed**.
* **Tamper-evident:** hash-chained (`seq`, `prev_hash`, `hash`), append-only at the model level, `verify_chain()` exposed to reviewers. Direct SQL remains possible for a database administrator; the chain makes tampering detectable, and DB-level controls (separate low-privilege app user, backups, restricted access) are deployment requirements.
* **Content:** UTC time, actor, role, estate, gate, shift, pseudonymous device hash, session hash, action, record type, safe record id, target unit label, data category, purpose and its validated reference, decision (Allowed / Denied / No Match / Emergency), reason code, request id. **Never** names, numbers, narratives, photos or raw search terms (one-way keyed hash only).
* **Visibility:** org admins and auditors (read-only) see everything; security managers see **officer** activity only and never their own; officers see nothing; nobody sees signals about themselves.
* **Retention:** `access_log_retention_days` (default 730). `services/retention.py` is the **only** deletion path (scheduled, daily): it removes a contiguous prefix, keeps emergency and under-review rows and the newest row, and records `through_seq/through_hash` in the audit chain as the anchor. Defaults are placeholders pending legal review (Ghana DPA).

## 3. Review and misuse detection
`services/access_review.py` (hourly job + on demand). Signals, all configurable: many different households in an hour, repeated lookups of one household with no case/visit reference, repeated denials, high-volume suggestion lookups, attempts outside shift/gate/estate/case, contact-reveal attempts with no matching workflow, privileged-access volume, break-glass use, overdue emergency reviews.
* Idempotent per rule/person/hour; alerts go to org admins and auditors via the outbox, **never** to the person concerned.
* A signal is **not** a finding. Nothing suspends, disciplines or blocks anyone automatically. Reviewers record an outcome and note. A fair investigation process is an organizational procedure to be written with counsel.

## 4. Emergency (break-glass)
On-duty officer or manager; documented reason (≥ 20 characters); **one unit**, contacts only; expiry ≤ 60 min (configurable, hard cap 120); max 3 per person per 24 h; immediate notification to managers and org admins; journaled as `Emergency`; mandatory review by a *different* manager/admin; unreviewed expired grants raise a high-severity signal. It never widens estate or tenant scope.

## 5. Shifts, devices and revocation
Shift = server-side proof of duty (estate, gate, device hash, absolute expiry, one live shift per person). `duty.revoke_device` ends shifts, marks the device revoked and clears web sessions; `duty.suspend_user` suspends all assignments. Every sensitive call re-checks the shift, device and account on the server, so a phone with a still-open screen loses access at once (PBAC-20).

## 6. Residual risks and honest limits
* A rostered, on-duty officer legitimately sees a **small** gate-level answer for any unit in their estate (needed for fast check-in). The controls are: minimum fields, plate-hint narrowing, hard hourly ceilings, journaling, anomaly review. This is a deliberate trade-off against gatehouse speed.
* The native dialer necessarily exposes the dialled number to the assigned officer's phone. Server-mediated calling (provider) would avoid that; it is not enabled.
* Managers keep administrative registry access (logged and reviewed). Whether to require an approved investigation reference for manager registry reads is an open governance decision for each association.
* A malicious database administrator can alter rows; mitigated by detection (hash chain) and deployment controls, not prevented by application code.
* Cross-organization rule: each organization is its own Frappe site; journals are per-site (verified over HTTP against both demo sites).
