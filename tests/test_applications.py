"""Exercise app task dispatch and managed startup files in temporary workspaces."""

import getpass
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import configuration


@unittest.skipUnless(shutil.which("ansible-playbook"), "Ansible is not installed")
class ApplicationTasksTests(unittest.TestCase):
    def run_playbook(self, base, play, *args):
        playbook = base / "playbook.yml"
        playbook.write_text(yaml.safe_dump([play]))
        result = subprocess.run(
            ["ansible-playbook", "-i", "localhost,", str(playbook), "-e", "ansible_become=false", *args],
            capture_output=True, text=True,
            env={**os.environ, "ANSIBLE_CONFIG": str(ROOT / "ansible/ansible.cfg"),
                 "ANSIBLE_LOCAL_TEMP": str(base / "local"), "ANSIBLE_REMOTE_TEMP": str(base / "remote"),
                 "ANSIBLE_NOCOLOR": "1"})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout

    def test_rpm_dispatch_respects_app_and_feature_tags(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            role = base / "packages"
            shutil.copytree(ROOT / "ansible/roles/packages", role)
            # Stub only the installation leaf; exercise the real role's include/apply tags.
            (role / "tasks/applications.yml").write_text(yaml.safe_dump([{
                "name": "Observe selected application",
                "ansible.builtin.debug": {"msg": {"application_key": "{{ packages_app.key }}",
                                                  "packages": "{{ packages_app.packages }}"}},
            }]))
            config = configuration.resolve(preset="work", use_local=False)[0]
            play = {"name": "Exercise app dispatch", "hosts": "localhost", "connection": "local",
                    "gather_facts": False, "vars": {"workstation": config}, "roles": [str(role)]}
            for tag, expected in (("vscode", ["vscode"]), ("azure_cli", ["azure_cli"]),
                                  ("applications", [app["key"] for app in config["selected"]["rpm_apps"]]),
                                  ("gnome", [])):
                with self.subTest(tag=tag):
                    output = self.run_playbook(base, play, "--check", "--tags", tag)
                    for app in config["selected"]["rpm_apps"]:
                        self.assertEqual(f'"application_key": "{app["key"]}"' in output,
                                         app["key"] in expected, output)

    def test_disabled_app_startup_converges_and_preserves_unrelated_files(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            home = base / "home"
            startup = home / ".config/autostart"
            startup.mkdir(parents=True)
            unrelated = startup / "unrelated.desktop"
            unrelated.write_text("Keep this startup entry\n")
            localsend = startup / "org.localsend.localsend_app.desktop"
            localsend.write_text("[Desktop Entry]\nX-GNOME-Autostart-enabled=true\n")
            config = configuration.resolve(use_local=False, local={"apps": {"localsend": {"enabled": False}}})[0]
            play = {"name": "Exercise startup configuration", "hosts": "localhost", "connection": "local",
                    "gather_facts": False,
                    "vars": {"workstation": config, "desktop_target_home": str(home),
                             "desktop_target_user": getpass.getuser()},
                    "tasks": [{"name": "Configure managed startup",
                               "ansible.builtin.import_tasks": str(ROOT / "ansible/roles/gnome/tasks/autostart.yml")}]}

            def snapshot():
                return {path.name: (path.read_bytes(), path.stat().st_mtime_ns) for path in startup.iterdir()}

            original = snapshot()
            self.run_playbook(base, play, "--check", "--diff")
            self.assertEqual(snapshot(), original)
            self.run_playbook(base, play)
            self.assertIn("X-GNOME-Autostart-enabled=false", localsend.read_text())
            self.assertIn("Exec=flatpak run org.localsend.localsend_app", localsend.read_text())
            self.assertIn("X-GNOME-Autostart-enabled=false",
                          (startup / "com.github.IsmaelMartinez.teams_for_linux.desktop").read_text())
            self.assertEqual(snapshot()[unrelated.name], original[unrelated.name])
            applied = snapshot()
            output = self.run_playbook(base, play)
            self.assertIn("changed=0", output)
            self.assertEqual(snapshot(), applied)


if __name__ == "__main__":
    unittest.main()
