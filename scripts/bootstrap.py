#!/usr/bin/env python3
"""Orchestrate configuration, Ansible, and chezmoi without owning their state."""

import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def run(command, **kwargs):
    return subprocess.run(command, check=True, cwd=ROOT, **kwargs)


def require_fedora():
    release = Path("/etc/os-release").read_text()
    if 'ID=fedora\n' not in release and 'ID="fedora"\n' not in release:
        raise ValueError("This setup supports Fedora only.")
    if os.geteuid() == 0:
        raise ValueError("Run bootstrap as the desktop user, with sudo available.")


def dependencies(tools, readonly=False):
    missing = [package for executable, package in tools.items() if not shutil.which(executable)]
    if not missing:
        return
    if readonly:
        raise ValueError(f"Missing dependencies: {', '.join(missing)}. Install them before checking.")
    run(["sudo", "dnf", "install", "-y", *sorted(set(missing))])


def choose(label, values, selected, multiple=False):
    if shutil.which("gum"):
        command = ["gum", "choose", "--header", label]
        if multiple:
            command += ["--no-limit"]
        if selected:
            command += ["--selected", ",".join(selected)]
        result = run([*command, *values], text=True, stdout=subprocess.PIPE).stdout.splitlines()
        return result if multiple else result[0]
    print(f"\n{label}")
    for index, value in enumerate(values, 1):
        print(f"  {index}. {'[x]' if value in selected else '[ ]'} {value}")
    answer = input("Numbers separated by commas, or none (Enter keeps selection): " if multiple
                   else "Number (Enter keeps current selection): ").strip()
    if not answer:
        return selected if multiple else selected[0]
    if multiple and answer.lower() == "none":
        return []
    try:
        indices = [int(x.strip()) - 1 for x in answer.split(",")]
        if any(x < 0 or x >= len(values) for x in indices) or (not multiple and len(indices) != 1):
            raise ValueError
        result = list(dict.fromkeys(values[x] for x in indices))
        return result if multiple else result[0]
    except ValueError as exc:
        raise ValueError("Invalid selection; use the displayed numbers.") from exc


def confirm(message):
    if shutil.which("gum"):
        return subprocess.run(["gum", "confirm", message], cwd=ROOT).returncode == 0
    return input(f"{message} [y/N] ").strip().lower() in ("y", "yes")


def text_input(label, current):
    if shutil.which("gum"):
        return run(["gum", "input", "--header", label, "--value", current],
                   text=True, stdout=subprocess.PIPE).stdout.strip()
    return input(f"{label} [{current}]: ").strip() or current


def configure(config, local, engine):
    """The UI emits overrides; it never runs workstation installation commands."""
    import copy

    local = copy.deepcopy(local)
    defaults = engine.read_yaml(ROOT / "config/defaults.yml")
    local.setdefault("machine", {})["type"] = choose(
        "Machine type", ["desktop", "laptop"], [config["machine"]["type"]])
    enabled = choose("Features", list(engine.FEATURES),
                     [x for x in engine.FEATURES if config["features"][x]], multiple=True)
    local["features"] = {key: key in enabled for key in engine.FEATURES}
    if "desktop" in enabled:
        local["preferences"] = dict(config["preferences"])
        for key in ("shell", "terminal", "editor", "browser"):
            local["preferences"][key] = choose(
                key.capitalize(), list(engine.PREFERENCES[key]), [config["preferences"][key]])
        apps = choose("Applications", list(config["apps"]),
                      [key for key, value in config["apps"].items() if value], multiple=True)
        local["apps"] = {key: key in apps for key in config["apps"]}
        if local["preferences"]["editor"] == "vscode":
            local["apps"]["vscode"] = True
    if "development" in enabled:
        development = dict(config["development"])
        components = ["dotnet", "java", "node", "python", "containers", "terraform",
                      "powershell", "typst", "anaconda", "ai_clis"]
        wanted = choose("Development tooling", components,
                        [key for key in components if development[key]], multiple=True)
        for key in components:
            if isinstance(development[key], list):
                development[key] = development[key] if key in wanted else []
                if key in wanted and not development[key]:
                    if key == "ai_clis":
                        development[key] = ["antigravity", "claude-code", "codex"]
                    else:
                        default = {"dotnet": "8.0", "java": "21", "node": "22", "python": "system"}[key]
                        development[key] = text_input(f"{key} versions, comma-separated", default).split(",")
                        development[key] = [value.strip() for value in development[key]]
            else:
                development[key] = key in wanted
        local["development"] = development
        if development["containers"]:
            local.setdefault("preferences", {})["container_engine"] = choose(
                "Container engine", ["podman", "docker"], [config["preferences"]["container_engine"]])
    for group in ("desktop", "development", "work", "gaming", "virtualization"):
        selected = config["flatpak"]["applications"][group]
        apps = list(dict.fromkeys(defaults["flatpak"]["applications"][group] + selected))
        if group in enabled and apps:
            local.setdefault("flatpak", {}).setdefault("applications", {})[group] = choose(
                f"{group.capitalize()} Flatpaks", apps, selected, multiple=True)
    local["git"] = dict(config["git"])
    for key in ("name", "email"):
        local["git"][key] = text_input(f"Personal Git {key}", config["git"][key])
    if "work" in enabled:
        for key in ("work_name", "work_email"):
            local["git"][key] = text_input(f"Git {key}", config["git"][key])
    return local


