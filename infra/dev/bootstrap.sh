#!/usr/bin/env bash
# Bootstrap the CPCP development bench with TWO isolated organization sites.
# Run from the repo root (Git Bash / WSL / Linux / macOS):  bash infra/dev/bootstrap.sh
set -euo pipefail
export MSYS_NO_PATHCONV=1  # Git Bash on Windows must not rewrite container paths
C="docker compose -f infra/dev/compose.yaml"
$C up -d
$C exec -u root bench chown frappe:frappe /home/frappe/bench-data
$C exec bench bash -lc '
set -euo pipefail
export MSYS_NO_PATHCONV=1  # Git Bash on Windows must not rewrite container paths
# Dev-only: the local MariaDB container has no TLS and sits on a private compose network.
printf "[client]
skip-ssl
" > "$HOME/.my.cnf"
cd /home/frappe/bench-data
if [ ! -d frappe-bench/apps/frappe ]; then
  bench init --skip-redis-config-generation --frappe-branch "$FRAPPE_REF" --python "$HOME/.pyenv/versions/3.12.15/bin/python" frappe-bench
fi
cd frappe-bench
bench set-config -g db_host mariadb
bench set-config -g redis_cache redis://redis:6379/0
bench set-config -g redis_queue redis://redis:6379/1
bench set-config -g redis_socketio redis://redis:6379/2
bench set-config -g developer_mode 1
bench set-config -g serve_default_site 0 || true
# Link the custom app from the mounted workspace (editable install).
if [ ! -e apps/frappe_cpcp ]; then ln -s /workspace/apps/frappe_cpcp apps/frappe_cpcp; fi
./env/bin/pip install -q -e apps/frappe_cpcp
grep -qx frappe_cpcp sites/apps.txt || { [ -n "$(tail -c1 sites/apps.txt)" ] && echo >> sites/apps.txt; echo frappe_cpcp >> sites/apps.txt; }
for SITE in org-a.localhost org-b.localhost; do
  if [ ! -d "sites/$SITE" ]; then
    bench new-site "$SITE" --db-root-password "$CPCP_DEV_DB_ROOT_PASSWORD" --admin-password "$CPCP_DEV_ADMIN_PASSWORD" --mariadb-user-host-login-scope="%"
  fi
  bench --site "$SITE" install-app frappe_cpcp || true
  bench --site "$SITE" set-config allow_tests true
done
bench --site org-a.localhost list-apps
'
