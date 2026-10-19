# Community contributions and pull-request review

CPCP is open source, pre-alpha, and handles exceptionally sensitive information about households, visitors, movement, locations, and potential financial penalties. We welcome bug fixes, accessibility improvements, documentation, tests, and focused features.

## Where to participate

- [Discussions](https://github.com/Exnav29/community-parking-compliance-platform/discussions) — Q&A, ideas, proposals, showcases, and general community conversations.
- [Issues](https://github.com/Exnav29/community-parking-compliance-platform/issues) — reproducible bugs and agreed, trackable development tasks.
- [Pull requests](https://github.com/Exnav29/community-parking-compliance-platform/pulls) — code and documentation changes.
- [Private vulnerability reporting](https://github.com/Exnav29/community-parking-compliance-platform/security/advisories/new) — security reports (never report vulnerabilities or personal information in public discussions).

Before implementing a large change, please open an Idea discussion or issue to coordinate scope and avoid duplicate work.

## PR screening pipeline

The repository runs free GitHub Actions checks on proposed pull requests:

1. **CI / core-tests:** Python core tests, critical lint, deterministic DocType and permission-matrix regeneration.
2. **CI / secret-scan:** gitleaks for accidentally committed secrets.
3. **PR Screening / dependency-review:** reject newly introduced dependencies with known high or critical vulnerabilities. This is not a complete license-compatibility audit.
4. **PR Screening / file-safety:** block suspicious tracked credential, key, database, and binary-build artifact paths. Treat results as a first filter, not a comprehensive data-leak detector.
5. **PR Screening / mobile-lint:** run the mobile React/TypeScript linter.
6. **Mobile / web:** typecheck, unit tests, web build and Android debug build when mobile files change.
7. **CodeQL (GitHub code scanning):** static security analysis where configured by repository administrators. Check the GitHub security tab for supported-language coverage and findings.

These checks may run after the PR is opened; their success does **not** mean the code is approved. GitHub may require manual authorization to execute Actions from first-time external contributors. No PR is automatically merged.

## What humans still check

Maintainer approval is essential for changes involving:

- tenant isolation and authorizations, including direct API and Frappe DocType bypasses;
- access to resident, visitor, contact, evidence, or location data;
- anonymity and sensitive audit trails, including denial and rollback behavior;
- incident deduplication, fee idempotency, clamp/tow safety, and financial correctness;
- data retention, mobile offline caching, encryption, backups, and cross-device synchronization;
- new dependencies, their supply-chain security, and third-party licenses;
- changes to GitHub Actions, security checks, deployment scripts, permissions, or CODEOWNERS.

Require test evidence for each changed behavior. Scan for personal data even when GitHub secret scanning is green. Use only synthetic records in PRs, tickets, fixtures, screenshots, and logs.

## Review outcomes

- **Checks failing or incomplete:** do not merge; request corrections or investigate false positives.
- **Checks green and high-risk:** perform manual security/design review and adversarial tests.
- **Checks green and low-risk:** review diff and documentation, then merge only with maintainer approval.
- **No maintainer available:** leave the PR open; do not enable unattended auto-merge.

Maintainership currently rests with @Exnav29. PR reviews are welcomed from other community members, but merge authority remains with authorized maintainers. Community reviews and AI reviews are advisory.

## Contributor instructions

See [CONTRIBUTING.md](../../CONTRIBUTING.md) for DCO sign-off, local tests and change etiquette. Every commit must be signed off with `git commit -s` to certify contributor rights. This does not assign copyright to CPCP's sponsor.

CPCP is licensed under Apache-2.0. Real enforcement, payment collection, and public deployment remain off pending proper authorization and legal review.
