# Ola Dash 1.0 plan

Status: r2 (2026-10-30), after three r1 reviews in `docs/plan/reviews/r1-*.md`. Owner: abhi245y.

## Goal

Make the Ola Dash SDK host a complete dash for the Ola S1 Pro Gen 1 that an owner can install with one command and
extend from the dash: a redesigned look (overlay, lock screen, host screens), a theme pack (multi-dial, terminal,
minimal, AAOS-style card home), quick and safe theme switching, theme options, a settings screen, an app launcher,
a store for themes and plugins, a recovery path, and Android Auto with scooter essentials always on screen.

What 1.0 is not, said plainly so nothing disappoints:
- **Lock**: the scooter's own passcode flow, drawn by the host in the dash's style. No phone-as-key, no remote lock,
  no change to the scooter's lock behaviour.
- **Android Auto**: a separate receiver app (Open Headunit) in front, with the host's dash bar on one edge showing
  speed, battery and telltales. Not AA cards inside a theme, not automatic connection, not guaranteed helmet audio.
  An AA receiver embedded in the host is research (E7.S4).
- **Install**: one command from a laptop on the same Wi-Fi as the scooter, using the head unit's vendor diagnostics
  service. Linux first. The installer arrives in milestone M5, not first.

## Repositories

| Repo | Holds |
|---|---|
| `ola-dash-sdk` | The one host app (Rust + Slint + Java), host screens, safety overlay, contract, sim, `check-themes`, vehicle interface, plugin API, reference themes, developer docs. All host work lands here. |
| `ola-dash` (this repo) | The product: theme pack, installer, recovery watchdog APK, store index and its submission CI, release pipeline, owner docs, this plan. Pins the SDK as a submodule at `sdk/` and builds `sdk/host/build.sh` with the product themes bundled. |
| `ola-can-reference` | CAN catalog. Gets new observations from this work (handlebar buttons, IMU). |
| `ola-dev-skill` | Agent skill. Synced when the contract, theme format, store or installer change. |

D1: the host stays in the SDK because `sim` compiles `host/src/theme_root.rs` and `host/ui/*` (`sim/src/main.rs:36,551,561`); moving it would break `check-themes` and both CI jobs. The SDK can be changed freely for the product; only the safety guarantees below are fixed.

## Fixed safety guarantees

The look of every safety element (telltales, alert cards, lock screen, strip) may be redesigned. What it guarantees may not:

1. The host draws telltales, alerts and the passcode keypad above everything a theme draws. No theme or plugin can hide, cover, fake-drive or weaken them. (Today a theme can, see E0.S2: this is the first fix.)
2. No vehicle command except the gated trunk request. Plugins have a display-only API; their APKs are ordinary Android apps, which the store screens (E6.S1).
3. Unknown data shows as unknown. Stale data is marked stale (E0.S3).
4. Every interactive host screen and every app launch needs `parked` (E0.S4), one gate, defined once.
5. When the scooter leaves `parked`, the host comes back to the front unless the AA receiver is in front, and the dash bar covers that case.
6. With the stock HMI disabled, the host keypad is the only passcode entry on the scooter. A dead host strands the rider, so recovery (E5.S2) blocks any install by people other than the owner.
7. Anything that changes the scooter needs the owner's go-ahead for that session. The dash never signs in to any account. The dash and installer never touch OTA.

## Platform facts the plan depends on

