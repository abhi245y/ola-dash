# Day-look board critique

Six boards were generated with the built-in image tool, then given one targeted colour/strip correction pass. Pillow normalized exports to 1280×768, 8-bit RGB; it did not repaint the boards. These are concept boards, not pixel-exact implementation assets: the generator retained small geometry changes, approximate colours and subtle tonal variation despite explicit constraints.

`compare.png` is 1920×1290, RGB, 1,599,355 bytes: one row per theme, with night ride, day ride and day park columns. Source hashes confirm `prompts.md` and all six references remained unchanged. Generation prompts are recorded in `generation-prompts.md` and `correction-prompts.md`.

## Measurement method

Contrast uses linearized sRGB relative luminance: channels ≤0.04045 are divided by 12.92; other channels use `((c+0.055)/1.055)^2.4`. Luminance weights are 0.2126, 0.7152 and 0.0722. Ratio is `(Llighter+0.05)/(Ldarker+0.05)`.

Two sets of results follow: exact specified palette calculations, and measurements from exported riding PNGs. Sample measurements use median RGB from named regions, selecting pixels near the intended colour and excluding antialiased boundaries with a one-pixel erosion where possible. Coordinates and measured RGB values are in `contrast-measurements.json`; `build_outputs.py` reproduces them. These are representative interior samples, not worst-case ratios over every pixel or sunlight measurements. Parked boards were inspected visually; their text ratios are not separately certified.

Thresholds: primary text 7:1; secondary text 4.5:1; meaning-bearing lines, tracks and cells 3:1. Strong digital contrast helps sunlight legibility but does not measure glossy-panel reflections or panel luminance.

## Twin Dial

**Works.** Warm instrument ground, dark numerals and slate regen preserve the two-dial hierarchy. Copper remains distinct from the luminous green warning lights. Battery, pack, range, trip and clock remain in their existing slots. Riding shows 42 km/h and 2.0 kW; parked keeps 0 and P.

| Role | Specified colour on #F6F3EC | Palette ratio | PNG sample on #F4F3EB | Sample ratio |
|---|---|---:|---|---:|
| Primary text | #0F2A2A | 13.68:1 | #09292C | 13.82:1 |
| Secondary text | #4A5C5C | 6.37:1 | #344C53 | 8.24:1 |
| Main scales/ticks | #0F2A2A | 13.68:1 | #0A2B30 | 13.47:1 |
| Needle | #803D0D | 7.31:1 | #8C4614 | 6.30:1 |
| Regen | #4A5C6C | 6.24:1 | #4F6571 | 5.50:1 |
| Empty small-gauge track | Dark meaning-bearing ink required | ≥3:1 required | #C6CBCF | **1.47:1 — fail** |

**Fails.** Pale unfilled small-dial tracks disappear against the ground and fail 3:1. Main ink and secondary text pass their thresholds, but none of the sampled role colours equals the requested hex exactly. Needle is lighter and more orange than specified, increasing resemblance to amber; it still reads as burnt copper beside the green lights. Regen remains neutral slate rather than status blue.

Geometry is close, not traced exactly. Large rims and inner arcs were redrawn; needle bodies are thicker, hubs larger and some numeral spacing changed. The sampled upper rim starts at y=71 versus y=72 in the reference. Bottom horizontal rule is inset instead of edge-to-edge. At x=700, the day ground starts at y=45 on ride and y=53 on park; the host strip should end at y=48. Warning glyphs were also redrawn. Pixel comparison of the first 48 rows differs at 99.99% of ride pixels and 99.96% of park pixels, largely from tiny colour/background changes; those percentages are not geometric displacement percentages. Flat-colour rule also fails: a blank ground patch spans 2/3/2 RGB channel levels.

**Before implementation — three changes:**

1. Use shipped geometry, font metrics, strokes and the unchanged 48-pixel host strip; change only theme tokens and live values.
2. Apply exact flat palette, including #803D0D copper and #4A5C6C regen. Darken every empty gauge track to a specified meaning-bearing ink with ≥3:1 contrast.
3. Bind needles and fill arcs to the displayed data. Parked charging retains requested 2.0 kW here; confirm runtime charge-sign convention and needle direction when connecting telemetry.

## Terminal

**Works.** Left hero/right fixed-row structure survives, including block bars, all eight rows, prompt and cursor. Requested text values are present, including 3,218 km. Dim labels, dividers and empty cells remain visible on the warm ground; no scanlines were added.

