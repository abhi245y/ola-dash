import io
import json
import stat
import struct
import subprocess
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
            manifest = ct.unpack(z, dest)
            ct.check_tree(dest, None, manifest)
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
        self.refused({**good_files(), "a.svg": b"<svg>" + b" " * (256 * 1024) + b"</svg>"}, pattern="SVG")

    def test_svg_dimensions_are_not_limited(self):
        for svg in ('<svg width="3000px" height="10"></svg>', '<svg viewBox="0 0 5000 5000"></svg>'):
            with self.subTest(svg=svg):
                z = make_zip(self.tmp / "g.zip", {**good_files(), "a.svg": svg})
                with mock.patch.object(ct, "sim_checks"):
                    self.assertEqual(ct.main([str(z)]), 0)

    def test_svg_size_boundary(self):
        svg = b"<svg>" + b" " * (256 * 1024 - 11) + b"</svg>"
        z = make_zip(self.tmp / "g.zip", {**good_files(), "a.svg": svg})
        with mock.patch.object(ct, "sim_checks"):
            self.assertEqual(ct.main([str(z)]), 0)

    def test_svg_bad_header(self):
        self.refused({**good_files(), "bad.svg": "not svg"}, pattern="not an SVG")

    def test_png_pixel_budget(self):
        self.refused({**good_files(), **{f"{i}.png": png(2048, 2048) for i in range(4)}}, pattern="pixels")

    def test_png_pixel_budget_boundary(self):
        files = {**good_files(), "preview.png": png(2000, 2000),
                 **{f"{i}.png": png(2000, 2000) for i in range(3)}}
        z = make_zip(self.tmp / "g.zip", files)
        with mock.patch.object(ct, "sim_checks"):
            self.assertEqual(ct.main([str(z)]), 0)
        self.refused({**files, "extra.png": png(1, 1)}, pattern="pixels")

    def test_png_bad_header(self):
        self.refused({**good_files(), "bad.png": b"not png"}, pattern="bad header")
        self.refused({**good_files(), "bad.png": png()[:16]}, pattern="bad header")

    def test_unsupported_compression(self):
        for compression in (zipfile.ZIP_BZIP2, zipfile.ZIP_LZMA):
            with self.subTest(compression=compression):
                info = zipfile.ZipInfo("extra.txt")
                info.compress_type = compression
                self.refused(good_files(), [(info, b"x")], pattern="compression")

    def test_control_characters(self):
        for char in ("\x01", "\t", "\n", "\x7f", "\x85"):
            with self.subTest(char=char):
                self.refused({**good_files(), f"bad{char}.txt": "x"}, pattern="unsafe path")

    def test_case_duplicate_names(self):
        self.refused({**good_files(), "PREVIEW.PNG": png()}, pattern="duplicate")

    def test_missing_preview(self):
        f = good_files()
        del f["preview.png"]
        self.refused(f, pattern="preview.png")

    def test_reserved_id(self):
        for i in ("default", "fallback", "last-resort", "active", "previous", "bad", "strikes", "restart", "minimal"):
            self.refused(good_files(i), pattern="reserved")
        self.refused(good_files("Fallback"), pattern="does not match")

    def test_malformed_id(self):
        self.refused(good_files("bad id!"), pattern="does not match")
        self.refused(good_files("x" * 65), pattern="does not match")

    def test_animation_tick(self):
        slint = "export component Main { x: animation-tick() * 1; y: animation-tick(); z: animation-tick(); w: animation-tick(); }"
        self.refused({**good_files(), "main.slint": slint}, pattern="animation-tick")

    def test_animation_tick_spellings_and_extensions(self):
        for ext in ("slint", "txt", "json"):
            for call in ("animation_tick()", "animation-tick ()", "animation_tick\n("):
                with self.subTest(ext=ext, call=call):
                    self.refused({**good_files(), f"extra.{ext}": call * 4}, pattern="animation-tick")

    def test_animation_tick_total_across_files(self):
        self.refused({**good_files(), "a.txt": "animation_tick()" * 2,
                      "b.json": "animation-tick ()" * 2}, pattern="animation-tick")

    def test_animation_tick_counts_comments_and_strings(self):
        source = 'u: "//"; a: animation_tick(); // animation-tick()\n'
        self.refused({**good_files(), "extra.txt": source * 2}, pattern="animation-tick")

    def test_manifest_parsed_once(self):
        z = make_zip(self.tmp / "g.zip", good_files())
        with mock.patch.object(ct.json, "loads", wraps=json.loads) as loads, mock.patch.object(ct, "sim_checks"):
            self.assertEqual(ct.main([str(z)]), 0)
        self.assertEqual(loads.call_count, 1)

    def test_subprocess_timeout(self):
        with mock.patch.object(ct.subprocess, "run", return_value=mock.Mock(returncode=0)) as run:
            ct.run(["checker"])
        self.assertEqual(run.call_args.kwargs["timeout"], 300)
        with mock.patch.object(ct.subprocess, "run", side_effect=subprocess.TimeoutExpired("checker", 300)):
            with self.assertRaisesRegex(ct.Refuse, "timed out"):
                ct.run(["checker"])

    def test_main_reports_timeout(self):
        z = make_zip(self.tmp / "g.zip", good_files())
        with mock.patch.object(ct.subprocess, "run", side_effect=subprocess.TimeoutExpired("checker", 300)):
            self.assertEqual(ct.main([str(z)]), 1)

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

    def test_reserved_plugin_packages(self):
        for prefix in ("dev.olatool.", "com.olaelectric.", "com.ola.", "android.", "com.android."):
            with self.subTest(prefix=prefix):
                self.assertTrue(self.check(plugins=[self.plugin(package=prefix + "example")]))
        self.assertEqual(self.check(plugins=[self.plugin(package="com.olaf.example")]), [])

    def test_release_asset_urls(self):
        urls = ("https://github.com/a/b", "https://github.com/a/b/releases/tag/v1",
                "https://github.com/a/b/releases/download/", "https://github.com/a/b/c/releases/download/v1/x",
                "https://github.com/a/b/releases/download/v1/x\n", "https://github.com/a/b/releases/download/v1/x y")
        for url in urls:
            for field in ("url", "preview"):
                with self.subTest(url=url, field=field):
                    self.assertTrue(self.check([self.theme(**{field: url})]))
            self.assertTrue(self.check(plugins=[self.plugin(url=url)]))
        self.assertEqual(self.check([self.theme(url="https://github.com/a-b.c/d_e/releases/download/v1/x")]), [])

    def test_package_size_caps(self):
        self.assertEqual(self.check([self.theme(size=4 * 1024 * 1024)],
                                    [self.plugin(size=50 * 1024 * 1024)]), [])
        self.assertTrue(self.check([self.theme(size=4 * 1024 * 1024 + 1)]))
        self.assertTrue(self.check(plugins=[self.plugin(size=50 * 1024 * 1024 + 1)]))

    def test_invalid_previous_index_fails(self):
        for argv in ([], ["--changed"]):
            with self.subTest(argv=argv), mock.patch.object(ci.subprocess, "run", return_value=mock.Mock(
                    returncode=0, stdout="{broken")), mock.patch("sys.stderr", new_callable=io.StringIO) as err:
                self.assertEqual(ci.main(argv), 1)
                self.assertIn("origin/main:store/index.json", err.getvalue())

    def test_absent_previous_index_is_allowed(self):
        absent = "fatal: path 'store/index.json' does not exist in 'origin/main'"
        with mock.patch.object(ci.subprocess, "run", return_value=mock.Mock(returncode=128, stderr=absent)):
            self.assertIsNone(ci.previous_index())
        with mock.patch.object(ci.subprocess, "run", return_value=mock.Mock(returncode=128, stderr="fatal: bad revision")):
            self.assertRaises(ValueError, ci.previous_index)

    def test_previous_index_is_used(self):
        previous = {"seq": 999, "themes": [], "plugins": []}
        with mock.patch.object(ci.subprocess, "run", return_value=mock.Mock(
                returncode=0, stdout=json.dumps(previous))):
            self.assertEqual(ci.previous_index(), previous)
            self.assertEqual(ci.main([]), 1)

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

    def test_manifest_resource_references(self):
        for value in ('"@string/home"', '@0x7f010001', '(type 0x01)@0x7f010001'):
            tree = MANIFEST + HOME_ACTIVITY.replace('"android.intent.category.HOME"', value)
            with self.subTest(value=value):
                self.assertIn("manifest uses a resource reference; write names literally", cp.decide(PERMS, tree, {})[0])
        tree = MANIFEST.replace('".WeatherService"', '"@string/service"')
        self.assertIn("manifest uses a resource reference; write names literally", cp.decide(PERMS, tree, {})[0])
        labelled = MANIFEST.replace('    E: application (line=8)\n', '    E: application (line=8)\n      A: http://schemas.android.com/apk/res/android:label(0x01010001)=@0x7f0f0001\n      A: http://schemas.android.com/apk/res/android:icon(0x01010002)=@0x7f0d0001\n')
        self.assertNotIn("manifest uses a resource reference; write names literally", cp.decide(PERMS, labelled, {})[0])

    def test_dynamic_dex_loading_strings(self):
        for name in ("DexClassLoader", "InMemoryDexClassLoader", "DexFile"):
            for sep in ("/", "."):
                for encoding in ("utf-8", "utf-16-le"):
                    with self.subTest(name=name, sep=sep, encoding=encoding):
                        blob = sep.join(("dalvik", "system", name)).encode(encoding)
                        self.assertTrue(cp.decide(PERMS, MANIFEST, {"classes.dex": blob})[0])

    def test_executable_assets(self):
        for ext in ("dex", "jar", "apk", "zip", "so", "DEX"):
            name = f"assets/nested/code.{ext}"
            with self.subTest(name=name):
                self.assertTrue(any(name in p for p in cp.decide(PERMS, MANIFEST, {name: b"code"})[0]))
        self.assertEqual(cp.decide(PERMS, MANIFEST, {"assets/data.txt": b"data"})[0], [])

    def test_scans_all_apk_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            apk = Path(tmp) / "plugin.apk"
            signed = mock.Mock(returncode=0, stdout="certificate SHA-256 digest: " + "a" * 64, stderr="")
            for name in ("res/raw/payload.txt", "lib/arm64-v8a/plugin.so", "assets/payload.txt", "other.dex"):
                with self.subTest(name=name):
                    make_zip(apk, {"AndroidManifest.xml": b"manifest", name: b"ICommanderService"})
                    with mock.patch.object(cp, "tool", side_effect=[
                            mock.Mock(returncode=0, stdout=PERMS), mock.Mock(returncode=0, stdout=MANIFEST), signed
                    ]), mock.patch("sys.stderr", new_callable=io.StringIO) as err:
                        self.assertEqual(cp.main(["checker", str(apk)]), 1)
                    self.assertIn(name, err.getvalue())

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