- Slint 1.18.1 on Android has one window; host screens and the overlay live in the interpreted root with the theme. Compiles run with `spin_on` on the UI thread (`host/src/lib.rs:324,329`): the screen freezes while compiling.
- `ComponentInstance::set_property` reaches only root properties; values for the inner `Dash` go through mirrors generated in `theme_root.rs` (`MIRRORS`).
- `VehicleBridge` keeps `REAL[]` per field and can replay it (`VehicleBridge.java:376-381`). `TrunkGate` already holds the park rule with a tri-state lock.
- Android 10: background activity starts are blocked except for apps holding the `SYSTEM_ALERT_WINDOW` appop. Knowing the foreground package needs `PACKAGE_USAGE_STATS`.
- No Back key on the panel (the red button is power/lock). The stock HMI sets `keepScreenOn`; the host does not yet.
- Root is reachable only through the vendor diagnostics service on `[::1]:50005` / link-local IPv6 port 50005, unauthenticated (ola-s1-rea `02`, `13`, `17`). Anyone on the scooter's network has the same power; owner docs must say so.
- The vehicle interface already delivers handlebar D-pad callbacks (`IHandleBarCallbacks.onDpad_*`), IMU data and a brightness level; ride logs show `onDpad_Drive_Mode` presses, and IMU values are logged as object names only.

## Measure first (scooter session A)

Recorded in `ola-dash/docs/measurements.md`. Each row names what it decides.

| Id | What | Decides |
|---|---|---|
| M-compile | Probe + root compile per bundled theme; again after E1 adds host screens | E0.S6 switch mechanism |
| M-start | Cold start to first frame, after a cold reboot | E0.S6, watchdog timeout |
| M-ram | Host PSS per theme, with `hmiclient` disabled | AA fit |
| M-frame | Frame time per theme with mock ride data | E4 theme rules |
| M-replay | Which fields the parser replays on subscribe (is speed 0 known at a cold start in Park?) | E0.S4 reachability |
| M-home | Does `cmd package set-home-activity` work without disabling `hmiclient`, and does the stock HMI stay in the background? | E5.S2 recovery design |
| M-dev | `Sensor.TYPE_LIGHT` present; `date` after cold boot without network; `com.android.packageinstaller` present; HTTPS to GitHub works with the head unit CA store; panel follows `SCREEN_BRIGHTNESS`; SAW background start works | E3.S2, E6, E1.S4 brightness, E2 |
| M-dpad | Which handlebar buttons fire callbacks while parked and riding, and what the stock HMI does with them | E1.S5 |
| M-aa | AA spike numbers (E7.S1), if the owner's phone is there | E7 |

## Milestones

| Milestone | Stories | Scooter |
|---|---|---|
| M1 Safe core | E0.S1-S5, E1.S1 | Session A at the end |
| M2 Hub | E0.S6, E1.S2-S6 | Verification |
| M3 Beyond the dash | E2, E7.S1 spike if not done in A | Session B |
| M4 Theme pack | E3, E4 | Perf check |
| M5 Install and recovery | E5 | Session C: install, crash-loop, restore |
| M6 Store | E6 | Install test |
| AA mode | E7.S2-S3 after the spike and E2.S1 | Ride test |
| Research | E8, any time | No |

## Epics, stories and tasks

`[ ]` open, `[~]` in progress, `[x]` done. Repo in brackets. Each story has acceptance criteria (AC).

### E0 Foundation and safety fixes

**E0.S1 Product repo bootstrap** [ola-dash]
- [ ] T1 SDK submodule at `sdk/`; README (what this repo is, link to SDK docs), CHANGELOG.
- [ ] T2 SDK `host/build.sh`: optional `EXTRA_THEMES=<dir>` copies each theme folder into the APK assets under `themes/`; `MainActivity.copyAssets` already copies assets to `files/`.
- [ ] T3 `tools/build.sh` in ola-dash: builds the SDK host with `themes/` bundled, on `arlp-pc`.
- AC: clean clone + `git submodule update --init` + `tools/build.sh` produces an APK with the product themes listed in `files/themes/`.

**E0.S2 Theme sandbox** [SDK] (critical; blocks E0.S6, E3, E6)
- [ ] T1 Import guard: `Compiler::set_file_loader` on the probe and root compiles serves only the contract and files inside the theme folder; anything else fails the compile, so the loader falls back.
- [ ] T2 The overlay and lock screen read host-private mirrors (`HostState`) of every input they show (indicators, beams, ready, locked, side stand, fault, charging, alert code, clock, battery), written from Rust beside `Vehicle.*`. A theme writing `Vehicle.*` then breaks only its own drawing.
- [ ] T3 The two adversarial themes from the r1 review (`docs/plan/reviews/fixtures/evil1`, `evil2`) become negative tests in `check-themes`: overlay pixels must match the reference with them loaded.
- AC: both fixtures render full telltales, the side-stand card and the keypad in `sim`; a theme importing a host file fails to load and falls back.

