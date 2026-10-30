# Ola Dash 1.0 plan

Status: r3 final (2026-10-30), after review passes r1 (safety, scope, install), r2 (coverage, implementability) and r3 (final check) in
`docs/plan/reviews/`. Owner: abhi245y. Implementation notes for M1 and M2 stories are in
`reviews/r2-implementability.md` (file:line mechanics); implementer briefs quote the relevant section.

## Goal

Make the Ola Dash SDK host a complete dash for the Ola S1 Pro Gen 1 that an owner can install with one command and
extend from the dash: a redesigned look (overlay, lock screen, host screens), a theme pack (multi-dial, terminal,
minimal, AAOS-style card home), quick and safe theme switching, theme options, a settings screen, an app launcher,
handlebar-button navigation, a store for themes and plugins, a recovery path, and Android Auto with scooter
essentials always on screen.

What 1.0 is not, said plainly:
- **Lock**: the scooter's own passcode flow, drawn by the host in the dash's style. No phone-as-key, no remote lock,
  no change to the scooter's lock behaviour. An owner PIN for settings is in the backlog (owner's choice).
- **Android Auto**: a separate receiver app (Open Headunit) in front, with the host's dash bar on one edge showing
  speed, battery and telltales. Not AA cards inside a theme, not automatic connection, not guaranteed helmet audio.
  An embedded receiver is research (E7.S4).
- **Install**: one command from a Linux laptop on the same Wi-Fi as the scooter, through the head unit's vendor
  diagnostics service. It arrives in M5. After an OTA the owner re-runs the installer.

## Repositories

| Repo | Holds |
|---|---|
| `ola-dash-sdk` | The one host app (Rust + Slint + Java), host screens, safety overlay, contract, sim, `check-themes`, vehicle interface, plugin API, reference themes, developer docs. All host work lands here. |
| `ola-dash` (this repo, github.com/abhi245y/ola-dash) | The product: theme pack, installer, recovery watchdog APK, store index and submission CI, release pipeline, owner docs, this plan. Pins the SDK as a submodule at `sdk/` (last pushed SDK commit; `SDK_DIR=<checkout>` overrides it for unpushed work) and builds `sdk/host/build.sh` with the product themes bundled. |
| `ola-can-reference` | CAN catalog. Gets new observations (handlebar buttons, IMU) from session logs. |
| `ola-dev-skill` | Agent skill. Synced after SDK pushes that change the contract, theme format, store or installer. |

D1: the host stays in the SDK because `sim` compiles `host/src/theme_root.rs` and `host/ui/*`. The SDK can be changed
freely for the product; only the safety guarantees below are fixed.

## Fixed safety guarantees

The look of every safety element (telltales, alert cards, lock screen, strip) may be redesigned. What it guarantees may not:

1. The host draws telltales, alerts and the passcode keypad above everything a theme draws, in a host font, from host state. No theme or plugin can hide, cover, blank or feed them. (Today a theme can, in four ways; E0.S2 fixes it first.)
2. No vehicle command except the gated trunk request. Plugins have a display-only API; their APKs are ordinary Android apps, which the store screens (E6.S1).
3. Unknown data shows as unknown and stale data is marked stale, for everything the host draws (overlay, host screens, dash bar). Numbers a theme draws are controlled by store review (E6.S1.T4).
4. Every interactive host screen and every app launch needs `parked` (E0.S4): one gate, defined once in `TrunkGate.java`.
5. When the scooter leaves `parked`, host screens close, and the host comes back to the front unless the AA receiver is in front, which the dash bar covers.
6. With the stock HMI disabled, the host keypad is the only passcode entry. A dead host strands the rider, so recovery (E5.S2) blocks installs by anyone but the owner.
7. Anything that changes the scooter needs the owner's go-ahead for that session. The dash never signs in to any account. The dash and installer never touch OTA.

## Platform facts the plan depends on

