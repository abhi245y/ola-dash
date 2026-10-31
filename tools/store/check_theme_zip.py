#!/usr/bin/env python3
"""Store check for a theme zip (PLAN E6.S1 T1, T3).

usage: check_theme_zip.py THEME.zip [--out DIR] [--id ID]

Unpacks safely (counting inflated bytes), applies the package caps, runs the SDK's
tools/check-themes.sh on the result, then renders preview captures into --out.
Exits 1 with "REFUSED: <reason>" on the first problem.
"""
import argparse
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SDK = ROOT / "sdk"

ID_RE = re.compile(r"[a-z0-9-]{1,64}")
ALWAYS_RESERVED = {"default", "fallback", "last-resort", "active", "previous", "bad", "strikes", "restart"}
EXTS = {".slint", ".json", ".png", ".svg", ".ttf", ".otf", ".ttc", ".txt"}
MAX_FILES = 200
MAX_INFLATED = 2 * 1024 * 1024
MAX_IMAGE = 2048
MAX_SVG = 256 * 1024
MAX_PIXELS = 16_000_000
MAX_TICKS = 3


class Refuse(Exception):
    pass


def reserved_ids():
    ids = set(ALWAYS_RESERVED)
    for base in (ROOT / "themes", SDK / "themes"):
        if base.is_dir():
            ids |= {p.name.lower() for p in base.iterdir() if p.is_dir()}
    return ids


def check_id(theme_id):
    if not isinstance(theme_id, str) or not ID_RE.fullmatch(theme_id):
        raise Refuse(f"theme id {theme_id!r} does not match [a-z0-9-]{{1,64}}")
    if theme_id.lower() in reserved_ids():
        raise Refuse(f"theme id {theme_id!r} is reserved")


def unpack(zip_path, dest):
    """Extract into dest, return the theme.json dict. Raises Refuse."""
    try:
        zf = zipfile.ZipFile(zip_path)
    except (zipfile.BadZipFile, OSError) as e:
        raise Refuse(f"not a readable zip: {e}")
    with zf:
        infos = zf.infolist()
        if len(infos) > MAX_FILES:
            raise Refuse(f"{len(infos)} entries, more than {MAX_FILES}")
        names = [i.filename for i in infos]
        if len({n.casefold() for n in names}) != len(names):
            raise Refuse("duplicate entry names")
        for i in infos:
            n = i.orig_filename
            parts = n.split("/")
            if ("\\" in n or n.startswith("/") or re.match(r"[A-Za-z]:", n) or ".." in parts
                    or any(ord(c) < 32 or 127 <= ord(c) < 160 for c in n)):
                raise Refuse(f"unsafe path {n!r}")
            if i.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
                raise Refuse(f"{n!r}: compression type not supported")
            mode = i.external_attr >> 16
            if mode and stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR):  # 0: writers that set no type
                raise Refuse(f"{n!r} is a symlink or special entry")
            if not i.is_dir() and Path(n).suffix.lower() not in EXTS:
                raise Refuse(f"{n!r}: extension not allowed (allowed: {' '.join(sorted(EXTS))})")
        files = [i for i in infos if not i.is_dir()]
        # theme folder at the zip root, or inside exactly one top-level folder
        if any(i.filename == "theme.json" for i in files):
            strip = ""
        else:
            tops = {i.filename.split("/")[0] for i in infos}
            strip = next(iter(tops)) + "/" if len(tops) == 1 else None
            if strip is None or not any(i.filename == strip + "theme.json" for i in files):
                raise Refuse("theme.json not found at the zip root or in a single top-level folder")
        total = 0
        for i in files:
            rel = i.filename[len(strip):]
            if not rel:
                raise Refuse(f"unsafe path {i.filename!r}")
            out = dest / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            try:
                with zf.open(i) as src, open(out, "wb") as dst:
                    while chunk := src.read(65536):
                        total += len(chunk)
                        if total > MAX_INFLATED:
                            raise Refuse(f"more than {MAX_INFLATED} bytes inflated")
                        dst.write(chunk)
            except (RuntimeError, zipfile.BadZipFile, NotImplementedError) as e:
                raise Refuse(f"cannot read {i.filename!r}: {e}")
    try:
        return json.loads((dest / "theme.json").read_text("utf-8"))
    except (ValueError, OSError) as e:
        raise Refuse(f"theme.json is not valid JSON: {e}")