**E0.S3 Host hardening** [SDK]
- [ ] T1 Stale data: `HostState.data-stale` set on parser disconnect or binding death, and when no vehicle callback arrived for 5 s while `state == drive`; cleared on resubscribe. The strip shows a host "NO DATA" badge and the dash bar shows `--` for speed. Contract v7 adds `Vehicle.data-stale` so themes can grey out their own speed.
- [ ] T2 `FLAG_KEEP_SCREEN_ON` while `state == drive` or charging.
- [ ] T3 `Trace` logs IMU fields and handlebar events with values, not object names.
- [ ] T4 Upstream: add the D-pad callback evidence and IMU field logging to `ola-can-reference` observations (correlate `0x6AD` with `onDpad_*` from session A logs).
- AC: killing the parser shows NO DATA within 5 s; logs show IMU numbers.

**E0.S4 Parked gate** [SDK]
- [ ] T1 `ParkGate.parked()` = the `TrunkGate` park rule (tri-state BCM unlocked, state `park`, real speed known and 0, not test mode) or (`charging` and unlocked). `TrunkGate.refusal` calls it. One JVM test file covers both.
- [ ] T2 Push `parked` to Rust as a field id for host UI only (not the theme contract). `sim --parked`.
- [ ] T3 When `parked` turns false: host screens close within one frame (state kept); if another app is in front and it is not the AA receiver, the host brings itself to front (needs SAW, `PACKAGE_USAGE_STATS`; until granted, log only).
- AC: JVM test for each input including unknowns (fail closed); M-replay risk recorded.

**E0.S5 Measurement kit** [ola-dash]
- [ ] T1 SDK: one log line each for probe compile, root compile, `create()`, first frame.
- [ ] T2 `tools/measure.sh`: cycles themes via `files/themes/active` + restart, collects timings and PSS; plus the M-dev and M-home checks as a written checklist.
- [ ] T3 Run session A with the owner; write `docs/measurements.md`.
- AC: every M-row except M-aa has a number or a yes/no.

**E0.S6 Theme switching** [SDK] (after session A)
- [ ] T1 Mechanism by M-start vs M-compile: if a restart costs under 0.5 s more than a compile, switch = write `files/themes/active` and restart the activity (re-wires everything, no new code paths). Otherwise in-process swap: `run_event_loop()` + `show()` the new root, drop the old one without `hide()`, re-run `wire()` and `theme_root::bind()`, replay `REAL[]` and the plugin snapshot. A static "Switching" card is shown for one loop tick before compiling.
- [ ] T2 Switch only while `parked`, no alert and unlocked. Re-check the gate after the switch.
- [ ] T3 "Keep this theme? Reverting in 10 s" after every switch.
- [ ] T4 Bad-theme guard in `MainActivity.onCreate` before Slint starts: if the last two starts with theme X never reached "first frame + 10 s", set `default` active and mark X bad.
- AC: switching on the scooter keeps keypad, trunk and media callbacks working; a theme that panics on first frame is reverted within two starts.

### E1 Hub: look, shell, settings, lock

Host screens are host code in `host/ui/`. They read the theme's checked `lock-style` through `LockConfig.style` (D2), so every theme styles them for free.

**E1.S1 Contract v7** [SDK]
- [ ] T1 `Actions.open-apps()`, `Actions.open-themes()` (settings at the Theme pane).
- [ ] T2 `Display` global: `in property <bool> night`; `Vehicle.data-stale` (E0.S3).
- [ ] T3 Theme options: `theme.json` `options` (`color | bool | int | choice`, `choice` is a string) and matching `in property <T> opt-<id>` on `Dash`; the `MIRRORS` generator adds `opt-<id>` on `Host` and binds it into `Dash`; types must map (color to Brush, bool, int to Number, choice to String) or the option is skipped with a log line.
- [ ] T4 `docs/contract.md`, `contract-version` 7, `sim --opt id=value --night`, `check-themes` validates `options`. v6 themes load unchanged.
- [ ] T5 Upstream: sync `ola-dev-skill` (contract, theme template gets one option and night).

