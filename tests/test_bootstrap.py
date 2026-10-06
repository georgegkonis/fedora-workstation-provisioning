"""Exercise orchestration without executing installation or accessing the real home."""

import contextlib
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import bootstrap
import configuration


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        shutil.copytree(configuration.ROOT / "config", self.root / "config")
        for module in (bootstrap, configuration):
            mock = patch.object(module, "ROOT", self.root)
            mock.start()
            self.addCleanup(mock.stop)
        self.local = self.root / ".local.yml"

    def execute(self, *args):
        with patch.object(sys, "argv", ["bootstrap", "--local", str(self.local), *args]), \
                patch.object(bootstrap, "require_fedora"), \
                patch.object(bootstrap, "dependencies") as dependencies, \
                patch.object(bootstrap, "collections"), \
                patch.object(bootstrap, "run") as run, \
                contextlib.redirect_stdout(io.StringIO()):
            bootstrap.main()
        return run, dependencies

    def test_check_uses_check_mode_and_never_saves_selections(self):
        content = "# Keep my comments\nfeatures:\n  work: false\n"
        self.local.write_text(content)
        run, dependencies = self.execute("--check", "--diff", "--preset", "minimal")
        self.assertEqual(self.local.read_text(), content)
        self.assertTrue(dependencies.call_args.args[1])
        ansible, chezmoi = [call.args[0] for call in run.call_args_list]
        self.assertEqual(ansible[0], "ansible-playbook")
        self.assertIn("--check", ansible)
        self.assertIn("--diff", ansible)
        self.assertEqual(chezmoi[0], "chezmoi")
        self.assertEqual(chezmoi[-1], "diff")
        self.assertNotIn("--force", chezmoi)

    def test_inspection_creates_no_runtime_files_and_runs_no_tools(self):
        run, dependencies = self.execute("--show-config", "--preset", "minimal")
        run.assert_not_called()
        dependencies.assert_not_called()
        self.assertFalse((self.root / ".workstation").exists())
        self.assertFalse(self.local.exists())

    def test_reapply_preserves_local_comments_when_selection_is_unchanged(self):
        content = "# Keep my comments\n_selection:\n  preset: minimal\n  machine: ''\n"
        self.local.write_text(content)
        self.execute("--yes")
        self.assertEqual(self.local.read_text(), content)
        effective = configuration.read_yaml(self.root / ".workstation/effective.yml")
        chezmoi = json.loads((self.root / ".workstation/chezmoi.json").read_text())
        self.assertEqual(effective, chezmoi["data"]["workstation"])

    def test_no_local_apply_preserves_saved_configuration(self):
        self.local.write_text("features:\n  work: true\n")
        self.execute("--preset", "minimal", "--no-local")
        self.assertEqual(self.local.read_text(), "features:\n  work: true\n")
        self.assertFalse(configuration.read_yaml(self.root / ".workstation/effective.yml")["features"]["work"])

    def test_readonly_dependencies_do_not_install(self):
        with patch.object(shutil, "which", return_value=None), patch.object(bootstrap, "run") as run:
            with self.assertRaisesRegex(ValueError, "Missing dependencies"):
                bootstrap.dependencies({"chezmoi": "chezmoi"}, readonly=True)
        run.assert_not_called()

    def test_unattended_apply_needs_explicit_intent(self):
        with self.assertRaisesRegex(ValueError, "unattended"):
            self.execute()
        self.assertFalse((self.root / ".workstation").exists())


if __name__ == "__main__":
    unittest.main()
