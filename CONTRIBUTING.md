# Contributing to CPCP

Thank you for helping. This project handles sensitive community data, so a few rules are firm.

## Ground rules
1. **Synthetic data only.** Never put real names, plates, phone numbers, GPS points, photos, logs or
   credentials in code, tests, issues or PRs. Fixtures use fictitious values (see `demo/`).
2. **Authorization is centralized.** New endpoints must call `permissions.authorize` /
   `core.authz.decide` and ship negative tests (resident, auditor, other estate, other organization).
3. **Safety gates stay off.** Do not add default-on enforcement, fees or payment behavior.
4. **Append-only means append-only** (audit, evidence, visit events, receipts).
5. No code from other repositories unless its license is compatible with Apache-2.0 and it is listed in
   `docs/legal/THIRD_PARTY_LICENSES.md`.

## License and sign-off (inbound = outbound)
Contributions are licensed under Apache-2.0 and you keep your own copyright; the DCO is a certification of your right to contribute, not a copyright assignment. Certify the [Developer Certificate of Origin](https://developercertificate.org/)
by signing off every commit: `git commit -s`.

## Community and automated checks
Please ask questions or propose major features in [Discussions](https://github.com/Exnav29/community-parking-compliance-platform/discussions) first. Use Issues for confirmed defects and bounded tasks. Pull requests run automated tests, secret scanning, dependency review, sensitive-file detection and mobile lint. CI results do not substitute for human security review. See the [PR Review Guide](docs/community/PULL_REQUEST_REVIEW.md) for the full checklist and high-risk areas. First-time external contributors may need their workflows approved before GitHub Actions will run.

## Workflow
- Fork, branch, open a PR against `main`. Keep PRs focused; update docs and `CHANGELOG.md`.
- Run before pushing: `cd apps/frappe_cpcp && python -m pytest` and `ruff check .`.
  Frappe integration tests: `bench --site org-a.localhost run-tests --app frappe_cpcp` (see README).
- DocTypes are generated from `scripts/gen_doctypes.py`; edit the generator, regenerate, commit both.
- Schema changes need a patch in `patches.txt` and must not break existing sites.
- Accessibility and low-end-Android usability are requirements, not extras.

## Reporting problems
Bugs and features: GitHub issues (redact logs). Vulnerabilities: see [SECURITY.md](SECURITY.md), not public issues.
