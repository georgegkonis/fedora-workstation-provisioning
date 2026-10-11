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

    def test_upgrade_is_opt_in_and_extends_the_tag_selection(self):
        def tags(*args):
            ansible = self.execute("--preset", "minimal", "--no-local", *args)[0].call_args_list[0].args[0]
            return ansible[ansible.index("--tags") + 1] if "--tags" in ansible else None
        self.assertIsNone(tags())
        self.assertEqual(tags("--upgrade"), "all,upgrade")
        self.assertEqual(tags("--upgrade", "--tags", "gnome"), "gnome,upgrade")
        self.assertEqual(tags("--tags", "upgrade"), "upgrade")

    def test_inspection_creates_no_runtime_files_and_runs_no_tools(self):
        run, dependencies = self.execute("--show-config", "--preset", "minimal")
        run.assert_not_called()
        dependencies.assert_not_called()
        self.assertFalse((self.root / ".workstation").exists())
        self.assertFalse(self.local.exists())

    def test_reapply_preserves_local_comments_when_selection_is_unchanged(self):
        content = "# Keep my comments\n_selection:\n  preset: minimal\n"
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

    def test_background_choices_follow_new_app_selections(self):
        config = configuration.resolve(use_local=False)[0]
        original = json.loads(json.dumps(config))

        def choose(label, values, selected, multiple=False):
            if label == "Personal applications":
                return []
            if label == "Flatpaks allowed to run in the background":
                self.assertNotIn("Steam", values)
                return ["LocalSend"]
            if label == "Flatpaks denied background execution":
                self.assertNotIn("LocalSend", values)
                return ["Spotify"]
            return selected if multiple else selected[0]

        with patch.object(bootstrap, "choose", side_effect=choose), \
                patch.object(bootstrap, "text_input", side_effect=lambda label, current: current):
            local = bootstrap.configure(config, {}, configuration)
        selected = configuration.resolve(local=local)[0]["selected"]["flatpak_background"]
        self.assertCountEqual(selected, [{"application": "org.localsend.localsend_app", "allowed": True},
                                        {"application": "com.spotify.Client", "allowed": False}])
        self.assertEqual(config, original)
        self.assertTrue(configuration.resolve(local=local)[0]["apps"]["steam"]["flatpak"]["background"],
                        "inactive apps must retain saved background choices")

    def test_check_normalizes_legacy_selections_without_writing_them(self):
        content = "# Keep legacy choices\napps:\n  onepassword: false\nflatpak:\n  applications:\n    desktop:\n    - org.localsend.localsend_app\n"
        self.local.write_text(content)
        self.execute("--check", "--tags", "flatpak_background")
        self.assertEqual(self.local.read_text(), content)
        effective = configuration.read_yaml(self.root / ".workstation/effective.yml")
        self.assertFalse(effective["apps"]["onepassword"]["enabled"])
        self.assertNotIn("com.spotify.Client", effective["selected"]["flatpaks"])
        self.assertNotIn("applications", effective["flatpak"])

    def test_normal_apply_saves_only_the_normalized_override_format(self):
        self.local.write_text("apps:\n  onepassword: false\n")
        self.execute("--yes")
        saved = configuration.read_yaml(self.local)
        self.assertEqual(saved["apps"]["onepassword"], {"enabled": False})

    def test_background_and_startup_choices_emit_app_overrides(self):
        config = configuration.resolve(use_local=False)[0]
        original = json.loads(json.dumps(config))

        def choose(label, values, selected, multiple=False):
            if label == "Flatpaks allowed to run in the background":
                return list(values)
            if label == "Applications started at login":
                return []
            self.assertNotEqual(label, "Flatpaks denied background execution",
                                "an empty candidate set must not invoke the picker")
            return selected if multiple else selected[0]

        with patch.object(bootstrap, "choose", side_effect=choose), \
                patch.object(bootstrap, "text_input", side_effect=lambda label, current: current):
            local = bootstrap.configure(config, {}, configuration)
        selected = configuration.resolve(local=local)[0]["selected"]
        self.assertTrue(all(item["allowed"] for item in selected["flatpak_background"]))
        for name in ("1password", "org.localsend.localsend_app", "jetbrains-toolbox"):
            self.assertFalse(next(item for item in selected["autostart"] if item["name"] == name)["enabled"])
        self.assertEqual(config, original)

    def test_unattended_apply_needs_explicit_intent(self):
        with self.assertRaisesRegex(ValueError, "unattended"):
            self.execute()
        self.assertFalse((self.root / ".workstation").exists())


if __name__ == "__main__":
    unittest.main()
