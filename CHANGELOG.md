# Changelog
Format: [Keep a Changelog](https://keepachangelog.com/), versioning: [SemVer](https://semver.org/) (0.x = unstable API).

## [Unreleased]
### Added
- Resident report photos with metadata stripping before persistence; backup/restore verification script; CycloneDX SBOMs, licence policy check, Dependabot and a supply-chain CI job; threat model, app-store compliance matrix and dependency findings documents.
- PRD v1.8 consolidated (`docs/spec/PRD_v1.8.md`) and implemented: purpose-based access control (gate shifts on registered devices, assigned-case checks), no standing officer registry/visitor-log access, request guard for Desk/REST/search/export/print, durable hash-chained access journal written on a separate DB connection (fails closed), Access Review API with misuse signals (never automatic action), break-glass emergency access with independent review, device revocation and user suspension, journal retention job; PBAC-01..20 tests (in-process and HTTP).
- PRD v1.7 consolidated (`docs/spec/PRD_v1.7.md`): episode-based incident identity, many allegations per case, active-case detection, claim lease, unique active keys, deadlock-safe find-or-create, manager merge/split, repeat-offender metrics; AC-D01..D18 tests and parallel HTTP concurrency tests.
- Contact resolution, calls/SMS records, notice clock, gated enforcement, charges, appeals, reports, mobile app (see STATUS).
- Repository governance: Apache-2.0, NOTICE, CONTRIBUTING (DCO), code of conduct, security policy, templates, CI.
- Framework-independent domain core with unit tests: authorization matrix, visitor sessions, notice clock,
  charge engine, allegation triage and anonymous receipts, hash-chained audit log, geo helpers.
- Frappe app `frappe_cpcp`: DocTypes (generated), permission hooks, protected registry, visitor and allegation APIs.
- Dev environment: Docker Compose + bootstrap script for a Frappe v15 bench with two organization sites.
