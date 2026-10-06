"""Use a real chezmoi binary against temporary homes when it is available."""

import hashlib
import json
from contextlib import closing
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import configuration


@unittest.skipUnless(shutil.which("chezmoi"), "chezmoi is not installed")
class DotfileTests(unittest.TestCase):
    def test_profiles_preserve_existing_state_and_converge(self):
        profiles = [
            ("personal", {}),
            ("personal", {"apps": {"onepassword": False}}),
            ("personal", {"preferences": {"browser": "chrome"}}),
            ("minimal", {}),
            ("work", {"git": {"work_name": "Work Example", "work_email": "work@example.test"},
                             "preferences": {"shell": "zsh"}, "development": {"anaconda": True},
                             "jetbrains_versions": {"Rider": "2026.2"}}),
        ]
        for preset, overrides in profiles:
            with self.subTest(preset=preset, overrides=overrides), tempfile.TemporaryDirectory() as directory:
                base = Path(directory)
                home = base / "home"
                home.mkdir()
                config, _, _ = configuration.resolve(preset=preset, local=overrides)
                config_file = base / "chezmoi.json"
                config_file.write_text(json.dumps({"sourceDir": str(ROOT / "chezmoi"),
                                                   "destDir": str(home), "data": {"workstation": config}}))
                (home / ".bashrc").write_text("export CUSTOM=kept\n")
                (home / ".gitconfig").write_text("[user]\n name = Old Name\n email = old@example.test\n[alias]\n st = status\n")
                editor = home / ".config/Code/User"
                editor.mkdir(parents=True)
                settings = editor / "settings.json"
                settings.write_text('// JSONC\n{"custom.example": true, "editor.inlineSuggest.enabled": false,}\n')
                rider = home / ".config/JetBrains/Rider2026.2/options"
                rider.mkdir(parents=True)
                (rider / "editor.xml").write_text('<application><component name="Unrelated"/></application>')
                firefox = home / ".config/mozilla/firefox"
                firefox_profile = firefox / "random.Profile 1"
                firefox_profile.mkdir(parents=True)
                (firefox / "profiles.ini").write_text(
                    "[Profile0]\nName=default-release\nIsRelative=1\nPath=random.Profile 1\nStoreID=a1b2\n"
                    "[InstallTEST]\nDefault=random.Profile 1\n")
                personal_profile = firefox / "other.random"
                personal_profile.mkdir()
                (firefox / "Profile Groups").mkdir()
                with closing(sqlite3.connect(firefox / "Profile Groups/a1b2.sqlite")) as database:
                    database.execute("CREATE TABLE Profiles (name TEXT, path TEXT)")
                    database.executemany("INSERT INTO Profiles VALUES (?, ?)",
                                         [("Personal", personal_profile.name), ("Work", firefox_profile.name)])
                    database.commit()
                user_js = firefox_profile / "user.js"
                user_js.write_text('// Keep\nuser_pref("custom.example", true);\n')
                command = [shutil.which("chezmoi"), "--config", str(config_file),
                           "--persistent-state", str(base / "state.boltdb")]

                def run(*args):
                    return subprocess.run([*command, *args], check=True, capture_output=True, text=True)

                def snapshot():
                    return {str(path.relative_to(home)): (hashlib.sha256(path.read_bytes()).hexdigest(), path.stat().st_mtime_ns)
                            for path in home.rglob("*") if path.is_file()}

                original = snapshot()
                run("apply", "--dry-run", "--verbose")
                self.assertEqual(snapshot(), original)
                run("apply", "--force")
                applied = snapshot()
                self.assertEqual(applied[".config/Code/User/settings.json"],
                                 original[".config/Code/User/settings.json"],
                                 "VS Code settings content and modification time must stay unchanged")
                run("apply", "--force")
                self.assertEqual(snapshot(), applied, "second apply must not rewrite files")
                run("--exclude", "scripts", "verify")
                self.assertEqual(run("--exclude", "scripts", "diff").stdout, "")
                self.assertIn("CUSTOM=kept", (home / ".bashrc").read_text())
                self.assertEqual((home / ".bashrc").read_text().count("# BEGIN CHEZMOI MANAGED WORKSTATION"), 1)
                self.assertIn("st = status", (home / ".gitconfig").read_text())
                self.assertTrue(user_js.read_text().startswith('// Keep\nuser_pref("custom.example", true);\n'))
                if config["features"]["desktop"] and config["preferences"]["browser"] == "firefox":
                    self.assertIn('user_pref("browser.startup.homepage", "https://start.duckduckgo.com/");',
                                  user_js.read_text())
                    self.assertEqual(user_js.read_text().count("// BEGIN CHEZMOI MANAGED FIREFOX"), 1)
                    self.assertIn('user_pref("privacy.globalprivacycontrol.enabled", true);', user_js.read_text())
                    personal_js = (personal_profile / "user.js").read_text()
                    self.assertIn('user_pref("signon.generation.enabled", false);', personal_js)
                    self.assertNotIn('user_pref("privacy.globalprivacycontrol.enabled", true);', personal_js)
                else:
                    self.assertEqual(user_js.read_text(), '// Keep\nuser_pref("custom.example", true);\n')
                    self.assertFalse((personal_profile / "user.js").exists())
                if preset == "minimal":
                    self.assertFalse((home / ".var/app/org.mozilla.firefox/data/bin/1password-wrapper.sh").exists())
                if preset == "work":
                    self.assertNotIn("Old Name", (home / ".gitconfig").read_text())
                    self.assertIn("work@example.test", (home / ".config/git/work.gitconfig").read_text())
                    self.assertIn("Unrelated", (rider / "editor.xml").read_text())
                    self.assertTrue((home / ".zshrc").exists())
                    self.assertIn("conda.sh", (home / ".config/shell/workstation.sh").read_text())


if __name__ == "__main__":
    unittest.main()
