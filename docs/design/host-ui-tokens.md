# Host UI design language: "Ride Buddy, day and night"

Owner-approved 2026-10-31 (plan decision D13). Applies to host-owned UI in the SDK: warning-light strip, alert cards,
lock screen, hub button and host screens (settings, launcher, switcher). Comps: SDK `.impeccable/mocks/e1s2/h-*.png`
(day and night, settings and lock). Themes still restyle the lock screen and host screens through `lock-style` (D2)
and the strip through `overlay-style`; these tokens are the host defaults.

## Rules

1. One fact per screen. The strip owns warning lights only. The clock, battery and lock state each appear once.
2. Two modes, same layout: day (light) and night (dark), switched by `HostState.night` (the host mirrors `Display.night`; default day).
3. The strip is the anchor: always dark teal in both modes, exactly 48 px top/bottom, 72 px left/right.
4. Selection is a thick sunny pill (fill `accent`, text `ink`). In day mode an outline selection uses `ink`, never yellow (yellow on the light ground is 1.4:1).
5. No scenery, gradients, glow or bevels. At most one small flat line illustration per screen, only in empty states.
6. Glove targets: 64 px minimum, 16 px gaps; the passcode keypad's Delete is the strong key, Clear is quiet and separated.
7. Warning-light semantic colours and minimum sizes stay host-fixed (telltale 28 px, alert text 32 px).

## Colour

| Token | Day | Night | Use |
|---|---|---|---|
| `bg` | `#F6F3EC` | `#0B1C1C` | screen ground |
| `surface` | `#FFFFFF` | `#163636` | cards, keys, rail |
| `surface-quiet` | `#EDE8DD` | `#102828` | pressed key, chips ("Current") |
| `line` | `#D9D2C3` | `#24504E` | hairlines, card borders |
| `text` | `#0F2A2A` | `#EFE6D6` | primary text (13.7:1 / 14.2:1 on `bg`) |
| `text-muted` | `#4A5C5C` | `#A9B5AE` | secondary text (6.4:1 / 8.3:1) |
| `accent` | `#FFC94A` | `#FFC94A` | selection pill, primary button fill, hub button |
| `ink` | `#0F2A2A` | `#0F2A2A` | text on `accent`; day-mode outline selection |
| `strip-bg` | `#0F2A2A` | `#071414` | warning-light strip |
| `strip-fg` | `#EFE6D6` | `#EFE6D6` | strip labels, unlit glyph outlines at 40 % |

Status colours are unchanged host constants (`OverlayTokens`): indicators green, high beam blue, side stand amber, fault and alerts red.

## Type

Host font family `OlaDash Host`, rebuilt from **Figtree** (OFL, humanist, strong weights) with `tools/subset-host-font.py`,
weights 500, 700, 800. Scale (px): strip label 16/700, caption 18/500, body 22/500, row 26/700, title 40/800,
keypad digit 44/700, clock 120/800. Tabular figures for clock, battery and digits. Nothing smaller than 16 px.

## Shape and spacing

8 px grid. Radius: key 18, card 20, panel 24, pill fully round. Rail row 72 px tall. Close button 64 px circle.
Keypad keys at least 180 x 96 px with 16 px gaps. Hub button: the strip's end cell, 64 x 48, `accent` fill, visible only
when parked, no alert, unlocked, not test mode.

## Screens

- **Strip**: dark band, lights as solid glyphs, lit in their status colour, unlit as 40 % `strip-fg` outlines; NO DATA and TEST DATA badges in its end cell.
- **Lock screen**: left column clock (120), date (22), battery `82%` with a small battery glyph (40); right column caption, six passcode cells, keypad. Lock and charging state only in the strip.
- **Settings**: left rail (rows 72 px, selected = pill), right pane with title, content, one primary button, close button; a small status line `18:24 · 82%` at the bottom right (the strip carries no clock or battery, so this is their one place).
- **Alert cards**: `surface` card on a 60 % scrim, red/amber frame by severity, icon + title (32) + one-line hint; same in both modes.