- Slint 1.18.1 on Android has one window. Host screens, the overlay and the theme share the interpreted root. A second `android_main` in one process fails (`set_platform` returns `AlreadySet`), so a restart means a new process. Compiles run with `spin_on` on the UI thread (`lib.rs:324,329`): the screen freezes while compiling.
- `PopupWindow`s are drawn after the whole root tree and take touches. Host text without `font-family` inherits the theme's `default-font-family` (`theme_root.rs:64`). Font imports bypass the compiler's file loader.
- `ComponentInstance::set_property` reaches only root properties. `MIRRORS` (`theme_root.rs:76-85`) mirrors `Dash` outputs today; E1.S1 adds the inbound direction for options.
- `VehicleBridge` keeps `REAL[]` for vehicle slots and replays it; host slots 30-39 are not replayed. Alerts (`pushAlerts`) and unlock state (`UnlockController.publish`) are pushed directly. `TrunkGate` holds the park rule with a tri-state lock.
- `MainActivity.copyAssets` overwrites every bundled asset into `files/` on every start.
- Android 10: background activity starts need the `SYSTEM_ALERT_WINDOW` appop; knowing the foreground package needs `PACKAGE_USAGE_STATS`; a foreground service needs `FOREGROUND_SERVICE` and a notification channel.
- No Back key on the panel. The stock HMI sets `keepScreenOn`; the host does not yet.
- Root is reachable only through the vendor diagnostics service (gRPC, `[::1]:50005` locally, link-local IPv6 port 50005 on the network), unauthenticated. `ola-root-helper` (`dev.olatool.boothelper`) already has a Java gRPC client for it (Gradle, `grpc-okhttp`). Anyone on the scooter's network has the same power; owner docs say so.
- The vehicle interface delivers handlebar D-pad callbacks (`onDpad_*`, logged by `HandleBarCallbacksBase`), IMU data (`IMUData.toString()` prints the floats) and a brightness level.

## Measure first: scooter session A

Checklist with one shell line per row in `ola-dash/docs/session-a.md`; results in `ola-dash/docs/measurements.md`.

| Id | What | Decides |
|---|---|---|
| M-compile | Probe + root compile per theme; again after E1 adds host screens | E0.S6 mechanism, watchdog window |
| M-start | Cold start to first frame (`Displayed dev.olatool.dash`), with the product themes bundled | E0.S6, watchdog window |
| M-restart | After `exit(0)` of the home app: is it relaunched, how fast; does `recreate()` keep the process | E0.S6, E5.S2 |
| M-ram | Host PSS per theme with `hmiclient` disabled | AA fit |
| M-frame | Frame time per theme with mock ride data | E4 rules |
| M-replay | Fields the parser replays on subscribe (is speed 0 known at a cold start in Park?) | E0.S4 reachability |
| M-rate | Longest gap between real callbacks at steady speed | E0.S3 stale timeout |
| M-sleep | Does a locked scooter still sleep the panel with `FLAG_KEEP_SCREEN_ON` set? | E0.S3.T2 |
| M-home | Does `cmd package set-home-activity` work without disabling `hmiclient`; does the stock HMI stay in the background? | E5.S2 design |
| M-dev | `Sensor.TYPE_LIGHT`; `date` and `AUTO_TIME` after a cold boot without network; `com.android.packageinstaller`; HTTPS to GitHub with the head unit CA store; panel follows `screen_brightness`; SAW background start | E3.S1, E6, E1.S4, E2 |
| M-dpad | Which handlebar buttons fire while parked and riding, and what the stock HMI does with them | E1.S6 |
| M-aa | AA spike numbers (E7.S1), if the owner's phone is there | E7 |

Brightness: if the panel only follows the vehicle path (`setScooterBrightnessLevel`), the D-log records whether that counts as a vehicle command before any code uses it.

## Milestones

| Milestone | Stories, in order | Scooter |
|---|---|---|
| M1 Safe core | E0.S2 (two PRs), E0.S4, E0.S3, E0.S5, E0.S1, E1.S1 PR A | Session A at the end |
| M2 Hub | E1.S2, E1.S3, E1.S4 PR1, E0.S6, E1.S4 PR2, E1.S5, E1.S6 | Verification |
| M3 Beyond the dash | E2 (SAW and usage-stats grants set by hand over the root service in the session-B checklist); E7.S1 if not done in A | Session B |
| M4 Theme pack | E1.S1 PR B, E3, E4.S1-S3, E4.S5; E4.S4 after E8 | Perf check |
| M5 Install and recovery | E5 | Session C: install, crash-loop, restore |
| M6 Store | E6 | Install test |
| AA mode | E7.S2-S3 after the spike and E2.S1 | Ride test |
| Research | E8, any time | No |

## Epics, stories and tasks

`[ ]` open, `[~]` in progress, `[x]` done. Repo in brackets. Each story has acceptance criteria (AC).

### E0 Foundation and safety fixes

**E0.S1 Product repo bootstrap** [ola-dash]
- [x] T1 SDK submodule at `sdk/`; README (what this repo is, links to SDK docs), CHANGELOG.
- [x] T2 [SDK] `host/build.sh`: optional `EXTRA_THEMES=<dir>` copies each folder with a `theme.json` into `assets/themes/<id>/`; nothing else in `build.sh` changes. Bundled ids are reserved: they update with the host, the store never updates or removes them (`copyAssets` would undo it).
- [x] T3 `tools/build.sh`: the rsync + ssh recipe from `sdk/host/README.md` to `arlp-pc:~/Documents/ola-dash-build`, `EXTRA_THEMES=$PWD/themes`, APK copied back to `out/`.
- AC: with `themes/minimal` copied in as a placeholder, `unzip -l out/*.apk | grep assets/themes/minimal/theme.json` matches.

