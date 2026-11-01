# E4.S6 day-look concept boards (Ola Dash, unofficial electric-scooter dashboard)

Goal: a light **day** look for three themes whose current dark look becomes their **night** look. Owner rule (D14): every first-party theme has day and night, switched by one flag. The day look keeps the night look's layout, geometry, fonts, sizes and every element in the same place; **only colours change**. Do not add, remove, move or resize anything. The night references in this folder (`ref-night-*.png`) are captures of the shipped themes: trace their layout exactly, but use the shared numbers below.

Shared facts: landscape 1280x768 screen, edge to edge, no device frame, no brand marks, crisp readable text, solid flat colours (no gradients, glow, texture, shading, bevels). The top 48 px is the host warning-light strip and stays exactly as in the references: a dark band in both looks, real scooter lights only, lit ones in their status colour. The yellow square hub button at the strip's far right appears on the parked/charging boards only, none on the riding boards (as in the references). Status colours (green, blue, amber, red) belong only to the strip's lights. Every fact appears once per screen. Numbers, written exactly like this: speed 42 km/h, mode Sport, battery 68 %, range 54 km, trip 12.4 km, odometer 3,218 km, clock 18:24, power 2.0 kW, pack temperature 31 °C.

Day rules for all three: for direct Indian sunlight on a glossy panel. Light warm ground, near-black ink. Primary text at least 7:1 on the ground, secondary text at least 4.5:1. Lines that carry meaning (dial scales and ticks, gauge tracks, bar outlines and empty cells, row dividers) at least 3:1 on the ground; purely decorative borders may be lighter. Accent never looks like a status colour.

## Theme 1: Twin Dial (day)
References: `ref-night-twin-ride.png`, `ref-night-twin-charge.png`. Look "Instrument" in daylight: a printed precision gauge face. Ground #F6F3EC. Dial face fill = the ground #F6F3EC; rims, scales, ticks and numerals #0F2A2A; secondary text (km/h, kW, RANGE, TRIP, BATTERY, PACK labels, small-dial end marks) #4A5C5C. Needle exactly #803D0D (burnt copper: the night needle #FF7A1A mixed 50 % with black; this is how every accent option becomes its day colour, so draw exactly that). Regen side of the power dial exactly #4A5C6C (neutral slate). Small battery and pack dials follow the same inks.
IMAGE twin-day-ride.png: riding as in the riding reference, at 42 km/h and 2.0 kW.
IMAGE twin-day-park.png: parked and charging as in the charging reference.

## Theme 2: Terminal (day)
References: `ref-night-term-ride.png`, `ref-night-term-charge.png`. Same monospace font, fixed columns, rows, block-character bar gauges and `>` prompt with a block cursor. Day idea: an e-ink or printout terminal. Ground #F4F1EA. Ink exactly #0F5A2E (deep phosphor green) for values, the hero speed and bar fills; labels, empty bar cells and row dividers in one dim green that still reaches 4.5:1 on the ground (no transparency). No scanlines. Boards show the green option only.
IMAGE term-day-ride.png: riding as in the riding reference, with the shared numbers.
IMAGE term-day-park.png: parked and charging as in the charging reference.

## Theme 3: Minimal (day)
References: `ref-night-min-ride.png`, `ref-night-min-park.png`. Plain text layout: Settings and trunk buttons, clock, big speed with unit and mode, battery/range/trip line, media card with Pause/Next, Android Auto. Day: ground #F6F3EC, text #0F2A2A, secondary text #4A5C5C, buttons and media card flat #EDE8DD, no border, button text #0F2A2A; disabled Open trunk text #4A5C5C on that fill, no transparency.
IMAGE min-day-ride.png: riding at 42 km/h, Sport, as in the riding reference.
IMAGE min-day-park.png: parked as in the parked reference.

## Outputs
- The six PNGs above, 1280x768, 8-bit RGB.
- `compare.png`: per theme one row: night ride reference, day ride, day park; 8-bit, under 2 MB.
- `critique.md`: per theme, what works, what fails (sunlight contrast, anything that moved or changed shape against the reference, accent too close to a status colour), up to three changes before implementation, and measured contrast on the day ground for: primary text, secondary text, meaning-bearing lines; Twin Dial needle and regen; Terminal ink and dim.
- No absolute file paths in any written file.