| Role | Specified colour on #F4F1EA | Palette ratio | PNG sample on #F2EFE8 | Sample ratio |
|---|---|---:|---|---:|
| Primary text / ink | #0F5A2E | 7.38:1 | #0E5E31 | **6.86:1 — fail 7:1** |
| Secondary / dim labels | #46604B | 6.13:1 | #39513E | 7.56:1 |
| Meaning-bearing row dividers | #46604B | 6.13:1 | #2A4A35 | 8.59:1 |
| Empty bar cells | #46604B | 6.13:1 | #466754 | 5.49:1 |

**Fails.** Specified ink passes 7:1, but the generator lightened it and darkened the ground enough for sampled hero contrast to fall below 7:1. Labels, dividers and empty cells became different greens instead of one dim colour. Thin individual dots and light seams between filled blocks can disappear in glare even where sampled dark dot interiors pass.

Font remains monospace in character but is heavier than the reference; hero glyph construction, label weight, cursor height, dot lattice and bar segmentation changed. Rows drift slightly downward. The dark band ends at y=52 on ride and y=54 on park at x=700, rather than y=48. First-48-row pixel differences are 20.13% and 25.34%, so the host strip is not literally preserved. Battery fill looks closer to two-thirds than an exact 68%; the parked and riding power bars differ despite both reading 2.0 kW. Blank ground patch spans 2/2/2 RGB channel levels, violating perfectly flat colour.

Green body ink is an explicit theme exception to the general strip-only status-colour rule. Deep phosphor green is darker than the lit strip green, but shares its hue family. It must remain a stable theme colour, never imply readiness or success.

**Before implementation — three changes:**

1. Retain original monospace font, row/column coordinates, block glyphs, cursor and unchanged host strip.
2. Apply exact #F4F1EA ground, #0F5A2E ink and opaque #46604B for every dim role; this restores specified 7.38:1 primary contrast and removes texture.
3. Derive all bar fills from telemetry and existing scales; verify 68%, 42 km/h and 2.0 kW against numeric readouts, including charging direction.

## Minimal

**Works.** Hero, controls, clock, battery/range/trip and media controls retain the reference arrangement. Parked P and start instruction remain. Disabled trunk copy is readable without transparency. Neutral ink avoids status-colour confusion.

| Role | Specified colour on #F6F3EC | Palette ratio | PNG sample on #F6F3EC | Sample ratio |
|---|---|---:|---|---:|
| Primary text | #0F2A2A | 13.68:1 | #0F2D2C | 13.23:1 |
| Secondary text | #4A5C5C | 6.37:1 | #415656 | 7.04:1 |
| Disabled trunk text | #4A5C5C | 6.37:1 | #43595B | 6.72:1 |
| Meaning-bearing lines | None in reference | N/A | None added | N/A |

On the specified button fill #EDE8DD, primary text reaches 12.41:1 and disabled text 5.77:1. Actual disabled text on sampled fill #ECE6DA reaches 5.99:1. Fill-to-ground contrast is only 1.10:1 specified and 1.12:1 sampled; that is intentional for the requested borderless treatment, not a line-contrast pass. Visible labels carry the controls' identity.

**Fails.** Card and button surfaces, dark hero ink and host strip retain tonal variation. Ground patch spans 2/3/2 channel levels, even though its median matches #F6F3EC. Font appearance and hero spacing are close but not identical. Media blocks stop above the bottom edge rather than extending to the reference edge; corner rounding and text baselines also drift. At x=700 the strip ends at y=51 on ride and y=52 on park. First-48-row pixel differences are 99.59% and 100.00%, mostly background/antialias differences rather than wholesale relocation. No new status-coloured accent appears outside the strip.

**Before implementation — three changes:**

1. Keep existing font metrics, control rectangles, corner radii, media bottom edge and the exact 48-pixel host strip.
2. Apply exact solid background, ink, secondary and fill tokens; remove generated texture and shading.
3. Keep disabled trunk text opaque #4A5C5C and verify its disabled behaviour independently of the subtle colour distinction.

## Data interpretation

Shared readings replace existing fields only. Riding uses Sport and 42; parked keeps reference 0/P instead of showing a moving speed while parked. Minimal parked retains its start instruction. Odometer appears only in Terminal; power and pack temperature appear only where the reference contains them. Adding missing fields would violate the stronger layout/no-new-elements constraint. Media metadata remains unchanged. Both charging boards display the literal requested 2.0 kW; charging state is supplied by the strip light, not an invented minus sign.

All requested files exist and pass format checks. Remaining exact-palette, flatness and geometry failures above prevent treating these generated boards as implementation approval.
