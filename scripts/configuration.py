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
    if path == "apps":
        return  # App records have an explicit schema and permit new stable keys.
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


def validate_apps(config):
    apps = config["apps"]
    flatpak_ids = []
    for key, app in apps.items():
        label = f"apps.{key}"
        require(re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]*", key) is not None,
                f"{label}: invalid app key")
        require(isinstance(app, dict), f"{label}: expected an app mapping")
        required = {"name", "enabled", "feature", "installer"}
        optional = {"flatpak", "rpm", "vendor", "requires", "integration", "autostart"}
        require(required <= app.keys() and not (app.keys() - required - optional),
                f"{label}: require name, enabled, feature and installer; unknown fields are not allowed")
        require(isinstance(app["name"], str) and bool(app["name"].strip())
                and "\n" not in app["name"] and "\r" not in app["name"],
                f"{label}.name: expected a nonempty single-line name")
        require(type(app["enabled"]) is bool, f"{label}.enabled: expected bool")
        require(app["feature"] in (*FEATURES, "base"), f"{label}.feature: unknown feature")
        installer = app["installer"]
        require(installer in ("flatpak", "rpm", "vendor"), f"{label}.installer: choose flatpak, rpm or vendor")
        require(installer in app and isinstance(app[installer], dict),
                f"{label}: declare a {installer} mapping")
        require(not ({"flatpak", "rpm", "vendor"} - {installer}) & app.keys(),
                f"{label}: only the selected installer may be declared")
        source = app[installer]
        if installer == "flatpak":
            require("id" in source and not (source.keys() - {"id", "background", "own_names"}),
                    f"{label}.flatpak: require id; optional fields are background and own_names")
            require(isinstance(source["id"], str) and re.fullmatch(
                r"[A-Za-z_][A-Za-z0-9_-]*(?:\.[A-Za-z_][A-Za-z0-9_-]*){2,}", source["id"]) is not None,
                f"{label}.flatpak.id: invalid application ID")
            require(source.get("background") is None or type(source["background"]) is bool,
                    f"{label}.flatpak.background: expected bool or null (unmanaged)")
            string_list(source.get("own_names", []), f"{label}.flatpak.own_names")
            flatpak_ids.append(source["id"])
        elif installer == "rpm":
            require(set(source) == {"packages"}, f"{label}.rpm: require only packages")
            string_list(source["packages"], f"{label}.rpm.packages")
            require(bool(source["packages"]), f"{label}.rpm.packages: expected at least one package")
        else:
            require(source == {"task": "jetbrains"}, f"{label}.vendor: supported task is jetbrains")
        if "integration" in app:
            integration_packages = {"onepassword": {"1password", "1password-cli"},
                                    "vicinae": {"vicinae"}}
            require(app["integration"] in integration_packages and installer == "rpm"
                    and integration_packages[app["integration"]] <= set(source["packages"]),
                    f"{label}.integration: supported integrations require their native RPMs")
        requirements = app.get("requires", {})
        require(isinstance(requirements, dict) and not (requirements.keys() -
                ({"features", "development", "apps"} | set(PREFERENCES))),
                f"{label}.requires: unknown requirements")
        for field, choices in (("features", FEATURES), ("apps", apps),
                               ("development", [name for name, value in config["development"].items()
                                                if type(value) is bool])):
            string_list(requirements.get(field, []), f"{label}.requires.{field}")
            require(set(requirements.get(field, [])) <= set(choices), f"{label}.requires.{field}: unknown selection")
        for field in PREFERENCES:
            if field in requirements:
                require(requirements[field] in PREFERENCES[field], f"{label}.requires.{field}: invalid preference")
        if "autostart" in app:
            startup = app["autostart"]
            require(isinstance(startup, dict) and not (startup.keys() - {"enabled", "name", "command", "try_exec"}),
                    f"{label}.autostart: unknown fields")
            require(type(startup.get("enabled", True)) is bool, f"{label}.autostart.enabled: expected bool")
            require(installer == "flatpak" or "command" in startup,
                    f"{label}.autostart: native and vendor apps require a command")
            for field in ("name", "command", "try_exec"):
                if field in startup:
                    require(isinstance(startup[field], str) and bool(startup[field])
                            and "\n" not in startup[field] and "\r" not in startup[field],
                            f"{label}.autostart.{field}: expected a nonempty single-line string")
            require(re.fullmatch(r"[A-Za-z0-9_.-]+", startup.get("name", key)) is not None,
                    f"{label}.autostart.name: invalid desktop entry name")
    require(len(flatpak_ids) == len(set(flatpak_ids)), "apps: duplicate Flatpak IDs")
    # Validate dependency cycles even for apps currently disabled by a feature.
    visited = set()

    def visit(key, stack):
        require(key not in stack, f"apps.{key}.requires.apps: dependency cycle")
        if key not in visited:
            for dependency in apps[key].get("requires", {}).get("apps", []):
                visit(dependency, stack | {key})
            visited.add(key)

    for key in apps:
        visit(key, set())


