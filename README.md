# Community Parking & Compliance Platform (CPCP)

Open-source, multi-organization software for residential estates, HOAs and gated communities:
resident/unit/vehicle registry, fast gatehouse visitor check-in/out, resident parking-concern reporting
(identified or anonymous), security triage, and — behind explicit legal gates — warnings, enforcement
accounting and appeals. **The goal is voluntary compliance and safe access, not fine revenue.**

> **CPCP is an internal working title**, not a cleared brand.
> **Status: early development (pre-alpha). Not production ready. Not app-store published.**
> Live clamping, towing, fines, payments, public registration and store publication are **disabled by
> default** and need separate written authorization and local legal review.

## What exists today

| Area | State |
|---|---|
| Domain core, 35-DocType Frappe app, incident lifecycle (v1.7), **purpose-based resident privacy (v1.8)**, communications, gated enforcement, reports | Implemented and verified; see [docs/STATUS.md](docs/STATUS.md) |
| Mobile app (React + Capacitor) | Implemented; awaiting physical-device validation |
| Isolated Frappe site per organization (dev: 2 sites), cross-tenant isolation | Verified over HTTP |
| Desktop management console, map/finance screens | Not started |

See [docs/STATUS.md](docs/STATUS.md) for verified results and blockers, and
[docs/spec/PRD_v1.8.md](docs/spec/PRD_v1.8.md) for the specification.

## Architecture in brief
One isolated Frappe site (own database, files, backups) **per subscribing organization**; one or more estates
inside it. Authorization is a single tested service (`core/authz.py`) called by every API and by Frappe
`has_permission` / `permission_query_conditions` hooks. Residents have no access to the resident/vehicle
registry or visitor log, and **security officers have no standing directory access either**: every sensitive lookup needs a server-verified purpose (a live gate shift or an assigned case), returns minimum fields, and is written to a tamper-evident journal ([docs/security/PRIVACY_PBAC.md](docs/security/PRIVACY_PBAC.md)). Anonymous reports use a separate unauthenticated intake with no reporter correlator.
Details: [docs/architecture/ARCHITECTURE.md](docs/architecture/ARCHITECTURE.md).

## Quick start (Docker, synthetic data only)
```bash
cp .env.example .env            # then edit placeholders
bash infra/dev/bootstrap.sh     # Frappe v15 bench + two sites: org-a.localhost, org-b.localhost
```
Pure-Python domain tests need no Frappe:
```bash
python -m venv .venv && . .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install pytest && cd apps/frappe_cpcp && python -m pytest
```

## Contributing
Contributions are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md). Security issues: [SECURITY.md](SECURITY.md).
Never include real resident, visitor, plate, GPS or credential data in issues or PRs.

## License
Original code: [Apache License 2.0](LICENSE), Copyright (c) 2026 Johnathan Lightfoot and contributors (see [NOTICE](NOTICE)); sponsored by Bulletproof Automations. Third-party components keep their own licenses
([docs/legal/THIRD_PARTY_LICENSES.md](docs/legal/THIRD_PARTY_LICENSES.md)). Open-source code does not grant access
to any association's data, hosted accounts, payment merchant accounts or app-signing keys.
