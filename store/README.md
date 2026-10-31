# Store

`index.json` is the catalogue the dash store client reads (format: [schema.md](schema.md)). It is unsigned in 1.0 (PLAN D6): the client relies on HTTPS from GitHub, the SHA-256 of each download, the signing-cert pin of each plugin, and a `seq` that never goes down. Whoever can merge to `main` controls the catalogue.

## Submit

1. Build your theme zip (theme folder, see schema.md for limits) or your signed plugin APK.
2. Upload it as a GitHub release asset in your own repo.
3. Open a PR here that adds one entry to `store/index.json` and raises `seq` by 1. For a plugin, `python3 tools/store/check_plugin_apk.py your.apk` prints the fragment to paste (needs `aapt2` and `apksigner` from Android build-tools).

## What CI checks (`.github/workflows/store.yml`)

- `check_index.py`: schema, unique ids, reserved ids, `https://github.com/` URLs, `seq` not lower than `origin/main`'s.
- For each new or changed entry: the download matches `size` and `sha256`.
- Themes (`check_theme_zip.py`): safe unpack with the caps, then the SDK's `check-themes.sh` (import guard, banned words, host-font check, sandbox fixtures), then riding (t=20) and locked captures, uploaded as the `store-previews` artifact.
- Plugins (`check_plugin_apk.py`): no `SYSTEM_ALERT_WINDOW`, `BIND_ACCESSIBILITY_SERVICE`, `BIND_DEVICE_ADMIN`, `BIND_NOTIFICATION_LISTENER_SERVICE`, `REQUEST_INSTALL_PACKAGES`, `PACKAGE_USAGE_STATS`, no HOME activity, no reference to `com.olaelectric.vehicleparser`, `com.olaelectric.vehicleinterface` or `ICommanderService`, a `dev.olatool.dash.plugin.PLUGIN` service, and the entry's package, versionCode, cert, slots and permissions equal what the APK declares.

CI cannot see everything. A plugin is an ordinary Android app that the host does not sandbox.

## Reviewer rules (PLAN E6.S1 T4)

- A theme must not draw a passcode or PIN entry, or anything that looks like the host keypad.
- Open the CI captures. Every number a theme draws must match the sim's mock values for that capture (riding at t=20; the locked capture shows no vehicle numbers). A theme that shows a static or invented speed, range or battery is refused.
