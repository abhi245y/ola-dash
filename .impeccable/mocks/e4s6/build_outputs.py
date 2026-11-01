"""Export generated boards, build comparison, and measure sampled sRGB contrast.

Optional arguments: six generated source images in NAMES order. Without arguments,
rebuild comparison and measurements from exported boards. No repainting is done.
"""
from pathlib import Path
import hashlib
import json
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

NAMES = [f'{theme}-day-{state}.png' for theme in ('twin', 'term', 'min') for state in ('ride', 'park')]

if len(sys.argv) > 1:
    assert len(sys.argv) == 7, 'Supply exactly six generated sources.'
    for name, source in zip(NAMES, sys.argv[1:]):
        with Image.open(source) as im:
            original_size = im.size
            im = im.convert('RGB').resize((1280, 768), Image.Resampling.LANCZOS)
            im.save(name, optimize=True)
            print(name, original_size, '->', im.size)

def rgb(value):
    return np.array([int(value[i:i+2], 16) for i in (1, 3, 5)], dtype=float)

def hexrgb(value):
    return '#' + ''.join(f'{int(round(c)):02X}' for c in value)

def luminance(value):
    v = np.asarray(value, dtype=float) / 255
    v = np.where(v <= .04045, v / 12.92, ((v + .055) / 1.055) ** 2.4)
    return float(v @ [.2126, .7152, .0722])

def contrast(a, b):
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + .05) / (lo + .05)

def sample(arr, box, target=None):
    x0, y0, x1, y1 = box
    region = arr[y0:y1, x0:x1].astype(float)
    if target is None:
        pixels = region.reshape(-1, 3)
    else:
        limit = 30 if min(rgb(target)) > 170 else 65
        mask = np.linalg.norm(region - rgb(target), axis=2) < limit
        core = mask.copy()
        core[1:] &= mask[:-1]
        core[:-1] &= mask[1:]
        core[:, 1:] &= mask[:, :-1]
        core[:, :-1] &= mask[:, 1:]
        pixels = region[core if core.sum() >= 5 else mask]
        assert len(pixels), (box, target)
    return np.median(pixels, axis=0)

CONFIG = {
    'twin': ((610, 85, 670, 140), {
        'primary': ((245, 385, 395, 490), '#0F2A2A'),
        'secondary': ((282, 500, 370, 540), '#4A5C5C'),
        'scale_ticks': ((315, 80, 340, 115), '#0F2A2A'),
        'needle': ((180, 130, 330, 330), '#803D0D'),
        'regen': ((720, 120, 845, 510), '#4A5C6C'),
        'empty_gauge_track': ((560, 565, 590, 625), '#CBD0D2'),
    }),
    'term': ((475, 80, 565, 140), {
        'primary_ink': ((32, 250, 365, 450), '#0F5A2E'),
        'secondary_dim': ((635, 100, 710, 140), '#46604B'),
        'row_divider': ((640, 146, 1245, 152), '#46604B'),
        'empty_cells': ((970, 99, 1084, 137), '#46604B'),
    }),
    'min': ((510, 90, 700, 150), {
        'primary': ((500, 240, 770, 415), '#0F2A2A'),
        'secondary': ((530, 425, 750, 465), '#4A5C5C'),
        'disabled_text': ((285, 88, 445, 115), '#4A5C5C'),
        'button_fill': ((55, 75, 220, 85), None),
    }),
}

measurements = {}
for theme, (ground_box, roles) in CONFIG.items():
    name = f'{theme}-day-ride.png'
    arr = np.asarray(Image.open(name).convert('RGB'))
    ground = sample(arr, ground_box)
    records = {}
    for role, (box, target) in roles.items():
        value = sample(arr, box, target)
        records[role] = {'rgb': hexrgb(value), 'contrast': round(contrast(value, ground), 3), 'roi': box}
    ground_pixels = arr[ground_box[1]:ground_box[3], ground_box[0]:ground_box[2]].reshape(-1, 3)
    measurements[theme] = {'ground': hexrgb(ground), 'ground_roi': ground_box,
                           'ground_channel_span': np.ptp(ground_pixels.astype(int), axis=0).tolist(),
                           'roles': records}

for name in NAMES:
    theme = name.split('-')[0]
    reference = f'ref-night-{theme}-' + ('ride.png' if 'ride' in name else ('park.png' if theme == 'min' else 'charge.png'))
    a = np.asarray(Image.open(name))[:48]
    b = np.asarray(Image.open(reference).convert('RGB'))[:48]
    measurements.setdefault('strip', {})[name] = round(float(np.any(a != b, axis=2).mean() * 100), 2)

Path('contrast-measurements.json').write_text(json.dumps(measurements, indent=2) + '\n')

# Pillow's bundled default font keeps this script portable and paths relative.
font = ImageFont.load_default(size=22)
small = ImageFont.load_default(size=18)
canvas = Image.new('RGB', (1920, 1290), '#E2DED5')
draw = ImageDraw.Draw(canvas)
for i, (theme, title) in enumerate((('twin', 'Twin Dial'), ('term', 'Terminal'), ('min', 'Minimal'))):
    top = i * 430
    for col, heading in enumerate((f'{title} | Night ride', f'{title} | Day ride', f'{title} | Day park')):
        draw.text((col * 640 + 12, top + 10), heading, font=font, fill='#0F2A2A')
    for col, name in enumerate((f'ref-night-{theme}-ride.png', f'{theme}-day-ride.png', f'{theme}-day-park.png')):
        with Image.open(name) as im:
            canvas.paste(im.convert('RGB').resize((640, 384), Image.Resampling.LANCZOS), (col * 640, top + 40))
canvas.save('compare.png', optimize=True)
assert Path('compare.png').stat().st_size < 2_000_000

checksums = json.loads(Path('.source-checksums.json').read_text())
assert all(hashlib.sha256(Path(name).read_bytes()).hexdigest() == value for name, value in checksums.items())
for name in NAMES + ['compare.png']:
    with Image.open(name) as im:
        assert im.mode == 'RGB'
        if name != 'compare.png':
            assert im.size == (1280, 768)
    assert Path(name).read_bytes()[24] == 8  # PNG IHDR bit depth
print(json.dumps(measurements, indent=2))
print('compare.png bytes:', Path('compare.png').stat().st_size)
print('All seven source files unchanged; PNG dimensions, RGB and bit depth verified.')
