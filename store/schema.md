# Store index format

`store/index.json` is a single JSON object. It is at most 1 MB. The store client fetches it over HTTPS from GitHub and refuses a `seq` lower than the last one it accepted.

```json
{"seq": 1, "themes": [], "plugins": []}
```

| Field | Type | Rule |
|---|---|---|
| `seq` | integer >= 1 | Never decreases. `tools/store/check_index.py` compares it with `origin/main`. |
| `themes` | array | Theme entries. |
| `plugins` | array | Plugin entries. |

Unknown keys are refused (they catch typos).

## Theme entry

| Field | Type | Rule |
|---|---|---|
| `id` | string | `[A-Za-z0-9_-]{1,64}`, unique in `themes`, equals `id` in the zip's `theme.json`. Reserved (any case): `default`, `fallback`, `last-resort`, `active`, and every folder in this repo's `themes/` (and the SDK's `themes/`). |
| `name` | string | Display name. |
| `version` | string | Display version, e.g. `1.2.0`. |
| `author` | string | |
| `licence` | string | SPDX id, e.g. `GPL-3.0-or-later`. |
| `url` | string | `https://github.com/...` release asset (zip). |
| `size` | integer | Bytes of the zip as downloaded. |
| `sha256` | string | 64 lowercase hex, of the zip. |
| `preview` | string | `https://github.com/...` URL of the preview PNG. |

## Plugin entry

| Field | Type | Rule |
|---|---|---|
| `package` | string | Android package name, unique in `plugins`. |
| `name` | string | Display name. |
| `versionCode` | integer >= 1 | Matches the APK. |
| `url` | string | `https://github.com/...` release asset (APK). |
| `size` | integer | Bytes of the APK. |
| `sha256` | string | 64 lowercase hex, of the APK. |
| `cert_sha256` | string | 64 lowercase hex, SHA-256 of the signing certificate. The client pins it. |
| `slots` | array of string | Subset of `widgets`, `media`, `navigation`; what the manifest declares. |
| `permissions` | array of string | Every permission the APK requests. |

`tools/store/check_plugin_apk.py <apk>` prints `package`, `versionCode`, `cert_sha256`, `slots` and `permissions` as the JSON fragment to paste into the entry.

## Packages

A theme package is a zip of the theme folder (files at the zip root, or inside one top-level folder). Limits: 200 files, 2 MB inflated, extensions `.slint .json .png .svg .ttf .otf .ttc .txt`, images up to 2048 x 2048, `preview.png` required, at most 3 `animation-tick(` uses. `tools/store/check_theme_zip.py` enforces them and then runs the SDK's `check-themes.sh`.
