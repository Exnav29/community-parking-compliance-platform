# Backup and restore (verified procedure)

Each organization is its own Frappe site, so backup and restore are per site.

## Procedure (what `infra/dev/backup_restore_check.sh` runs)
1. `bench --site <site> backup --with-files` creates four artifacts: database dump, **private files** archive (evidence and resident photos), public files archive and a copy of `site_config.json`.
2. Restore into a **new** site: `bench new-site <name>` then `bench --site <name> --force restore <db.sql.gz> --with-private-files <private.tar> --with-public-files <public.tar>`, then `bench --site <name> migrate`.
3. **Secrets are not in the database dump.** Keys in `site_config.json` (`cpcp_anon_signing_key`, `cpcp_sms_callback_secret`, DB credentials) must be restored from the organization's secrets store. The dev script copies the `cpcp_*` keys from the config backup; production must use a proper secrets manager and never commit or email the config backup.
4. Verify with `frappe_cpcp.ops.backup_facts.collect` on both sites and compare.

## What is compared (identical on source and restored site)
Row counts for 21 core doctypes; **sensitive-access journal** row count and hash-chain integrity; **audit chain** row count and integrity; ledger totals per charge class; SHA-256 digest over every private evidence/resident-photo file.

## Result (2026-10-19, dev stack, synthetic data)
`bash infra/dev/backup_restore_check.sh` -> **RESTORE VERIFIED**: journal 2026 rows chain intact -> 2026 rows chain intact; audit chain 1895 rows intact -> 1895; ledger identical; 1 private file, digest `800dea72...` identical on both sites.

## Not yet proven (be explicit)
* Restore of a backup onto a different host/MariaDB minor version; point-in-time recovery; backup encryption at rest and off-site copy; scheduled backups and alerting on failure; restore time objectives. These are deployment tasks for the hosting plan, to be done before any real data.
* Tenant offboarding export/deletion (PRD 24.6) is not implemented yet.