def active_apps(config):
    active = {}

    def enabled(key):
        if key not in active:
            app = config["apps"][key]
            requirements = app.get("requires", {})
            active[key] = (app["enabled"] and (app["feature"] == "base" or config["features"][app["feature"]])
                           and all(config["features"][feature] for feature in requirements.get("features", []))
                           and (not requirements.get("development") or config["features"]["development"])
                           and all(config["development"][name] for name in requirements.get("development", []))
                           and all(config["preferences"][name] == requirements[name]
                                   for name in PREFERENCES if name in requirements)
                           and all(enabled(dependency) for dependency in requirements.get("apps", [])))
        return active[key]

    return {key: app for key, app in config["apps"].items() if enabled(key)}


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
    records(config["flatpak"]["remotes"], "flatpak.remotes", ("name", "url"))
    require(len({x["name"] for x in config["flatpak"]["remotes"]}) ==
            len(config["flatpak"]["remotes"]), "flatpak.remotes: duplicate names")
    validate_apps(config)
    gnome = config["gnome"]
    records(gnome["system_extensions"], "gnome.system_extensions", ("package", "uuid"))
    for key in ("user_extensions", "enabled_extensions"):
        string_list(gnome[key], f"gnome.{key}")
    declared = [x["uuid"] for x in gnome["system_extensions"]] + gnome["user_extensions"]
    require(len(declared) == len(set(declared)),
            "gnome: extension declared as both system and user or duplicated")
    require(set(gnome["enabled_extensions"]) <= set(declared),
            "gnome.enabled_extensions must be declared in gnome.system_extensions or gnome.user_extensions")
    records(gnome["autostart"], "gnome.autostart", ("name", "title", "command"), ("try_exec",))
    names = [x["name"] for x in gnome["autostart"]]
    require(len(names) == len(set(names)), "gnome.autostart: duplicate names")
    for item in gnome["autostart"]:
        require(re.fullmatch(r"[A-Za-z0-9_.-]+", item["name"]) is not None,
                "gnome.autostart: invalid name")
        require("\n" not in item["title"] + item["command"] + item.get("try_exec", ""),
                "gnome.autostart: fields must be single-line")
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
        editor = config["preferences"]["editor"]
        require(editor in active_apps(config), f"preferences.editor={editor} requires an active apps.{editor} declaration")
        browser = config["preferences"]["browser"]
        require(browser in active_apps(config), f"preferences.browser={browser} requires an active apps.{browser} declaration")
        terminal = config["preferences"]["terminal"].replace("-", "_")
        require(terminal in active_apps(config), f"preferences.terminal requires an active apps.{terminal} declaration")
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
    features, development = config["features"], config["development"]
    preferences, packages = config["preferences"], config["packages"]
    apps = active_apps(config)

    def unique(items):
        return list(dict.fromkeys(items))

    def when(condition, items):
        return list(items) if condition else []

    desktop_packages = packages["desktop"] + [preferences["shell"]]
    selected_packages = unique(
        packages["base"] + when(features["desktop"], desktop_packages)
        + when(features["development"], packages["development"])
        + when(features["work"], packages["work"]) + when(features["personal"], packages["personal"])
        + when(features["virtualization"], packages["virtualization"]) + config["fonts"])
    flatpaks_by_feature = {feature: [app["flatpak"]["id"] for app in apps.values()
                                   if app["installer"] == "flatpak" and app["feature"] == feature]
                          for feature in ("base", *FEATURES)}
    selected_flatpaks = [app["flatpak"]["id"] for app in apps.values() if app["installer"] == "flatpak"]
    rpm_apps = [{"key": key, "name": app["name"], "feature": app["feature"], "packages": app["rpm"]["packages"]}
                for key, app in apps.items() if app["installer"] == "rpm"]
    app_packages = unique([package for app in rpm_apps for package in app["packages"]])
    vicinae = any(app.get("integration") == "vicinae" for app in apps.values())
    user_services = list(config["services"]["user"])
    if vicinae and not any(service["name"] in ("vicinae", "vicinae.service") for service in user_services):
        user_services.append({"name": "vicinae.service", "enabled": True, "state": "started"})
    vicinae_extension = when(vicinae, ["vicinae@dagimg-dot"])
    startup_entries = []
    for key, app in config["apps"].items():
        if "autostart" not in app:
            continue
        startup = app["autostart"]
        flatpak_id = app.get("flatpak", {}).get("id")
        entry = {"name": startup.get("name", flatpak_id or key), "title": app["name"],
                 "command": startup.get("command", f"flatpak run {flatpak_id}"),
                 "enabled": key in apps and startup.get("enabled", True)}
        if "try_exec" in startup:
            entry["try_exec"] = startup["try_exec"]
        startup_entries.append(entry)
    startup_entries += [{**item, "enabled": True} for item in config["gnome"]["autostart"]]
    require(len({item["name"] for item in startup_entries}) == len(startup_entries),
            "apps.autostart and gnome.autostart must not declare the same desktop entry twice")

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
    expected_rpms = unique(selected_packages + app_packages + config["hardware"]["packages"]
                           + when(selected_flatpaks, ["flatpak"]) + when(features["development"], toolchains))
    return {"apps": list(apps), "rpm_apps": rpm_apps,
            "coprs": unique(config["repositories"]["copr"] + when(vicinae, ["quadratech188/vicinae"])),
            "user_services": user_services,
            "gnome_user_extensions": unique(config["gnome"]["user_extensions"] + vicinae_extension),
            "gnome_enabled_extensions": unique(config["gnome"]["enabled_extensions"] + vicinae_extension),
            "integrations": unique([app["integration"] for app in apps.values() if "integration" in app]),
            "vendor_tasks": unique([app["vendor"]["task"] for app in apps.values() if app["installer"] == "vendor"]),
            "desktop_packages": desktop_packages, "packages": selected_packages,
            "flatpaks_by_feature": flatpaks_by_feature, "flatpaks": selected_flatpaks,
            "flatpak_background": [{"application": app["flatpak"]["id"], "allowed": app["flatpak"]["background"]}
                                   for app in apps.values() if app["installer"] == "flatpak"
                                   and app["flatpak"].get("background") is not None],
            "flatpak_overrides": [{"application": app["flatpak"]["id"], "own_name": name}
                                  for app in apps.values() if app["installer"] == "flatpak"
                                  for name in app["flatpak"].get("own_names", [])],
            "autostart": startup_entries, "system_services": system_services,
            "expected_rpms": expected_rpms}



