#!/usr/bin/env python3
"""Store check for a plugin APK (PLAN E6.S1 T3).

usage: check_plugin_apk.py PLUGIN.apk

Needs Android build-tools (aapt2, apksigner) on PATH. Prints the JSON fragment for the
index entry, or "REFUSED: <reasons>" and exit 1.
"""
import hashlib
import json
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

BANNED_PERMS = {
    "android.permission." + p
    for p in (
        "SYSTEM_ALERT_WINDOW",
        "BIND_ACCESSIBILITY_SERVICE",
        "BIND_DEVICE_ADMIN",
        "BIND_NOTIFICATION_LISTENER_SERVICE",
        "REQUEST_INSTALL_PACKAGES",
        "PACKAGE_USAGE_STATS",
    )
}
BANNED_STRINGS = ["com.olaelectric.vehicleparser", "com.olaelectric.vehicleinterface", "ICommanderService"]
PLUGIN_ACTION = "dev.olatool.dash.plugin.PLUGIN"
SLOTS_META = "dev.olatool.dash.plugin.slots"
SLOTS = {"widgets", "media", "navigation"}
HOME = "android.intent.category.HOME"


def parse_xmltree(text):
    """aapt2 dump xmltree -> list of (tag, attrs, parent_index); attrs keyed by local name."""
    nodes, stack = [], []  # stack: (indent, node index)
    for line in text.splitlines():
        indent = len(line) - len(line.lstrip())
        s = line.strip()
        if s.startswith("E: "):
            while stack and stack[-1][0] >= indent:
                stack.pop()
            nodes.append((s[3:].split()[0], {}, stack[-1][1] if stack else None))
            stack.append((indent, len(nodes) - 1))
        elif s.startswith("A: ") and nodes:
            m = re.match(r"A: (?:\S+:)?([\w-]+)(?:\(0x[0-9a-f]+\))?=\s*(?:\(type 0x\w+\))?(?:\"([^\"]*)\"|(\S+))", s)
            if m:
                nodes[-1][1][m.group(1)] = m.group(2) if m.group(2) is not None else m.group(3)
    return nodes


def needle_hits(blobs):
    """Names of blobs containing a banned string (dotted or slashed, UTF-8 or UTF-16LE)."""
    hits = []
    for name, data in blobs.items():
        for n in BANNED_STRINGS:
            for v in {n, n.replace(".", "/")}:
                if v.encode() in data or v.encode("utf-16-le") in data:
                    hits.append(f"{name} references {n}")
                    break
    return hits


def decide(perms_out, xmltree_out, blobs):
    """Pure decision on canned tool output. Returns (problems, info); info lacks the cert."""
    nodes = parse_xmltree(xmltree_out)
    perms = set(re.findall(r"^uses-permission[\w-]*: name='([^']+)'", perms_out, re.M))
    perms |= {a.get("name") for t, a, _ in nodes if t.startswith("uses-permission") and a.get("name")}
    problems = [f"requests {p}" for p in sorted(perms & BANNED_PERMS)]
    if any(t == "category" and a.get("name") == HOME for t, a, _ in nodes):
        problems.append("has an activity with category HOME")
    problems += needle_hits({"AndroidManifest.xml (text)": xmltree_out.encode(), **blobs})
    def ancestors(i):
        out = []
        while nodes[i][2] is not None:
            i = nodes[i][2]
            out.append(nodes[i][0])
        return out

    has_service = any(t == "action" and a.get("name") == PLUGIN_ACTION and ancestors(i)[:2] == ["intent-filter", "service"]
                      for i, (t, a, _) in enumerate(nodes))
    if not has_service:
        problems.append(f"no service with action {PLUGIN_ACTION}")
    slots = [s.strip() for a in (a for t, a, _ in nodes if t == "meta-data" and a.get("name") == SLOTS_META)
             for s in (a.get("value") or "").split(",") if s.strip()]
    if not slots or not set(slots) <= SLOTS:
        problems.append(f"meta-data {SLOTS_META} must list some of {sorted(SLOTS)}, got {slots}")
    manifest = next((a for t, a, _ in nodes if t == "manifest"), {})
    vc = manifest.get("versionCode", "")
    info = {
        "package": manifest.get("package"),
        "versionCode": int(vc, 0) if re.fullmatch(r"(0x[0-9a-f]+|\d+)", vc or "") else None,
        "slots": slots,
        "permissions": sorted(perms),
    }
    if not info["package"] or info["versionCode"] is None:
        problems.append("manifest has no package or versionCode")
    return problems, info


def tool(name, *args):
    exe = shutil.which(name)
    if not exe:
        sys.exit(f"error: {name} not on PATH (Android build-tools needed)")
    return subprocess.run([exe, *args], capture_output=True, text=True)


def main(argv):
    if len(argv) != 2:
        sys.exit(__doc__)
    apk = argv[1]
    perms = tool("aapt2", "dump", "permissions", apk)
    tree = tool("aapt2", "dump", "xmltree", "--file", "AndroidManifest.xml", apk)
    if perms.returncode or tree.returncode:
        print("REFUSED: aapt2 cannot read the APK: " + (perms.stderr or tree.stderr).strip(), file=sys.stderr)
        return 1
    try:
        with zipfile.ZipFile(apk) as z:
            blobs = {n: z.read(n) for n in z.namelist()
                     if re.fullmatch(r"classes\d*\.dex", n) or n == "AndroidManifest.xml"}
    except zipfile.BadZipFile as e:
        print(f"REFUSED: not a zip: {e}", file=sys.stderr)
        return 1
    problems, info = decide(perms.stdout, tree.stdout, blobs)
    signed = tool("apksigner", "verify", "--print-certs", apk)
    certs = re.findall(r"certificate SHA-256 digest: ([0-9a-f]{64})", signed.stdout)
    if signed.returncode or len(certs) != 1:
        problems.append("apksigner: signature invalid or not exactly one signer " + signed.stderr.strip())
    if problems:
        print("REFUSED:\n  " + "\n  ".join(problems), file=sys.stderr)
        return 1
    raw = Path(apk).read_bytes()
    print(json.dumps({"package": info["package"], "versionCode": info["versionCode"],
                      "size": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
                      "cert_sha256": certs[0], "slots": info["slots"], "permissions": info["permissions"]}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
