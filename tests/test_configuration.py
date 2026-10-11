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

    def test_background_permissions_follow_selected_features(self):
        personal = self.resolve(use_local=False)["selected"]["flatpak_background"]
        self.assertEqual([item["application"] for item in personal],
                         ["org.localsend.localsend_app", "com.valvesoftware.Steam"])
        work = self.resolve(preset="work", use_local=False)["selected"]["flatpak_background"]
        self.assertEqual([item["application"] for item in work],
                         ["org.localsend.localsend_app", "com.github.IsmaelMartinez.teams_for_linux"])
        inactive = self.resolve(local={"features": {key: False for key in engine.FEATURES}})
        self.assertEqual(inactive["selected"]["flatpak_background"], [])

    def test_legacy_background_permission_overrides_replace_the_list(self):
        declaration = [{"application": "com.valvesoftware.Steam", "allowed": False}]
        config = self.resolve(local={"flatpak": {"background": declaration}})
        self.assertEqual(config["selected"]["flatpak_background"], declaration)
        self.assertEqual(self.resolve(local={"flatpak": {"background": []}})
                         ["selected"]["flatpak_background"], [])

    def test_legacy_background_permissions_reject_invalid_declarations(self):
        invalid = [
            [{"application": "org.example.App"}],
            [{"application": "org.example.App", "allowed": "true"}],
            [{"application": "org.example.App", "allowed": 1}],
            [{"application": "../App", "allowed": True}],
            [{"application": "org.example.App", "allowed": True, "extra": "yes"}],
            [{"application": "org.example.App", "allowed": True},
             {"application": "org.example.App", "allowed": False}],
        ]
        for declarations in invalid:
            with self.subTest(declarations=declarations), self.assertRaises(engine.ConfigurationError):
                self.resolve(local={"flatpak": {"background": declarations}})

    def test_app_overrides_merge_without_repeating_metadata(self):
        local = {"apps": {"steam": {"enabled": False},
                          "localsend": {"flatpak": {"background": False}}}}
        config = self.resolve(local=local)
        self.assertEqual(config["apps"]["localsend"]["name"], "LocalSend")
        self.assertEqual(config["apps"]["localsend"]["flatpak"]["id"], "org.localsend.localsend_app")
        self.assertNotIn("com.valvesoftware.Steam", config["selected"]["flatpaks"])
        self.assertEqual(config["selected"]["flatpak_background"],
                         [{"application": "org.localsend.localsend_app", "allowed": False}])
        unmanaged = self.resolve(local={"apps": {"localsend": {"flatpak": {"background": None}}}})
        self.assertNotIn("org.localsend.localsend_app",
                         [item["application"] for item in unmanaged["selected"]["flatpak_background"]])

    def test_new_app_records_are_consumed_by_their_installer(self):
        local = {"apps": {
            "example": {"name": "Example App", "enabled": True, "feature": "personal",
                        "installer": "flatpak", "flatpak": {"id": "org.example.App", "background": False,
                                                              "own_names": ["org.example.Tray"]},
                        "autostart": {"enabled": True}},
            "rpm_example": {"name": "RPM Example", "enabled": True, "feature": "work",
                            "installer": "rpm", "rpm": {"packages": ["example-package"]}},
        }}
        selected = self.resolve(local=local)["selected"]
        self.assertIn("org.example.App", selected["flatpaks_by_feature"]["personal"])
        self.assertIn({"application": "org.example.App", "own_name": "org.example.Tray"},
                      selected["flatpak_overrides"])
        startup = next(item for item in selected["autostart"] if item["name"] == "org.example.App")
        self.assertEqual(startup["command"], "flatpak run org.example.App")
        self.assertTrue(startup["enabled"])
        self.assertNotIn("example-package", selected["expected_rpms"])
        local["features"] = {"work": True, "personal": False}
        selected = self.resolve(local=local)["selected"]
        self.assertNotIn("org.example.App", selected["flatpaks"])
        self.assertIn("example-package", selected["expected_rpms"])
        self.assertFalse(next(item for item in selected["autostart"] if item["name"] == "org.example.App")["enabled"])

    def test_app_dependencies_and_startup_follow_enablement(self):
        config = self.resolve(local={"apps": {"podman_desktop": {"enabled": False},
                                              "pods": {"requires": {"apps": ["podman_desktop"]}},
                                              "localsend": {"enabled": False}}})
        self.assertNotIn("com.github.marhkb.Pods", config["selected"]["flatpaks"])
        self.assertNotIn("io.podman_desktop.PodmanDesktop", config["selected"]["flatpaks"])
        self.assertFalse(next(item for item in config["selected"]["autostart"]
                              if item["name"] == "org.localsend.localsend_app")["enabled"])
        self.assertFalse(next(item for item in config["selected"]["autostart"]
                              if item["name"] == "com.github.IsmaelMartinez.teams_for_linux")["enabled"])
        independent = self.resolve(local={"apps": {"podman_desktop": {"enabled": False}}})
        self.assertIn("com.github.marhkb.Pods", independent["selected"]["flatpaks"],
                      "independent app selections must not inherit the old combined toggle")

    def test_app_schema_rejects_invalid_records(self):
        invalid = [
            {"localsend": {"enabled": "true"}},
            {"localsend": {"name": "bad\nname"}},
            {"localsend": {"feature": "unknown"}},
            {"localsend": {"installer": "unknown"}},
            {"localsend": {"flatpak": {"background": "true"}}},
            {"localsend": {"flatpak": {"background": 1}}},
            {"localsend": {"flatpak": {"id": "../bad"}}},
            {"localsend": {"flatpak": {"own_names": ["duplicate", "duplicate"]}}},
            {"localsend": {"requires": {"apps": ["missing"]}}},
            {"localsend": {"requires": {"development": ["dotnet"]}}},
            {"localsend": {"requires": {"browser": "unknown"}}},
            {"localsend": {"requires": {"unknown": True}}},
            {"localsend": {"requires": {"apps": ["steam"]}},
             "steam": {"requires": {"apps": ["localsend"]}}},
            {"localsend": {"autostart": {"enabled": "true"}}},
            {"localsend": {"autostart": {"name": "../bad"}}},
            {"localsend": {"autostart": {"command": "bad\ncommand"}}},
            {"vscode": {"rpm": {"packages": []}}},
            {"jetbrains": {"vendor": {"task": "unknown"}}},
            {"onepassword": {"integration": "unknown"}},
            {"extra": {"name": "Duplicate", "enabled": False, "feature": "desktop", "installer": "flatpak",
                       "flatpak": {"id": "org.localsend.localsend_app"}}},
            {"localsend": {"unknown": True}},
        ]
        for apps in invalid:
            with self.subTest(apps=apps), self.assertRaises(engine.ConfigurationError):
                self.resolve(local={"apps": apps})

    def test_legacy_app_selections_are_normalized_without_mutation(self):
        local = {"apps": {"podman_desktop": False, "jetbrains": False}, "work": {"azure_cli": False},
                 "flatpak": {"applications": {"desktop": ["org.localsend.localsend_app", "org.example.App"]},
                             "background": [{"application": "org.localsend.localsend_app", "allowed": False}]}}
        original = copy.deepcopy(local)
        config, _, normalized = engine.resolve(local=local)
        self.assertEqual(local, original)
        self.assertNotIn("work", normalized)
        self.assertNotIn("flatpak", normalized)
        self.assertFalse(config["apps"]["spotify"]["enabled"])
        self.assertFalse(config["apps"]["pods"]["enabled"])
        self.assertFalse(config["apps"]["azure_cli"]["enabled"])
        self.assertIn("org.example.App", config["selected"]["flatpaks"])
        self.assertEqual(config["selected"]["flatpak_background"],
                         [{"application": "org.localsend.localsend_app", "allowed": False}])

    def test_editor_browser_and_terminal_apps_must_be_active(self):
        for key in ("vscode", "firefox", "ptyxis"):
            with self.subTest(key=key), self.assertRaises(engine.ConfigurationError):
                self.resolve(local={"apps": {key: {"enabled": False}}})
        config = self.resolve(local={"preferences": {"editor": "neovim", "terminal": "gnome-terminal"},
                                     "apps": {"vscode": {"enabled": False}}})
        self.assertIn("gnome-terminal", config["selected"]["expected_rpms"])
        self.assertNotIn("ptyxis", config["selected"]["expected_rpms"])
        self.assertNotIn("code", config["selected"]["expected_rpms"])

    def test_supplemental_startup_does_not_disable_declared_apps(self):
        entry = {"name": "helper", "title": "Hardware helper", "command": "/usr/bin/helper"}
        config = self.resolve(local={"gnome": {"autostart": [entry]}})
        self.assertTrue(next(item for item in config["selected"]["autostart"]
                             if item["name"] == "org.localsend.localsend_app")["enabled"])
        self.assertIn({**entry, "enabled": True}, config["selected"]["autostart"])
        legacy = self.resolve(local={"apps": {"onepassword": True}, "gnome": {"autostart": []}})
        self.assertTrue(all(not item["enabled"] for item in legacy["selected"]["autostart"]))
        with self.assertRaises(engine.ConfigurationError):
            self.resolve(local={"apps": {"localsend": {"autostart": False}}, "gnome": {"autostart": []}})

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
        self.assertIn("io.podman_desktop.PodmanDesktop", podman["flatpaks_by_feature"]["development"])
        docker = self.resolve(local={"preferences": {"container_engine": "docker"}})["selected"]
        self.assertEqual([x["name"] for x in docker["system_services"]], ["docker.service"])
        self.assertNotIn("io.podman_desktop.PodmanDesktop", docker["flatpaks_by_feature"]["development"])
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
