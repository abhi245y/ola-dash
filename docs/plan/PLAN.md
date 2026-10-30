# Ola Dash 1.0 plan

Status: draft r1 (2026-10-30). Owner: abhi245y. Reviews: see `docs/plan/reviews/`.

## Goal

Turn the Ola Dash SDK host into a complete dash app for the Ola S1 Pro Gen 1 that any owner can install and extend:
a redesigned theme pack (dials, minimal, terminal, AAOS-style card home), seamless theme switching, theme
customisation, a host-owned settings screen, an app launcher, a polished lock screen, an on-dash store for themes
and plugins, a one-command installer with a recovery path, and Android Auto that keeps essential scooter information
on screen.

## Repositories

| Repo | Holds | Status |
|---|---|---|
| `ola-dash` (this repo, new) | The product: Android host app, host screens (settings, launcher, store, switcher, dash bar), product theme pack, store client, installer, recovery watchdog. | New |
| `ola-dash-sdk` | The developer kit: theme contract, sim, `check-themes`, vehicle interface, plugin API, reference themes, docs. | Existing, public |
| `ola-dash-store` (new, later) | Signed store index and CI that validates submissions. | E4 |

Decision D1: `ola-dash` consumes `ola-dash-sdk` as a git submodule at `sdk/`, pinned to a commit. The host source
(`host/`) moves from the SDK into this repo at SDK commit `b453daf` (provenance recorded in the import commit). The
SDK keeps its host until this repo reaches parity on hardware (milestone M1 verified on the scooter); then the SDK's
`host/` is replaced by a pointer to this repo. Contract changes are made in the SDK first, then the submodule is bumped.

## Fixed constraints (not up for redesign)

1. Safety model from `ola-dash-sdk/docs/safety.md` stays: the host owns telltales, alerts and the lock keypad; themes
   style but never hide them; no vehicle command except the gated trunk request; plugins are display-only; no unlock
   bypass. "Proper lock" means lock-screen UX and an optional owner PIN for dash settings, never a vehicle lock command.
2. One stopped/parked gate, defined once in Java and mirrored to Rust, decides every interactive host screen.
3. Hardware is small: SDM450, 8x A53, Adreno 506, 2.78 GiB RAM with about 0.78 GiB available at the one sample,
   Android 10, 1280x768. Every performance claim in this plan is a measurement task, not an assumption.
4. Licensing: GPL-3.0-or-later (Slint). Open Headunit is AGPL-3.0; combining is allowed by GPLv3 section 13 but no
   code is ported before a licence check (E6.S4). No Ola Electric logos, artwork, fonts or colours.
5. Builds run on `arlp-pc` in `~/Documents/ola-dash-<feature>`, one folder per feature, deleted when done. Ask before
   installing anything there. `/tmp` on the laptop is RAM-backed: large files go in the project `tmp/`.
6. Anything that changes the scooter (install, home swap, appops, reboot) needs the owner's go-ahead for that session.
   No PSN-style account flows: the dash never signs in to Ola or Google services.

## Measure first

These numbers decide designs. They are collected in E0.S4 and recorded in `docs/measurements.md`.

| Id | What | Decides | Threshold |
|---|---|---|---|
| M-compile | Probe + root compile time per bundled theme on the SDM450 | Hot-swap design (E0.S5), whether host screens live in the interpreted root | Switch feels instant under 300 ms; 300 ms to 1.5 s needs a host transition card; above 1.5 s, host screens move to a separate, compile-once layer |
| M-ram | Host PSS per theme, idle and riding | Whether host + AA receiver fit together | Host under 150 MB PSS |
| M-frame | Frame time with mock ride data per theme (GL renderer) | Theme pack rules (animation, dial counts) | 60 fps target, 30 fps floor |
| M-start | Cold start to first frame | Recovery watchdog timeout | Measured value x 3 |
| M-aa | AA receiver connect time, decode latency, RAM with host alive | E6 go/no-go | See E6.S1 |

## Milestones

| Milestone | Contents | Needs scooter |
|---|---|---|
| M0 Plan | This document, reviewed | No |
| M1 Hub skeleton | E0, E1.S1-S4, E2.S3 | Measurement and verification sessions |
| M2 Safe beyond the dash | E1.S5 dash bar, E5.S1 recovery watchdog | Yes |
| M3 Theme pack | E2.S1-S2, E3 | Perf check only |
| M4 Store | E4 | Install test |
| M5 Installer | E5.S2-S4 | Yes, full install and rollback |
| AA track | E6, starts with the spike whenever the owner, phone and scooter are together | Yes |
| Research | E7, any time | No |

