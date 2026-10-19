# Management console (desktop web)

`apps/web` is a React + TypeScript single-page app for association management, security supervisors, finance and designated auditors. Security
officers and residents do **not** use it (they have the mobile app); a role with no pages sees a plain message.

## Security model
* **The console is only a client.** Every page calls the same server APIs the mobile app uses, or Frappe's resource API for plain lists. The server
  decides everything; navigation is built from the server's per-role manifest purely for convenience (`src/nav.ts`, unit-tested).
* **Same-origin.** The production build is served by Frappe at `/assets/frappe_cpcp/web/` so the session cookie is bound to the organization's own
  site (no tenant id is ever sent by the client). `npm run dev` proxies to the dev server and picks the site with a Host header.
* **Personal-data lists are recorded.** Opening Residents, Vehicles or Visitors goes through `guards.before_request`, which journals every open by
  a manager or admin. Exports and printing of those doctypes are refused for every role.
* **No client-side secrets, no tokens in URLs, no tenant switching in the browser.**

## Pages
| Page | Who (server-enforced) | What it does |
|---|---|---|
| Overview | managers, admins, auditors (view), finance (+ledger) | Reports vs episodes, compliance, gate, communications; each figure states its denominator |
| Cases and reports | managers, admins | Consolidated resident-report queue ("N independent reports"); case list and filters; case panel: review candidate links, merge, split, reassign, end episode (manager determination), reopen, credit a duplicated penalty |
| Map | managers, admins | Verified episodes (one pin each, with accuracy circle) and, separately, unverified allegations; date/type filters |
| Residents, units, vehicles | managers, admins | Registers with add forms; visitor presence and history. Gate staff cannot open it |
| Staff and devices | admins (assignments), managers (shifts, revoke device, suspend) | Role assignments, on-duty shifts |
| Policies | admins | Policy versions (draft -> independent approval -> active), legal gate status (read-only) |
| Access review | admins, auditors (read-only), managers (officer activity only) | Journal search and filters, per-person summary, review signals and outcomes, emergency reviews, integrity checks, CSV export (admin) |

## Build and verify
```bash
cd apps/web && npm ci && npm run build        # writes apps/frappe_cpcp/frappe_cpcp/public/web
bench build --app frappe_cpcp                  # links the app's public folder into sites/assets (once)
# open http://<site>/assets/frappe_cpcp/web/index.html
CPCP_DEMO_PASSWORD=... python -m pytest tests/console -q     # what each role may load, over HTTP
```
**Not done:** screenshots/screen recordings, accessibility audit with a screen reader, localization, a dedicated finance/invoice page (ledger
totals appear in Overview), appeals review screen and policy "simulator" (AC-25), tenant onboarding UI. The build output is git-ignored and built in CI.
