#!/usr/bin/env bash
# Start the Frappe web server (both sites, routed by Host header) on 127.0.0.1:8000, in the background.
set -euo pipefail
export MSYS_NO_PATHCONV=1
docker compose -f infra/dev/compose.yaml exec -d bench bash -lc 'cd /home/frappe/bench-data/frappe-bench && bench serve --port 8000 > /tmp/serve.log 2>&1'