**E0.S2 Theme sandbox** [SDK] (critical; blocks E0.S6, E3, E4, E6)
PR1:
- [x] T1 `theme_root.rs` gets the one loader used by host and sim (`Compiler::set_file_loader`) on the probe compile, which is the gate (the root compile runs only after the probe passed, and also serves `files/host`). The loader canonicalizes the requested path, refuses symlinks, allows only the contract dir and the canonical theme dir, and returns `Some(Err(..))` for anything else (`None` falls through to the disk). `build_from_path` reads the entry file without the loader, so the entry gets the same path and keyword check in Rust first. Any theme file containing `PopupWindow`, `Tooltip` (lowered to a popup), `ContextMenuArea`, `MenuBar` or `std-widgets.slint` is refused (substring; a comment fails closed).
- [x] T2 Fixtures under SDK `tools/fixtures/` (not `themes/`): `evil2` (imports `../../host/ui/overlay.slint`, writes `HostState`), `evil3` (full-screen no-auto-close `PopupWindow`). `check-themes.sh` requires `sim --check` to fail on both.
PR2:
- [ ] T3 `HostState` mirrors (`overlay.slint:74-90`): left/right indicator, high beam, headlight, ready, locked, charging, clock text, battery. Rust `apply()` writes them beside `Vehicle.*`; the overlay (`:139-149`) and lock screen (`:320-321`) read only `HostState`; sim `Feeder::push` and `host/test/unlock-preview.rs` set them too.
- [ ] T4 Host font: overlay, lock screen and every host screen set `font-family` to a host-unique family name, registered from Rust (`slint::register_font_from_path`) before `load_ui` so its faces come first in fontique's family list; host text uses only weights the host font ships. `sim --check` rejects a theme whose `.ttf`/`.otf` bytes contain the host family name (ASCII or UTF-16BE substring); fixture `evil4` (blank-glyph font claiming the host name) must fail. E6.S1.T3 reuses the check. Why: fontique merges same-name registrations and picks the first exact-weight face; theme fonts register in path order (`collect_custom_fonts.rs:20-22`, fontique `collection/mod.rs:769-779`, `matching.rs:376-378`).
- [ ] T5 `sim --pixel X,Y` prints the colour at a point of the screenshot. `check-themes.sh`: `evil1` passes `sim --check`, and at t=13 the left-indicator pixel and a keypad key (`--state locked`) match `themes/minimal`.
- Notes: `@image-url` and font files are read at runtime outside the loader; they can only display, which is acceptable. A theme re-declaring `global HostState` is harmless (only root exports are public).
- AC: `check-themes.sh` exits 0 only if evil1 keeps a full overlay and keypad and evil2, evil3 and evil4 fail to load; host text uses the host font in every theme; `cargo test` and `unlock-preview` pass.

**E0.S3 Host hardening** [SDK]
- [ ] T1 Stale data: `HostState.data-stale` (field id 38, host range, not replayed). Set on `onServiceDisconnected` / `onBindingDied`, and from the existing 1 s keep-alive tick when no real vehicle callback (`realVehicleEvent()`) arrived for 5 s while `state == drive` (`// ponytail: 5 s until M-rate calibrates it`); cleared in `subscribe`. Strip badge "NO DATA" copied from the TEST DATA block. `sim --stale`.
- [ ] T2 `getWindow().addFlags(FLAG_KEEP_SCREEN_ON)` in `MainActivity.onCreate` (M-sleep verifies the locked panel still sleeps).
- [ ] T3 One log line each for probe compile, root compile, `create()`, and first frame (`set_rendering_notifier`, once).
- [ ] T4 Check a calls log for IMU floats and handlebar booleans (code already logs them); close with no code if present.
- AC: `sim --stale` shows the badge; on the dev scooter `am force-stop com.olaelectric.vehicleparser` shows NO DATA within 5 s.

