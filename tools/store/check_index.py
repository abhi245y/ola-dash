#!/usr/bin/env python3
"""Validate store/index.json (PLAN E6.S1 T2). See store/schema.md.

usage: check_index.py [--changed]

Without flags: validate, exit 1 on any problem.
--changed: validate, then print a JSON array of the entries that are new or different
compared with origin/main ({"kind": "theme"|"plugin", ...entry}), for the CI download step.
Previous index = `git show origin/main:store/index.json` when available.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_theme_zip import ID_RE, reserved_ids  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
MAX_BYTES = 1024 * 1024
MAX_THEME = 4 * 1024 * 1024
MAX_PLUGIN = 50 * 1024 * 1024
SHA = re.compile(r"[0-9a-f]{64}")
PKG = re.compile(r"[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z][A-Za-z0-9_]*)+")
RESERVED_PACKAGES = ("dev.olatool.", "com.olaelectric.", "com.ola.", "android.", "com.android.")
SLOTS = {"widgets", "media", "navigation"}
STR, URL, INT, HASH = "str", "url", "int", "sha"
THEME = {"id": "id", "name": STR, "version": STR, "author": STR, "licence": STR,
         "url": URL, "size": INT, "sha256": HASH, "preview": URL}
PLUGIN = {"package": "pkg", "name": STR, "versionCode": INT, "url": URL, "size": INT,
          "sha256": HASH, "cert_sha256": HASH, "slots": "slots", "permissions": "perms"}


def _field(kind, v):
    if kind == STR:
        return isinstance(v, str) and v != ""
    if kind == URL:
        return isinstance(v, str) and re.fullmatch(r"https://github\.com/[\w.-]+/[\w.-]+/releases/download/\S+", v) is not None
    if kind == INT:
        return type(v) is int and v >= 1
    if kind == HASH:
        return isinstance(v, str) and SHA.fullmatch(v) is not None
    if kind == "id":
        return isinstance(v, str) and ID_RE.fullmatch(v) is not None
    if kind == "pkg":
        return isinstance(v, str) and PKG.fullmatch(v) is not None and not v.startswith(RESERVED_PACKAGES)
    if kind == "slots":
        return isinstance(v, list) and v != [] and all(s in SLOTS for s in v)
    if kind == "perms":
        return isinstance(v, list) and all(isinstance(p, str) and p for p in v)


def _entries(items, spec, key, label, problems, reserved=()):
    seen = set()
    for n, e in enumerate(items):
        where = f"{label}[{n}]"
        if not isinstance(e, dict):
            problems.append(f"{where}: not an object")
            continue
        for k in e.keys() - spec.keys():
            problems.append(f"{where}: unknown key {k!r}")
        for k, kind in spec.items():
            if not _field(kind, e.get(k)):
                problems.append(f"{where}: bad or missing {k!r}" + (" (https://github.com/ only)" if kind == URL else ""))
        cap = MAX_THEME if label == "themes" else MAX_PLUGIN
        if type(e.get("size")) is int and e["size"] > cap:
            problems.append(f"{where}: size {e['size']} is over {cap}")
        ident = e.get(key)
        if isinstance(ident, str):
            if ident.lower() in seen:  # case-insensitive: a case-folding filesystem would merge them
                problems.append(f"{where}: duplicate {key} {ident!r}")
            seen.add(ident.lower())
            if ident.lower() in reserved:
                problems.append(f"{where}: id {ident!r} is reserved")


def validate(index, raw_size, previous=None):
    problems = []
    if raw_size > MAX_BYTES:
        problems.append(f"index is {raw_size} bytes, over {MAX_BYTES}")
    if not isinstance(index, dict):
        return ["index is not a JSON object"]
    for k in index.keys() - {"seq", "themes", "plugins"}:
        problems.append(f"unknown key {k!r}")
    seq = index.get("seq")
    if type(seq) is not int or seq < 1:
        problems.append("seq must be an integer >= 1")
    elif isinstance(previous, dict) and type(previous.get("seq")) is int and seq < previous["seq"]:
        problems.append(f"seq {seq} is lower than origin/main's {previous['seq']}")
    elif (isinstance(previous, dict) and seq == previous.get("seq")
          and (index.get("themes"), index.get("plugins")) != (previous.get("themes"), previous.get("plugins"))):
        problems.append(f"entries changed but seq is still {seq}; raise it")
    for k in ("themes", "plugins"):
        if not isinstance(index.get(k), list):
            problems.append(f"{k} must be an array")
            return problems
    _entries(index["themes"], THEME, "id", "themes", problems, reserved_ids())
    _entries(index["plugins"], PLUGIN, "package", "plugins", problems)
    return problems


def changed(index, previous):
    old = {("theme", e.get("id")): e for e in (previous or {}).get("themes", [])}
    old |= {("plugin", e.get("package")): e for e in (previous or {}).get("plugins", [])}
    out = []
    for kind, key, items in (("theme", "id", index["themes"]), ("plugin", "package", index["plugins"])):
        out += [{"kind": kind, **e} for e in items if old.get((kind, e[key])) != e]
    return out


def previous_index():
    r = subprocess.run(["git", "-C", str(ROOT), "show", "origin/main:store/index.json"],
                       capture_output=True, text=True)
    try:
        return json.loads(r.stdout) if r.returncode == 0 else None
    except ValueError as e:
        raise ValueError(f"origin/main:store/index.json is not valid JSON: {e}")


def main(argv):
    path = ROOT / "store" / "index.json"
    raw = path.read_bytes()
    try:
        index = json.loads(raw)
    except ValueError as e:
        print(f"error: {path} is not valid JSON: {e}", file=sys.stderr)
        return 1
    try:
        previous = previous_index()
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    problems = validate(index, len(raw), previous)
    if problems:
        print("\n".join("error: " + p for p in problems), file=sys.stderr)
        return 1
    if "--changed" in argv:
        print(json.dumps(changed(index, previous)))
    else:
        print(f"ok: seq {index['seq']}, {len(index['themes'])} theme(s), {len(index['plugins'])} plugin(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
