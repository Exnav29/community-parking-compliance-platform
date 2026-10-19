# ADR-0001: Frappe v15 and site-per-organization tenancy
Status: accepted (2026-10-19)

**Context.** On 2026-10-19 GitHub's latest Frappe release is v15.123.1 (MIT); v16 tags exist (16.52.0) but are not
the default release; `frappe_docker` v4.1.1 defaults to v15.

**Decision.** Pin Frappe v15.123.1 for development. One isolated Frappe site per organization.

**Consequences.** v16-only features (custom permission types) are not used. Re-evaluate v16 before first pilot.