**E0.S4 Parked gate** [SDK]
- [x] T1 In `TrunkGate.java`, extract `notParked(testMode, bcmUnlocked, state, speedKmh)` from `refusal()`; `parked(..)` = `notParked(..) == null` or (charging and BCM unlocked and not test mode; speed not required while charging). `refusal()` calls it. Extend `TrunkGateTest.java`, including unknowns (fail closed) and "charging + test mode = not parked".
- [x] T2 Field id 39 pushed with `nativeSet` (not `setNum`) from the callbacks that change its inputs; `HostState.parked` in Slint. Sim derives it from the scenario (park, trunk, charge).
- [x] T3 Log `parked -> false while paused` (`onPause`/`onResume` flag in `MainActivity`). Closing host screens is E1.S3; bringing the host forward is E2.S1.
- Note (M-replay risk): `parked` reads only the real BCM lock callback, so after a cold start in Park it stays false until the parser replays or re-fires that callback; if session A shows it never does, settings are unreachable until the scooter is locked and unlocked once. Fails closed.
- AC: `javac -d host/build-tests host/java/dev/olatool/dash/TrunkGate.java host/test/TrunkGateTest.java && java -cp host/build-tests dev.olatool.dash.TrunkGateTest` passes and T1 adds those lines to `docs/testing.md`; the M-replay risk is written in the story notes.

**E0.S5 Measurement kit** [ola-dash]
- [x] T1 `tools/measure.sh` (session-A tooling, debug build and adb): push SDK themes with `run-as`, cycle `files/themes/active`, restart with `am force-stop` + `am start`, collect `OlaDash` timings and `TOTAL PSS`.
- [x] T2 `docs/session-a.md`: one line per Measure-first row, plus the AA spike block if the phone is there. HTTPS probe: `am start -a android.intent.action.VIEW -d https://github.com`, or `curl` through the 50005 shell.
- [ ] T3 Run session A with the owner; write `docs/measurements.md`; add handlebar and IMU evidence to `ola-can-reference` observations (`0x6AD` as a hypothesis).
- AC: every M-row except M-aa has a number or a yes/no.

**E0.S6 Theme switching** [SDK] (after E1.S4 PR1)
- [ ] T1 Restart switch: show the host "Switching to <theme>" screen (spinner) for one frame at least, write `files/themes/previous` and `active`, write the clean-exit marker (so neither the strikes guard nor the watchdog counts it as a crash), then `Runtime.getRuntime().exit(0)`; the system relaunches the home app (M-restart).
- [ ] T1b Hide the gap: the activity's `android:windowBackground` is a static drawable that matches the switching screen (dark fill + centred bitmap), so the rider sees the same screen from exit until the new theme's first frame. Android 10 cannot animate a window background, so the spinner is still only before exit and after the first frame.
- [ ] T1c Faster start: `copyAssets` copies only when the APK changed (marker with `lastUpdateTime`), not on every start.
- [ ] T1d Target: tap to new theme on screen in 2 s or less on the scooter (owner: "fine as long as it is not a laggy restart"). Measure it; if it is slower after T1c, open the in-process swap story from the backlog.
- Unlock: a dash restart does not lock the scooter (the lock is BCM state). The host must not show the keypad while it waits for the first lock callback after a restart; it shows the switching screen until lock state is known (M-replay says how long).
- [ ] T2 Only while `parked`, no alert, unlocked, not test mode.
- [ ] T3 Root screen `confirm-theme`: "Keep this theme? Reverting in 10 s", Slint `Timer`; confirm deletes `previous`, timeout restores it and restarts.
- [ ] T4 (separate small PR, Java only, any time) Bad-theme guard: `files/themes/strikes` = `<name> <n>`, set in `onCreate`, cleared 10 s after `onCreate`; two failed starts with the same theme make the third start load `default` and mark the theme bad. Test with a debug-only `debug.oladash.panic` property the Rust side reads.
- AC: on the scooter, tap to new theme in 2 s or less with no keypad flash and no blank frame; keypad, trunk and media work after the switch; a theme that panics at start is replaced on the third start.

### E1 Hub: look, shell, settings

Design process for E1.S2 and E4 (owner rule): the `impeccable` skill drives the redesign; Codex CLI generates concept
boards and image assets (`image_generation`) and gives a written critique of each comp; the lead agent and the owner
make the final call; the agreed token list is the input to the implementer PR. Host screens read the theme's checked
`lock-style` through `LockConfig.style` (D2), so every theme styles them.

