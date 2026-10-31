"""Offline tests; never contact a device or run host discovery commands."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

DIRECTORY = Path(__file__).resolve().parent
sys.path.insert(0, str(DIRECTORY))
SPEC = importlib.util.spec_from_file_location("installer", DIRECTORY / "ola-dash-install.py")
installer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(installer)
rpc = installer.olarpc


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.known_good = self.directory / "known-good.txt"
        self.known_good.write_text("# session A\nfake/session-a/build\n")
        self.fake = installer.fake_outputs()
        self.stdout = io.StringIO()
        self.stderr = io.StringIO()
        self.enterContext(contextlib.redirect_stdout(self.stdout))
        self.enterContext(contextlib.redirect_stderr(self.stderr))
        self.connect = self.enterContext(patch.object(rpc, "connect"))
        self.connect.side_effect = AssertionError("Tests must not connect")
        self.process = self.enterContext(patch.object(installer.subprocess, "run"))
        self.process.side_effect = AssertionError("Tests must not run discovery")

    def preflight(self, **kwargs):
        options = dict(fake=self.fake, known_good=self.known_good, yes=True)
        options.update(kwargs)
        installer.preflight(None, **options)

    def test_target_scopes(self):
        cases = (
            ("fe80::1%wlan0", None, "ipv6:[fe80::1%wlan0]:50005"),
            ("fe80::1", "wlan0", "ipv6:[fe80::1%wlan0]:50005"),
            ("fe80::1", 6, "ipv6:[fe80::1%6]:50005"),
            ("ipv6:[fe80::1%6]", None, "ipv6:[fe80::1%6]:50005"),
            ("[2001:db8::1]", None, "ipv6:[2001:db8::1]:50005"),
            ("fe90::1", "eth0", "ipv6:[fe90::1%eth0]:50005"),
        )
        for host, scope, expected in cases:
            with self.subTest(host=host, scope=scope):
                self.assertEqual(rpc.build_target(host, scope=scope), expected)
        for host, scope in (("fe80::1", None), ("fe90::1", None),
                            ("fe80::1%", None), ("fe80::1%x%y", None),
                            ("fe80::1%x", "y"), ("127.0.0.1", None)):
            with self.subTest(host=host, scope=scope), self.assertRaises(ValueError):
                rpc.build_target(host, scope=scope)

    def test_payload_and_response_match_vendor_protocol(self):
        self.assertEqual(rpc._cmd_payload("id -u"), b"\x0a\x05id -u")
        self.assertEqual(rpc._decode_response(b"\x08\x01\x12\x020\n"), (1, "0\n"))
        channel = Mock()
        channel.unary_unary.return_value.return_value = b"\x08\x01\x12\x010"
        self.assertEqual(rpc.call(channel, "id -u", 1), (1, "0"))
        channel.unary_unary.assert_called_once()
        self.assertEqual(channel.unary_unary.call_args.args[0],
                         "/wifican.WifiCanRpc/ExecuteADBCommand")
        channel.unary_unary.return_value.assert_called_once_with(
            b"\x0a\x05id -u", timeout=1)

    def test_connect_imports_grpc_lazily(self):
        with patch.dict(sys.modules, {"grpc": None}), self.assertRaisesRegex(
                RuntimeError, "pip install grpcio"):
            # Bypass setUp's no-network mock; import fails before channel creation.
            real_spec = importlib.util.spec_from_file_location("offline_rpc", DIRECTORY / "olarpc.py")
            offline_rpc = importlib.util.module_from_spec(real_spec)
            real_spec.loader.exec_module(offline_rpc)
            offline_rpc.connect("ipv6:[fe80::1%fake0]:50005", 1)

    def test_allowlist_blocks_writes_and_suffixes_before_transport(self):
        commands = (
            "pm install /data/local/tmp/dash.apk",
            "pm disable-user com.olaelectric.ota",
            "appops set dev.olatool.dash WRITE_SETTINGS allow",
            "settings put secure enabled_notification_listeners x",
            "reboot", "sh -c id${IFS}-u", "id -u; reboot",
            "id -u\nreboot", "id -u && reboot", "id -u > /data/local/tmp/x",
            "id -u$(reboot)", "id -u extra", "df -k /data; reboot",
            "pm list packages -e com.olaelectric.ota; reboot",
        )
        with patch.object(rpc, "call") as call:
            for command in commands:
                with self.subTest(command=command), self.assertRaises(ValueError):
                    installer.read_command(None, command, fake={command: (1, "0")})
            call.assert_not_called()

    def test_read_command_real_path_and_failures(self):
        with patch.object(rpc, "call", return_value=(1, "0\n")) as call:
            self.assertEqual(installer.read_command("channel", "id -u"), "0")
            call.assert_called_once_with("channel", "id -u", 3.0)
        for reply in ((2, "unlisted secret"), None):
            fake = {} if reply is None else {"id -u": reply}
            with self.subTest(reply=reply), self.assertRaises(RuntimeError) as exc:
                installer.read_command(None, "id -u", fake=fake)
            self.assertNotIn("unlisted secret", str(exc.exception))

    def test_preflight_known_build_root_and_ota_enabled(self):
        self.preflight()
        output = self.stdout.getvalue()
        self.assertIn("Root: yes", output)
        self.assertIn("Known build: yes", output)
        self.assertIn("786432", output)
        self.assertIn(f"OTA ({installer.OTA}): enabled", output)
        self.assertIn("Preflight passed", output)

    def test_preflight_refuses_non_root_even_with_overrides(self):
        self.fake["id -u"] = (1, "2000")
        with self.assertRaisesRegex(RuntimeError, "not root"):
            self.preflight(allow_unknown_build=True)
        self.assertNotIn("Preflight passed", self.stdout.getvalue())

    def test_preflight_unknown_build_refused_unless_overridden(self):
        self.known_good.write_text("# filled from session A\n")
        with self.assertRaisesRegex(RuntimeError, "unknown build"):
            self.preflight()
        self.preflight(allow_unknown_build=True)
        self.assertIn("Known build: no", self.stdout.getvalue())
        self.assertIn("Preflight passed", self.stdout.getvalue())

    def test_preflight_ota_disabled_or_absent_is_report_only(self):
        self.fake[f"pm list packages -e {installer.OTA}"] = (1, "")
        self.preflight()
        self.assertIn("not listed as enabled", self.stdout.getvalue())
        self.assertIn("Preflight passed", self.stdout.getvalue())

    def test_preflight_ota_filter_does_not_match_other_package(self):
        self.fake[f"pm list packages -e {installer.OTA}"] = (
            1, f"package:{installer.OTA}.other")
        self.preflight()
        self.assertIn("not listed as enabled", self.stdout.getvalue())

    def test_package_query_error_is_not_reported_as_disabled_or_absent(self):
        self.fake[f"pm list packages -e {installer.OTA}"] = (1, "Error: unlisted secret")
        with self.assertRaisesRegex(RuntimeError, "Package state read failed"):
            self.preflight()
        self.fake[f"pm list packages -e {installer.HMI}"] = (1, "Error: unlisted secret")
        with self.assertRaisesRegex(RuntimeError, "Package state read failed"):
            installer.backup(None, self.directory / "failed", fake=self.fake)
        self.assertFalse((self.directory / "failed").exists())
        self.assertNotIn("unlisted secret", self.stdout.getvalue())

    def test_owner_confirmation_defaults_no_and_accepts_y(self):
        for response in ("", "n", "yes"):
            with self.subTest(response=response), patch("builtins.input", return_value=response):
                with self.assertRaisesRegex(RuntimeError, "owner confirmation"):
                    self.preflight(yes=False)
        with patch("builtins.input", side_effect=EOFError), self.assertRaises(RuntimeError):
            self.preflight(yes=False)
        with patch("builtins.input", return_value="Y") as prompt:
            self.preflight(yes=False)
            self.assertIn("parked, on the stand, charged above 30 %", prompt.call_args.args[0])
        with patch("builtins.input", side_effect=AssertionError("--yes must skip prompt")):
            self.preflight(yes=True)

    def test_backup_json_shape_and_exact_read_set(self):
        self.fake[f"pm list packages -d {installer.DASH}"] = (1, f"package:{installer.DASH}")
        self.fake[installer.LISTENERS] = (1, "dev.olatool.dash/.Listener")
        self.fake[f"appops get {installer.DASH} WRITE_SETTINGS"] = (1, "WRITE_SETTINGS: allow")
        with patch.object(installer, "read_command", wraps=installer.read_command) as read:
            path = installer.backup(None, self.directory / "out", fake=self.fake)
        self.assertRegex(path.name, r"^backup-\d{8}T\d{6}\.\d{6}Z\.json$")
        data = json.loads(path.read_text())
        self.assertEqual(set(data), {"packages", "home_activity", "appops",
                                     "enabled_notification_listeners"})
        self.assertEqual(data["packages"], {installer.HMI: "enabled", installer.DASH: "disabled"})
        self.assertEqual(data["home_activity"], f"{installer.HMI}/.MainActivity")
        self.assertEqual(set(data["appops"]), {installer.DASH})
        self.assertEqual(set(data["appops"][installer.DASH]), set(installer.APP_OPS))
        self.assertEqual(data["appops"][installer.DASH]["WRITE_SETTINGS"], "WRITE_SETTINGS: allow")
        self.assertEqual(data["enabled_notification_listeners"], "dev.olatool.dash/.Listener")
        commands = {call.args[1] for call in read.call_args_list}
        expected = {installer.HOME, installer.LISTENERS}
        expected.update(f"appops get {installer.DASH} {op}" for op in installer.APP_OPS)
        expected.update(f"pm list packages {flag} {package}"
                        for package in (installer.HMI, installer.DASH) for flag in ("-e", "-d"))
        self.assertEqual(commands, expected)

    def test_backup_absent_package_and_failed_read_no_file(self):
        path = installer.backup(None, self.directory, fake=self.fake)
        self.assertEqual(json.loads(path.read_text())["packages"][installer.DASH], "not-installed")
        del self.fake[installer.LISTENERS]
        with self.assertRaises(RuntimeError):
            installer.backup(None, self.directory / "failed", fake=self.fake)
        self.assertFalse((self.directory / "failed").exists())

    def test_backup_inconsistent_package_refused(self):
        self.fake[f"pm list packages -d {installer.HMI}"] = (1, f"package:{installer.HMI}")
        with self.assertRaisesRegex(RuntimeError, "inconsistent"):
            installer.backup(None, self.directory / "failed", fake=self.fake)
        self.assertFalse((self.directory / "failed").exists())

    def test_parse_neighbors_filters_and_preserves_scopes(self):
        output = """fe80::1 dev wlan0 lladdr aa:bb:cc:dd:ee:ff REACHABLE
