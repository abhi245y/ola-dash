# Store

`index.json` is the catalogue the dash store client reads (format: [schema.md](schema.md)). It is unsigned in 1.0 (PLAN D6): the client relies on HTTPS from GitHub, the SHA-256 of each download, the signing-cert pin of each plugin, and a `seq` that never goes down. Whoever can merge to `main` controls the catalogue.

## Submit

1. Build your theme zip (theme folder, see schema.md for limits) or your signed plugin APK.
2. Upload it as a GitHub release asset in your own repo.
3. Open a PR here that adds one entry to `store/index.json` and raises `seq` by 1. For a plugin, `python3 tools/store/check_plugin_apk.py your.apk` prints the JSON fragment; paste it verbatim (needs `aapt2` and `apksigner` from Android build-tools).

## Trust model

A store PR is merged only when its diff touches `store/index.json` alone. PRs touching `tools/`, `.github/`, `sdk` or `.gitmodules` are reviewed as code, and the store checks are re-run from main against the submitted index and assets. A passing check from modified PR code is not trusted. `.github/CODEOWNERS` assigns these paths to the maintainer.

Branch protection must require "up to date before merging" so two PRs cannot merge catalogue changes with the same `seq`.

## What CI checks (`.github/workflows/store.yml`)

- `check_index.py`: schema, unique ids, reserved theme ids and plugin package prefixes, GitHub release-asset URLs, download size caps (4 MB themes, 50 MB plugins), `seq` not lower than `origin/main`'s. An unparseable index on `origin/main` fails the check.
- For each new or changed entry: the download matches `size` and `sha256`.
- Themes (`check_theme_zip.py`): safe unpack with the caps, then the SDK's `check-themes.sh` (import guard, banned words, host-font check, sandbox fixtures), then riding (t=20) and locked captures, uploaded as the `store-previews` artifact.
- Plugins (`check_plugin_apk.py`): no `SYSTEM_ALERT_WINDOW`, `BIND_ACCESSIBILITY_SERVICE`, `BIND_DEVICE_ADMIN`, `BIND_NOTIFICATION_LISTENER_SERVICE`, `REQUEST_INSTALL_PACKAGES`, `PACKAGE_USAGE_STATS`, no HOME activity or manifest resource references, no reference in any APK entry to `com.olaelectric.vehicleparser`, `com.olaelectric.vehicleinterface`, `ICommanderService`, `dalvik.system.DexClassLoader`, `dalvik.system.InMemoryDexClassLoader` or `dalvik.system.DexFile` (including slashed forms), no `.dex .jar .apk .zip .so` files under `assets/`, a `dev.olatool.dash.plugin.PLUGIN` service, and the entry's package, versionCode, cert, slots and permissions equal what the APK declares.

The APK checker is a tripwire, not a sandbox: runtime-built strings evade it. The real guarantee is that a plugin is an ordinary app the owner enables per slot; the host gives it a display-only API and does not sandbox the Android app.

## Reviewer rules (PLAN E6.S1 T4)

- A theme must not draw a passcode or PIN entry, or anything that looks like the host keypad.
- Open the CI captures. Every number a theme draws must match the sim's mock values for that capture (riding at t=20; the locked capture shows no vehicle numbers). A theme that shows a static or invented speed, range or battery is refused.