**E1.S2 Design language and safety visuals** [SDK]
- [ ] T1 Design pass (concept boards, then tokens) for the new look: strip, telltale glyphs, alert cards, lock screen, host screen components (rail, pane, list row, toggle, slider, button). Sunlight and glove rules: 64 px minimum targets, 4.5:1 text contrast.
- [ ] T2 Implement it in `overlay.slint`, `unlock.slint` and a shared `host/ui/kit.slint`; keep the host minimums (telltale 28 px, alert text 32 px) and colour + icon meaning.
- AC: sim captures of every overlay state in all four placements; reviewers sign off.

**E1.S3 Host shell** [SDK]
- [ ] T1 Screen state in the root: `dash | settings | apps`, drawn between `Dash` and `HostOverlay`, so the lock screen and alerts always cover host screens.
- [ ] T2 Hub button: the strip's own end cell, 64 px or more along the strip, never moves or shrinks a telltale; shown only while `parked`, no alert and unlocked.
- [ ] T3 Close button on every screen; the parked gate closes them too. No Back key.
- AC: from any theme, parked, the owner reaches settings and apps; riding, the hub button is gone and screens close.

**E1.S4 Settings core** [SDK]
- [ ] T1 Rail and pane, rail rows 72 px, at most seven items: Theme, Display, Android Auto, Plugins, Apps, Security, About. This story builds Theme (list, options, switch), Display (night: auto / on / off; brightness if M-dev says the panel follows it; 12/24 h clock) and About (versions, contract, cert digest, logs size and clear). Other panes arrive with their stories.
- [ ] T2 `files/settings.json`, atomic write (temp + rename); a parse failure renames it `.bad` and starts from defaults.
- [ ] T3 First-run card: pick a theme, night mode.
- AC: settings survive a restart; a corrupt file never crashes the host.

**E1.S5 Handlebar buttons** [SDK] (needs M-dpad)
- [ ] T1 Map the buttons that fire into host navigation while a host screen is open (next, previous, select, close); `PlayOrPause` to media while riding if the stock HMI does the same. Read-only: the host never sends a D-pad event.
- AC: settings usable with gloves using only the handlebar buttons.

**E1.S6 Lock screen** [SDK]
- [ ] T1 Lock screen in the new design: clock, battery, charging progress while locked, styled by `lock-style`.
- [ ] T2 Plugins pane: per-slot enable writes `files/plugins/enabled` (replaces `run-as`).
- AC: unchanged passcode behaviour; plugins enabled without adb.

### E2 Beyond the dash

**E2.S1 Dash bar** [SDK] (safety-critical)
- [ ] T1 Overlay window (`TYPE_APPLICATION_OVERLAY`) shown in the host's `onPause`, hidden in `onResume`, held by a foreground service while another app is in front. Speed, battery, indicators, high beam, side stand, fault, ready, NO DATA, back-to-dash. Fed from the same Java state as `pushAlerts`; shares colour constants with the overlay.
- [ ] T2 Critical alerts (fall, tow, side stand, steering lock) expand the bar window to full screen, then bring the activity forward. A vehicle lock brings the host lock screen forward.
- [ ] T3 Height 48 / 64 / 80 px, default 64, speed digits 44 px or more, opaque. Edge is a setting; default bottom, top in AA mode until E7.S1 answers the margin question.
- [ ] T4 Scooter matrix: launched app in front then DRIVE (host returns within 1 s), AA receiver in front, Android settings in front, ride longer than the screen timeout, parser killed, host process killed.
- AC: a foreground app without `SYSTEM_ALERT_WINDOW` cannot cover the bar; only the host holds SAW (installer grants, store refuses APKs that request it).

