# Session A checklist

Owner session on the dev scooter. Each row: the line to run, what to record, where. Record in [measurements.md](measurements.md) (table "Session A") unless the row says otherwise.

Commands are `adb shell ...` on the root adb session. "Vendor shell" means the vendor diagnostics shell on port 50005 (`ola.py shell`), for anything adb cannot do without root.

## Safety

- Scooter parked on the stand, key present, charger state noted.
- Debug build of the host installed; nothing else installed or updated, except the AA receiver in M-aa (owner go-ahead).
- Needs the `sdk/` submodule (E0.S1 merged), or `SDK_DIR=../ola-dash-sdk` for `tools/measure.sh`.
- Pull logs into `tmp/` only (gitignored; they carry vehicle identifiers).
- No OTA (`com.olaelectric.ota` is not touched), no account sign-in, no Ola login.
- Restore the stock HMI at any point, and always at the end:

```sh
bash sdk/host/test/hmi-swap.sh stock
```

- Steps that change the scooter are marked **changes the scooter: owner go-ahead**. Ask first; run the undo line afterwards.
- Starting the scooter or riding is a supervised step, never scripted.

## Before

```sh
adb shell getprop ro.build.fingerprint        # record in the block header
adb shell pm list packages -d | grep hmiclient   # is the stock HMI disabled?
adb shell run-as dev.olatool.dash cat files/themes/active   # record; measure.sh restores it
```

## Rows

### M-compile, M-start, M-ram (per theme)

Product themes bundled, `hmiclient` disabled for M-ram only (see M-home for the swap).

```sh
tools/measure.sh          # all SDK themes; appends to docs/measurements.md
tools/measure.sh --dry-run   # print the adb lines first
```

Record: probe, root, create, first-frame ms (M-compile), `Displayed` time (M-start), `TOTAL PSS` (M-ram). Repeat the run after E1 adds host screens. For M-ram run once more with `hmiclient` disabled (**changes the scooter: owner go-ahead**; undo: `adb shell pm enable com.olaelectric.hmiclient`).

### M-restart

Process death of the home app, which is what E0.S6 relies on. The dev app must be home (see M-home).

```sh
adb logcat -c
adb shell kill $(adb shell pidof dev.olatool.dash)
sleep 5; adb shell pidof dev.olatool.dash
adb logcat -d | grep -E 'Start proc .*dev.olatool.dash|Displayed dev.olatool.dash'
# second: the same with force-stop
adb shell am force-stop dev.olatool.dash
```

Record: relaunched yes/no for each, seconds from the kill to `Displayed`. If the panel stays blank (a dead home app leaves the panel blank on this unit), recover with `adb shell am start -n dev.olatool.dash/.MainActivity`, then `bash sdk/host/test/hmi-swap.sh stock`.

Does `recreate()` keep the process? Force a configuration change and compare the PID:

```sh
adb shell pidof dev.olatool.dash
adb shell settings put system font_scale 1.15     # changes the scooter: owner go-ahead
sleep 3; adb shell pidof dev.olatool.dash
adb shell settings put system font_scale 1.0      # undo
```

Changes the scooter: owner go-ahead (home app is stopped for a few seconds). Undo: `bash sdk/host/test/hmi-swap.sh stock`.

### M-frame

Mock ride data per theme, on the test channel (debug build).

```sh
sdk/host/test/inject.sh motor onSpeedChanged 25
adb shell dumpsys gfxinfo dev.olatool.dash reset
sleep 30
adb shell dumpsys gfxinfo dev.olatool.dash | grep -E 'Total frames|Janky|50th|90th|95th|99th'
sdk/host/test/inject.sh off
```

Record per theme: frames, janky %, 50th/90th/99th percentile ms. If gfxinfo shows no frames (Slint renders its own surface), record that and use the `first-frame` log instead.

### M-replay

Does the parser replay its state on subscribe, and is speed 0 known at a cold start in Park?

```sh
adb logcat -c
adb shell am force-stop dev.olatool.dash
adb shell am start -n dev.olatool.dash/.MainActivity
sleep 10
mkdir -p tmp && adb pull /sdcard/Android/data/dev.olatool.dash/files/logs tmp/logs
grep -m40 -E 'onSpeedChanged|LockState|onVehicleStateChanged|DriveMode|Soc' tmp/logs/calls-*.log   # `<epoch ms> IMotor...onSpeedChanged [25]`
```

Record: the callbacks present in the first second after start and their args (speed, state, lock, mode, battery); whether `onSpeedChanged 0` is among them; time from start to the first one. Repeat locked and unlocked, parked.

### M-rate

Riding, steady speed, supervised. Scooter off the stand or on a rolling stand only with the owner's go-ahead.

```sh
adb pull /sdcard/Android/data/dev.olatool.dash/files/logs tmp/logs
grep onSpeedChanged tmp/logs/calls-*.log     # `<epoch ms> IMotor...onSpeedChanged [25]`; real callbacks are in the file, not logcat
```

Record: longest gap in seconds between real `onSpeedChanged` callbacks over a minute at constant speed; also the shortest. Feeds the 5 s stale timeout.

### M-sleep

Locked scooter, `FLAG_KEEP_SCREEN_ON` set by the host.

