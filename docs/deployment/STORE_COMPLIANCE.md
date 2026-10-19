# App-store compliance matrix (Apple App Store, Google Play, Samsung Galaxy Store)

**Status: preparation only.** Nothing has been submitted, nothing is signed with release keys, and no developer accounts are used. Rules change; each row must be re-checked against the current official policy on the day of any submission (links in PRD sections 25.4 and 27). "Implemented" means present in code; "Verified" means exercised on a real device (none yet).

| Requirement | Apple | Google Play | Samsung | Where / status |
|---|---|---|---|---|
| Real native functionality, not a website wrapper | 4.2 | Minimum functionality | Quality | Native camera, one-shot foreground GPS, keystore storage, offline drafts, dialer hand-off. **Implemented, not device-verified** |
| Contextual permissions, minimal scope | Purpose strings | Runtime permissions | Same as Android | iOS `Info.plist`: camera, when-in-use location (strings written; photo library explicitly "not used"). Android: camera + fine/coarse location (foreground only) from Capacitor plugins; **no background location, contacts, SMS or call-log permissions**. Implemented |
| No restricted SMS/call-log permissions | n/a | Restricted permissions | Same | Calls use the dial intent; SMS is sent server-side. Implemented |
| Privacy policy URL, in-app link | Required | Required | Required | **Blocked**: needs the legal entity, text and hosting (owner decision) |
| Privacy nutrition label / Data safety / Samsung declarations | Required | Required | Required | Draft data inventory below. **Pending** owner approval and SDK review |
| Account deletion in app (and on web for Google) | 5.1.1(v) | Required | Required | **Not implemented.** Needs design with retention/legal-hold rules (PRD 25.3, AC-32) |
| Reviewer demo access | Demo accounts | Test credentials | Test credentials | Synthetic demo organization and roles exist (`seed.sh`). **Reviewer packaging pending** |
| Payments inside the app | 3.1.x | Payments policy | Same | None: no in-app purchase/checkout; enforcement payment disabled by legal gate; B2B subscription via web contract. Implemented (by absence) |
| Target SDK / API level | current Xcode SDK | current target API | follows Android | Capacitor 8 defaults at build time; **re-check on submission day** |
| Signed release builds | Distribution profile | Play App Signing | Samsung signing | CI makes **unsigned debug APK only**. Release signing keys are not in the repo and need a protected pipeline (owner/accounts) |
| Crash/diagnostics without personal data | Privacy manifest | Data safety | Same | No analytics or crash SDK included. Implemented |
| Accessibility basics | HIG | Accessibility | Same | Large targets, labels, text plus icon, no colour-only status. **Not audited** with TalkBack/VoiceOver |
| iOS archive / TestFlight | Required | n/a | n/a | **Blocked**: needs macOS + Apple Developer account |

## Draft data inventory (for the store declarations; pending approval)
| Data | Collected | Purpose | Shared | Optional |
|---|---|---|---|---|
| Email/account id | Yes (staff, residents) | Sign-in | No third parties | No |
| Approximate/precise location | Only when the user taps Capture location | Document a parking report | No | Yes |
| Photos | Only when the user takes one | Evidence / report | No | Yes |
| Plate numbers, unit labels | Yes | Gate and incident operations | No | No |
| Phone numbers | Server-side only; masked on device | Contact responsible party | SMS provider (mock until approved) | No |
| Crash/usage analytics | **None** | - | - | - |
| Device identifier | Pseudonymous hash for shift binding | Revocation | No | No |

Retention and deletion rules: see `docs/security/PRIVACY_PBAC.md` (journal) and PRD sections 15 and 24.6; the Ghana Data Protection Act review is an open legal item.