**E2.S2 App launcher** [SDK]
- [ ] T1 Java lists launchable activities and writes each icon once to `cache/icons/<pkg>.png`; Rust loads the list (label, package, icon path) into a Slint grid: 5 columns, 96 px icons, 24 px labels, dock of favourites. Rescan when the launcher opens.
- [ ] T2 Hidden by default: `com.olaelectric.*`, `com.ola.*`, Android Settings, the dash, the watchdog. "Show system apps" in the Apps pane.
- [ ] T3 Launch only while parked, including the AA receiver; `Actions.open-android-auto()` gets the same gate. Android settings: parked only.
- AC: 40 apps scroll smoothly; launching while not parked is refused with a host message.

### E3 Theme system v2

**E3.S1 Options and night in settings** [SDK]
- [ ] T1 Theme pane renders controls from `options`; values per theme in `settings.json`; applied live without recompiling.
- [ ] T2 Night mode: light sensor if present (M-dev), else clock with editable times, else manual; `auto` falls back to manual when the clock is implausible. Night is optional per theme: absent means the day look.
- AC: changing an option or night updates the theme with no recompile.

**E3.S2 Theme list and previews** [SDK]
- [ ] T1 Theme pane shows `preview.png` (riding state with the overlay, rendered by `sim`); placeholder when missing. Rescans `files/themes/` when opened; locally pushed themes get a "sideloaded" badge.

### E4 Theme pack [ola-dash]

Every theme: concept board, implementation, `sim` captures (riding, parked, charging, locked, alert), `lock-style`, overlay settings, `preview.png`, `check-themes` pass, under 2 MB, M-frame check on the scooter. Dials and needles are drawn with paths and `sin`/`cos`, never `transform-rotation`. At most three `animation-tick()` bindings. Contract data only: no theme depends on a plugin.

- [ ] E4.S1 **Twin dial**: analog speedometer, power/regen dial (`current-a` x `voltage-v`), small battery and temperature dials. Options: accent, needle style, digital speed overlay, power bar instead of dial.
- [ ] E4.S2 **Terminal**: monospace on black, readout lines that change only when values change, ASCII bar gauges, one blinking cursor. Options: green, amber, white; scanlines.
- [ ] E4.S3 **Zen**: speed and battery only, very large type, for sunlight.
- [ ] E4.S4 **Cockpit**: AAOS-style card home (navigation card from `Navigation`, media card, vehicle card, plugin widgets). After E8.
- [ ] E4.S5 Default theme refresh to the new design language [SDK].

### E5 Release, recovery, installer [ola-dash unless noted]