def collections(readonly):
    if not importlib.util.find_spec("packaging"):
        if readonly:
            raise ValueError("Install python3-packaging before checking collection versions.")
        run(["sudo", "dnf", "install", "-y", "python3-packaging"])
    import yaml
    from packaging.specifiers import SpecifierSet

    result = run(["ansible-galaxy", "collection", "list", "--format", "json"],
                 text=True, stdout=subprocess.PIPE)
    installed = json.loads(result.stdout)
    requirement = yaml.safe_load((ROOT / "ansible/requirements.yml").read_text())["collections"][0]
    versions = SpecifierSet(requirement["version"])
    if any(requirement["name"] in group and group[requirement["name"]]["version"] in versions
           for group in installed.values()):
        return
    if readonly:
        raise ValueError("Missing a compatible community.general; run ansible-galaxy collection install -r ansible/requirements.yml.")
    run(["ansible-galaxy", "collection", "install", "-r", "ansible/requirements.yml"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preset")
    parser.add_argument("--machine", help="Hardware definition in config/machines")
    parser.add_argument("--local", default=str(ROOT / ".local.yml"))
    parser.add_argument("--no-local", action="store_true", help="Ignore saved overrides for this run")
    parser.add_argument("--yes", action="store_true", help="Apply without configuration/confirmation prompts")
    parser.add_argument("--configure", action="store_true", help="Edit selections even when .local.yml exists")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--show-config", action="store_true")
    modes.add_argument("--validate", action="store_true")
    modes.add_argument("--syntax-check", action="store_true")
    modes.add_argument("--check", action="store_true", help="Ansible check mode and chezmoi dry run")
    modes.add_argument("--verify", action="store_true", help="Verify selected installed state")
    parser.add_argument("--diff", action="store_true")
    parser.add_argument("--tags")
    parser.add_argument("--dotfiles", action="store_true", help="Run only chezmoi")
    args = parser.parse_args()
    readonly = args.check or args.syntax_check or args.verify or args.show_config or args.validate
    inspect_only = args.show_config or args.validate or args.syntax_check
    interactive = sys.stdin.isatty() and sys.stdout.isatty()
    if args.configure and (readonly or not interactive):
        raise ValueError("--configure requires an interactive apply run.")
    if not inspect_only:
        require_fedora()
    if not importlib.util.find_spec("yaml"):
        if readonly:
            raise ValueError("Install python3-pyyaml before inspecting/checking configuration.")
        run(["sudo", "dnf", "install", "-y", "python3-pyyaml"])
    import configuration as engine
    import yaml

    config, selection, local = engine.resolve(args.preset, args.machine, args.local, not args.no_local)
    if args.show_config:
        print(yaml.safe_dump(config, sort_keys=False), end="")
        return
    if args.validate:
        print("Configuration valid.")
        return
    if not readonly and not args.yes and not args.preset and not interactive:
        raise ValueError("Use --preset NAME or --yes for unattended setup.")
    if not readonly and interactive and not args.yes and (args.configure or not args.preset):
        if not shutil.which("gum"):
            print("gum is unavailable; using text prompts (install gum for the selection UI).")
        if args.configure or not Path(args.local).exists() or confirm("Edit saved selections?"):
            local = configure(config, local, engine)
            config, selection, local = engine.resolve(selection["preset"], selection["machine"], local=local)
    print("\nEffective workstation configuration:\n" + yaml.safe_dump(config, sort_keys=False), flush=True)
    if not readonly and interactive and not args.yes and not args.preset:
        if not confirm("Apply this configuration?"):
            print("Cancelled; selections were not saved.")
            return
    dotfiles = args.dotfiles or not args.tags or "dotfiles" in args.tags.split(",")
    tools = {} if args.dotfiles else {"ansible-playbook": "ansible", "ansible-galaxy": "ansible"}
    if dotfiles and not args.syntax_check:
        tools.update({"chezmoi": "chezmoi", "git": "git"})
    dependencies(tools, readonly)
    runtime = ROOT / ".workstation"
    runtime.mkdir(mode=0o700, exist_ok=True)
    effective = runtime / "effective.yml"
    effective.write_text(yaml.safe_dump(config, sort_keys=False))
    effective.chmod(0o600)
    if not readonly and not args.no_local:
        saved = {"_selection": selection, **local}
        local_path = Path(args.local)
        if not local_path.exists() or engine.read_yaml(local_path) != saved:
            local_path.write_text(yaml.safe_dump(saved, sort_keys=False))
            local_path.chmod(0o600)
    if not args.dotfiles:
        collections(readonly)
        env = {**os.environ, "ANSIBLE_CONFIG": str(ROOT / "ansible/ansible.cfg")}
        playbook = "ansible/playbooks/verify.yml" if args.verify else "ansible/playbook.yml"
        command = ["ansible-playbook", "-i", "ansible/intentory.ini", playbook,
                   "-e", json.dumps({"workstation_effective_file": str(effective)})]
        if args.syntax_check:
            command += ["--syntax-check"]
        elif interactive and not args.verify:
            command += ["--ask-become-pass"]
        if args.check:
            command += ["--check"]
        if args.diff:
            command += ["--diff"]
        if args.tags:
            command += ["--tags", args.tags]
        run(command, env=env)
    if dotfiles and not args.syntax_check:
        chezmoi_config = runtime / "chezmoi.json"
        chezmoi_config.write_text(json.dumps({"sourceDir": str(ROOT / "chezmoi"),
                                             "data": {"workstation": config}}, indent=2) + "\n")
        chezmoi_config.chmod(0o600)
        command = ["chezmoi", "--config", str(chezmoi_config),
                   "--persistent-state", str(runtime / "chezmoi-state.boltdb")]
        if args.verify:
            # Always-run configuration scripts are pending actions, not tracked files.
            run([*command, "--exclude", "scripts", "verify"])
        elif args.check:
            run([*command, "diff"] if args.diff else [*command, "apply", "--dry-run", "--verbose"])
        else:
            # Modification scripts preserve unrelated state; owned files converge without prompts.
            run([*command, "apply", "--force"])
    if readonly:
        print("Requested checks completed; workstation state was not applied.")
    else:
        print("Configuration applied. See any 'Optional GNOME extension needs attention' messages above.")
        if config["features"]["desktop"]:
            print("Log out/in to load GNOME extensions and login-shell changes. Authenticate applications separately.")
        if config["features"]["work"] and not config["git"]["work_email"]:
            print("Set git.work_name and git.work_email in .local.yml before committing work projects.")
        if config["apps"]["jetbrains"] and config["features"]["desktop"]:
            print("Launch JetBrains Toolbox to install/authenticate IDEs; then set jetbrains_versions for preferences.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        print(f"Setup stopped: {exc}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        sys.exit(130)
