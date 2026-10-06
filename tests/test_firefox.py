"""Exercise Firefox profile discovery and merges against temporary homes."""

from pathlib import Path
import runpy
import sqlite3
import tempfile
import unittest

firefox = runpy.run_path(str(Path(__file__).resolve().parents[1] /
                            "chezmoi/.chezmoitemplates/firefox.py"))


class FirefoxTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.root = self.home / ".config/mozilla/firefox"
        self.root.mkdir(parents=True)
        self.source = self.home / "curated.js"
        self.source.write_text('user_pref("browser.urlbar.suggest.searches", false);\n')

    def profile(self, root=None, name="random.Profile 1"):
        root = root or self.root
        profile = root / name
        profile.mkdir(parents=True)
        (root / "profiles.ini").write_text(
            f"[Profile0]\nName=default-release\nIsRelative=1\nPath={name}\nDefault=1\n")
        return profile

    def test_installation_defaults_override_legacy_and_deduplicate_aliases(self):
        legacy = self.profile(name="legacy.default")
        current = self.root / "random.Profile 1"
        current.mkdir()
        other = self.root / "beta.default"
        other.mkdir()
        with (self.root / "profiles.ini").open("a") as registry:
            registry.write("[InstallRELEASE]\nDefault=random.Profile 1\n"
                           "[InstallBETA]\nDefault=beta.default\n")
        alias = self.home / ".mozilla/firefox"
        alias.parent.mkdir()
        alias.symlink_to(self.root, target_is_directory=True)
        self.assertEqual(firefox["default_profiles"](self.home), sorted([current, other]))
        self.assertFalse((legacy / "user.js").exists())

    def test_legacy_flatpak_default_and_absolute_paths(self):
        for location in (".var/app/org.mozilla.firefox/.mozilla/firefox",
                         ".var/app/org.mozilla.firefox/.config/mozilla/firefox"):
            with self.subTest(location=location):
                root = self.home / location
                profile = self.profile(root)
                (root / "profiles.ini").write_text(
                    f"[Profile0]\nDefault=1\nIsRelative=0\nPath={profile}\n")
                self.assertIn(profile, firefox["default_profiles"](self.home))

    def test_missing_and_external_profiles_are_not_created_or_modified(self):
        with tempfile.TemporaryDirectory() as directory:
            outside = Path(directory)
            (self.root / "profiles.ini").write_text(
                f"[InstallONE]\nDefault=missing\n[InstallTWO]\nDefault={outside}\n")
            firefox["apply_preferences"](self.home, self.source)
            self.assertEqual(firefox["default_profiles"](self.home), [])
            self.assertFalse((self.root / "missing").exists())
            self.assertEqual(list(outside.iterdir()), [])

    def test_merge_preserves_unmanaged_content_and_updates_only_owned_block(self):
        unmanaged = '// Custom\r\nuser_pref("custom.example", true);\r\n'
        merge = firefox["merge_preferences"]
        first = merge(unmanaged, self.source.read_text())
        updated = merge(first + "// Tail\n", 'user_pref("browser.urlbar.suggest.searches", true);\n')
        self.assertTrue(updated.startswith(unmanaged))
        self.assertTrue(updated.endswith("// Tail\n"))
        self.assertIn('user_pref("browser.urlbar.suggest.searches", true);', updated)
        self.assertNotIn('user_pref("browser.urlbar.suggest.searches", false);', updated)
        self.assertEqual(updated.count(firefox["BEGIN"]), 1)
        self.assertEqual(merge(updated, 'user_pref("browser.urlbar.suggest.searches", true);\n'), updated)

    def test_malformed_markers_fail_without_overwriting_user_file(self):
        profile = self.profile()
        path = profile / "user.js"
        begin, end = firefox["BEGIN"], firefox["END"]
        for original in (begin + "\n", end + "\n", end + "\n" + begin + "\n",
                         begin + "\n" + end + "\n" + begin + "\n" + end + "\n"):
            with self.subTest(original=original):
                path.write_text(original)
                with self.assertRaisesRegex(ValueError, "Malformed"):
                    firefox["apply_preferences"](self.home, self.source)
                self.assertEqual(path.read_text(), original)

    def test_apply_creates_private_file_preserves_existing_mode_and_converges(self):
        profile = self.profile()
        path = profile / "user.js"
        apply = firefox["apply_preferences"]
        apply(self.home, self.source)
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        expected = path.read_bytes()
        path.chmod(0o640)
        before = path.stat().st_mtime_ns
        apply(self.home, self.source)
        self.assertEqual(path.read_bytes(), expected)
        self.assertEqual(path.stat().st_mtime_ns, before)
        self.source.write_text('user_pref("browser.urlbar.suggest.searches", true);\n')
        apply(self.home, self.source)
        self.assertEqual(path.stat().st_mode & 0o777, 0o640)
        self.assertIn('user_pref("browser.urlbar.suggest.searches", true);', path.read_text())

    def test_external_user_js_symlink_is_rejected(self):
        profile = self.profile()
        with tempfile.TemporaryDirectory() as directory:
            outside = Path(directory) / "user.js"
            outside.write_text("// Keep\n")
            (profile / "user.js").symlink_to(outside)
            with self.assertRaisesRegex(ValueError, "outside"):
                firefox["apply_preferences"](self.home, self.source)
            self.assertEqual(outside.read_text(), "// Keep\n")

    def group_profiles(self):
        work = self.profile()
        personal = self.root / "other.random"
        personal.mkdir()
        unrelated = self.root / "unrelated"
        unrelated.mkdir()
        with (self.root / "profiles.ini").open("a") as registry:
            registry.write("StoreID=a1b2\n[InstallTEST]\nDefault=random.Profile 1\n")
        groups = self.root / "Profile Groups"
        groups.mkdir()
        database = groups / "a1b2.sqlite"
        connection = sqlite3.connect(database)
        self.addCleanup(connection.close)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("CREATE TABLE Profiles (name TEXT, path TEXT)")
        rows = [("Personal", personal.name), ("Work", work.name), ("Other", unrelated.name)]
        connection.executemany("INSERT INTO Profiles VALUES (?, ?)", rows)
        connection.commit()
        for name, value in (("personal", "personal-setting"), ("work", "work-setting")):
            (self.source.parent / (name + ".js")).write_text(f'user_pref("example", "{value}");\n')
        return work, personal, unrelated, connection, rows

    def test_profile_group_preserves_distinct_personal_and_work_preferences(self):
        work, personal, unrelated, connection, rows = self.group_profiles()
        firefox["apply_preferences"](self.home, self.source, work_enabled=True)
        self.assertIn('user_pref("example", "personal-setting");', (personal / "user.js").read_text())
        self.assertNotIn("work-setting", (personal / "user.js").read_text())
        self.assertIn('user_pref("example", "work-setting");', (work / "user.js").read_text())
        self.assertNotIn("personal-setting", (work / "user.js").read_text())
        self.assertFalse((unrelated / "user.js").exists())
        self.assertEqual(connection.execute("SELECT name, path FROM Profiles").fetchall(), rows)

    def test_work_profile_is_unchanged_when_work_feature_is_disabled(self):
        work, personal, _, _, _ = self.group_profiles()
        path = work / "user.js"
        path.write_text('// Keep work preferences\nuser_pref("example", "existing-work");\n')
        apply = firefox["apply_preferences"]
        for enabled in (False, True, False):
            with self.subTest(work_enabled=enabled):
                before = (path.read_bytes(), path.stat().st_mtime_ns)
                apply(self.home, self.source, work_enabled=enabled)
                self.assertIn('user_pref("example", "personal-setting");', (personal / "user.js").read_text())
                if enabled:
                    self.assertIn('user_pref("example", "work-setting");', path.read_text())
                else:
                    self.assertEqual((path.read_bytes(), path.stat().st_mtime_ns), before)

    def test_unreadable_profile_group_fails_before_writes(self):
        profile = self.profile()
        with (self.root / "profiles.ini").open("a") as registry:
            registry.write("StoreID=a1b2\n")
        groups = self.root / "Profile Groups"
        groups.mkdir()
        (groups / "a1b2.sqlite").write_text("Not a database")
        with self.assertRaisesRegex(ValueError, "Cannot read Firefox profile group"):
            firefox["apply_preferences"](self.home, self.source)
        self.assertFalse((profile / "user.js").exists())


if __name__ == "__main__":
    unittest.main()