## Epics, stories and tasks

Format: `[ ]` open, `[~]` in progress, `[x]` done. Each story lists acceptance criteria (AC).

### E0 Foundation

**E0.S1 Repo bootstrap**
- [ ] T1 Add `ola-dash-sdk` as submodule at `sdk/`, pinned to `b453daf`.
- [ ] T2 Import `host/` from the SDK at `b453daf`; point `host/build.sh` at `sdk/contract`, `sdk/sdk/vehicle-interface`, `sdk/sdk/plugin-api`, `sdk/themes/default`.
- [ ] T3 README, CONTRIBUTING (short), CHANGELOG, `docs/` skeleton linking to SDK docs instead of copying them.
- [ ] T4 Build on `arlp-pc` from a clean clone; debug APK identical in behaviour to the SDK build.
- AC: clean clone + `git submodule update --init` + `host/build.sh` produces an APK; `sdk/tools/check-themes.sh` passes.

**E0.S2 Release flavor** (from SDK roadmap "Next")
- [ ] T1 `host/build.sh --release`: manifest with `android:debuggable="false"`, release keystore outside the repo (path from env), versionCode from git tag.
- [ ] T2 The test channel is already gated on `FLAG_DEBUGGABLE`; add a check that the release APK has the flag off (`aapt2 dump badging`) in the build script.
- [ ] T3 `apksigner verify` and print the signing cert SHA-256 (needed by E4 and E5).
- AC: release APK installs over nothing, has no test receiver, and its cert digest is printed.

**E0.S3 Parked gate**
- [ ] T1 `ParkGate.java` (pure, JVM-tested like `TrunkGate`): `parked = !locked && state in {park, charging} && speed known && speed < 1 km/h`, all from real (non-test) callbacks.
- [ ] T2 Push `parked` to Rust as a field id; expose to host UI only (not the theme contract).
- [ ] T3 Rule: when `parked` turns false, every interactive host screen closes back to the dash within one frame; screen state is kept for when it reopens.
- AC: JVM test covers each input; sim flag `--parked` toggles it.

**E0.S4 Measurements** (needs scooter session)
- [ ] T1 Timing logs around probe compile, root compile, `create()`, first frame (`OlaDash` tag, one line each).
- [ ] T2 `tools/measure.sh`: installs, cycles themes via `files/themes/active` + restart, collects logcat timings and `dumpsys meminfo` PSS, writes `docs/measurements.md`.
- [ ] T3 Frame-time sample with mock ride data (debug test channel) per theme.
- AC: every "Measure first" row except M-aa has a number.

**E0.S5 Theme hot-swap**
- [ ] T1 Keep the latest value of every field in Rust (`LAST` table) so a new root can be filled immediately.
- [ ] T2 `switch_theme(id)`: build the new root, re-apply `LAST`, plugins and overlay config, show it, then drop the old root. On compile failure keep the current theme and report the error to the host UI.
- [ ] T3 If M-compile is over 300 ms: show a host transition card during the switch. If over 1.5 s: redesign (record in D-log) before continuing.
- [ ] T4 Persist the choice to `files/themes/active` only after the new root is shown.
- AC: switching between bundled themes on the scooter needs no restart, telltales never disappear during the switch, a broken theme cannot replace a working one.

### E1 Host shell, settings, launcher, lock

Host screens are host code in `host/ui/`, like the overlay and keypad. They are styled from the active theme's
`lock-style` tokens (contract v6), with the host contrast checks and host fallback colours. No new style struct.

**E1.S1 Host shell**
- [ ] T1 Screen state in the host root: `dash | apps | settings | store | switcher`. The overlay stays above all of them.
- [ ] T2 Entry points: existing `Actions.open-settings()`; new `Actions.open-apps()` and `Actions.open-theme-switcher()` (contract v7, additive). A host-owned hub button in the telltale strip, visible only while parked, so every theme has a way in.
- [ ] T3 Back/close: hardware back, a close button, and the parked gate (E0.S3).
- AC: from any theme, parked, the owner can reach settings, apps and the switcher; riding, none of them open.