**E1.S1 Contract v7** [SDK]
PR A (M1):
- [ ] T1 `Actions.open-apps()`, `Actions.open-themes()`: wired to log lines in `wire()` and sim until E1.S3.
- [ ] T2 `Display` global `in property <bool> night`; `Vehicle.data-stale` (the `apply()` arm writes `HostState` and `Vehicle`).
- [ ] T3 `contract-version` 7, `HOST_CONTRACT`, `docs/contract.md`, CHANGELOG.
PR B (M4):
- [ ] T4 Theme options: `theme.json` `options` `[{id, type: color|bool|int|choice, default, label, values?}]`, id `[a-z0-9-]`, at most 16; `Dash` declares `in property <T> opt-<id>` (`int`, `bool`, `string`, `color` only). `root_source` emits the same properties on `Host` and binds them into `dash := Dash {..}`; options whose probe type does not map are skipped with a log line. `sim --opt id=value`, `--night`; `sim --check` validates `options`. Rule in `docs/themes.md`: option properties are `int`, `bool`, `string` or `color` (`length` passes the probe as Number and fails the root compile, which `sim --check` catches).
- [ ] T5 Skill sync after the first SDK push of v7 (`tools/sync.py`; template theme gets one option and night by hand).
- AC: the four v6 themes pass `check-themes` unchanged; `sim themes/default --opt accent=#ff0000` changes nothing and logs one skip line.

**E1.S2 Design language and safety visuals** [SDK]
- [ ] T1 Design (process above): concept boards for strip, telltale glyphs, alert cards, lock screen, settings frame; token list (colours, type scale, radii, sizes) agreed with the owner. Sunlight and gloves: 64 px targets, 4.5:1 text contrast. Strip stays 48 px (top/bottom) and 72 px (left/right) in v7.
- [ ] T2 Implement: `OverlayTokens`, glyph paths, alert card, `unlock.slint` (adds charging progress while locked), `HOST_LOCK` defaults. Host minimums stay (telltale 28 px, alert text 32 px), colour + icon meaning stays.
- AC: 30 sim captures (four placements x alerts 1-6, locked, locked-error, cooldown, charge) on the PR; `theme_root.rs` contrast tests pass; passcode behaviour unchanged.

**E1.S3 Host shell** [SDK]
- [ ] T1 `in property <string> screen: "dash"` on `Host`; screens drawn with `if` between `dash := Dash` and `HostOverlay`, so the lock screen and alerts cover them. Navigation stays in Slint. `screen` resets to `dash` in the same evaluation when `parked` turns false or an alert starts.
- [ ] T2 Hub button: the strip's end cell, 64 px along the strip by the strip height, never moves or shrinks a telltale; visible only when `parked`, no alert, unlocked, not test mode. Added to the host-owned list in `docs/safety.md`.
- [ ] T3 Close button on every screen. `apps` is a placeholder until E2.S2. `host/ui/kit.slint` with only the parts the frame uses (rail row, close button).
- [ ] T4 `sim --screen settings|apps`.
- AC: parked, the owner reaches the settings frame and the apps placeholder from any theme; leaving `parked` closes them in one frame (sim capture pair).

**E1.S4 Settings core** [SDK]
- [ ] PR1: `files/settings.json` owned by Rust (read in `run()` before `load_ui`, exposed as root properties, written by root callback `set-setting(key, value)` via temp file + rename; a parse failure renames it `.bad` and starts from defaults, unit-tested). Rail and pane, rail rows 72 px; the rail lists only panes that exist. Panes: Display (night on/off, 12/24 h clock in the `CLOCK_HHMM` arm, brightness only if M-dev allows), About (from `files/about.json` written by Java at start: version + git rev, contract, cert SHA-256, log size and clear). Navigation model on every pane: `cursor`, `move(d)`, `select()`, `close()`, used by touch and by E1.S5.
- [ ] PR2 (after E0.S6): Theme pane (installed themes, apply via E0.S6), first-run card (theme, night) shown when `parked`, or `state == park` with speed unknown; it launches nothing.
- AC: settings survive a restart; a corrupt file never crashes the host; `sim --screen settings` captures per pane.

**E1.S5 Plugins pane** [SDK]
- [ ] T1 `PluginHost` writes `files/plugins/installed.json` (package, label, declared slots) on every refresh; the pane lists it; a toggle calls `set-plugin(pkg, slots)`; Rust rewrites `files/plugins/enabled` (format in `docs/plugins.md`) and sends `plugins.refresh` through `onDashAction`, which calls `PluginHost.refresh()`.
- [ ] T2 `sim --screen plugins --plugins-file <json>` capture.
- AC: `example-sysinfo` enabled and disabled from the dash on the dev scooter with no adb.

**E1.S6 Handlebar buttons** [SDK] (needs M-dpad)
- [ ] T1 Override the `onDpad_*` methods in the `HANDLEBAR` callbacks; push with `nativeSet` to ids 52-56 (`SLOTS` 57), not replayed; `HostState.dpad-*`; the root maps them to the pane navigation model while a host screen is open. `PlayOrPause` goes to `media.play-pause` while riding only if the stock HMI does the same. The host never sends a D-pad event.
- [ ] T2 Sim: a `FocusScope` maps arrow, enter and escape keys onto the same properties.
- AC: settings usable with gloves through the handlebar buttons only (`inject.sh handlebar ...` in test mode, then a real press).

