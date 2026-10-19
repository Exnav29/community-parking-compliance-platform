# Security Policy

## Reporting a vulnerability
**Do not open a public issue.** Use GitHub's private vulnerability reporting:
*Security → Report a vulnerability* on this repository. Include affected version/commit, impact,
reproduction steps (synthetic data only) and any suggested fix. Never include real resident data or credentials.

We aim to acknowledge reports within 5 business days and to agree a remediation and disclosure timeline with
the reporter. Please allow time for a fix before public disclosure.

## Supported versions
Pre-alpha: only `main` is supported. There are no production deployments of this project.

## Scope highlights
Cross-tenant access, resident access to the registry or visitor log, anonymous-report deanonymization,
auditor write access, audit-chain tampering, and any path to enable enforcement/payments without the legal
gates are treated as release-blocking.

## Hotfix process
Fix on a private advisory branch, run the full authorization and tenant-isolation suites, release a patched tag,
then publish the advisory.
