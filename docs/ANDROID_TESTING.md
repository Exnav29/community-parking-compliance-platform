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
| 0 | **Officer sign-in, before starting a shift** | Home shows ONLY **Start shift** (and Settings). No Check In, no lookups, no cases until a shift is started |
| 0b | Start shift, choose a gate | Home shows Check In / Check Out / Find Vehicle / Resident Reports / My assigned cases; header says *on duty*; a notice says lookups are recorded |
| 1 | (after 0b) Home actions | As above; Settings shows the gate you are on, not a gate picker |
| 2 | Returning visitor: type unit **A1**, type 2-3 letters of the plate you can see, tap the suggestion, Confirm | **<= 20 s**; at most 3 suggestions; **no names, phone numbers or dates shown**; Settings shows typical check-in time |
| 2b | Unit lookup with the plate-hint box left empty, repeated more than 10 times in an hour | Later lookups are refused (hourly ceiling); a reviewer sees a signal in the Access Review |
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

## v1.8 privacy checks (phone + a second supervisor login)
| # | Check | Pass when |
|---|---|---|
| P1 | Officer with no shift tries Check In / Find Vehicle (end the shift in Settings, or use a second phone) | Nothing opens; no resident data appears |
| P2 | Supervisor revokes the officer's device (or ends the shift) while the officer's screen is still open | The officer's next lookup fails at once |
| P3 | Airplane mode: save a check-in, then inspect phone storage/backup | Only plate, unit label and times of that one action; no names, phones or lists. Unsent items vanish after 72 hours and on sign-out |
| P4 | Officer opens **My assigned cases**; supervisor reassigns the case to someone else | The case disappears for the first officer; contacts can no longer be opened |
| P5 | Sign in as a **resident** | No staff screens, no lookups, no visitor list; community summary shows only large counts |
| P6 | Lock-screen notifications | No plate, unit, phone or name appears |
