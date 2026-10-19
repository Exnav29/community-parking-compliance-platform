#!/usr/bin/env bash
# Backup -> restore-into-a-NEW-site -> compare facts (AC-18). Dev stack only; synthetic data.
#   bash infra/dev/backup_restore_check.sh [source-site]      (default org-a.localhost)
# Exit code 0 only if every compared fact is identical.
set -euo pipefail
export MSYS_NO_PATHCONV=1
SRC="${1:-org-a.localhost}"
DST="restore-check.localhost"
C="docker compose -f infra/dev/compose.yaml"
$C exec -T bench bash -lc "
set -euo pipefail
cd /home/frappe/bench-data/frappe-bench
SRC=$SRC; DST=$DST
rm -rf /tmp/bk && mkdir -p /tmp/bk
bench --site \$SRC execute frappe_cpcp.ops.backup_facts.ensure_sample_private_file >/dev/null 2>&1 || true
bench --site \$SRC backup --with-files > /tmp/bk/backup.log 2>&1
cat /tmp/bk/backup.log | tail -8
B=sites/\$SRC/private/backups
DB=\$(ls -t \$B/*-database.sql.gz | head -1)
PRIV=\$(ls -t \$B/*-private-files.tar | head -1)
PUB=\$(ls -t \$B/*-files.tar | head -1)
CFG=\$(ls -t \$B/*-site_config_backup.json | head -1)
echo \"backup: \$DB | \$PRIV\"
bench --site \$SRC execute frappe_cpcp.ops.backup_facts.collect | tail -1 > /tmp/bk/source.json
bench drop-site \$DST --force --db-root-password \"\$CPCP_DEV_DB_ROOT_PASSWORD\" >/dev/null 2>&1 || true
rm -rf sites/\$DST
bench new-site \$DST --db-root-password \"\$CPCP_DEV_DB_ROOT_PASSWORD\" --admin-password \"\$CPCP_DEV_ADMIN_PASSWORD\" --mariadb-user-host-login-scope='%' >/dev/null 2>&1
bench --site \$DST --force restore \"\$DB\" --with-private-files \"\$PRIV\" --with-public-files \"\$PUB\" --db-root-password \"\$CPCP_DEV_DB_ROOT_PASSWORD\" 2>&1 | tail -3
# Secrets live in site_config, which is NOT in the database dump. Operators restore them from the secrets store; here we copy the cpcp_* keys from the config backup.
python3 - \"\$CFG\" sites/\$DST/site_config.json <<'PY'
import json, sys
src, dst = json.load(open(sys.argv[1])), json.load(open(sys.argv[2]))
dst.update({k: v for k, v in src.items() if k.startswith('cpcp_')})
json.dump(dst, open(sys.argv[2], 'w'), indent=1)
PY
bench --site \$DST migrate >/dev/null 2>&1
bench --site \$DST execute frappe_cpcp.ops.backup_facts.collect | tail -1 > /tmp/bk/restored.json
python3 - <<'PY'
import json
a, b = json.load(open('/tmp/bk/source.json')), json.load(open('/tmp/bk/restored.json'))
a.pop('site'); b.pop('site')
bad = [k for k in a if a[k] != b[k]]
print('SOURCE  :', json.dumps(a['counts'], sort_keys=True)[:300], '...')
print('journal :', a['access_journal'], '->', b['access_journal'])
print('audit   :', a['audit_chain'], '->', b['audit_chain'])
print('ledger  :', a['ledger'], '->', b['ledger'])
print('files   :', a['private_files']['count'], 'files, digest', a['private_files']['digest'][:16], '->', b['private_files']['digest'][:16])
if bad:
    print('MISMATCH in', bad); raise SystemExit(1)
print('RESTORE VERIFIED: all compared facts are identical')
PY
bench drop-site \$DST --force --db-root-password \"\$CPCP_DEV_DB_ROOT_PASSWORD\" >/dev/null 2>&1 || true
"
