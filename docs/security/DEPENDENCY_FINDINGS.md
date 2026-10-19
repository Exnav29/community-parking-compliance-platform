# Dependency vulnerability findings (open items, not fixed)

Scan date: 2026-10-19. Tools: `npm audit`, `pip-audit` against the package list in `docs/legal/sbom/backend-bench-env.cdx.json`.

## Mobile app (npm)
* `npm audit --omit=dev`: **0 vulnerabilities** in what ships in the app.
* `npm audit` (including dev tooling): 3 moderate, all via `@capacitor/cli -> xcode`, used only on a developer/CI machine to sync native projects. A forced fix is a breaking major upgrade; tracked by Dependabot.

## Backend (Python packages installed with Frappe v15.123.1)
`pip-audit` reports known advisories in packages that come from **Frappe's own pinned dependency tree** (CPCP adds no Python runtime dependency of its own except Pillow, which Frappe already ships):

| Package | Installed | Fix available | CPCP exposure assessment |
|---|---|---|---|
| pyjwt | 2.13.0 | 2.14.0 / 2.15.0 | Used by Frappe's OAuth/social-login code paths; CPCP does not use JWT. Confirm Frappe's pin range before upgrading. |
| werkzeug | 3.1.6 | 3.1.9 | Web server library under Frappe. Upgrade is the priority item. |
| oauthlib | 3.3.1 | 4.0.0 (major) | Frappe OAuth; not used by CPCP APIs (session-cookie auth). |
| pypdf | 6.15.0 | up to 6.19.0 | PDF handling inside Frappe print/attach features. CPCP **denies print/PDF/export for every sensitive doctype**, which removes the main reachable path, but Frappe itself may still parse uploaded PDFs elsewhere. |
| weasyprint | 69.0 | 70.0 | PDF rendering for print formats (same reasoning). |
| pdfkit | 1.0.0 | none listed | Same. |

**Status: OPEN.** Required action before any pilot: re-run the audit against the newest Frappe v15 patch, test upgrading the packages above within Frappe's declared constraints in staging, and if Frappe's pins block a fix, either wait for an upstream release or apply a tested constraint override. Do not deploy to production with these unresolved. The scan is repeated by the `supply-chain` CI job (report only, because the fix path is upstream).

## Process
Dependabot (npm, pip, GitHub Actions, Docker) is enabled via `.github/dependabot.yml`. SBOMs live in `docs/legal/sbom/` (CycloneDX JSON). `scripts/license_check.py` enforces the licence policy and `docs/legal/license-exceptions.json` records reasoned exceptions.