**E1.S2 Contract v7 (in the SDK)**
- [ ] T1 `Actions.open-apps()`, `Actions.open-theme-switcher()`.
- [ ] T2 `Display` global: `in property <bool> night` (host decides from clock or owner setting).
- [ ] T3 Theme options as optional `Dash` `in` properties named `opt-<id>` (see E2.S1), declared in `theme.json`.
- [ ] T4 Update `docs/contract.md`, bump `contract-version` to 7, sim support, reference themes unchanged (v6 still loads).
- AC: v6 themes load unchanged on a v7 host; `check-themes` validates v7 manifests.

**E1.S3 Settings screen**
- [ ] T1 Sections: Theme (picker, options), Display (night mode: auto by clock / on / off; brightness via `WRITE_SETTINGS`), Clock (12/24 h), Plugins (per-slot enable, writes `files/plugins/enabled`), Apps (dock favourites, hidden apps), Android Auto (receiver package, auto-return), Security (owner PIN), Logs (size, clear), About (versions, contract, cert digest, licences).
- [ ] T2 Settings persisted in one `files/settings.json`, written atomically (temp + rename).
- [ ] T3 "Open Android settings" behind the owner PIN when one is set.
- AC: every setting survives a restart; plugins can be enabled without adb.

**E1.S4 App launcher**
- [ ] T1 Java lists launchable activities, renders each icon once to a 96 px PNG in `cache/icons/`, sends a JSON list to Rust.
- [ ] T2 Grid + dock of favourites; long-press to pin or hide. Refresh on package add/remove.
- [ ] T3 Launch only while parked. The AA receiver is the one exception (E6). Return path: HOME brings the host back (it is the home app).
- AC: 40 apps scroll smoothly; icon cache under 2 MB; launching while not parked is refused with a host message.

**E1.S5 Dash bar** (safety-critical)
- [ ] T1 When another app is in front, the host shows an overlay window (`TYPE_APPLICATION_OVERLAY`, needs `SYSTEM_ALERT_WINDOW` appop) on one screen edge: speed, battery, indicators, high beam, side stand, fault, ready, and a back-to-dash button. Plain Android Views in Java, not Slint.
- [ ] T2 Critical alerts (fall, tow, side stand, steering lock) bring the host activity to the front.
- [ ] T3 Edge and size are a setting; default bottom, 48 px.
- [ ] T4 Test matrix on the scooter: launcher app in front, AA receiver in front, screen off/on, host process restart.
- AC: with any app in front, speed and telltales are visible and alerts escalate; the bar can not be dismissed by the foreground app.

**E1.S6 Lock and owner PIN**
- [ ] T1 Lock screen polish: clock, battery, charging progress while locked, now-playing (read-only) on the host lock screen, styled by `lock-style`.
- [ ] T2 Optional owner PIN for settings, store, hidden apps and Android settings. PBKDF2 hash in `files/`, 5 attempts then 60 s cooldown. Separate from the scooter passcode; never sent anywhere.
- [ ] T3 Forgotten PIN: reset only from the installer (adb), never from the dash.
- AC: the scooter's own passcode flow is unchanged; owner PIN cannot be brute-forced from the screen faster than the cooldown allows.

### E2 Theme system v2

**E2.S1 Theme options**
- [ ] T1 `theme.json` `options`: `{id, label, type: color|bool|choice|int, default, choices?, min?, max?}`. Max 12 options.
- [ ] T2 Host validates each option against the `opt-<id>` property the probe compile finds (type must match) and sets it on the theme's `Dash`. Unknown or mismatched options are ignored with a log line.
- [ ] T3 Settings renders controls from the schema; values stored per theme in `settings.json`; live preview.
- [ ] T4 SDK: JSON schema for `theme.json` v2, `check-themes` validates it, `sim --opt id=value`.
- AC: changing an option updates the running theme without a recompile.

**E2.S2 Night mode**
- [ ] T1 Host sets `Display.night` from the setting (auto by clock with fixed sunset/sunrise times the owner can edit; or on; or off).
- [ ] T2 Themes in E3 support both.
- AC: switching day/night needs no recompile.

**E2.S3 Theme switcher**
- [ ] T1 Carousel of installed themes with `preview.png` (rendered by `sim` in CI; placeholder card when missing).
- [ ] T2 Tap applies via hot-swap (E0.S5); failure keeps the current theme and shows why.
- AC: switching from the carousel takes under the M-compile budget and never shows a broken screen.

### E3 Theme pack

