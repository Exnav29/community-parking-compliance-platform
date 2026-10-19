# Changelog
Format: [Keep a Changelog](https://keepachangelog.com/), versioning: [SemVer](https://semver.org/) (0.x = unstable API).

## [Unreleased]
### Added
- Repository governance: Apache-2.0, NOTICE, CONTRIBUTING (DCO), code of conduct, security policy, templates, CI.
- Framework-independent domain core with unit tests: authorization matrix, visitor sessions, notice clock,
  charge engine, allegation triage and anonymous receipts, hash-chained audit log, geo helpers.
- Frappe app `frappe_cpcp`: DocTypes (generated), permission hooks, protected registry, visitor and allegation APIs.
- Dev environment: Docker Compose + bootstrap script for a Frappe v15 bench with two organization sites.
