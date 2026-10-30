# Review r2: coverage of r1 and consistency (Fable)

Reviewed: PLAN.md r2. Code refs: SDK = ola-dash-sdk, crates = ~/.cargo/registry.

1. **PopupWindow covers the overlay after the sandbox.** A theme `PopupWindow { close-policy: no-auto-close; ... }` is drawn after the root tree (i-slint-core 1.18.1 window.rs `draw_contents`) and takes touches. No bundled theme uses popups or `std-widgets.slint`. Loader refuses files containing `PopupWindow`, `ContextMenuArea`, `MenuBar` or importing `std-widgets.slint`; fixture `evil3`.
2. **Host text inherits the theme font** (`theme_root.rs:64` forwards `default-font-family`; no host `Text` sets `font-family`). A blank-glyph TTF blanks alert text and keypad labels. Host elements use a bundled host font; store rejects theme fonts claiming a host family name; fixture `evil4`.
3. **Loader semantics.** `None` falls through to the filesystem (typeloader.rs:1470-1473): refuse with `Some(Err)`. Paths are cleaned, not canonicalized (fileaccess.rs:37): canonicalize, require under the canonical theme dir, refuse symlinks. The callback has no importer context and the root compile must serve `files/host`, so the probe is the gate. Sim compiles separately (sim/src/main.rs:549-562): put the loader in `theme_root.rs` so sim and `check-themes` use it.
4. **Negative tests pass vacuously.** evil2 imports an absolute laptop path. Move fixtures into the SDK with relative imports. evil1 must pass `sim --check` with an intact overlay (region compare against `themes/minimal`), evil2/3/4 must fail `sim --check`. Add `sim --compare-overlay`; references regenerate in E1.S2.
5. **Watchdog false-triggers on the plan's own blocking compiles.** Window = max(M-start x 3, 3 heartbeat periods, max M-compile + one period); write `busy-until` before every `spin_on` compile; while another app is in front, the dash bar's foreground service writes the heartbeat; AC adds "AA in front 30 min never triggers restore".
6. **`copyAssets` overwrites store updates and resurrects uninstalls** (MainActivity.java:109-132). Bundled pack ids are reserved: they update with the host, the store cannot update or remove them. State the id charset `[A-Za-z0-9_-]{1,64}` (lib.rs:285-287).
7. **Milestones vs dependencies.** Session B needs SAW and usage-stats grants by hand over the root service. E0.S6 last in M2. M4 row: E4.S4 after E8. E0.S3.T1 must not name the dash bar.
8. **Strip geometry.** Strip is 48/72 px in the contract; hub button 64 px won't fit. Decide: strip stays 48/72, hub button 64 x 48 is the one documented exception (or v7 strip 64 px with 48/72 kept for v6 themes).
9. **Two stories own the Theme pane.** E1.S4 = list + switch + night on/off; E3.S1 = options controls + auto night. Security rail item has no story. Plugins pane belongs in E1.S4.
10. **Restart branch.** `set_platform` returns `AlreadySet` on a second `android_main` in one process (slint android.rs:153-166; lib.rs:508-511). If recreate fails, restart = `System.exit(0)` + relaunch.
11. **Replay is partial.** `pushAlerts()` and `UnlockController.publish()` call `nativeSet` directly; slots 30-39 are not in `REAL[]`. Replay = `REAL[]` + `pushAlerts()` + `UnlockController.publish()` + clock + parked + plugin snapshot.
12. **Mirrors scope.** Needed for the seven `Vehicle.*` telltale reads (overlay.slint:139-149) and clock/battery (:320-321); alert, side stand, fault, auth are already `HostState`. Host screens, hub button and dash bar read only `HostState`/Java state. Guarantee 3 covers host-drawn elements; theme-drawn values are controlled by store review.
13. **Keep-alive blind under AA** (r1 safety 7 dropped): bar window uses `FLAG_WATCH_OUTSIDE_TOUCH` to feed `TOUCHED`; verify in session B.
14. **First-run card unreachable** if speed 0 is never replayed: show it when parked or `state == park` with speed unknown; it launches nothing.
15. **Wording:** `MIRRORS` mirrors `Dash` outputs today; inbound `opt-<id>` is new work.
16. **Rejecting `BIND_NOTIFICATION_LISTENER_SERVICE` blocks third-party media plugins**: media slot = host built-in source only in 1.0, or allow with review.

r1 items dropped silently or partly: safety 7 (watch-outside-touch), safety 2 (Java tick), safety 9 (unlock-preview test), safety 11 (hub button in safety.md host-fixed list), safety 15 (D-log brightness decision), safety 16 (`AUTO_TIME`), scope 2 (second init), scope 3 (replay), scope 7 (release before store), install 1/9 (re-run after OTA doc), install 3a (index ≤ 1 MB), install 5 (Wi-Fi once, cellular unmeasured).

Verified: `set_file_loader` exists (api.rs:986); `REAL[]` vehicle slots only; `TrunkGate` tri-state; `MIRRORS` out-only; `copyAssets` overwrites; `spin_on` at lib.rs:324,329. A theme re-declaring `global HostState` is harmless (only root exports are public). `@image-url` bypasses the loader but only displays a file.

Verdict: E0.S2 as written leaves guarantee 1 false (popups, inherited font, symlinks, loader semantics); the watchdog numbers false-trigger on blocking compiles. Rest is ordering, ownership and wording.
