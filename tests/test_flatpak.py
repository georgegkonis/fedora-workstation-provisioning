"""Exercise portal tasks with a fake Flatpak CLI, never the desktop permission store."""

import getpass
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which("ansible-playbook"), "Ansible is not installed")
class FlatpakBackgroundTests(unittest.TestCase):
    def test_permissions_are_additive_idempotent_and_check_mode_is_readonly(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            state = base / "permissions.json"
            original = {"org.example.Denied": "yes", "org.example.Unmanaged": "ask"}
            state.write_text(json.dumps(original))
            cli = base / "flatpak"
            cli.write_text(f"#!{sys.executable}\n" + '''import json
import os
from pathlib import Path
import sys
state = Path(os.environ["MOCK_FLATPAK_STATE"])
permissions = json.loads(state.read_text())
args = sys.argv[1:]
if args[0] == "permission-show":
    if os.environ.get("MOCK_FLATPAK_FAIL_READ") == "1":
        sys.exit(2)
    app = args[1]
    print(f"notifications\\tnotification\\t{app}\\tyes\\t0x00")
    if app in permissions:
        print(f"background\\tbackground\\t{app}\\t{permissions[app]}\\t0x00")
elif args[:3] == ["permission-set", "background", "background"]:
    permissions[args[3]] = args[4]
    state.write_text(json.dumps(permissions))
else:
    sys.exit(3)
''')
            cli.chmod(0o755)
            declarations = [{"application": "org.example.Allowed", "allowed": True},
                            {"application": "org.example.Denied", "allowed": False}]
            user_env = {"PATH": f"{base}:{os.environ['PATH']}", "MOCK_FLATPAK_STATE": str(state)}

            def run(*args, verify=False):
                variable = "verify_flatpak_background_app" if verify else "flatpak_background_app"
                task_file = (ROOT / "ansible/tasks/verify-flatpak-background.yml" if verify else
                             ROOT / "ansible/roles/flatpak/tasks/background.yml")
                playbook = base / "playbook.yml"
                playbook.write_text(yaml.safe_dump([{
                    "name": "Exercise background permissions", "hosts": "localhost",
                    "connection": "local", "gather_facts": False,
                    "vars": {"desktop_target_user": getpass.getuser(), "desktop_user_env": user_env},
                    "tasks": [{"name": "Exercise declared permissions",
                               "ansible.builtin.include_tasks": str(task_file),
                               "loop": declarations, "loop_control": {"loop_var": variable}}],
                }]))
                return subprocess.run(
                    ["ansible-playbook", "-i", "localhost,", str(playbook),
                     "-e", "ansible_become=false", *args], capture_output=True, text=True,
                    env={**os.environ, "ANSIBLE_CONFIG": str(ROOT / "ansible/ansible.cfg"),
                         "ANSIBLE_LOCAL_TEMP": str(base / "local"),
                         "ANSIBLE_REMOTE_TEMP": str(base / "remote"), "ANSIBLE_NOCOLOR": "1"})

            mismatch = run(verify=True)
            self.assertNotEqual(mismatch.returncode, 0, mismatch.stdout)
            self.assertIn("does not match", mismatch.stdout)
            before = state.read_bytes()
            preview = run("--check", "--diff")
            self.assertEqual(preview.returncode, 0, preview.stdout + preview.stderr)
            self.assertIn("changed=2", preview.stdout)
            self.assertEqual(state.read_bytes(), before)
            applied = run()
            self.assertEqual(applied.returncode, 0, applied.stdout + applied.stderr)
            self.assertIn("changed=2", applied.stdout)
            self.assertEqual(json.loads(state.read_text()),
                             {**original, "org.example.Allowed": "yes", "org.example.Denied": "no"})
            converged = run()
            self.assertEqual(converged.returncode, 0, converged.stdout + converged.stderr)
            self.assertIn("changed=0", converged.stdout)
            verified = run(verify=True)
            self.assertEqual(verified.returncode, 0, verified.stdout + verified.stderr)
            user_env["MOCK_FLATPAK_FAIL_READ"] = "1"
            before = state.read_bytes()
            failed = run()
            self.assertNotEqual(failed.returncode, 0, failed.stdout)
            self.assertEqual(state.read_bytes(), before, "failed reads must never trigger permission writes")


if __name__ == "__main__":
    unittest.main()
