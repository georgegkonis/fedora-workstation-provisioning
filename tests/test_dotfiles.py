"""Use a real chezmoi binary against temporary homes when it is available."""

import hashlib
import json
from pathlib import Path
import shutil
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
            ("minimal", {}),
            ("work", {"git": {"work_name": "Work Example", "work_email": "work@example.test"},
                             "preferences": {"shell": "zsh"}, "development": {"anaconda": True},
                             "jetbrains_versions": {"Rider": "2026.2"}}),
        ]
        for preset, overrides in profiles:
            with self.subTest(preset=preset), tempfile.TemporaryDirectory() as directory:
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
