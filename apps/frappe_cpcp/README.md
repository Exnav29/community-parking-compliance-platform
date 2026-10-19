# frappe_cpcp

The custom Frappe application for the Community Parking & Compliance Platform.
See the repository root `README.md` and `docs/architecture/ARCHITECTURE.md`.

* `frappe_cpcp/core/` – framework-independent domain logic (pure Python, unit tested without Frappe).
* `frappe_cpcp/cpcp/doctype/` – DocTypes (generated from `scripts/gen_doctypes.py`) and controllers.
* `frappe_cpcp/api/` – whitelisted, authorization-checked service endpoints.
