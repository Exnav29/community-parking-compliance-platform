# Third-party components and licenses
Verified 2026-10-19 against upstream repositories/registries (GitHub API, npm registry). Re-verify before each release.

| Component | Version pinned | License | Use | Notes |
|---|---|---|---|---|
| Frappe Framework | v15.123.1 (dev) | MIT | Backend framework (installed in bench, not vendored) | v16 tags exist; v15 chosen as current "latest" release, see ADR-0001 |
| frappe_docker / frappe/bench image | latest (dev only) | MIT | Dev environment | Not redistributed |
| MariaDB 10.6, Redis 7 | container images | GPL-2.0 / BSD-3 | Dev services (separate processes) | Not linked into CPCP |
| Capacitor | 8.5.3 (planned) | MIT | Native shell | Phase 0 PoC pending |
| React | 19.3.1 (planned) | MIT | Mobile/web UI | |
| Vite | 8.3.4 (planned) | MIT | Build | |
| TypeScript | 7.0.2 (planned) | Apache-2.0 | Build | |
| Leaflet | 1.9.4 (planned) | BSD-2-Clause | Maps | Tile provider terms to be reviewed |
| pytest / ruff (dev) | latest | MIT | Tests / lint | |

**ERPNext (GPL-3.0) is not used.** Any GPL/AGPL dependency requires a documented compatibility review first.
Machine-generated SBOM/license inventory in CI is pending (tracked in docs/STATUS.md).
