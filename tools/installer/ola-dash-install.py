#!/usr/bin/env python3
"""Read-only installer core for Ola Dash (E5.S3)."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import ipaddress
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

import olarpc

HMI = "com.olaelectric.hmiclient"
DASH = "dev.olatool.dash"
OTA = "com.olaelectric.ota"
APP_OPS = ("SYSTEM_ALERT_WINDOW", "GET_USAGE_STATS",
           "REQUEST_INSTALL_PACKAGES", "WRITE_SETTINGS")
HOME = ("cmd package resolve-activity --brief -a android.intent.action.MAIN "
        "-c android.intent.category.HOME")
LISTENERS = "settings get secure enabled_notification_listeners"
KNOWN_GOOD = Path(__file__).with_name("known-good.txt")

# Complete command prefixes: no suffixes, extra arguments, or shell syntax.
READ_ONLY_PREFIXES = (
    "id -u",
    "getprop ro.build.fingerprint",
    "df -k /data",
    f"pm list packages -e {OTA}",
    *(f"pm list packages {flag} {package}"
      for package in (HMI, DASH) for flag in ("-e", "-d")),
    HOME,
    *(f"appops get {DASH} {op}" for op in APP_OPS),
    LISTENERS,
)


def read_command(channel, command, *, fake=None, timeout=3.0):
    if command not in READ_ONLY_PREFIXES:
        raise ValueError("Command refused by read-only allowlist")
    try:
        status, output = fake[command] if fake is not None else olarpc.call(
            channel, command, timeout)
    except Exception:
        raise RuntimeError(f"Read failed: {command}") from None
    if status not in (0, 1):
        raise RuntimeError(f"Read failed: {command}")
    return output.strip()


def fake_outputs():
    outputs = {
        "id -u": (1, "0"),
        "getprop ro.build.fingerprint": (1, "fake/session-a/build"),
        "df -k /data": (1, "Filesystem 1K-blocks Used Available Use% Mounted on\n"
                        "/dev/fake 1048576 262144 786432 25% /data"),
        f"pm list packages -e {OTA}": (1, f"package:{OTA}"),
        HOME: (1, f"priority=0 preferredOrder=0 match=0x108000 specificIndex=-1 isDefault=true\n{HMI}/.MainActivity"),
        LISTENERS: (1, "null"),
    }
    for package in (HMI, DASH):
        for flag in ("-e", "-d"):
            outputs[f"pm list packages {flag} {package}"] = (
                1, f"package:{package}" if package == HMI and flag == "-e" else "")
    for op in APP_OPS:
        outputs[f"appops get {DASH} {op}"] = (1, "No operations.")
    return outputs


def package_listed(output, package):
    lines = output.splitlines()
    if any(not line.startswith("package:") for line in lines):
        raise RuntimeError("Package state read failed")
    return f"package:{package}" in lines


def preflight(channel, *, fake=None, allow_unknown_build=False, yes=False,
              known_good=KNOWN_GOOD, timeout=3.0):
    def read(command):
        return read_command(channel, command, fake=fake, timeout=timeout)

    if read("id -u") != "0":
        raise RuntimeError("Preflight refused: diagnostics service is not root")
    print("Root: yes")
    fingerprint = read("getprop ro.build.fingerprint")
    builds = {line.strip() for line in Path(known_good).read_text().splitlines()
              if line.strip() and not line.lstrip().startswith("#")}
    known = bool(fingerprint) and fingerprint in builds
    print(f"Build fingerprint: {fingerprint or '(empty)'}")
    print(f"Known build: {'yes' if known else 'no'}")
    if not known and not allow_unknown_build:
        raise RuntimeError("Preflight refused: unknown build; use "
                           "--allow-unknown-build only for owner testing")
    print("Free space on /data (KiB):")
    print(read("df -k /data"))
    enabled = package_listed(read(f"pm list packages -e {OTA}"), OTA)
    print(f"OTA ({OTA}): {'enabled' if enabled else 'not listed as enabled'}")
    if not yes:
        try:
            answer = input("Confirm parked, on the stand, charged above 30 % [y/N]: ")
        except EOFError:
            answer = ""
        if answer.strip().lower() != "y":
            raise RuntimeError("Preflight refused: owner confirmation required")
    print("Preflight passed")


def backup(channel, out, *, fake=None, timeout=3.0):
    def read(command):
        return read_command(channel, command, fake=fake, timeout=timeout)

    packages = {}
    for package in (HMI, DASH):
        enabled = package_listed(read(f"pm list packages -e {package}"), package)
        disabled = package_listed(read(f"pm list packages -d {package}"), package)
        if enabled and disabled:
            raise RuntimeError("Backup refused: inconsistent package state")
        packages[package] = "enabled" if enabled else (
            "disabled" if disabled else "not-installed")
    data = {
        "packages": packages,
        "home_activity": (read(HOME).splitlines() or [""])[-1].strip(),
        "appops": {DASH: {op: read(f"appops get {DASH} {op}") for op in APP_OPS}},
        "enabled_notification_listeners": read(LISTENERS),
    }
    directory = Path(out)
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    path = directory / f"backup-{stamp}.json"
    with path.open("x", encoding="utf-8") as stream:
        json.dump(data, stream, indent=2)
        stream.write("\n")
    print(f"Backup: {path}")
    return path


def parse_interfaces(output):
    interfaces = []
    for line in output.splitlines():
        match = re.match(r"\d+: ([^:]+):", line)
        if match:
            interfaces.append(match.group(1).split("@", 1)[0])
    return list(dict.fromkeys(interfaces))


def parse_neighbors(output, interfaces=None):
    candidates = []
    for line in output.splitlines():
        fields = line.split()
        if len(fields) < 3 or fields[1] != "dev":
            continue
        try:
            address = ipaddress.IPv6Address(fields[0])
        except ValueError:
            continue
        iface = fields[2]
        if not address.is_link_local or not str(address).startswith("fe80:"):
            continue
        if interfaces is not None and iface not in interfaces:
            continue
        candidates.append((str(address), iface))
    return list(dict.fromkeys(candidates))


def local_read(args):
    result = subprocess.run(args, capture_output=True, text=True, timeout=3,
                            check=True)
    return result.stdout


def discover(*, iface=None, fake=None, timeout=1.0):
    if fake is not None:
        interfaces = [iface or "fake0"]
        neighbors = f"fe80::1234 dev {interfaces[0]} lladdr 02:00:00:00:00:01 STALE"
    else:
        interfaces = parse_interfaces(local_read(["ip", "-o", "link", "show", "up"]))
        if iface:
            if iface not in interfaces:
                raise RuntimeError("Requested interface is not up")
            interfaces = [iface]
        ping = shutil.which("ping6") or shutil.which("ping")
        if not ping:
            raise RuntimeError("Discovery requires ping6 or ping")
        for interface in interfaces:
            args = [ping]
            if Path(ping).name != "ping6":
                args.append("-6")
            try:
                subprocess.run(args + ["-c", "1", "-W", "1", "-I", interface,
                                       "ff02::1"], stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, timeout=2, check=False)
            except subprocess.TimeoutExpired:
                pass
        neighbors = local_read(["ip", "-6", "neigh"])
    candidates = parse_neighbors(neighbors, interfaces)
    for address, interface in candidates:
        channel = None
        root = False
        try:
            target = olarpc.build_target(address, scope=interface)
            if fake is None:
                channel = olarpc.connect(target, timeout)
            root = read_command(channel, "id -u", fake=fake, timeout=timeout) == "0"
        except RuntimeError:
            pass
        finally:
            if channel is not None:
                channel.close()
        print(f"{address}%{interface} root: {'yes' if root else 'no'}")
    if not candidates:
        print("No link-local IPv6 candidates found")


def positive_timeout(value):
    number = float(value)
    if not 0 < number <= 60:
        raise argparse.ArgumentTypeError("timeout must be greater than 0 and at most 60")
    return number


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("discover", "preflight", "backup"):
        command = sub.add_parser(name)
        command.add_argument("--fake", action="store_true",
                             help="use canned data; no network or local discovery")
        command.add_argument("--timeout", type=positive_timeout,
                             default=1.0 if name == "discover" else 3.0)
        if name == "discover":
            command.add_argument("--iface", help="only scan this up interface")
        else:
            command.add_argument("--ipv6", required=True, help="IPv6 address, e.g. fe80::1%%wlan0")
            command.add_argument("--scope", help="interface name or index")
        if name == "preflight":
            command.add_argument("--allow-unknown-build", action="store_true")
            command.add_argument("--yes", action="store_true", help="skip owner confirmation")
        if name == "backup":
            command.add_argument("--out", required=True, help="local backup directory")
    args = parser.parse_args(argv)
    channel = None
    try:
        fake = fake_outputs() if args.fake else None
        if args.command == "discover":
            discover(iface=args.iface, fake=fake, timeout=args.timeout)
        else:
            target = olarpc.build_target(args.ipv6, scope=args.scope)
            if fake is None:
                channel = olarpc.connect(target, args.timeout)
            if args.command == "preflight":
                preflight(channel, fake=fake, timeout=args.timeout,
                          allow_unknown_build=args.allow_unknown_build, yes=args.yes)
            else:
                backup(channel, args.out, fake=fake, timeout=args.timeout)
        return 0
    except (RuntimeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except (OSError, subprocess.SubprocessError):
        print("Error: local file or discovery command failed", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    finally:
        if channel is not None:
            channel.close()


if __name__ == "__main__":
    sys.exit(main())