### E2 Beyond the dash

**E2.S1 Dash bar** [SDK] (safety-critical)
- [ ] T1 `TYPE_APPLICATION_OVERLAY` window shown in `onPause`, hidden in `onResume`, held by a foreground service (manifest: `FOREGROUND_SERVICE`, notification channel) while another app is in front. Shows speed, battery, indicators, high beam, side stand, fault, ready, NO DATA, back-to-dash, read from `REAL[]` and the alert fields. Shares colour constants with the overlay. `FLAG_WATCH_OUTSIDE_TOUCH` feeds `TOUCHED` so the keep-alive sees touches in other apps. The service also writes the watchdog heartbeat while the host is paused.
- [ ] T2 When `parked` turns false and the foreground package (usage stats) is not the AA receiver, bring the host forward. Critical alerts (fall, tow, side stand, steering lock) expand the bar to full screen, then bring the host forward. A vehicle lock brings the host lock screen forward.
- [ ] T3 Height 48 / 64 / 80 px, default 64, speed digits 44 px or more, opaque. Edge setting; default bottom, top in AA mode until E7.S1 answers the margin question.
- [ ] T4 Scooter matrix: launched app then DRIVE (host returns within 1 s); AA receiver in front 30 min; Android settings in front; ride longer than the screen timeout; parser killed (speed shows `--`); host process killed; keep-alive touches delivered.
- AC: an app without `SYSTEM_ALERT_WINDOW` cannot cover the bar; only the host holds SAW.

**E2.S2 App launcher** [SDK]
- [ ] T1 Java lists launchable activities and writes each icon once to `cache/icons/<pkg>.png`, then `files/apps.json`; Rust loads it into a Slint grid when the launcher opens: 5 columns, 96 px icons, 24 px labels, dock of favourites (in `settings.json`).
- [ ] T2 Hidden by default: `com.olaelectric.*`, `com.ola.*`, Android Settings, the dash, the watchdog. Apps pane: favourites, hidden apps, "show system apps".
- [ ] T3 Launch only while parked, including the AA receiver; `Actions.open-android-auto()` gets the same gate. Android settings: parked only.
- AC: 40 apps scroll smoothly; launching while not parked is refused with a host message.

### E3 Theme system v2

**E3.S1 Options and auto night** [SDK] (after E1.S1 PR B)
- [ ] T1 Theme pane renders controls from `options`; values per theme in `settings.json`; applied live through the `opt-<id>` root properties.
- [ ] T2 Night `auto`: light sensor if present (M-dev), else clock with editable times; falls back to manual when `AUTO_TIME` is off or the year is implausible. Night is optional per theme.
- AC: changing an option or night updates the theme with no recompile.

**E3.S2 Theme list and previews** [SDK]
- [ ] T1 Theme pane shows `preview.png` (riding state with overlay, rendered by `sim`) or a placeholder; rescans `files/themes/` when opened; themes without `.store` (written by the store client) get a "sideloaded" badge.

### E4 Theme pack [ola-dash]

Design process as in E1. Every theme: concept board (Codex) and critique, owner sign-off, implementation, `sim` captures (riding, parked, charging, locked, alert), `lock-style`, overlay settings, `preview.png`, `check-themes` pass (sandbox included), under 2 MB, M-frame on the scooter. Dials are drawn with paths and `sin`/`cos`, never `transform-rotation`. At most three `animation-tick()` bindings. Contract data only. Night optional.

- [ ] E4.S1 **Twin dial**: analog speedometer, power/regen dial (`current-a` x `voltage-v`), small battery and temperature dials. Options: accent, needle style, digital speed overlay, power bar instead of dial.
- [ ] E4.S2 **Terminal**: monospace on black, readout lines that change only when values change, ASCII bar gauges, one blinking cursor. Options: green, amber, white; scanlines.
- [ ] E4.S3 **Zen**: speed and battery only, very large type, for sunlight.
- [ ] E4.S4 **Cockpit**: AAOS-style card home (navigation, media, vehicle, plugin widgets). After E8.
- [ ] E4.S5 Default theme refresh to the new design language [SDK].

### E5 Release, recovery, installer [ola-dash unless noted]

