# Installer core (E5.S3)

Linux first. Requires Python 3.10+, `ip` (iproute2), and `ping6` or `ping`
for discovery. Install the only Python dependency: `pip install grpcio`.
No adb, protobuf compiler, or Python package installation is needed.

The vendor diagnostics service on IPv6 TCP 50005 runs commands as root
without authentication. Anyone on the scooter's network has the same access.
An OTA may remove this service. This tool only reads the scooter; it never
changes OTA or other scooter state.

Run from the repository root:

```sh
python3 tools/installer/ola-dash-install.py discover --iface wlan0
python3 tools/installer/ola-dash-install.py preflight --ipv6 fe80::1234%wlan0
python3 tools/installer/ola-dash-install.py backup --ipv6 fe80::1234%wlan0 --out backups
```

Omit `--iface` to discover on every up interface. Discovery pings `ff02::1`,
reads `ip -6 neigh`, and sends only `id -u` to each `fe80::` candidate with a
short timeout. Output gives `address%iface` and whether root answered.
Use `%iface`, `%index`, or `--scope iface` with link-local addresses.

Preflight reads UID, build fingerprint, `/data` free space (`df -k`), and
`pm list packages -e com.olaelectric.ota`. Absence from that list means
"not listed as enabled", which may also mean not installed. Root is required.
`known-good.txt` starts empty and must be filled with exact fingerprints from
session A. Unknown builds refuse unless `--allow-unknown-build` is given for
owner testing. The owner must confirm "parked, on the stand, charged above
30 %" with `y`; `--yes` skips this prompt. No other vehicle checks run.

Backup reads enabled/disabled package lists for `com.olaelectric.hmiclient`
and `dev.olatool.dash`, the resolved HOME activity, the Dash appops
`SYSTEM_ALERT_WINDOW`, `GET_USAGE_STATS`, `REQUEST_INSTALL_PACKAGES`,
`WRITE_SETTINGS`, and the secure notification listener list (all enabled listeners, including other apps' component names, kept so restore can put it back exactly). It writes only
these fields to `DIR/backup-<UTC timestamp>.json`. Package states are
`enabled`, `disabled`, or `not-installed`; home, individual appop replies,
and listener list are preserved as text. Backup collects every read before
creating the file. Keep the backup for later recovery.

Every remote command passes one allowlist of complete read-only command
prefixes; suffixes, extra arguments, and shell syntax are refused.
Install, uninstall, restore, status, and theme push belong to E5.S4.

Offline use (no grpcio or network needed):

```sh
python3 tools/installer/ola-dash-install.py discover --fake
python3 tools/installer/ola-dash-install.py preflight --ipv6 fe80::1%fake0 --fake --allow-unknown-build --yes
python3 tools/installer/ola-dash-install.py backup --ipv6 fe80::1%fake0 --out /tmp/ola-backups --fake
python3 -m unittest tools/installer/test_installer.py -v
```

The fake transport is a command-to-`(status, output)` dictionary. It uses the
same allowlist and command paths as the real transport. Client functions in
`olarpc.py` are vendored from MIT-licensed `ola-s1-rea/scripts/ola.py`, with
attribution and license retained in that module.
