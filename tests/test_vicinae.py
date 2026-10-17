"""Exercise shortcuts using a private D-Bus and dconf database."""
import getpass
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(all(shutil.which(t) for t in ("ansible-playbook", "dbus-run-session", "gsettings")),
                     "Ansible and GNOME tools are required")
class VicinaeShortcutTests(unittest.TestCase):
    def test_shortcut_check_mode_preservation_and_convergence(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            role = ROOT / "ansible/roles/gnome"
            play = [{"name": "Isolated integration", "hosts": "localhost", "connection": "local",
                     "gather_facts": False,
                     "vars": {"role_path": str(role), "desktop_target_user": getpass.getuser(),
                              "desktop_user_env": {"XDG_CONFIG_HOME": str(base / "config"),
                              "DBUS_SESSION_BUS_ADDRESS": "{{ lookup('env', 'DBUS_SESSION_BUS_ADDRESS') }}"}},
                     "tasks": [{"name": "Configure shortcut", "ansible.builtin.import_tasks": str(role / "tasks/vicinae.yml")}]}]
            playbook = base / "playbook.yml"
            playbook.write_text(yaml.safe_dump(play))
            script = r'''
import ast
import subprocess
import sys
schema = "org.gnome.settings-daemon.plugins.media-keys"
key = "custom-keybindings"
keep = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/keep/"
owned = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/vicinae/"
def run(*args):
    result = subprocess.run(args, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout.strip()
def paths():
    return ast.literal_eval(run("gsettings", "get", schema, key).removeprefix("@as "))
run("gsettings", "set", schema, key, repr([keep]))
command = ["ansible-playbook", "-i", "localhost,", sys.argv[1], "-e", "ansible_become=false"]
run(*command, "--check", "--diff")
assert paths() == [keep], paths()
run(*command)
assert paths() == [keep, owned], paths()
entry = schema + ".custom-keybinding:" + owned
assert run("gsettings", "get", entry, "command") == "'vicinae toggle'"
assert run("gsettings", "get", entry, "binding") == "'<Super><Control>space'"
assert "changed=0" in run(*command)
assert paths() == [keep, owned], paths()
'''
            result = subprocess.run(["dbus-run-session", "--", "python3", "-c", script, str(playbook)],
                                    capture_output=True, text=True,
                                    env={**os.environ, "XDG_CONFIG_HOME": str(base / "config"),
                                         "ANSIBLE_CONFIG": str(ROOT / "ansible/ansible.cfg"),
                                         "ANSIBLE_LOCAL_TEMP": str(base / "local"),
                                         "ANSIBLE_REMOTE_TEMP": str(base / "remote"), "ANSIBLE_NOCOLOR": "1"})
            if result.returncode == 127 and "Operation not permitted" in result.stderr:
                self.skipTest("Private D-Bus sockets are blocked by this sandbox")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