```sh
adb shell dumpsys power | grep -E 'mWakefulness|Display Power'
sleep 120
adb shell dumpsys power | grep -E 'mWakefulness|Display Power'
```

Record: wakefulness at 0 and 120 s after locking (Awake or Asleep). Note: a screenshot of a sleeping panel is white; wake with `input keyevent KEYCODE_WAKEUP`.

### M-home

Does `set-home-activity` work without disabling `hmiclient`; does the stock HMI stay in the background?

```sh
adb shell cmd package set-home-activity dev.olatool.dash/.MainActivity
adb shell cmd package resolve-activity --brief -a android.intent.action.MAIN -c android.intent.category.HOME | tail -1
adb shell input keyevent KEYCODE_HOME
sleep 3
adb shell dumpsys activity activities | grep -E 'topResumedActivity|mResumedActivity'
adb shell pidof com.olaelectric.hmiclient
```

Record: resolve-activity result, top activity after HOME, whether `hmiclient` still runs. **Changes the scooter: owner go-ahead.** Undo: `adb shell cmd package set-home-activity com.olaelectric.hmiclient/.MainActivity` or `bash sdk/host/test/hmi-swap.sh stock`.

### M-render (GL renderer looks)

The sim uses the software renderer; the scooter uses Skia on OpenGL. With the dash in front, capture the strip and the lock screen:

```sh
adb exec-out screencap -p > tmp/gl-strip.png        # riding or parked, a few telltales lit
```

Record: unlit telltale outlines are crisp (not blurred or missing), lit glyphs fill cleanly, lock-screen text and keys match the sim captures. Lock the scooter and capture again for the lock screen.

### M-dev

Read-only unless noted.

| Item | Line | Record |
|---|---|---|
| Light sensor | `adb shell dumpsys sensorservice \| grep -i light` | present yes/no, name, range |
| Clock after cold boot, no network | after a cold boot with no network: `adb shell date; adb shell settings get global auto_time` | date correct yes/no, `auto_time` value |
| Package installer | `adb shell pm path com.android.packageinstaller` | path or empty |
| HTTPS to GitHub | first `adb shell pm resolve-activity -a android.intent.action.VIEW -d https://github.com` (is there a browser?) and `which curl` in the vendor shell; then `adb shell am start -a android.intent.action.VIEW -d https://github.com`, or `curl -sI https://github.com` in the vendor shell | page loads yes/no; certificate error text if any; "no probe available" if neither exists. Vendor-shell curl does not use Android's CA store, which is what E6 needs, so a browser result counts for more |
| Panel follows brightness | `adb shell settings get system screen_brightness`; then `adb shell settings put system screen_brightness 30`; observe the panel within 5 s (hmiclient may override it); undo with the value read first | panel changes yes/no |
| SAW grant | `adb shell appops get dev.olatool.dash SYSTEM_ALERT_WINDOW`; `adb shell appops set dev.olatool.dash SYSTEM_ALERT_WINDOW allow` | grant works yes/no. The background-start test is deferred to E2: `am start` from a root shell is never a background start |

Brightness and SAW: **changes the scooter: owner go-ahead.** Undo: `adb shell settings put system screen_brightness <value read first>`; `adb shell appops set dev.olatool.dash SYSTEM_ALERT_WINDOW default`. If the panel only follows `setScooterBrightnessLevel`, say so; whether that counts as a vehicle command goes in the D-log before any code uses it.

### M-dpad

Handlebar buttons, parked then riding (riding supervised by the owner). The host writes handlebar callbacks to `calls-*.log`.

```sh
# press each handlebar button once, noting the order
adb pull /sdcard/Android/data/dev.olatool.dash/files/logs tmp/logs
grep onDpad_ tmp/logs/calls-*.log
```

Record per button: callback fired parked yes/no, riding yes/no, and what the stock HMI does with it (watch the stock screen with `hmiclient` enabled). Also keep the raw `tmp/logs/can-*.log` for the `ola-can-reference` observations (`0x6AD` is a hypothesis, not a fact).

### M-aa (optional, E7.S1 spike)

Only if the owner's phone is there. Parked. Installing the receiver **changes the scooter: owner go-ahead**; undo: `adb shell pm uninstall com.andrerinas.headunitrevived`. Write the result in `docs/aa-spike.md` (go/no-go), numbers also here.

```sh
adb shell pm list packages | grep headunitrevived        # installed? pin release and sha256
adb shell dumpsys meminfo com.andrerinas.headunitrevived | grep 'TOTAL PSS'   # during a session
adb shell dumpsys meminfo dev.olatool.dash | grep 'TOTAL PSS'
adb shell 'cat /vendor/etc/media_codecs*.xml' | grep -E 'avc|hevc'   # decoders
```

Record: connect route (Headunit Server on shared Wi-Fi first), seconds from connect to video, touch-to-screen latency (by feel or 240 fps phone video), decoder name, host + receiver PSS, audio route, touch works, how to return to the dash, whether the receiver can leave a margin for the dash bar, whether it exposes navigation state to other apps. No phone sign-in on the scooter; the phone is the phone's.

## After

```sh
bash sdk/host/test/hmi-swap.sh stock
bash sdk/host/test/hmi-swap.sh status
```

Check: stock HMI home, `hmiclient` enabled, brightness restored, dash `active` restored. Commit measurements.md.
