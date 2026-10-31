# Store index format

`store/index.json` is a single JSON object. It is at most 1 MB. The store client fetches it over HTTPS from GitHub and refuses a `seq` lower than the last one it accepted.

```json
{"seq": 1, "themes": [], "plugins": []}
```

| Field | Type | Rule |
|---|---|---|
| `seq` | integer >= 1 | Never decreases, and goes up whenever the themes or plugins change. `tools/store/check_index.py` compares it with `origin/main`. |
| `themes` | array | Theme entries. |
| `plugins` | array | Plugin entries. |

Unknown keys are refused (they catch typos).

## Theme entry

| Field | Type | Rule |
|---|---|---|
| `id` | string | `[a-z0-9-]{1,64}` (the SDK theme id rule), unique in `themes`, equals `id` in the zip's `theme.json`. Reserved (any case): `default`, `fallback`, `last-resort`, `active`, `previous`, `bad`, `strikes`, `restart` (host selection files in `files/themes/`), and every folder in this repo's `themes/` (and the SDK's `themes/`). |
| `name` | string | Display name. |
| `version` | string | Display version, e.g. `1.2.0`. |
| `author` | string | |
| `licence` | string | SPDX id, e.g. `GPL-3.0-or-later`. |
| `url` | string | `https://github.com/...` release asset (zip). |
| `size` | integer | Bytes of the zip as downloaded, 1 through 4 MB (4 * 1024 * 1024). |
| `sha256` | string | 64 lowercase hex, of the zip. |
| `preview` | string | `https://github.com/...` URL of the preview PNG. |

## Plugin entry

| Field | Type | Rule |
|---|---|---|
| `package` | string | Android package name, unique in `plugins`; must not start with `dev.olatool.`, `com.olaelectric.`, `com.ola.`, `android.` or `com.android.`. |
| `name` | string | Display name. |
| `versionCode` | integer >= 1 | Matches the APK. |
| `url` | string | `https://github.com/...` release asset (APK). |
| `size` | integer | Bytes of the APK, 1 through 50 MB (50 * 1024 * 1024). |
| `sha256` | string | 64 lowercase hex, of the APK. |
| `cert_sha256` | string | 64 lowercase hex, SHA-256 of the signing certificate. The client pins it. |
| `slots` | array of string | Subset of `widgets`, `media`, `navigation`; what the manifest declares. |
| `permissions` | array of string | Every permission the APK requests. |

`tools/store/check_plugin_apk.py <apk>` prints `package`, `versionCode`, `cert_sha256`, `slots` and `permissions` as the JSON fragment to paste into the entry.

## Packages

A theme package is a zip of the theme folder (files at the zip root, or inside one top-level folder). Theme ids are `[a-z0-9-]{1,64}`. Limits: 200 entries, 2 MB inflated, extensions `.slint .json .png .svg .ttf .otf .ttc .txt`, PNGs up to 2048 x 2048 with at most 16,000,000 decoded pixels across all PNGs, SVGs at most 256 KB (256 * 1024 bytes), and `preview.png` required. Only ZIP_STORED and ZIP_DEFLATED compression is accepted. Names must not contain control characters or duplicate another name ignoring case.

At most 3 animation-tick calls are counted across every `.slint`, `.txt` and `.json` file, comments included. Both `animation-tick` and `animation_tick`, with whitespace before `(`, count. This count is a hint; the runtime guard is the control. `tools/store/check_theme_zip.py` enforces these package checks and then runs the SDK's `check-themes.sh`.