Every theme: design concept first, then implementation, `sim` captures for riding / parked / charging / locked /
alert states, `lock-style`, overlay settings, options where useful, day and night, `check-themes` pass, under 2 MB,
and an on-device frame-time check (M-frame). Needles and dial ticks are drawn with paths and `sin`/`cos`, never
`transform-rotation` (ignored by the sim renderer). Few `animation-tick()` bindings.

- [ ] E3.S1 **Twin dial**: analog speedometer plus a power/regen dial (from `current-a` x `voltage-v`) and small battery and temperature dials. Options: accent colour, needle style, show power dial.
- [ ] E3.S2 **Sport**: very large digital speed, power bar, trip peak speed and average, mode-coloured accent.
- [ ] E3.S3 **Terminal**: monospace green or amber on black, live readout lines that change only when values change, ASCII bar gauges, blinking cursor (one tick binding). Options: colour (green, amber, white), scanlines on/off.
- [ ] E3.S4 **Cockpit** (AAOS-style card home): navigation card, media card, vehicle card (battery, range, temps), plugin widgets, app dock. Feeds from E7 research.
- [ ] E3.S5 **Zen**: minimal, speed and battery only, large type, ideal for sunlight.
- [ ] E3.S6 Refresh the default theme to the new craft bar (keeps its role as the fallback; stays in the SDK).
- AC per theme: all captures in `docs/img/themes/`, perf within M-frame, reviewer sign-off.

### E4 Store and mods

**E4.S1 Mod format**
- [ ] T1 Theme package: zip of the theme folder (`theme.json` v2, `.slint`, `.png`, `.svg`, `.ttf`, `.otf`, `.txt`, `.json` only), 2 MB unpacked cap, 200 files cap, `preview.png` required.
- [ ] T2 Plugin entry: package, versionCode, APK SHA-256, signing cert SHA-256, slots, one-line permission summary.

**E4.S2 Store index repo (`ola-dash-store`)**
- [ ] T1 `index.json` listing themes and plugins with URLs (GitHub release assets), sizes and SHA-256.
- [ ] T2 Ed25519 detached signature `index.json.sig`, signed offline by the maintainer with `tools/sign-index`; public key compiled into the host.
- [ ] T3 CI on submissions: unpack checks, `check-themes`, `sim` previews, size caps, hashes. CI never holds the signing key.
- AC: a tampered index or artifact is rejected by the host.

**E4.S3 Store client**
- [ ] T1 Fetch index over HTTPS (Java), verify signature (Rust, `ed25519-dalek`, since Android 10 has no Ed25519 in JCA), list with previews.
- [ ] T2 Theme install: download, SHA-256 check, safe unzip (no absolute paths, no `..`, no symlinks, caps from E4.S1), probe compile, then move into `files/themes/<id>/`. Update and uninstall. A theme that fails to compile is never activated.
- [ ] T3 Parked only; works on Wi-Fi; resumable is not required.
- AC: install, update, uninstall of a theme on the scooter without adb.

**E4.S4 Plugin install**
- [ ] T1 Verify downloaded APK hash and signing cert against the index before installing.
- [ ] T2 `PackageInstaller` session (the installer grants `REQUEST_INSTALL_PACKAGES`); Android shows its own confirmation.
- [ ] T3 After install, open the plugin's slot enable screen (E1.S3). Uninstall via `ACTION_DELETE`.
- AC: plugin installed and enabled from the dash in under a minute.

**E4.S5 Mod developer experience**
- [ ] T1 `sdk/tools/new-theme.sh <id>` copies a template theme with options and lock style.
- [ ] T2 Docs: submitting to the store; sync the `ola-dev-skill`.

### E5 Installer, updates, recovery

**E5.S1 Recovery watchdog** (blocking: no end-user install before this is done)
- [ ] T1 Read `ola-s1-rea/docs/14-gen1-boot-helper.md` and `17-gen1-root-helper.md`; decide where a root-side boot check can live.
- [ ] T2 Host writes a heartbeat file every 5 s once the first frame is drawn.
- [ ] T3 Root-side check after boot: no heartbeat within M-start x 3, or three crashes within 10 minutes, re-enables `com.olaelectric.hmiclient` and makes it home again. Logged.
- [ ] T4 Manual restore: `installer restore` and a documented adb one-liner.
- AC: a deliberately crash-looping host build restores the stock HMI on the scooter without a laptop.