**E5.S1 Release build and pipeline**
- [ ] T1 [SDK] `host/build.sh --release`: `debuggable` off (the test channel is gated on it), keystore from env, versionCode from the git tag; the script checks the flag with `aapt2 dump badging`, runs `apksigner verify` and prints the cert SHA-256.
- [ ] T2 GitHub Actions in ola-dash: on tag, build the release APK, publish APK + SHA256SUMS + cert digest (the skill's release pattern).

**E5.S2 Recovery** (blocks installs by anyone but the owner)
- [ ] T1 From M-home: if the host can be home without disabling `hmiclient`, the installer never disables it, and uninstalling the host restores stock by itself.
- [ ] T2 Watchdog APK `ola-dash-watchdog`: own process and signing, `BOOT_COMPLETED` and an explicit request from the host; acts only through `[::1]:50005`; fails closed and logs if the service or root is not there.
- [ ] T3 Host heartbeat written by a `slint::Timer` on the UI thread every 5 s (`elapsedRealtime`), so a hung event loop stops it. Failure = display interactive and no heartbeat for M-start x 3, or 3 abnormal exits in 10 min (no clean-exit marker and a new pid; activity recreation is not a crash). Restore = exactly `hmi-swap.sh stock`.
- [ ] T4 Manual restore: `installer restore`, and one typeable line shown on the host's last-resort screen and in the owner docs (works from the ola-s1-rea phone app).
- [ ] T5 [SDK] `docs/safety.md`: stranded-rider consequence, unauthenticated vendor root service, plugins are ordinary apps.
- AC: a deliberately crash-looping build restores the stock HMI on the scooter without a laptop; normal sleep and wake never trigger it.

**E5.S3 Installer core**
- [ ] T1 Python 3 + `grpcio`, Linux first. Scooter discovery over link-local IPv6 (ping `ff02::1`, neighbour table), reusing the ola-s1-rea client code.
- [ ] T2 Preflight: `id -u` = 0 over the service, build fingerprint in the known-good list, free space, OTA package state reported (never changed), owner confirms the scooter is parked and charged.
- [ ] T3 Backup: package states, current home, appops it will change.

**E5.S4 Installer commands**
- [ ] T1 `install`: push APKs in chunks, install host and watchdog, grant notification listener, `SYSTEM_ALERT_WINDOW`, `PACKAGE_USAGE_STATS`, `REQUEST_INSTALL_PACKAGES`, `WRITE_SETTINGS` (if M-dev needs it), set home, wait for the heartbeat.
- [ ] T2 `uninstall` and `restore` replay the backup; `status` prints versions, home, grants, OTA state. Every step idempotent.
- [ ] T3 `push-theme <dir>`: validate locally with `check-themes`, push into `files/themes/<id>/`, chown to the app uid. The mod-author loop after the release flavor.
- AC: fresh MoveOS 5 scooter on the same Wi-Fi as the laptop, no prior tooling, to a working dash in one command, and back to stock in one.

### E6 Store

**E6.S1 Format, index, submission CI** [ola-dash]
- [ ] T1 Theme package: zip of the theme folder, only `.slint .json .png .svg .ttf .otf .txt`, 2 MB inflated, 200 files, images up to 2048 x 2048, `preview.png` required; ids `default`, `fallback`, `last-resort` reserved.
- [ ] T2 `store/index.json` in this repo: `seq`, entries with URL (release asset), size, SHA-256; plugins add package, versionCode, signing cert SHA-256, slots, permissions.
- [ ] T3 CI on submissions: unpack caps, `check-themes` (with the sandbox negative tests), `sim` previews, `animation-tick` count. Plugin APKs: `aapt2 dump permissions`; reject `SYSTEM_ALERT_WINDOW`, `BIND_ACCESSIBILITY_SERVICE`, `BIND_DEVICE_ADMIN`, `BIND_NOTIFICATION_LISTENER_SERVICE`, `REQUEST_INSTALL_PACKAGES`, `PACKAGE_USAGE_STATS`, HOME activities, and dex or manifest references to `com.olaelectric.vehicleparser`, `com.olaelectric.vehicleinterface`, `ICommanderService`.
- [ ] T4 Store rules for reviewers: no passcode or PIN entry UI in themes; check that the numbers on sim captures match the mock values.

**E6.S2 Store client: browse** [SDK]
- [ ] T1 Fetch `index.json` over HTTPS from GitHub (Java); TLS failure is an error, never a fallback to http. Refuse a `seq` lower than the last accepted. List with previews, parked only.

**E6.S3 Store client: themes** [SDK]
- [ ] T1 Download, SHA-256 check, safe unzip counting inflated bytes (no absolute paths, no `..`, no symlinks, caps from E6.S1), probe compile (parked, with the "Switching"-style static card), then move into `files/themes/<id>/`. Update and uninstall. A theme that fails is never activated.

**E6.S4 Store client: plugins and host update** [SDK]
- [ ] T1 Verify APK hash and signing cert against the index, then a `PackageInstaller` session (Android shows its confirmation); open the Plugins pane after install; uninstall via `ACTION_DELETE`.
- [ ] T2 Host self-update the same way (same signer, Android refuses downgrades); the watchdog treats that restart as clean.
- AC: a theme and a plugin installed, updated and removed on the scooter without a laptop.

### E7 Android Auto

**E7.S1 Spike** (owner, phone and scooter together, parked; go/no-go)
- [ ] T1 Confirm the receiver's package id (host constant `com.andrerinas.headunitrevived`, project renamed Open Headunit); pin a release and checksum.
- [ ] T2 Measure connect route (Headunit Server on shared Wi-Fi first), time to video, latency, decoder, host + receiver RAM, audio route, touch, return to the dash.
- [ ] T3 Can the receiver use a video resolution or margin that leaves room for the dash bar? Does it expose navigation state to other apps?
- AC: `docs/aa-spike.md` with go/no-go.

**E7.S2 AA mode** (if go) [SDK]
- [ ] T1 Android Auto pane: receiver package, return to dash on disconnect, optional auto-launch on phone connect (parked only).
- [ ] T2 The receiver is the one app allowed to stay in front when `parked` turns false; dash bar on the free edge.
- AC: ride test with AA navigation: speed and telltales always visible, alerts escalate.

**E7.S3 Navigation to the dash**: only if E7.S1.T3 finds an interface; a plugin feeds `Navigation`.

**E7.S4 Embedded receiver** (research): licence check (AGPL-3.0 code in a GPL-3.0 host), effort to render decoded video under the Slint window, RAM from M-aa. Build only if E7.S2's limits are unacceptable.

### E8 Android Automotive exploration (research, timeboxed)

- [ ] T1 Which AAOS pieces and patterns (CarLauncher layout, media centre, Car UI library styles, Car App Library templates) can run app-level on Android 10 without car service or system privileges, and which can only be borrowed as design.
- [ ] T2 `docs/aaos-notes.md`; feeds E4.S4 and E2.S2.

## Backlog

- Owner PIN for settings and a "lock word" shown only on real host keypads (pending the owner's answer).
- Signed store index with two keys and expiry, when a mirror or second maintainer appears.
- Frame-time guard that reverts a theme which is too slow on the device.
- Theme sideload from a phone over the local network.
- macOS and Windows installer.
- Auto theme rules (per drive mode, while charging), miles, CarPlay, Gen 2.

## How the work runs

1. One story at a time in milestone order, on a branch `e<epic>-s<story>-<slug>` in the repo the story names.
2. An implementer agent writes the code from the story, builds on `arlp-pc` in `~/Documents/ola-dash-<slug>` (deleted after), and runs the checks (`check-themes`, `sim` captures, JVM tests, `cargo test`).
3. Two reviews of the diff: a Fable reviewer that gets the story and the diff, and the lead agent. Checks: correctness, the safety guarantees, slop (dead code, needless abstraction, comments that restate code), style match. The implementer fixes; repeat until both approve.
4. Scooter steps go into session checklists; nothing touches the scooter without the owner's go-ahead.
5. Merge to `main` locally; push only when the owner asks. Commits carry no co-author or tool attribution lines.
6. Close tasks here (`[x]`) and add decisions below. Each story notes its upstream follow-ups (SDK docs, CAN reference, skill).

## Decision log

- D1 (2026-10-30): host stays in the SDK; `ola-dash` holds the product parts and pins the SDK (r1 scope review 1).
- D2 (2026-10-30): host screens styled from `lock-style` via `LockConfig.style`; no new style struct.
- D3 (2026-10-30): theme options are `opt-<id>` `Dash` properties mirrored through `Host`; no options global.
- D4 (2026-10-30): AA in 1.0 is the separate receiver plus the host dash bar; embedded receiver is research.
- D5 (2026-10-30): the safety visuals may be redesigned (owner); the guarantees above may not.
- D6 (2026-10-30): store index unsigned in 1.0: HTTPS from GitHub + SHA-256 + plugin cert pins + monotonic `seq`. The installer already trusts the same account.
- D7 (2026-10-30): installer uses the vendor diagnostics service, not root adb.
- D8 (2026-10-30): launcher is a host Slint screen (owner asked for a designed launcher), with Java only listing apps and writing icon files.
