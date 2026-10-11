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
        config = self.resolve(preset="work", local={
            "features": {"personal": True}, "hardware": {"packages": ["local-package"]},
            "packages": {"base": ["git"]},
        })
        self.assertTrue(config["features"]["work"])
        self.assertTrue(config["features"]["personal"])
        self.assertEqual(config["hardware"]["packages"], ["local-package"])
        self.assertEqual(config["packages"]["base"], ["git"])
        self.assertIn("gcc", config["packages"]["development"])

    def test_saved_selection_and_explicit_preset(self):
        local = {"_selection": {"preset": "work"}}
        self.assertTrue(self.resolve(local=local)["features"]["work"])
        self.assertFalse(self.resolve(preset="minimal", local=local)["features"]["work"])
        self.assertIn("_selection", local, "resolving must not mutate supplied overrides")

    def test_no_local_ignores_saved_overrides(self):
        (self.root / ".local.yml").write_text("features:\n  work: true\n")
        self.assertTrue(self.resolve()["features"]["work"])
        self.assertFalse(self.resolve(use_local=False)["features"]["work"])

    def test_invalid_values_are_rejected(self):
        invalid = [
            {"features": {"develpment": True}},
            {"features": {"work": "yes"}},
            {"preferences": {"shell": "fish"}},
            {"development": {"dotnet": [8.0]}},
            {"development": {"ai_clis": ["unknown"]}},
            {"machine": {"id": "example"}},
            {"apps": {"vscode": False}},
            {"git": {"work_name": "Name"}},
            {"obsidian_vaults": [{"name": "../outside", "repo": "example"}]},
            {"services": {"user": [{"name": "bad/unit"}]}},
            {"services": {"system": [{"name": "docker", "state": "restarted"}]}},
            {"services": {"system": [{"name": "example", "unit": "../outside"}]}},
            {"gnome": {"user_extensions": [], "enabled_extensions": ["missing@example"]}},
            {"gnome": {"autostart": [{"name": "../x", "title": "X", "command": "x"}]}},
            {"gnome": {"autostart": [{"name": "x", "title": "X"}]}},
            {"gnome": {"autostart": [{"name": "x", "title": "X", "command": "a\nb"}]}},
            {"gnome": {"autostart": [{"name": "x", "title": "X", "command": "x"},
                                     {"name": "x", "title": "Y", "command": "y"}]}},
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
        self.assertEqual(config["development"]["dotnet"], ["8.0", "10.0"])

    def test_system_service_cannot_be_duplicated_in_hardware(self):
        with self.assertRaisesRegex(engine.ConfigurationError, "same unit twice"):
            self.resolve(local={"services": {"system": [{"name": "example"}]},
                                "hardware": {"services": [{"name": "example.service"}]}})

    def test_committed_presets_validate(self):
        for path in (self.root / "config/presets").glob("*.yml"):
            with self.subTest(preset=path.stem):
                self.resolve(preset=path.stem, use_local=False)

    def test_selected_software_follows_features(self):
        personal = self.resolve(use_local=False)["selected"]
        work = self.resolve(preset="work", use_local=False)["selected"]
        minimal = self.resolve(preset="minimal", use_local=False)["selected"]
        self.assertIn("com.valvesoftware.Steam", personal["flatpaks"])
        self.assertNotIn("com.valvesoftware.Steam", work["flatpaks"])
        self.assertIn("com.github.IsmaelMartinez.teams_for_linux", work["flatpaks"])
        self.assertEqual(minimal["flatpaks"][-1], "org.mozilla.firefox")
        self.assertNotIn("dotnet-sdk-8.0", minimal["expected_rpms"])
        self.assertIn("dotnet-sdk-10.0", personal["expected_rpms"])
        self.assertNotIn("dotnet-sdk-10.0", work["expected_rpms"])
        self.assertEqual(len(personal["packages"]), len(set(personal["packages"])))

    def test_container_engine_selects_services_and_flatpaks(self):
        podman = self.resolve(use_local=False)["selected"]
        self.assertEqual(podman["system_services"], [])
        self.assertIn("io.podman_desktop.PodmanDesktop", podman["development_flatpaks"])
        docker = self.resolve(local={"preferences": {"container_engine": "docker"}})["selected"]
        self.assertEqual([x["name"] for x in docker["system_services"]], ["docker.service"])
        self.assertNotIn("io.podman_desktop.PodmanDesktop", docker["development_flatpaks"])
        self.assertIn("docker-ce", docker["expected_rpms"])
        declared = self.resolve(local={"preferences": {"container_engine": "docker"},
                                       "services": {"system": [{"name": "docker", "state": "stopped"}]}})
        self.assertEqual([x["name"] for x in declared["selected"]["system_services"]], ["docker"])

    def test_virtualization_adds_libvirt_socket_once(self):
        local = {"features": {"virtualization": True}}
        services = self.resolve(local=local)["selected"]["system_services"]
        self.assertEqual([x["name"] for x in services], ["virtqemud.socket"])
        local["services"] = {"system": [{"name": "virtqemud.socket", "enabled": False}]}
        services = self.resolve(local=local)["selected"]["system_services"]
        self.assertEqual(services, [{"name": "virtqemud.socket", "enabled": False}])

    def test_effective_configuration_does_not_share_mutable_defaults(self):
        first = self.resolve(use_local=False)
        original = copy.deepcopy(first)
        first["packages"]["base"].clear()
        self.assertEqual(self.resolve(use_local=False), original)


class GnomeSettingsTests(unittest.TestCase):
    def test_declarations_are_well_formed(self):
        for path in sorted((engine.ROOT / "ansible/roles/gnome/files").glob("*.yml")):
            with self.subTest(path=path.name):
                (variable, items), = engine.read_yaml(path).items()
                self.assertTrue(variable.startswith("gnome_"))
                keys = [item["key"] for item in items]
                self.assertEqual(len(keys), len(set(keys)), "duplicate dconf keys")
                for item in items:
                    self.assertEqual(set(item), {"key", "value", "description"})
                    self.assertTrue(all(isinstance(item[k], str) and item[k] for k in item))


if __name__ == "__main__":
    unittest.main()