fe80::1 dev wlan0 lladdr aa:bb:cc:dd:ee:ff STALE
fe80::1 dev eth0 lladdr aa:bb:cc:dd:ee:ff DELAY
fe80::2 dev wlan0 FAILED
fe80::3 dev wlan0 INCOMPLETE
2001:db8::1 dev wlan0 lladdr aa:bb:cc:dd:ee:ff STALE
ff02::1 dev wlan0 NOARP
not-ip dev wlan0 STALE
fe80::4 missing-interface
"""
        expected = [("fe80::1", "wlan0"), ("fe80::1", "eth0"),
                    ("fe80::2", "wlan0"), ("fe80::3", "wlan0")]
        self.assertEqual(installer.parse_neighbors(output), expected)
        self.assertEqual(installer.parse_neighbors(output, ["eth0"]), [("fe80::1", "eth0")])

    def test_parse_up_interfaces(self):
        self.assertEqual(installer.parse_interfaces(
            "1: lo: <LOOPBACK,UP> mtu 65536\n"
            "2: wlan0: <BROADCAST,UP> mtu 1500\n"
            "3: veth0@if4: <BROADCAST,UP> mtu 1500\n"), ["lo", "wlan0", "veth0"])

    def test_discovery_only_checks_root_and_reports_no_on_failure(self):
        for reply, expected in (((1, "0"), "yes"), ((1, "2000"), "no"),
                                ((2, "unlisted secret"), "no")):
            self.stdout.seek(0)
            self.stdout.truncate()
            with self.subTest(reply=reply), patch.object(
                    installer, "read_command", wraps=installer.read_command) as read:
                installer.discover(iface="wlan0", fake={"id -u": reply})
                self.assertEqual(self.stdout.getvalue(), f"fe80::1234%wlan0 root: {expected}\n")
                read.assert_called_once_with(None, "id -u", fake={"id -u": reply}, timeout=1.0)

    def test_discovery_real_path_pings_up_interfaces_and_closes_channels(self):
        channels = [Mock(), Mock()]
        self.connect.side_effect = channels
        self.process.side_effect = None
        with patch.object(installer, "local_read", side_effect=[
                "2: wlan0: <UP> mtu 1500\n3: eth0: <UP> mtu 1500\n",
                "fe80::1 dev wlan0 STALE\nfe80::2 dev eth0 STALE\n"]), \
                patch.object(installer.shutil, "which", return_value="/usr/bin/ping6"), \
                patch.object(rpc, "call", side_effect=[(1, "0"), (1, "2000")]) as call:
            installer.discover()
        self.assertEqual([item.args[0] for item in self.process.call_args_list], [
            ["/usr/bin/ping6", "-c", "1", "-W", "1", "-I", "wlan0", "ff02::1"],
            ["/usr/bin/ping6", "-c", "1", "-W", "1", "-I", "eth0", "ff02::1"]])
        self.assertEqual([item.args for item in self.connect.call_args_list], [
            ("ipv6:[fe80::1%wlan0]:50005", 1.0), ("ipv6:[fe80::2%eth0]:50005", 1.0)])
        self.assertEqual([item.args[1] for item in call.call_args_list], ["id -u", "id -u"])
        for channel in channels:
            channel.close.assert_called_once_with()
        self.assertEqual(self.stdout.getvalue(), "fe80::1%wlan0 root: yes\nfe80::2%eth0 root: no\n")

    def test_discovery_iface_filter_and_timeout_do_not_abort_scan(self):
        self.connect.side_effect = RuntimeError("No answer")
        self.process.side_effect = installer.subprocess.TimeoutExpired("ping", 2)
        with patch.object(installer, "local_read", side_effect=[
                "2: wlan0: <UP> mtu 1500\n3: eth0: <UP> mtu 1500\n",
                "fe80::1 dev wlan0 FAILED\nfe80::2 dev eth0 STALE\n"]), \
                patch.object(installer.shutil, "which", side_effect=[None, "/usr/bin/ping"]):
            installer.discover(iface="wlan0")
        self.assertEqual(self.process.call_args.args[0],
                         ["/usr/bin/ping", "-6", "-c", "1", "-W", "1", "-I", "wlan0", "ff02::1"])
        self.connect.assert_called_once_with("ipv6:[fe80::1%wlan0]:50005", 1.0)
        self.assertEqual(self.stdout.getvalue(), "fe80::1%wlan0 root: no\n")

    def test_cli_fake_all_commands_end_to_end(self):
        self.assertEqual(installer.main(["discover", "--fake"]), 0)
        common = ["--ipv6", "fe80::1%fake0", "--fake"]
        self.assertEqual(installer.main(["preflight", *common, "--yes"]), 1)
        self.assertEqual(installer.main(["preflight", *common, "--yes", "--allow-unknown-build"]), 0)
        self.assertEqual(installer.main(["backup", *common, "--out", str(self.directory)]), 0)
        self.assertEqual(len(list(self.directory.glob("backup-*.json"))), 1)
        self.connect.assert_not_called()
        self.process.assert_not_called()


if __name__ == "__main__":
    unittest.main()
