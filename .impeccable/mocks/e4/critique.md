# E4 concept critique

## Twin Dial — Instrument

Works: white speed dominates; copper needles give direction; requested numeric readouts appear once. Host strip is exactly 48 px, contains only nine listed lights plus hub, and uses correct riding/charging states.

Fails: dark minor scales, tiny electrical labels and bottom telemetry will disappear in sunlight. Reading needs no touch, but deciphering several dials costs riding attention. Parked needle crosses the digital zero. Ride needle position suggests more than 42; power scale and small gauge fills are approximate. Copper is too close to amber for confident peripheral distinction. Pack temperature lacks an explicit PACK label. Everything is drawable with Slint text, paths, arcs and sin/cos; subtle raster shading should be discarded.

Three changes before implementation:
1. Compute every needle and arc from calibrated numeric domains.
2. Enlarge support text, strengthen contrast, label PACK explicitly.
3. Reduce decorative ticks and separate copper from warning amber through luminance and shape.

## Terminal

Works: speed, units and fixed-column telemetry are readable; numeric facts occur once. Final 48 px host strip obeys content/state rules. Reading requires no tapping.

Fails: green-on-black looks bright indoors, but thin labels and scanlines lose clarity in sunlight. Near-equal row emphasis slows riding glances. Ride/park fonts and column positions drift. Block gauges approximate rather than faithfully encode values. CHG, prompt and host light repeat charging, as the requested concept itself requires. Green body text directly conflicts with the shared status-colour rule; this is the theme's explicit exception. Static images cannot prove cursor blinking. Slint can draw everything; raster phosphor shading adds no useful information.

Three changes before implementation:
1. Use one real monospace font, shared grid and stable hero size across states.
2. Remove scanlines/shading; enlarge and brighten secondary labels.
3. Compute gauge fills exactly and resolve the green/charging-duplication exceptions in the implementation contract.

## Zen

Works: strongest sunlight candidate. Huge black speed and two facts make riding glances cheap. Speed and battery occur once; reading needs no interaction. Final 48 px strip contains only listed lights and hub; charging stays outside body. Teal is distinct from warning green and blue.

Fails: battery fill looks closer to 70–72% than 68%; ride/park bar geometry differs. Speed sizing and alignment drift. Faint shading violates the solid background. Tiny hub is a poor bare-finger target. No graphic exceeds Slint paths, rounded rectangles and text; generated texture is unnecessary. Sunlight performance needs hardware testing.

Three changes before implementation:
1. Bind bar width to exactly 0.68 of one shared track.
2. Lock typography, baseline, margins and bar geometry across states.
3. Use exact flat colours and make the hub's invisible hit area fill its 48 px strip height.
