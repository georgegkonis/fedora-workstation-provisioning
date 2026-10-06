# Fedora workstation configuration

This repository configures a personal or work Fedora Workstation. Configuration data selects features and preferences; Ansible manages machine state, and chezmoi manages home configuration. Execution is additive: removing a selection does not uninstall software or purge unmanaged files.

```text
defaults → preset → hardware definition → local overrides
                         │
                 effective configuration
                         │
                  ┌──────┴──────┐
                  ▼             ▼
               Ansible       chezmoi
               Fedora        $HOME
```

## Fresh Fedora setup

```bash
git clone <repository-url>
cd laptop-provision
./bootstrap.sh
```

Run as your desktop account with sudo available. Bootstrap validates Fedora, resolves configuration, presents selections and a summary, installs missing bootstrap dependencies, runs Ansible, and applies chezmoi. Bootstrap dependencies are Python/PyYAML, Ansible, Git, chezmoi, and the `community.general` collection. They are installed only when missing. No workstation configuration is embedded in `bootstrap.sh`.

The interactive frontend uses [gum](https://github.com/charmbracelet/gum) when installed (`sudo dnf install gum`), with text prompts otherwise. Choose features, development components, applications, and preferences. Existing version lists are retained; additional versions can be selected in `.local.yml`. An existing local configuration can be reapplied or edited; `./bootstrap.sh --configure` opens the selections explicitly. Cancellation leaves saved selections unchanged.

## Presets and unattended setup

```bash
./bootstrap.sh --preset personal
./bootstrap.sh --preset work
./bootstrap.sh --preset minimal
```

Presets skip configuration questions and confirmation. A terminal run can still request the sudo password. Unattended execution requires working noninteractive sudo, or equivalent Ansible become configuration. `--yes` also skips configuration questions and confirmation when using saved selections/defaults.

`personal` uses the shared defaults. `work` enables work and disables gaming. `minimal` selects base packages and disables optional feature groups. Desktop and development are independently selectable. Gaming and virtualization currently use package/Flatpak lists and service defaults; they do not need placeholder roles.

For saved configurations using the former presets, change `_selection.preset` from `personal-desktop`/`personal-laptop` to `personal`, or from `work-laptop` to `work`, and remove any `machine.type` override.

For a minimal setup that ignores saved overrides:

```bash
just run --preset minimal --no-local                # apply base setup and dotfiles
just run --preset minimal --no-local --show-config  # preview the resolved configuration
just run --preset minimal --no-local --check --diff # dry run (requires bootstrap dependencies)
```

## Configuration and precedence

One loader, `scripts/configuration.py`, implements this order:

1. `config/defaults.yml`
2. `config/presets/<preset>.yml`, if selected
3. `config/machines/<machine>.yml`, if selected
4. `.local.yml`, or the file supplied with `--local`

Later mappings merge recursively; later lists and scalars replace earlier values. Disabling a feature makes its component selections inactive, without requiring all child options to be cleared. Unknown keys, duplicate YAML keys, malformed YAML, unsupported preferences/versions, incomplete identities, invalid unit definitions, and unknown presets/machines are rejected before provisioning.

`.local.yml` is ignored by Git. Bootstrap saves only selections/overrides there, not a copy of all defaults. Its optional `_selection` metadata remembers the preset and hardware definition:

```yaml
_selection:
  preset: work
  machine: ''
preferences:
  shell: zsh
development:
  dotnet: ['8.0']
  java: []
  node: ['22']
  python: ['system']
git:
  work_name: Your Name
  work_email: you@example.com
```

Explicit `--preset`/`--machine` flags select their respective layers, while local overrides still win. Use `--no-local` to ignore saved overrides for that run; it never overwrites the saved file. This also helps compare a pristine preset with an established configuration.

```bash
./bootstrap.sh --show-config
./bootstrap.sh --preset minimal --no-local --show-config
./bootstrap.sh --validate
```

Inspection/validation does not install dependencies or write configuration. Execution writes an ignored `.workstation/effective.yml` snapshot and `.workstation/chezmoi.json`; both engines consume that resolved state. Direct Ansible usage invokes the same loader. Do not edit generated files.

Existing `profile.local.yml` is automatically translated when `.local.yml` is absent. The next apply saves the translated overrides in `.local.yml`; the old file is preserved. Once migration is verified, the legacy file can be removed.

## Reapplying and updating

```bash
just run --yes                # reapply saved configuration
just run --yes --tags gnome
just run --yes --tags development
just run --yes --dotfiles
just run --verify
just update                   # update RPMs and system Flatpaks
```

`just run` forwards bootstrap arguments; without arguments it opens interactive setup. `just --usage run` summarizes common flags; `just run --help` lists all bootstrap options. `just update`, `just test`, and `just lint` also forward arguments to their underlying tools.

Repeat runs preserve unrelated packages, settings, shell startup code, Git configuration, and application configuration. Repository-owned keys converge to their declared values. Tagged runs can require prerequisites from a full run. GNOME extensions may require logout/login; authenticate applications separately.

Work identities are scoped to `~/Projects/Personal` and `~/Projects/Work`. A work machine has no global Git identity; commits elsewhere require an explicit identity. Set both `git.work_name` and `git.work_email` before committing work projects. Blank identities are allowed for machines where Git identity will be configured later; partially supplied identities fail validation.

Podman is the default container engine. Select `preferences.container_engine: docker` when Docker is required. The engine and Podman Desktop are separately selectable. Language lists use Fedora packages; availability depends on the destination Fedora release. An empty version list skips that ecosystem. Anaconda is optional and uses a pinned installer/checksum; batch installation accepts its installer terms.

## Dotfiles

Edit the files under `chezmoi/`, then run `just run --yes --dotfiles`. For chezmoi's own commands, use this repository's generated configuration and state file:

```bash
chezmoi --config .workstation/chezmoi.json \
  --persistent-state .workstation/chezmoi-state.boltdb diff
chezmoi --config .workstation/chezmoi.json \
  --persistent-state .workstation/chezmoi-state.boltdb edit ~/.config/shell/workstation.sh
```

Bootstrap does not replace another chezmoi repository's global configuration. [Modification scripts/templates](https://www.chezmoi.io/user-guide/manage-different-types-of-file/#manage-part-but-not-all-of-a-file) manage the shell hook and Git include while retaining unrelated content. Whole files under `.config/git/` and `.config/shell/` are explicitly repository-owned. Static files remain static.

Ansible installs VS Code when selected. Its extensions and personal editor settings belong to [VS Code Settings Sync](https://code.visualstudio.com/docs/configure/settings-sync): sign in and enable sync, including Extensions and Settings, after installation. Provisioning does not install or verify extensions, or modify VS Code settings. Existing extensions and settings are preserved. Remote SSH/container extensions require separate setup. The former `vscode.extensions` and `vscode.work_extensions` configuration keys are no longer supported; remove them from local overrides if present.

Selected JetBrains XML components live under `.chezmoitemplates/jetbrains`. A small chezmoi configuration script merges them into the selected versioned IDE directories; other XML components remain. Launch Toolbox to install IDEs, then set `jetbrains_versions: {Rider: '2026.2'}` and reapply dotfiles while the IDE is closed. This script does not install packages. Its XML outputs are outside chezmoi's normal `diff`/`verify` file tracking.

## Testing changes

```bash
just check                     # configuration, syntax, loader tests; no provisioning
just lint                      # ansible-lint
just run --check               # Ansible check mode, chezmoi dry run
just run --check --diff
```

Check mode never installs bootstrap dependencies or saves `.local.yml`; missing dependencies must be installed separately. It writes only ignored execution metadata. Vendor installers and GNOME extension downloads are skipped in check mode. Fresh-machine checks cannot fully predict repository availability or dependencies installed by earlier tasks. Chezmoi `diff` shows configuration scripts without executing them.

Direct debugging is supported:

```bash
export ANSIBLE_CONFIG="$PWD/ansible/ansible.cfg"
ansible-playbook -K -i ansible/intentory.ini ansible/playbook.yml --check --diff
ansible-playbook -K -i ansible/intentory.ini ansible/playbook.yml --tags gnome
ansible-playbook -i ansible/intentory.ini ansible/playbook.yml --tags profile_check
ansible-playbook -i ansible/intentory.ini ansible/playbook.yml \
  -e workstation_preset=minimal -e workstation_ignore_local=true --check
```

Direct Ansible applies only machine state; bootstrap applies chezmoi afterward. `dotfiles` is a bootstrap selection (`--tags dotfiles` or `--dotfiles`). The old setup/verify playbook paths remain compatibility entry points. The inventory name `ansible/intentory.ini` is intentional.

## Repository architecture

| Path | Ownership |
| --- | --- |
| `config/defaults.yml` | Features, preferences, semantic software lists and options |
| `config/presets/` | Reusable software configurations |
| `config/machines/` | Optional physical-machine definitions, added when needed |
| `scripts/configuration.py` | Precedence and validation shared by both engines |
| `scripts/bootstrap.py` | Interactive frontend, dependency checks and orchestration |
| `ansible/playbook.yml` | Readable machine-state role sequence |
| `ansible/roles/` | Base, repositories, packages, Flatpak, GNOME, development, work, services, hardware and application installation |
| `ansible/vars/catalog.yml` | Upstream release/checksum pins |
| `chezmoi/` | Home configuration and selected application preferences |
| `systemd/system/`, `systemd/user/` | Custom unit files, added only when needed |
| `justfile` | Convenience commands without configuration logic |

Ansible's explicit user context targets the desktop account and its D-Bus session; system changes use `become`. Custom systemd user units are the deliberate exception to chezmoi's ownership of home configuration: Ansible deploys and manages units together.

## Extending the configuration

Add ordinary RPMs to the appropriate `packages` group and Flatpak IDs to `flatpak.applications.<feature>` in `config/defaults.yml`. Add font RPMs to `fonts`. Lists are sufficient for ordinary applications; introduce dedicated options only for meaningful installation choices. Declare additional Flatpak remotes in `flatpak.remotes`; the existing application lists use Flathub.

Declare RPM repositories under `repositories.rpm` with `name`, `description`, `baseurl`, and `gpgkey`, or COPR names under `repositories.copr`. Repository setup precedes dependent installations. Special vendor repositories live in the repositories role. Microsoft PowerShell/Azure CLI retain the vendor RHEL 9 channel, with .NET excluded so SDKs come from Fedora. AI CLI scripts, pinned Typst/Anaconda archives, and Toolbox's vendor API are isolated installation exceptions; they do not run on every reapply once installed. Their updates remain vendor-managed, or require an explicit pin change where supported.

Declare services under `services.system` or `services.user`:

```yaml
services:
  user:
    - name: example.service
      unit: example.service       # committed systemd/user/example.service
      enabled: true
      state: started
```

`unit` is optional for packaged services. Install their packages in an appropriate package list. Declared system services override the automatic Docker/libvirt service defaults. User services require a running user session; bootstrap does not enable lingering automatically.

Add physical-machine overrides only when needed, for example `config/machines/thinkpad-t14.yml`, selected with `--machine thinkpad-t14`. These files accept only `machine` metadata and `hardware` package/service declarations. The loader sets `machine.id` from the selected definition. General applications belong in presets or local overrides.

GNOME settings are named declarations grouped under `ansible/roles/gnome/files/{interface,keyboard,input,extensions}.yml`. Each has a dconf `key`, GVariant `value`, and a description explaining intent. Discover settings with `gsettings list-recursively <schema>` and `dconf read <path>`; commit only deliberately selected values. The former dconf export is no longer applied. GNOME extensions are UUID lists in defaults; incompatible/failed optional extensions are reported and other configuration continues. Unmanaged enabled extensions are preserved.

For a new feature, add a default and validation, associate package/Flatpak lists with it, and add a role only when behavior is substantial. Extend the interactive frontend where useful; execution must work from configuration alone. Add validation tests and update this README when changing the public interface.

Keep credentials, tokens, private keys/certificates, and employer secrets out of Git and local configuration. Application authentication remains separate; password-manager integration can be added when a managed configuration actually needs a secret.

MIT License; see LICENSE. MoreWaita is downloaded under its upstream license.
