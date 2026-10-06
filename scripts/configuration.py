#!/usr/bin/env python3
"""Load and validate the configuration shared by Ansible and chezmoi."""

import argparse
import copy
import json
from pathlib import Path
import re
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]
FEATURES = ("desktop", "development", "work", "gaming", "virtualization")
PREFERENCES = {
    "shell": ("bash", "zsh"),
    "terminal": ("ptyxis", "gnome-terminal"),
    "editor": ("vscode", "neovim"),
    "browser": ("firefox", "chrome"),
    "container_engine": ("podman", "docker"),
}


class ConfigurationError(ValueError):
    pass


class UniqueKeyLoader(yaml.SafeLoader):
    """YAML's usual last-key-wins behavior hides configuration mistakes."""


def unique_mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if not isinstance(key, str):
            raise ConfigurationError("YAML mapping keys must be strings")
        if key in result:
            raise ConfigurationError(f"duplicate YAML key: {key}")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping
)


def read_yaml(path):
    try:
        result = yaml.load(path.read_text(), Loader=UniqueKeyLoader)
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigurationError(f"{path}: {exc}") from exc
    if not isinstance(result, dict):
        raise ConfigurationError(f"{path}: expected a YAML mapping")
    return result


def merge(base, override):
    """Only mappings merge. Lists and scalar values replace the earlier value."""
    result = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def named_file(directory, name):
    if not isinstance(name, str) or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]*", name):
        raise ConfigurationError(f"invalid {directory} name: {name!r}")
    path = ROOT / "config" / directory / f"{name}.yml"
    if not path.is_file():
        raise ConfigurationError(f"unknown {directory} selection: {name}")
    return path


def migrate_profile(path):
    old = read_yaml(path).get("profile")
    if not isinstance(old, dict):
        raise ConfigurationError(f"{path}: expected the legacy profile mapping")
    known = {"work_machine", "install_anaconda", "toolchains", "git",
             "jetbrains_versions", "obsidian_vaults"}
    if set(old) - known:
        raise ConfigurationError(f"{path}: unknown legacy profile keys: {set(old) - known}")
    result = {}
    if "work_machine" in old:
        result["features"] = {"work": old["work_machine"]}
    if "toolchains" in old:
        result["development"] = old["toolchains"]
    if "install_anaconda" in old:
        result.setdefault("development", {})["anaconda"] = old["install_anaconda"]
    for key in ("git", "jetbrains_versions", "obsidian_vaults"):
        if key in old:
            result[key] = old[key]
    return result


def local_configuration(path, use_local=True):
    if not use_local:
        return {}
    if path.exists():
        return read_yaml(path)
    legacy = ROOT / "profile.local.yml"
    if path == ROOT / ".local.yml" and legacy.is_file():
        print("Using legacy profile.local.yml; the next apply saves it as .local.yml.",
              file=sys.stderr)
        return migrate_profile(legacy)
    return {}


def require(condition, message):
    if not condition:
        raise ConfigurationError(message)


def validate_shape(value, reference, path=""):
    label = path or "configuration"
    require(type(value) is type(reference), f"{label}: expected {type(reference).__name__}")
    if isinstance(reference, dict) and reference:
        require(not (set(value) - set(reference)),
                f"{label}: unknown keys: {', '.join(sorted(set(value) - set(reference)))}")
        for key, expected in reference.items():
            require(key in value, f"{label}: missing {key}")
            validate_shape(value[key], expected, f"{path}.{key}".lstrip("."))


def string_list(value, label):
    require(isinstance(value, list) and all(isinstance(x, str) and x for x in value),
            f"{label}: expected a list of nonempty strings")
    require(len(value) == len(set(value)), f"{label}: duplicate entries")


def records(value, label, required, optional=()):
    require(isinstance(value, list), f"{label}: expected a list")
    for item in value:
        require(isinstance(item, dict), f"{label}: entries must be mappings")
        require(set(required) <= set(item), f"{label}: entries require {', '.join(required)}")
        require(set(item) <= set(required) | set(optional), f"{label}: unknown entry fields")
        for key in required:
            require(isinstance(item[key], str) and bool(item[key]),
                    f"{label}.{key}: expected a nonempty string")


def validate_services(value, label):
    records(value, label, ("name",), ("enabled", "state", "unit"))
    require(len({item["name"] for item in value}) == len(value), f"{label}: duplicate units")
    for item in value:
        require(re.fullmatch(r"[A-Za-z0-9_.@:-]+", item["name"]) is not None,
                f"{label}: invalid unit name")
        require(type(item.get("enabled", True)) is bool, f"{label}.enabled: expected bool")
        require(item.get("state", "started") in ("started", "stopped"),
                f"{label}.state: choose started or stopped")
        if "unit" in item:
            require(isinstance(item["unit"], str) and
                    re.fullmatch(r"[A-Za-z0-9_.@:-]+", item["unit"]) is not None,
                    f"{label}.unit: use a filename under systemd/system or systemd/user")
            scope = "user" if label == "services.user" else "system"
            require((ROOT / "systemd" / scope / item["unit"]).is_file(),
                    f"{label}: custom unit {item['unit']} does not exist")