**E5.S2 Installer**
- [ ] T1 One Python script (stdlib only + adb on PATH), Linux, macOS, Windows. Commands: `install`, `update`, `restore`, `uninstall`, `status`.
- [ ] T2 Preflight: device model and build fingerprint known-good list, free space, root adb present, battery above 30 %, scooter parked.
- [ ] T3 Backup: package states, current home, appops, settings touched.
- [ ] T4 Install APK, grant notification listener, `SYSTEM_ALERT_WINDOW`, `REQUEST_INSTALL_PACKAGES`, `WRITE_SETTINGS`, install the watchdog, swap home, wait for heartbeat, print result.
- [ ] T5 `uninstall` restores exactly what the backup recorded. Every step idempotent.
- AC: fresh scooter (rooted per ola-s1-rea) to working dash in one command, and back to stock in one command.

**E5.S3 Self-update**
- [ ] T1 Host APK listed in the store index; same signing key; update through `PackageInstaller`, parked only.

**E5.S4 Release pipeline**
- [ ] T1 GitHub Actions builds release APK on tag with the key from a secret, publishes APK + SHA-256 + cert digest.

### E6 Android Auto

**E6.S1 Spike** (owner, phone and scooter together, parked; go/no-go)
- [ ] T1 Confirm the current receiver package id (the host constant is `com.andrerinas.headunitrevived`; the project was renamed to Open Headunit) and pin an exact release and checksum.
- [ ] T2 Measure: connect route (Headunit Server over shared Wi-Fi first), time to video, latency, decoder, host + receiver RAM (M-aa), audio route, touch accuracy, return to the dash.
- [ ] T3 Check whether the receiver can reserve a screen margin (so the dash bar does not cover projected UI) and whether it exposes navigation state to other apps.
- AC: written go/no-go in `docs/aa-spike.md`.

**E6.S2 AA mode** (if go)
- [ ] T1 Launch the receiver from the dash and launcher; it is the one app allowed to stay in front while riding.
- [ ] T2 Dash bar (E1.S5) on the edge the receiver leaves free.
- [ ] T3 Return to the dash when the phone disconnects; optional auto-launch when the phone connects.
- AC: ride test with AA navigation: speed and telltales always visible, alerts escalate.

**E6.S3 Navigation to the dash**
- [ ] T1 Only if E6.S1.T3 finds an interface: feed turn-by-turn into the `Navigation` global through a plugin.

**E6.S4 Embedded receiver** (research, go/no-go only)
- [ ] T1 Licence check (AGPL-3.0 into GPL-3.0 combined work), effort estimate for rendering decoded video under the Slint NativeActivity window, and RAM from M-aa. Build only if E6.S2's limits are unacceptable.

### E7 Android Automotive exploration (research, timeboxed)

- [ ] T1 List AAOS components and patterns (CarLauncher layout, media centre, Car UI library styles, Car App Library templates) and whether each can run app-level on Android 10 without car service or system privileges.
- [ ] T2 Output: `docs/aaos-notes.md` with what to borrow as design (feeds E3.S4 and E1.S4) and what is out of reach.

## Backlog (not in 1.0)

- Theme sideload from a phone over the local network.
- Auto theme rules (per drive mode, while charging).
- Miles as a unit.
- CarPlay receiver.
- Gen 2 support.

## How the work runs

1. One story at a time, in milestone order. Each story gets a branch `e<epic>-s<story>-<slug>`.
2. An implementer agent writes the code from the story text, builds on `arlp-pc` in `~/Documents/ola-dash-<slug>`, and runs the checks (`check-themes`, `sim` captures, JVM tests, `cargo test`).
3. Two reviews on the diff: one by a Fable reviewer that gets the story and the diff only, one by the lead agent. Findings are fixed by the implementer. Repeat until both approve. Review checks: correctness, safety rules above, slop (dead code, needless abstraction, comments that restate code), and match with the surrounding code style.
4. Scooter steps are batched into owner sessions with a written checklist; nothing touches the scooter without the owner's go-ahead.
5. Merge to `main` locally; push only when the owner asks.
6. The plan is updated as stories close (`[x]`) and decisions are added below.

## Decision log

- D1 (2026-10-30): new repo `ola-dash` for the product; SDK as submodule. See Repositories.
- D2 (2026-10-30): host screens styled from `lock-style`, no new style struct.
- D3 (2026-10-30): theme options as `opt-<id>` `Dash` properties, no options global.
- D4 (2026-10-30): AA first as a separate receiver app plus the host dash bar; an embedded receiver is research only.
