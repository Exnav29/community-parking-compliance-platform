# Testing CPCP on an Android phone

**Status: implemented, awaiting physical-device validation.** The debug APK is built by GitHub Actions (workflow *Mobile*, artifact `cpcp-debug-apk-unsigned`; Gradle signs debug builds with its own throw-away debug key — no private keys are involved). It is a **test build** that allows plain HTTP to private LAN addresses; production builds require HTTPS.

## 1. Get the APK
`gh run download -R Exnav29/community-parking-compliance-platform -n cpcp-debug-apk-unsigned` (or Actions tab → latest *Mobile* run → Artifacts). Copy `app-debug.apk` to the phone, open it, allow "install unknown apps" for your file manager, install.

## 2. Run a local demo server (laptop on the same Wi-Fi)
```bash
cp .env.example .env && bash infra/dev/bootstrap.sh
CPCP_DEMO_PASSWORD='choose-a-test-password' bash infra/dev/seed.sh
bash infra/dev/serve.sh            # serves on port 8000
```
Find the laptop's LAN IP (`ipconfig`), allow port 8000 through the Windows firewall for the *Private* profile only, and make the phone's Wi-Fi the same network. In the app: association code `org-a`, server `http://<laptop-ip>:8000`, users `officer@`, `secmgr@`, `resident@`, `admin@demo-a.example.invalid` with your test password.
> Dev note: with several sites, Frappe picks the site from the Host header. For a phone using an IP, set `bench use org-a.localhost` and `serve_default_site` in `common_site_config.json` (see bootstrap), or browse via a hosts-file name.

## 3. Test plan (tick and report what fails)
| # | Check | Pass when |
|---|---|---|
| 1 | Sign in as officer | Home shows Check In / Check Out / Find Vehicle / Resident Reports / Active Cases |
| 2 | Returning visitor (unit A1 → tap suggestion → Confirm) | **≤ 20 s**; Settings shows typical check-in time |
| 3 | Check out | Select + confirm; visitor disappears |
| 4 | Airplane mode check-in, then reconnect | "Saved offline - Pending Sync", then "Synced" once |
| 5 | Resident (second login): Report a concern, identified | Reference shown; officer queue shows it |
| 6 | Officer: Claim → Take photo → Capture location → drag pin → Verify | Camera and location prompts appear only on tap; accuracy tier shown; pin reason required if moved |
| 7 | Deny location permission | Message + manual pin works |
| 8 | Case: Call → return → outcome → "told them" → clock | Dialer opens; clock starts only for Answered + confirmed |
| 9 | Case: Text → preview → Send | Status says *accepted*, not delivered |
| 10 | Resident cannot see visitors/registry | Only resident screens exist |
| 11 | Small screen / large font / sunlight | Targets ≥ 56 px, readable, no horizontal scroll |
| 12 | Sign out | Offline items wiped; back to sign-in |

Report problems with screenshots that contain **no real personal data**.