def image_size(path):
    data = path.read_bytes()
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        raise Refuse(f"{path.name}: not a PNG (bad header)")
    return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")


def check_tree(root, expect_id, manifest):
    theme_id = manifest.get("id") if isinstance(manifest, dict) else None
    check_id(theme_id)
    if expect_id and theme_id != expect_id:
        raise Refuse(f"theme.json id {theme_id!r} differs from the index id {expect_id!r}")
    if not (root / "preview.png").is_file():
        raise Refuse("preview.png is missing")
    ticks, pixels = 0, 0
    for p in (q for q in root.rglob("*") if q.is_file()):
        if p.suffix.lower() == ".png":
            w, h = image_size(p)
            if w > MAX_IMAGE or h > MAX_IMAGE:
                raise Refuse(f"{p.relative_to(root)} is {w:g} x {h:g}, over {MAX_IMAGE} x {MAX_IMAGE}")
            pixels += w * h
            if pixels > MAX_PIXELS:
                raise Refuse(f"{pixels} decoded PNG pixels, more than {MAX_PIXELS}")
        elif p.suffix.lower() == ".svg":
            if p.stat().st_size > MAX_SVG:
                raise Refuse(f"{p.relative_to(root)}: SVG larger than {MAX_SVG} bytes")
            if not re.search(rb"<svg\b[^>]*>", p.read_bytes()):
                raise Refuse(f"{p.name}: not an SVG")
        elif p.suffix.lower() in (".slint", ".txt", ".json"):
            ticks += len(re.findall(r"animation[-_]tick\s*\(", p.read_text("utf-8", "replace")))
    if ticks > MAX_TICKS:
        raise Refuse(f"{ticks} uses of animation-tick(, more than {MAX_TICKS}")
    return theme_id


def run(cmd, **kw):  # one seam for tests
    try:
        return subprocess.run(cmd, timeout=300, **kw)
    except subprocess.TimeoutExpired:
        raise Refuse(f"{cmd[0]} timed out after 300 seconds")


def sim_checks(theme_dir, out):
    """check-themes.sh (builds sim unless SIM is set), then preview captures."""
    if run([str(SDK / "tools" / "check-themes.sh"), str(theme_dir)]).returncode:
        raise Refuse("sdk tools/check-themes.sh failed (output above)")
    sim = os.environ.get("SIM") or str(SDK / "sim" / "target" / "release" / "sim")
    out.mkdir(parents=True, exist_ok=True)
    for state, at in (("ride", "20"), ("locked", "5")):
        png = out / f"{theme_dir.name}-{state}-t{at}.png"
        cmd = [sim, str(theme_dir), "--contract", str(SDK / "contract"),
               "--state", state, "--at", at, "--screenshot", str(png)]
        if run(cmd).returncode or not png.is_file():
            raise Refuse(f"sim could not render the {state} capture")
        print(f"capture: {png}")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("zip")
    ap.add_argument("--out", default="out", help="folder for preview captures")
    ap.add_argument("--id", help="id the index entry claims")
    a = ap.parse_args(argv)
    tmp = Path(tempfile.mkdtemp(prefix="theme-zip-"))
    try:
        stage = tmp / "stage"
        stage.mkdir()
        manifest = unpack(a.zip, stage)
        theme_id = manifest.get("id") if isinstance(manifest, dict) else None
        check_id(theme_id)
        theme_dir = tmp / theme_id  # sim wants the folder name to equal the id
        stage.rename(theme_dir)
        check_tree(theme_dir, a.id, manifest)
        sim_checks(theme_dir, Path(a.out))
    except Refuse as e:
        print(f"REFUSED: {e}", file=sys.stderr)
        return 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"ok: {theme_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
