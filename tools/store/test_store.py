import io
import json
import stat
import struct
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_index as ci  # noqa: E402
import check_plugin_apk as cp  # noqa: E402
import check_theme_zip as ct  # noqa: E402


def png(w=64, h=64):
    return b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + struct.pack(">II", w, h) + b"\x08\x06\0\0\0" + b"\0" * 4


def make_zip(path, files, extra=()):
    """files: {name: bytes}; extra: ready ZipInfo/bytes pairs."""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for n, d in files.items():
            z.writestr(n, d)
        for info, d in extra:
            z.writestr(info, d)
    return path


def good_files(theme_id="mytheme"):
    return {"theme.json": json.dumps({"id": theme_id}), "main.slint": "export component Main {}",
            "preview.png": png()}


class ThemeZip(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp, ignore_errors=True))

    def refused(self, files, extra=(), pattern=""):
        z = make_zip(self.tmp / "t.zip", files, extra)
        dest = self.tmp / "d"
        dest.mkdir(exist_ok=True)
        with mock.patch.object(ct, "run") as run, self.assertRaisesRegex(ct.Refuse, pattern):
            ct.unpack(z, dest)
            ct.check_tree(dest, None)
        run.assert_not_called()

    def test_zip_slip(self):
        self.refused({**good_files(), "../evil.txt": "x"}, pattern="unsafe path")

    def test_absolute(self):
        self.refused({**good_files(), "/etc/x.txt": "x"}, pattern="unsafe path")

    def test_symlink(self):
        info = zipfile.ZipInfo("link.txt")
        info.create_system = 3
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        self.refused(good_files(), [(info, "/etc/passwd")], pattern="symlink")

    def test_inflation_bomb(self):
        self.refused({**good_files(), "big.txt": b"\0" * (3 * 1024 * 1024)}, pattern="inflated")

    def test_too_many_files(self):
        self.refused({**good_files(), **{f"f{i}.txt": "x" for i in range(200)}}, pattern="entries")

    def test_bad_extension(self):
        self.refused({**good_files(), "run.sh": "x"}, pattern="extension")

    def test_big_png_by_header(self):
        self.refused({**good_files(), "bg.png": png(4096, 10)}, pattern="over 2048")

    def test_big_svg(self):
        self.refused({**good_files(), "a.svg": '<svg width="3000px" height="10"></svg>'}, pattern="over 2048")

    def test_missing_preview(self):
        f = good_files()
        del f["preview.png"]
        self.refused(f, pattern="preview.png")

    def test_reserved_id(self):
        for i in ("default", "fallback", "last-resort", "active", "minimal"):
            self.refused(good_files(i), pattern="reserved")
        self.refused(good_files("Fallback"), pattern="does not match")

    def test_malformed_id(self):
        self.refused(good_files("bad id!"), pattern="does not match")
        self.refused(good_files("x" * 65), pattern="does not match")

    def test_animation_tick(self):
        slint = "export component Main { x: animation-tick() * 1; y: animation-tick(); z: animation-tick(); w: animation-tick(); }"
        self.refused({**good_files(), "main.slint": slint}, pattern="animation-tick")

    def test_no_theme_json(self):
        self.refused({"main.slint": "x"}, pattern="theme.json not found")

    def test_good_zip_runs_sdk_checks(self):
        # single top-level folder is accepted too
        files = {f"mytheme/{n}": d for n, d in good_files().items()}
        z = make_zip(self.tmp / "g.zip", files)
        out = self.tmp / "out"
        def fake_run(cmd, **kw):  # sim "renders" by creating the capture file
            if "--screenshot" in cmd:
                Path(cmd[cmd.index("--screenshot") + 1]).write_bytes(png())
            return mock.Mock(returncode=0)

        with mock.patch.object(ct, "run", side_effect=fake_run) as run:
            self.assertEqual(ct.main([str(z), "--out", str(out), "--id", "mytheme"]), 0)
        cmds = [c.args[0] for c in run.call_args_list]
        self.assertTrue(cmds[0][0].endswith("check-themes.sh") and cmds[0][1].endswith("mytheme"))
        self.assertEqual([c[c.index("--state") + 1] for c in cmds[1:]], ["ride", "locked"])
        self.assertEqual(sorted(p.name for p in out.iterdir()), ["mytheme-locked-t5.png", "mytheme-ride-t20.png"])

    def test_main_reports_refusal(self):
        z = make_zip(self.tmp / "b.zip", {**good_files(), "x.exe": "x"})
        self.assertEqual(ct.main([str(z)]), 1)