def normalize_app_overrides(override, base):
    """Translate saved app selections to the unified schema without writing user files."""
    result = copy.deepcopy(override)
    legacy = (any(type(value) is bool for value in override.get("apps", {}).values())
              if isinstance(override.get("apps", {}), dict) else False)
    legacy = legacy or "work" in override or (isinstance(override.get("flatpak"), dict)
              and bool({"applications", "background", "overrides"} & override["flatpak"].keys()))
    explicit = result.get("apps", {})
    require(isinstance(explicit, dict), "apps: expected a mapping")
    explicit = {key: {"enabled": value} if type(value) is bool else value
                for key, value in explicit.items()}
    generated = {}
    if type(override.get("apps", {}).get("podman_desktop")) is bool:
        generated["pods"] = {"enabled": override["apps"]["podman_desktop"]}
    work = result.get("work")
    if isinstance(work, dict) and "azure_cli" in work:
        generated["azure_cli"] = {"enabled": work.pop("azure_cli")}
        if not work:
            result.pop("work")
    flatpak = result.get("flatpak", {})
    require(isinstance(flatpak, dict), "flatpak: expected a mapping")

    def catalog():
        return merge(base["apps"], merge(generated, explicit))

    def app_for_id(app_id, feature="desktop"):
        require(isinstance(app_id, str) and bool(app_id), "legacy Flatpak IDs must be nonempty strings")
        for key, app in catalog().items():
            if isinstance(app, dict) and isinstance(app.get("flatpak"), dict) and app["flatpak"].get("id") == app_id:
                return key
        key = app_id
        require(key not in catalog(), f"legacy Flatpak ID conflicts with app key: {key}")
        generated[key] = {"name": app_id, "enabled": False, "feature": feature,
                          "installer": "flatpak", "flatpak": {"id": app_id}}
        return key

    if "applications" in flatpak:
        groups = flatpak.pop("applications")
        require(isinstance(groups, dict) and set(groups) <= set(FEATURES),
                "legacy flatpak.applications: unknown feature group")
        for feature, ids in groups.items():
            string_list(ids, f"legacy flatpak.applications.{feature}")
            for key, app in catalog().items():
                if isinstance(app, dict) and app.get("installer") == "flatpak" \
                        and isinstance(app.get("flatpak"), dict) and "id" in app["flatpak"] \
                        and app.get("feature") == feature and not app.get("requires"):
                    generated.setdefault(key, {})["enabled"] = app["flatpak"]["id"] in ids
            for app_id in ids:
                generated.setdefault(app_for_id(app_id, feature), {})["enabled"] = True
    if "background" in flatpak:
        entries = flatpak.pop("background")
        records(entries, "legacy flatpak.background", ("application",), ("allowed",))
        require(len({item["application"] for item in entries}) == len(entries),
                "legacy flatpak.background: duplicate applications")
        for key, app in catalog().items():
            if isinstance(app, dict) and isinstance(app.get("flatpak"), dict) and "background" in app["flatpak"]:
                generated.setdefault(key, {}).setdefault("flatpak", {})["background"] = None
        for entry in entries:
            require(type(entry.get("allowed")) is bool, "legacy flatpak.background.allowed: expected bool")
            generated.setdefault(app_for_id(entry["application"]), {}).setdefault("flatpak", {})["background"] = entry["allowed"]
    if "overrides" in flatpak:
        entries = flatpak.pop("overrides")
        records(entries, "legacy flatpak.overrides", ("application", "own_name"))
        for key, app in catalog().items():
            if isinstance(app, dict) and isinstance(app.get("flatpak"), dict) and "own_names" in app["flatpak"]:
                generated.setdefault(key, {}).setdefault("flatpak", {})["own_names"] = []
        for entry in entries:
            key = app_for_id(entry["application"])
            generated.setdefault(key, {}).setdefault("flatpak", {}).setdefault("own_names", []).append(entry["own_name"])
    gnome = result.get("gnome", {})
    if isinstance(gnome, dict) and "autostart" in gnome:
        entries = gnome["autostart"]
        records(entries, "gnome.autostart", ("name", "title", "command"), ("try_exec",))
        require(len({entry["name"] for entry in entries}) == len(entries), "gnome.autostart: duplicate names")
        named_apps = {app["autostart"].get("name", app["flatpak"].get("id", key)
                      if isinstance(app.get("flatpak"), dict) else key): key
                      for key, app in catalog().items()
                      if isinstance(app, dict) and isinstance(app.get("autostart"), dict)}
        if legacy or any(entry["name"] in named_apps for entry in entries):
            for key in named_apps.values():
                generated.setdefault(key, {}).setdefault("autostart", {})["enabled"] = False
        supplemental = []
        for entry in entries:
            if entry["name"] in named_apps:
                key = named_apps[entry["name"]]
                generated.setdefault(key, {})["name"] = entry["title"]
                generated.setdefault(key, {})["autostart"] = {"enabled": True, "name": entry["name"],
                                                             "command": entry["command"]}
                if "try_exec" in entry:
                    generated[key]["autostart"]["try_exec"] = entry["try_exec"]
            else:
                supplemental.append(entry)
        gnome["autostart"] = supplemental
    if generated or "apps" in result:
        result["apps"] = merge(generated, explicit)
    if "flatpak" in result and not flatpak:
        result.pop("flatpak")
    return result


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
        config = merge(config, normalize_app_overrides(read_yaml(named_file("presets", preset)), config))
    local = normalize_app_overrides(local, config)
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
            config.pop("selected", None)
            validate(config)
            config["selected"] = select(config)
        else:
            config, _, _ = resolve(args.preset, args.local, not args.no_local)
    except ConfigurationError as exc:
        parser.exit(2, f"Configuration error: {exc}\n")
    print(json.dumps(config) if args.format == "json" else
          yaml.safe_dump(config, sort_keys=False), end="\n" if args.format == "json" else "")


if __name__ == "__main__":
    main()
