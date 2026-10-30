# Review r3: final check (Fable)

Reviewed: PLAN.md r3. Verdict: blocked M1 only on E0.S2.T1 text; fixed in r3 final.

1. Entry file never reaches the file loader (`slint-interpreter-1.18.1/api.rs:1016-1018` reads it with `load_from_path`, a plain `read_to_string`); the entry needs the same path and keyword check in Rust. (PR1 implementation already does this.)
2. Add `Tooltip` to the banned words: it lowers to a synthesized `PopupWindow` (`passes/lower_tooltips.rs:4-7,43`). Not vectors: `inherits PopupWindow` (literal caught), builtin aliasing (refused, `typeloader.rs:1099`, `:1796-1800`), `Dialog` and nested `Window` (stay in the item tree, `passes/windows.rs:17-31`), full-screen theme `TouchArea` (below `HostOverlay`).
3. evil4 dropped and font collision guarded only by store CI, which never sees sideloaded or bundled themes. Register the host font from Rust before `load_ui`; `sim --check` rejects theme fonts containing the host family name; fixture evil4.
4. Font resolution in Slint 1.18.1 (Skia, parley/fontique 0.11.1): same-name registrations merge into one family in insertion order (`collection/mod.rs:769-779`, `family.rs:40-41`); `match_font` returns the first exact-weight face (`matching.rs:376-378`); custom fonts register in lexicographic path order (`collect_custom_fonts.rs:20-22`, `eval.rs:2371`). A unique name alone is not sufficient.
5. Fixtures must fail for the stated reason, not any reason (vacuous pass).
6. E0.S4 AC cited a `docs/testing.md` command that does not exist; spell it out.
7. Residuals: canonical contract dir; `sim --screen plugins` capture; HTTPS probe method; option property types rule.
