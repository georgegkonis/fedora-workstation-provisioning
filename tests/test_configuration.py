"""Validate precedence and rejection before any workstation state can change."""

import copy
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import configuration as engine


class ConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        shutil.copytree(engine.ROOT / "config", self.root / "config")
        self.root_patch = patch.object(engine, "ROOT", self.root)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)
        self.addCleanup(self.temp.cleanup)

    def resolve(self, **kwargs):
        return engine.resolve(**kwargs)[0]

    def test_precedence_and_lists_replace(self):
        machines = self.root / "config/machines"
        machines.mkdir()
        (machines / "example.yml").write_text("machine:\n  type: laptop\nhardware:\n  packages: [hardware-package]\n")
        config = self.resolve(preset="personal-desktop", machine="example", local={
            "machine": {"type": "desktop"}, "hardware": {"packages": ["local-package"]},
            "packages": {"base": ["git"]},
        })
        self.assertEqual(config["machine"], {"type": "desktop", "id": "example"})
        self.assertEqual(config["hardware"]["packages"], ["local-package"])
        self.assertEqual(config["packages"]["base"], ["git"])
        self.assertIn("gcc", config["packages"]["development"])

    def test_saved_selection_and_explicit_preset(self):
        local = {"_selection": {"preset": "work-laptop"}}
        self.assertTrue(self.resolve(local=local)["features"]["work"])
        self.assertFalse(self.resolve(preset="minimal", local=local)["features"]["work"])
        self.assertIn("_selection", local, "resolving must not mutate supplied overrides")

    def test_no_local_ignores_saved_overrides(self):
        (self.root / ".local.yml").write_text("features:\n  work: true\n")
        self.assertTrue(self.resolve()["features"]["work"])
        self.assertFalse(self.resolve(use_local=False)["features"]["work"])

    def test_legacy_profile_is_translated_without_writing(self):
        (self.root / "profile.local.yml").write_text(
            "profile:\n  work_machine: true\n  install_anaconda: true\n"
            "  toolchains:\n    dotnet: ['9.0']\n    java: []\n    node: []\n    python: [system]\n")
        config = self.resolve()
        self.assertTrue(config["features"]["work"])
        self.assertTrue(config["development"]["anaconda"])
        self.assertEqual(config["development"]["dotnet"], ["9.0"])
        self.assertFalse((self.root / ".local.yml").exists())

    def test_machine_definition_cannot_select_general_apps(self):
        machines = self.root / "config/machines"
        machines.mkdir()
        (machines / "example.yml").write_text("apps:\n  jetbrains: false\n")
        with self.assertRaisesRegex(engine.ConfigurationError, "hardware"):
            self.resolve(machine="example")

    def test_invalid_values_are_rejected(self):
        invalid = [
            {"features": {"develpment": True}},
            {"features": {"work": "yes"}},
            {"preferences": {"shell": "fish"}},
            {"development": {"dotnet": [8.0]}},
            {"development": {"ai_clis": ["unknown"]}},
            {"machine": []},
            {"apps": {"vscode": False}},
            {"git": {"work_name": "Name"}},
            {"obsidian_vaults": [{"name": "../outside", "repo": "example"}]},
            {"services": {"user": [{"name": "bad/unit"}]}},
            {"services": {"system": [{"name": "docker", "state": "restarted"}]}},
            {"services": {"system": [{"name": "example", "unit": "../outside"}]}},
            {"gnome": {"extensions": []}},
        ]
        for override in invalid:
            with self.subTest(override=override), self.assertRaises(engine.ConfigurationError):
                self.resolve(local=override)

    def test_unknown_preset_and_path_traversal(self):
        for preset in ("missing", "../defaults", 42):
            with self.subTest(preset=preset), self.assertRaises(engine.ConfigurationError):
                self.resolve(preset=preset)

    def test_duplicate_and_malformed_yaml(self):
        path = self.root / ".local.yml"
        for value in ("features: {}\nfeatures: {}\n", "features: [\n", "- list\n"):
            path.write_text(value)
            with self.subTest(value=value), self.assertRaises(engine.ConfigurationError):
                self.resolve()

    def test_disabled_parent_makes_child_selections_harmless(self):
        config = self.resolve(preset="minimal")
        self.assertFalse(config["features"]["development"])
        self.assertTrue(config["development"]["containers"])
        self.assertEqual(config["development"]["dotnet"], ["8.0"])

    def test_system_service_cannot_be_duplicated_in_hardware(self):
        with self.assertRaisesRegex(engine.ConfigurationError, "same unit twice"):
            self.resolve(local={"services": {"system": [{"name": "example"}]},
                                "hardware": {"services": [{"name": "example.service"}]}})

    def test_committed_presets_validate(self):
        for path in (self.root / "config/presets").glob("*.yml"):
            with self.subTest(preset=path.stem):
                self.resolve(preset=path.stem, use_local=False)

    def test_effective_configuration_does_not_share_mutable_defaults(self):
        first = self.resolve(use_local=False)
        original = copy.deepcopy(first)
        first["packages"]["base"].clear()
        self.assertEqual(self.resolve(use_local=False), original)


if __name__ == "__main__":
    unittest.main()