class Index(unittest.TestCase):
    def theme(self, **kw):
        e = {"id": "neon", "name": "Neon", "version": "1.0.0", "author": "a", "licence": "MIT",
             "url": "https://github.com/a/b/releases/download/v1/neon.zip", "size": 10,
             "sha256": "a" * 64, "preview": "https://github.com/a/b/releases/download/v1/p.png"}
        return {**e, **kw}

    def plugin(self, **kw):
        e = {"package": "dev.example.weather", "name": "W", "versionCode": 3,
             "url": "https://github.com/a/b/releases/download/v1/w.apk", "size": 5, "sha256": "b" * 64,
             "cert_sha256": "c" * 64, "slots": ["widgets"], "permissions": ["android.permission.INTERNET"]}
        return {**e, **kw}

    def check(self, themes=(), plugins=(), seq=1, previous=None, size=100):
        return ci.validate({"seq": seq, "themes": list(themes), "plugins": list(plugins)}, size, previous)

    def test_repo_index_valid(self):
        raw = (ci.ROOT / "store" / "index.json").read_bytes()
        self.assertEqual(ci.validate(json.loads(raw), len(raw)), [])

    def test_good(self):
        self.assertEqual(self.check([self.theme()], [self.plugin()]), [])

    def test_bad_cases(self):
        cases = {
            "http url": self.check([self.theme(url="http://github.com/x")]),
            "other host": self.check([self.theme(url="https://example.com/x")]),
            "uppercase sha": self.check([self.theme(sha256="A" * 64)]),
            "short sha": self.check([self.theme(sha256="a" * 63)]),
            "reserved": self.check([self.theme(id="default")]),
            "bundled": self.check([self.theme(id="minimal")]),
            "dup theme": self.check([self.theme(), self.theme()]),
            "dup plugin": self.check(plugins=[self.plugin(), self.plugin()]),
            "unknown key": self.check([self.theme(extra=1)]),
            "bad slot": self.check(plugins=[self.plugin(slots=["vehicle"])]),
            "bool size": self.check([self.theme(size=True)]),
            "too big": self.check(size=2 * 1024 * 1024),
            "seq 0": self.check(seq=0),
        }
        for name, problems in cases.items():
            self.assertTrue(problems, name)

    def test_seq_monotonic(self):
        self.assertTrue(self.check(seq=2, previous={"seq": 3}))
        self.assertEqual(self.check(seq=3, previous={"seq": 3, "themes": [], "plugins": []}), [])
        self.assertTrue(self.check(seq=3, previous={"seq": 3, "themes": [self.theme()], "plugins": []}))
        self.assertEqual(self.check(seq=4, previous={"seq": 3, "themes": [self.theme()], "plugins": []}), [])

    def test_changed(self):
        old = {"themes": [self.theme()], "plugins": []}
        new = {"themes": [self.theme(), self.theme(id="other")], "plugins": [self.plugin()]}
        got = ci.changed(new, old)
        self.assertEqual([(e["kind"], e.get("id") or e["package"]) for e in got],
                         [("theme", "other"), ("plugin", "dev.example.weather")])


MANIFEST = """N: android=http://schemas.android.com/apk/res/android (line=2)
  E: manifest (line=2)
    A: package="dev.example.weather" (Raw: "dev.example.weather")
    A: http://schemas.android.com/apk/res/android:versionCode(0x0101021b)=3
    E: uses-permission (line=5)
      A: http://schemas.android.com/apk/res/android:name(0x01010003)="android.permission.INTERNET" (Raw: "android.permission.INTERNET")
    E: application (line=8)
      E: service (line=9)
        A: http://schemas.android.com/apk/res/android:name(0x01010003)=".WeatherService" (Raw: ".WeatherService")
        E: intent-filter (line=10)
          E: action (line=11)
            A: http://schemas.android.com/apk/res/android:name(0x01010003)="dev.olatool.dash.plugin.PLUGIN" (Raw: "dev.olatool.dash.plugin.PLUGIN")
        E: meta-data (line=13)
          A: http://schemas.android.com/apk/res/android:name(0x01010003)="dev.olatool.dash.plugin.slots" (Raw: "dev.olatool.dash.plugin.slots")
          A: http://schemas.android.com/apk/res/android:value(0x01010024)="widgets,media" (Raw: "widgets,media")
"""
PERMS = "package: dev.example.weather\nuses-permission: name='android.permission.INTERNET'\n"
HOME_ACTIVITY = """      E: activity (line=20)
        E: intent-filter (line=21)
          E: category (line=22)
            A: http://schemas.android.com/apk/res/android:name(0x01010003)="android.intent.category.HOME" (Raw: "android.intent.category.HOME")
"""


class PluginDecision(unittest.TestCase):
    def test_good(self):
        problems, info = cp.decide(PERMS, MANIFEST, {"classes.dex": b"Lcom/example/Foo;"})
        self.assertEqual(problems, [])
        self.assertEqual(info, {"package": "dev.example.weather", "versionCode": 3,
                                "slots": ["widgets", "media"], "permissions": ["android.permission.INTERNET"]})

    def test_banned_permissions(self):
        for p in cp.BANNED_PERMS:
            problems, _ = cp.decide(PERMS + f"uses-permission: name='{p}'\n", MANIFEST, {})
            self.assertEqual(problems, [f"requests {p}"])

    def test_banned_permission_only_in_xmltree(self):
        tree = MANIFEST.replace("android.permission.INTERNET", "android.permission.SYSTEM_ALERT_WINDOW")
        self.assertTrue(cp.decide("", tree, {})[0])

    def test_home_activity(self):
        problems, _ = cp.decide(PERMS, MANIFEST + HOME_ACTIVITY, {})
        self.assertEqual(problems, ["has an activity with category HOME"])

    def test_dex_strings(self):
        for blob in (b"..Lcom/olaelectric/vehicleparser/IParser;..", b"com.olaelectric.vehicleinterface",
                     "ICommanderService".encode("utf-16-le")):
            problems, _ = cp.decide(PERMS, MANIFEST, {"classes2.dex": blob})
            self.assertEqual(len(problems), 1, blob)

    def test_no_plugin_service(self):
        problems, _ = cp.decide(PERMS, MANIFEST.replace("dev.olatool.dash.plugin.PLUGIN", "x.Y"), {})
        self.assertTrue(any("no service" in p for p in problems))

    def test_bad_slots(self):
        problems, _ = cp.decide(PERMS, MANIFEST.replace("widgets,media", "vehicle"), {})
        self.assertTrue(any("slots" in p for p in problems))


if __name__ == "__main__":
    unittest.main()