class StorePolicy(unittest.TestCase):
    def test_workflow_limits(self):
        workflow = (ci.ROOT / ".github/workflows/store.yml").read_text()
        self.assertRegex(workflow, r"(?m)^    timeout-minutes: 30$")
        curl = next(line for line in workflow.splitlines() if line.strip().startswith("curl "))
        for option in ("--max-time 300", "--proto '=https'", "--proto-redir '=https'", '--max-filesize "$size"'):
            self.assertIn(option, curl)
        self.assertIn("${ANDROID_HOME:-}", workflow)

    def test_store_trust_policy(self):
        readme = (ci.ROOT / "store/README.md").read_text()
        for rule in ("tripwire, not a sandbox", "runtime-built strings", "ordinary app", "per slot",
                     "store/index.json` alone", "tools/", ".github/", "sdk", ".gitmodules",
                     "reviewed as code", "re-run from main", "up to date before merging", "verbatim"):
            with self.subTest(rule=rule):
                self.assertIn(rule, readme)

    def test_codeowners(self):
        rules = (ci.ROOT / ".github/CODEOWNERS").read_text().splitlines()
        for path in ("/tools/", "/.github/", "/sdk", "/.gitmodules"):
            self.assertIn(f"{path} @abhi245y", rules)

    def test_theme_schema(self):
        schema = (ci.ROOT / "store/schema.md").read_text()
        for rule in ("[a-z0-9-]{1,64}", ".ttc", "hint", "runtime guard", "256 KB", "16,000,000"):
            with self.subTest(rule=rule):
                self.assertIn(rule, schema)


if __name__ == "__main__":
    unittest.main()
