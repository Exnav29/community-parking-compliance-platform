## Summary
What changed and why? Link a related issue or discussion, if applicable.

Closes #

## Risk and privacy impact
- **Affected areas:** (e.g., gatehouse, mobile, permissions, billing, workflows)
- **Tenant isolation / resident data:** Describe impacts or write "none".
- **Enforcement, payments, messaging:** Confirm safety flags remain OFF by default.
- **Migration / backward compatibility:** Describe changes or write "none".

## Validation evidence
Give commands and results, not just "tests pass". Attach synthetic screenshots for UI changes.

## Contributor checklist
- [ ] I have read [CONTRIBUTING.md](../CONTRIBUTING.md) and the [Code of Conduct](../CODE_OF_CONDUCT.md).
- [ ] Automated PR screening and appropriate unit/integration tests pass, or I explained why they cannot run.
- [ ] Negative authorization and cross-tenant tests added/updated for permission or data changes.
- [ ] No real resident/visitor records, plates, phone numbers, GPS, photos, credentials, or secrets.
- [ ] Any new dependencies have been reviewed and documented in `docs/legal/THIRD_PARTY_LICENSES.md`.
- [ ] No real-world enforcement, fees, towing, SMS billing, or payment integrations activated.
- [ ] Schema changes have a non-destructive migration and recovery path.
- [ ] Documentation, examples, and CHANGELOG updated as appropriate.
- [ ] Every commit carries DCO sign-off (`git commit -s`).

**For maintainers:** Automated checks are a screening layer, never a substitute for human review of auth, privacy, safety, licensing, and financial logic. See [PR Review Guide](../docs/community/PULL_REQUEST_REVIEW.md).
