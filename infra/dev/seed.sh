#!/usr/bin/env bash
# Seed both dev sites with DIFFERENT synthetic organizations (profile a / profile b). Fictitious data only.
set -euo pipefail
export MSYS_NO_PATHCONV=1
C="docker compose -f infra/dev/compose.yaml"
PW="${CPCP_DEMO_PASSWORD:-}"
$C exec -e CPCP_DEMO_PASSWORD="$PW" bench bash -lc 'cd /home/frappe/bench-data/frappe-bench
bench --site org-a.localhost execute frappe_cpcp.setup.seed_demo --kwargs "{\"profile\":\"a\"}" | tail -1
bench --site org-b.localhost execute frappe_cpcp.setup.seed_demo --kwargs "{\"profile\":\"b\"}" | tail -1'
