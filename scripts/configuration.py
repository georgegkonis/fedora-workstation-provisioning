#!/usr/bin/env python3
"""Load and validate the configuration shared by Ansible and chezmoi."""

import argparse
import copy
import json
from pathlib import Path
import re

import yaml

ROOT = Path(__file__).resolve().parents[1]
FEATURES = ("desktop", "development", "work", "personal", "virtualization")
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


def local_configuration(path, use_local=True):
    if not use_local:
        return {}
    return read_yaml(path) if path.exists() else {}


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
    records(config["flatpak"]["overrides"], "flatpak.overrides", ("application", "own_name"))
    gnome = config["gnome"]
    records(gnome["system_extensions"], "gnome.system_extensions", ("package", "uuid"))
    for key in ("user_extensions", "enabled_extensions"):
        string_list(gnome[key], f"gnome.{key}")
    declared = [x["uuid"] for x in gnome["system_extensions"]] + gnome["user_extensions"]
    require(len(declared) == len(set(declared)),
            "gnome: extension declared as both system and user or duplicated")
    require(set(gnome["enabled_extensions"]) <= set(declared),
            "gnome.enabled_extensions must be declared in gnome.system_extensions or gnome.user_extensions")
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


def select(config):
    """Resolve what the selected features install; shared by apply and verification."""
    features, development, apps = config["features"], config["development"], config["apps"]
    preferences, work = config["preferences"], config["work"]
    flatpaks, packages = config["flatpak"]["applications"], config["packages"]

    def unique(items):
        return list(dict.fromkeys(items))

    def when(condition, items):
        return list(items) if condition else []

    desktop_packages = (packages["desktop"] + [preferences["shell"], preferences["terminal"]]
                        + when(preferences["editor"] == "neovim", ["neovim"]))
    desktop_flatpaks = flatpaks["desktop"] + [
        "org.mozilla.firefox" if preferences["browser"] == "firefox" else "com.google.Chrome"]
    podman_desktop = (features["desktop"] and features["development"] and development["containers"]
                      and apps["podman_desktop"] and preferences["container_engine"] == "podman")
    development_flatpaks = flatpaks["development"] + when(
        podman_desktop, ["io.podman_desktop.PodmanDesktop", "com.github.marhkb.Pods"])
    selected_packages = unique(
        packages["base"] + when(features["desktop"], desktop_packages)
        + when(features["development"], packages["development"])
        + when(features["work"], packages["work"]) + when(features["personal"], packages["personal"])
        + when(features["virtualization"], packages["virtualization"]) + config["fonts"])
    selected_flatpaks = unique(
        when(features["desktop"], desktop_flatpaks) + when(features["development"], development_flatpaks)
        + when(features["work"], flatpaks["work"]) + when(features["personal"], flatpaks["personal"])
        + when(features["virtualization"], flatpaks["virtualization"]))

    services = config["services"]["system"] + config["hardware"]["services"]
    declared = {service["name"] for service in services}
    docker = (features["development"] and development["containers"]
              and preferences["container_engine"] == "docker"
              and not declared & {"docker.service", "docker"})
    system_services = services + when(docker, [{"name": "docker.service", "enabled": True, "state": "started"}]) \
        + when(features["virtualization"] and "virtqemud.socket" not in declared,
               [{"name": "virtqemud.socket", "enabled": True, "state": "started"}])

    containers = (["podman"] if preferences["container_engine"] == "podman" else
                  ["docker-ce", "docker-ce-cli", "containerd.io", "docker-buildx-plugin",
                   "docker-compose-plugin"])
    toolchains = (
        [f"dotnet-sdk-{v}" for v in development["dotnet"]]
        + [f"java-{v}-openjdk-devel" for v in development["java"]]
        + [f"nodejs{v}" for v in development["node"]] + [f"nodejs{v}-npm" for v in development["node"]]
        + when("system" in development["python"], ["python3", "python3-pip"])
        + [f"python{v}" for v in development["python"] if v != "system"]
        + when(development["terraform"], ["terraform"]) + when(development["powershell"], ["powershell"])
        + when(development["containers"], containers))
    expected_rpms = unique(
        selected_packages + config["hardware"]["packages"] + when(selected_flatpaks, ["flatpak"])
        + when(features["desktop"] and apps["vscode"], ["code"])
        + when(features["desktop"] and apps["onepassword"], ["1password", "1password-cli"])
        + when(features["work"] and work["azure_cli"], ["azure-cli"])
        + when(features["development"], toolchains))
    return {"desktop_packages": desktop_packages, "desktop_flatpaks": desktop_flatpaks,
            "development_flatpaks": development_flatpaks, "packages": selected_packages,
            "flatpaks": selected_flatpaks, "system_services": system_services,
            "expected_rpms": expected_rpms}


def resolve(preset=None, local_path=None, use_local=True, local=None):
    path = Path(local_path).resolve() if local_path else ROOT / ".local.yml"
    local = copy.deepcopy(local if local is not None else local_configuration(path, use_local))
    selection = local.pop("_selection", {})
    require(isinstance(selection, dict) and set(selection) <= {"preset"},
            "_selection: expected preset")
    preset = preset if preset is not None else selection.get("preset", "")
    require(isinstance(preset, str), "preset name must be a string")
    config = read_yaml(ROOT / "config/defaults.yml")
    if preset:
        config = merge(config, read_yaml(named_file("presets", preset)))
    config = merge(config, local)
    validate_shape(config, read_yaml(ROOT / "config/defaults.yml"))
    validate(config)
    config["selected"] = select(config)
    return config, {"preset": preset}, local


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preset", default=None)
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
            config, _, _ = resolve(args.preset, args.local, not args.no_local)
    except ConfigurationError as exc:
        parser.exit(2, f"Configuration error: {exc}\n")
    print(json.dumps(config) if args.format == "json" else
          yaml.safe_dump(config, sort_keys=False), end="\n" if args.format == "json" else "")


if __name__ == "__main__":
    main()