def validate(config):
    validate_shape(config, read_yaml(ROOT / "config/defaults.yml"))
    require(config["machine"]["type"] in ("desktop", "laptop"),
            "machine.type: choose desktop or laptop")
    for key, choices in PREFERENCES.items():
        require(config["preferences"][key] in choices,
                f"preferences.{key}: choose {', '.join(choices)}")
    for parent in ("packages",):
        for key, items in config[parent].items():
            string_list(items, f"{parent}.{key}")
    string_list(config["fonts"], "fonts")
    string_list(config["hardware"]["packages"], "hardware.packages")
    for key, items in config["flatpak"]["applications"].items():
        string_list(items, f"flatpak.applications.{key}")
    records(config["flatpak"]["remotes"], "flatpak.remotes", ("name", "url"))
    require(len({x["name"] for x in config["flatpak"]["remotes"]}) ==
            len(config["flatpak"]["remotes"]), "flatpak.remotes: duplicate names")
    for key, items in config["gnome"].items():
        string_list(items, f"gnome.{key}")
    require(set(config["gnome"]["enabled_extensions"]) <= set(config["gnome"]["extensions"]),
            "gnome.enabled_extensions must be included in gnome.extensions")
    patterns = {"dotnet": r"[0-9]+\.[0-9]+", "java": r"[0-9]+", "node": r"[0-9]+",
                "python": r"system|[0-9]+\.[0-9]+"}
    for key, pattern in patterns.items():
        versions = config["development"][key]
        string_list(versions, f"development.{key}")
        require(all(re.fullmatch(pattern, x) for x in versions),
                f"development.{key}: use quoted version strings")
    string_list(config["development"]["ai_clis"], "development.ai_clis")
    require(set(config["development"]["ai_clis"]) <= {"antigravity", "claude-code", "codex"},
            "development.ai_clis: unsupported CLI")
    for prefix in ("", "work_"):
        name, email = (config["git"][prefix + key] for key in ("name", "email"))
        require(bool(name.strip()) == bool(email.strip()),
                f"git: provide both {prefix}name and {prefix}email, or leave both empty")
    for value in config["git"].values():
        require("\n" not in value and "\r" not in value, "git identity cannot contain newlines")
    if config["features"]["desktop"]:
        require(config["preferences"]["editor"] != "vscode" or config["apps"]["vscode"],
                "preferences.editor=vscode requires apps.vscode=true")
    for ide, version in config["jetbrains_versions"].items():
        require(ide in ("Rider", "PyCharm", "WebStorm", "DataGrip"),
                f"jetbrains_versions: unsupported IDE {ide}")
        require(isinstance(version, str) and re.fullmatch(r"[0-9]{4}\.[0-9]+", version),
                "jetbrains_versions: use quoted versions such as '2026.2'")
    records(config["obsidian_vaults"], "obsidian_vaults", ("name", "repo"), ("version",))
    for vault in config["obsidian_vaults"]:
        require(vault["name"] not in (".", "..") and
                re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._ -]*", vault["name"]),
                "obsidian_vaults.name must be a single safe directory name")
        require(isinstance(vault.get("version", "HEAD"), str),
                "obsidian_vaults.version: expected string")
    records(config["repositories"]["rpm"], "repositories.rpm",
            ("name", "description", "baseurl", "gpgkey"))
    string_list(config["repositories"]["copr"], "repositories.copr")
    for scope in ("system", "user"):
        validate_services(config["services"][scope], f"services.{scope}")
    validate_services(config["hardware"]["services"], "hardware.services")
    names = [x["name"] if "." in x["name"] else x["name"] + ".service"
             for x in config["services"]["system"] + config["hardware"]["services"]]
    require(len(names) == len(set(names)), "system and hardware services must not declare the same unit twice")


def resolve(preset=None, machine=None, local_path=None, use_local=True, local=None):
    path = Path(local_path).resolve() if local_path else ROOT / ".local.yml"
    local = copy.deepcopy(local if local is not None else local_configuration(path, use_local))
    selection = local.pop("_selection", {})
    require(isinstance(selection, dict) and set(selection) <= {"preset", "machine"},
            "_selection: expected preset and/or machine")
    preset = preset if preset is not None else selection.get("preset", "")
    machine = machine if machine is not None else selection.get("machine", "")
    require(isinstance(preset, str) and isinstance(machine, str),
            "preset and machine names must be strings")
    config = read_yaml(ROOT / "config/defaults.yml")
    if preset:
        config = merge(config, read_yaml(named_file("presets", preset)))
    if machine:
        overrides = read_yaml(named_file("machines", machine))
        require(set(overrides) <= {"machine", "hardware"},
                "machine definitions may contain only machine metadata and hardware options")
        config = merge(config, overrides)
        config["machine"]["id"] = machine
    config = merge(config, local)
    validate_shape(config, read_yaml(ROOT / "config/defaults.yml"))
    # The selected definition is an identity, not an independently overridable preference.
    require(config["machine"]["id"] == (machine or ""),
            "select a machine definition with --machine or _selection.machine")
    validate(config)
    return config, {"preset": preset, "machine": machine}, local


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preset", default=None)
    parser.add_argument("--machine", default=None)
    parser.add_argument("--local", default=None)
    parser.add_argument("--no-local", action="store_true")
    parser.add_argument("--format", choices=("yaml", "json"), default="yaml")
    parser.add_argument("--effective", help="Validate an already resolved configuration file")
    args = parser.parse_args()
    try:
        if args.effective:
            config = read_yaml(Path(args.effective))
            validate(config)
        else:
            config, _, _ = resolve(args.preset, args.machine, args.local, not args.no_local)
    except ConfigurationError as exc:
        parser.exit(2, f"Configuration error: {exc}\n")
    print(json.dumps(config) if args.format == "json" else
          yaml.safe_dump(config, sort_keys=False), end="\n" if args.format == "json" else "")


if __name__ == "__main__":
    main()
