# Measurements

Results of the session-A checklist ([session-a.md](session-a.md)). One block per session; date, build fingerprint and APK commit at the top of each.

## Per-theme timings

`tools/measure.sh` appends a dated table at the end of this file. Debug build; note the `hmiclient` state per block.

## Session A

2026-11-01, fingerprint `qti/msm8953_64/msm8953_64:10/QKQ1.191008.001/eng.root.20250712.021023:user/test-keys`, product APK at ola-dash fdc175a (SDK ffa8416), then SDK #27 for the restart check. Indicators: callbacks correct when the scooter is on (left 16:04:18-22, right 16:04:28-31); cruise control reported (ACTIV, engaged twice).

| Id | Result | Number or yes/no | Notes |
|---|---|---|---|
| M-compile | done (Default, first start after install) | probe 996 ms, root 824 ms, create 12 ms; warm restarts: probe 27-221 ms, root 262-435 ms | first start includes the asset copy; from logcat at 14:00, not saved |
| M-start | done | `Displayed` +3.0 s, first frame 4.05 s (first start after install); 0.70-1.1 s first frame on theme restarts | first start from logcat at 14:00, not saved. Force-stop cold starts (M-replay runs, 14:41-14:43, scooter off): probe 457-610 ms, root 673-1631 ms, `Displayed` +1.6-3.05 s, first frame 2.0-2.9 s |
| M-restart | relaunched yes (theme-switch exits and force-stop; `kill` of the process not run) | tap to new theme's first frame 2.0 s (Zen); force-stop cold start see M-start | old build aborted on every exit (SIGABRT, fixed in SDK #27); with `_exit(0)`: clean, crash buffer empty |
| M-ram | done (`hmiclient` disabled) | PSS 81.9 MB (Zen; dumpsys output not saved) | `top` RES 165-181 MB across the four themes |
| M-frame | gfxinfo shows no frames (Slint own surface) | parked CPU (not saved), % of one core over 10 s: Default 3.1, Twin Dial 0.8, Terminal 25.9, Zen 0.8 | Terminal's per-frame cursor (E4.S7 T5); GL captures crisp in all four themes |
| M-replay | replay yes, ~25 ms after `# profile service connected`, before the `# subscribed` marker | battery, range, odo, drive mode PARK, cruise availability | no `onSpeedChanged` and no lock state in the replay; with the scooter off: no live callbacks after the replay; CAN carries only 0x678/0x65D/0x66D every ~5-10 s |
| M-rate | done (ride, 41 km/h max) | `onSpeedChanged` every 100 ms median; longest gap 133 ms, shortest 62 ms | 8970 callbacks over the ride |
| M-sleep | | | |
| M-home | `set-home-activity` fails while `hmiclient` is enabled | no | "Error: Failed to set default home."; works after `pm disable-user` (hmi-swap). The dash package had been left disabled from an earlier session |
| M-dev: light sensor | none | no | only LIS2MDL magnetometer; auto night stays clock-only |
| M-dev: clock after cold boot | not cold-booted; with network: correct | `auto_time` = 1 | |
| M-dev: packageinstaller | present | /system/priv-app/PackageInstaller/PackageInstaller.apk | |
| M-dev: HTTPS to GitHub | yes via shell curl | HTTP 200 | no browser for VIEW intents; shell curl is not Android's CA store |
| M-dev: brightness | | | |
| M-dev: SAW background start | | | |
| M-dpad | no D-pad; volume up, volume down, play/pause | no callbacks fired | `onDpad_*` and the long-press callbacks stay false (no `true` in any session log); light button and halo: `isLowBeamOn`/`isHighBeamOn`/`isPositionLightOn` never change (false in every session, including the 16:04:36 and 16:04:40 light-button presses); side stand: `isSideStandOn` is right in every bind-time replay (false while riding, true 0.6 s after the ride session ended) but no live change callback came in the session where the stand went down; CAN candidates in PLAN E4.S7 T16-T17 |
| M-aa | | | |