**E5.S1 Release build and pipeline**
- [ ] T1 [SDK] Remove `android:debuggable` from the manifest; the debug build passes `aapt2 link --debug-mode`. `host/build.sh --release`: keystore from env, versionCode from the git tag, checks the flag with `aapt2 dump badging`, `apksigner verify`, prints the cert SHA-256.
- [ ] T2 GitHub Actions: on tag, build the release APK, publish APK + SHA256SUMS + cert digest (the skill's release pattern).

**E5.S2 Recovery** (blocks installs by anyone but the owner)
- [ ] T1 From M-home: if the host can be home without disabling `hmiclient`, the installer never disables it, and uninstalling the host restores stock by itself.
- [ ] T2 Watchdog APK `ola-dash-watchdog`: a Gradle project copied from `ola-root-helper`'s layout (its gRPC client), own process and signing, `BOOT_COMPLETED`; acts only through `[::1]:50005`; fails closed and logs if the service or root is missing.
- [ ] T3 Heartbeat: the host sends an explicit broadcast to the watchdog every 5 s from a `slint::Timer` on the UI thread (a hung event loop stops it); the dash bar service sends it while the host is paused; before every blocking compile the host sends `busy-until`. Failure = display interactive and no heartbeat for max(M-start x 3, 3 periods, max M-compile + 1 period), or 3 abnormal exits in 10 min (no clean-exit marker and a new pid). Restore = exactly `hmi-swap.sh stock`.
- [ ] T4 Manual restore: `installer restore`, and one typeable line on the host's last-resort screen and in the owner docs (works from the ola-s1-rea phone app).
- [ ] T5 [SDK] `docs/safety.md`: stranded-rider consequence, unauthenticated vendor root service, plugins are ordinary apps, host-owned list includes the hub button.
- AC: a crash-looping build restores the stock HMI without a laptop; sleep, wake, theme switch, store install and 30 min of AA in front never trigger it.

**E5.S3 Installer core**
- [ ] T1 Python 3 + `grpcio`, Linux first; scooter discovery over link-local IPv6 (ping `ff02::1`, neighbour table), reusing the ola-s1-rea client code.
- [ ] T2 Preflight: `id -u` = 0 over the service, build fingerprint in the known-good list, free space, `com.olaelectric.ota` state reported (never changed); the owner confirms parked and charged (deliberately the only vehicle check).
- [ ] T3 Backup: package states, current home, appops it will change.

**E5.S4 Installer commands**
- [ ] T1 `install`: push APKs in chunks, install host and watchdog, grant notification listener, `SYSTEM_ALERT_WINDOW`, `PACKAGE_USAGE_STATS`, `REQUEST_INSTALL_PACKAGES`, `WRITE_SETTINGS` (if M-dev needs it), set home, wait for the heartbeat.
- [ ] T2 `uninstall` and `restore` replay the backup; `status` prints versions, home, grants, OTA state. Every step idempotent.
- [ ] T3 `push-theme <dir>`: `check-themes` locally, push into `files/themes/<id>/`, chown to the app uid. The mod-author loop.
- [ ] T4 Owner docs: Wi-Fi is set once through Android settings (parked); cellular data use is unmeasured; re-run `install` after an OTA, and if the diagnostic service is gone no install or uninstall path remains (the watchdog and stock HMI still work).
- AC: fresh MoveOS 5 scooter on the same Wi-Fi as the laptop, no prior tooling, to a working dash in one command, and back to stock in one.

### E6 Store

**E6.S1 Format, index, submission CI** [ola-dash]
- [ ] T1 Theme package: zip of the theme folder, only `.slint .json .png .svg .ttf .otf .txt`, 2 MB inflated, 200 files, images up to 2048 x 2048, `preview.png` required; id `[A-Za-z0-9_-]{1,64}`; `default`, `fallback`, `last-resort` and bundled pack ids reserved.
- [ ] T2 `store/index.json` (at most 1 MB): `seq`, entries with URL (release asset), size, SHA-256; plugins add package, versionCode, signing cert SHA-256, slots, permissions.
- [ ] T3 CI: unpack caps, `check-themes` (with the sandbox fixtures), `sim` previews, `animation-tick` count, theme fonts must not claim the host font family. Plugin APKs: `aapt2 dump permissions`; reject `SYSTEM_ALERT_WINDOW`, `BIND_ACCESSIBILITY_SERVICE`, `BIND_DEVICE_ADMIN`, `BIND_NOTIFICATION_LISTENER_SERVICE` (1.0 media comes from the host's built-in source only), `REQUEST_INSTALL_PACKAGES`, `PACKAGE_USAGE_STATS`, HOME activities, and dex or manifest references to `com.olaelectric.vehicleparser`, `com.olaelectric.vehicleinterface`, `ICommanderService`.
- [ ] T4 Reviewer rules: no passcode or PIN entry UI in themes; numbers on sim captures match the mock values.

**E6.S2 Store client: browse** [SDK]
- [ ] T1 Fetch `index.json` over HTTPS from GitHub (Java); TLS failure is an error, never a fallback to http; refuse a `seq` lower than the last accepted; list with previews; parked only.

**E6.S3 Store client: themes** [SDK]
- [ ] T1 Download, SHA-256 check, safe unzip counting inflated bytes (no absolute paths, no `..`, no symlinks, caps from E6.S1), write `.store`, probe compile (parked, static card, `busy-until` sent), then move into `files/themes/<id>/`. Update and uninstall. A theme that fails is never activated.

**E6.S4 Store client: plugins and host update** [SDK]
- [ ] T1 Verify APK hash and signing cert against the index, then a `PackageInstaller` session (Android shows its confirmation); open the Plugins pane after install; uninstall via `ACTION_DELETE`.
- [ ] T2 Host self-update the same way (same signer, Android refuses downgrades); the host sends `busy-until` first so the watchdog treats the restart as clean.
- AC: a theme and a plugin installed, updated and removed on the scooter without a laptop.

### E7 Android Auto

**E7.S1 Spike** (owner, phone and scooter together, parked; go/no-go)
- [ ] T1 Confirm the receiver's package id (host constant `com.andrerinas.headunitrevived`, project renamed Open Headunit); pin a release and checksum.
- [ ] T2 Measure connect route (Headunit Server on shared Wi-Fi first), time to video, latency, decoder, host + receiver RAM, audio route, touch, return to the dash.
- [ ] T3 Can the receiver use a resolution or margin that leaves room for the dash bar? Does it expose navigation state to other apps?
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

- Owner PIN for settings and a "lock word" shown only on real host keypads (owner chose later).
- Signed store index with two keys and expiry, when a mirror or second maintainer appears.
- Frame-time guard that reverts a theme which is too slow on the device.
- In-process theme hot-swap (only if the restart switch misses the 2 s target after the faster start).
- Theme sideload from a phone over the local network.
- Third-party media plugins (needs a rule for `BIND_NOTIFICATION_LISTENER_SERVICE`).
- macOS and Windows installer; auto theme rules; miles; CarPlay; Gen 2.

## How the work runs

1. One story (or named PR) at a time, in milestone order, on a branch `e<epic>-s<story>-<slug>` in the repo the story names.
2. An implementer agent (effort `high` for safety-critical or tricky code, `medium` for mechanical work and docs) gets the story, its notes from `reviews/r2-implementability.md`, and the guarantees. It builds on `arlp-pc` in `~/Documents/ola-dash-<slug>` (deleted after) and runs the checks (`check-themes`, `sim` captures, JVM tests, `cargo test`).
3. Two reviews of the diff: a Fable reviewer (story + diff + guarantees) and the lead agent. Checks: correctness, guarantees, slop (dead code, needless abstraction, comments that restate code), style match. The implementer fixes; repeat until both approve.
4. Design stories add the Codex critique and the owner's sign-off before implementation.
5. Scooter steps go into session checklists; nothing touches the scooter without the owner's go-ahead.
6. Merge to `main` locally; push only when the owner asks. Commits carry no co-author or tool attribution lines.
7. Close tasks here (`[x]`), add decisions below, and land upstream follow-ups (SDK docs, CAN reference, skill).

## Decision log

- D1 (2026-10-30): host stays in the SDK; `ola-dash` holds the product parts and pins the SDK.
- D2: host screens styled from `lock-style` via `LockConfig.style`; no new style struct.
- D3: theme options are `opt-<id>` `Dash` properties mirrored through `Host`; no options global.
- D4: AA in 1.0 is the separate receiver plus the host dash bar; embedded receiver is research.
- D5: the safety visuals may be redesigned (owner); the guarantees may not.
- D6: store index unsigned in 1.0: HTTPS from GitHub + SHA-256 + plugin cert pins + monotonic `seq`.
- D7: installer and watchdog use the vendor diagnostics service, not root adb.
- D8: launcher is a host Slint screen (designed, theme-styled); Java only lists apps and writes icon files.
- D9: theme switch = process restart in 1.0 (second `android_main` cannot re-init Slint), hidden behind a switching screen and a matching window background; target 2 s tap to new theme; owner accepts a restart that is not laggy.
- D10: owner PIN deferred to the backlog (owner, 2026-10-30).
- D11: UI design through the impeccable skill; Codex makes concept boards and assets and critiques comps; owner and lead decide.
