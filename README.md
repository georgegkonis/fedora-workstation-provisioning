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

Run as your desktop account with sudo available. Bootstrap validates Fedora, resolves configuration, presents selections and a summary, installs missing bootstrap dependencies, runs Ansible, and applies chezmoi. Bootstrap dependencies are Python/PyYAML, Ansible, Git, chezmoi, and the `community.general` collection. They are installed only when missing. No workstation configuration is embedded in `bootstrap.sh`. `just` is optional: the base package set installs it after the first run, and every `just` recipe wraps `./bootstrap.sh`.

The interactive frontend uses [gum](https://github.com/charmbracelet/gum) when installed (`sudo dnf install gum`), with text prompts otherwise. Choose features, development components, applications, and preferences. Existing version lists are retained; additional versions can be selected in `.local.yml`. An existing local configuration can be reapplied or edited; `./bootstrap.sh --configure` opens the selections explicitly. Cancellation leaves saved selections unchanged.

## Presets and unattended setup

```bash
./bootstrap.sh --yes
./bootstrap.sh --preset work
./bootstrap.sh --preset minimal
```

Presets skip configuration questions and confirmation. A terminal run can still request the sudo password. Unattended execution requires working noninteractive sudo, or equivalent Ansible become configuration. `--yes` also skips configuration questions and confirmation when using saved selections/defaults.

Without a preset, the shared defaults apply (the personal setup). `work` enables work and disables personal (software kept off the work laptop, e.g. Steam, qBittorrent, Zotero). `minimal` is a stripped-down desktop: 1Password, a short Flatpak list and a few GNOME extensions. Desktop and development are independently selectable. Personal and virtualization select app records, dependency lists and service defaults; they do not need placeholder roles.

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
3. `.local.yml`, or the file supplied with `--local`

Later mappings merge recursively; later lists and scalars replace earlier values. Disabling a feature makes its component selections inactive, without requiring all child options to be cleared. Unknown keys, duplicate YAML keys, malformed YAML, unsupported preferences/versions, incomplete identities, invalid unit definitions, and unknown presets are rejected before provisioning.

`.local.yml` is ignored by Git. Bootstrap saves only selections/overrides there, not a copy of all defaults. Its optional `_selection` metadata remembers the preset:

```yaml
_selection:
  preset: work
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

An explicit `--preset` flag selects the preset layer, while local overrides still win. Use `--no-local` to ignore saved overrides for that run; it never overwrites the saved file. This also helps compare a pristine preset with an established configuration.

```bash
./bootstrap.sh --show-config
./bootstrap.sh --preset minimal --no-local --show-config
./bootstrap.sh --validate
```

Inspection/validation does not install dependencies or write configuration. Execution writes an ignored `.workstation/effective.yml` snapshot and `.workstation/chezmoi.json`; both engines consume that resolved state. Direct Ansible usage invokes the same loader. Do not edit generated files.

## Reapplying and updating

```bash
just run --yes                # reapply saved configuration
just run --yes --tags gnome
just run --yes --tags development
just run --yes --dotfiles
just run --verify
just update                   # upgrade RPMs and system Flatpaks only
just run --upgrade --yes      # upgrade first, then provision (e.g. a fresh machine)
```

`just run` forwards bootstrap arguments; without arguments it opens interactive setup. `just --usage run` summarizes common flags; `just run --help` lists all bootstrap options. `just test` and `just lint` also forward arguments to their underlying tools.

System upgrades are opt-in: runs never upgrade unlisted packages unless `--upgrade` (or `just update`) is given, which keeps repeat runs fast and repeatable. Use `./bootstrap.sh --upgrade` on a fresh machine so the first provisioning starts from current packages.

Repeat runs preserve unrelated packages, settings, shell startup code, Git configuration, and application configuration. Repository-owned keys converge to their declared values. Tagged runs can require prerequisites from a full run. GNOME extensions may require logout/login; authenticate applications separately.

The personal Git identity is the global default. On a work machine, repositories under `~/Projects/Work` override it with `git.work_name` and `git.work_email`; set both before committing work projects. `development.git_credential_manager` installs a pinned Git Credential Manager (HTTPS credentials, Secret Service store). Optional `git.signing_key` and `git.work_signing_key` (SSH public keys) enable 1Password commit signing, with the work key overriding under `~/Projects/Work`. Blank identities are allowed for machines where Git identity will be configured later; partially supplied identities fail validation.

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

Ansible installs VS Code when selected. Its extensions and personal editor settings belong to [VS Code Settings Sync](https://code.visualstudio.com/docs/configure/settings-sync): sign in and enable sync, including Extensions and Settings, after installation. Provisioning does not install or verify extensions, or modify VS Code settings. Existing extensions and settings are preserved. Remote SSH/container extensions require separate setup.

Ansible installs JetBrains Toolbox when selected, together with the inotify limits IDEs need. IDEs and their settings are not managed: install them through Toolbox, then sign in and enable [JetBrains Settings Sync](https://www.jetbrains.com/help/idea/sync.html).

Firefox preferences live in [`personal.js`](chezmoi/.chezmoitemplates/firefox/personal.js) and [`work.js`](chezmoi/.chezmoitemplates/firefox/work.js), curated separately from the current Personal and Work profiles. With desktop enabled and `preferences.browser: firefox`, a chezmoi script discovers installation-default profiles from `profiles.ini` in native, XDG, and Flatpak locations, then reads their profile-group databases to find Personal and Work by name. Personal receives its preferences whenever Firefox configuration is enabled. Work receives its preferences only when `features.work: true`; otherwise it is left untouched, even when it is the installation default. A default without a matching name receives `work.js` when `features.work` is enabled, otherwise `personal.js`. Discovery falls back to the legacy default only when installation defaults are absent, deduplicates symlinked directories, and skips missing profiles. Launch Firefox and create/name profiles before reapplying on a fresh machine; the script does not create profiles or change Firefox's registry/databases.

Edit the curated files, then run `just run --yes --dotfiles` and restart Firefox. The script merges a managed block into each selected profile's `user.js`, preserving unrelated content and avoiding writes when unchanged. It does not deploy profile databases, extension state, or theme assets. Bookmarks, extensions, search engines and other profile state come from Firefox Sync; sign in after creating the profiles. Its outputs are outside chezmoi's normal `diff`/`verify` tracking; dry runs do not execute it. Firefox [reads `user.js` on startup](https://firefox-source-docs.mozilla.org/modules/libpref/index.html), so listed preferences override saved settings each restart. Removing a preference from these files does not reset its previously saved value; reset it in `about:config` when needed.

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
ansible-playbook -K -i ansible/inventory.ini ansible/playbook.yml --check --diff
ansible-playbook -K -i ansible/inventory.ini ansible/playbook.yml --tags gnome
ansible-playbook -i ansible/inventory.ini ansible/playbook.yml --tags profile_check
ansible-playbook -i ansible/inventory.ini ansible/playbook.yml \
  -e workstation_preset=minimal -e workstation_ignore_local=true --check
```

Direct Ansible applies only machine state; bootstrap applies chezmoi afterward. `dotfiles` is a bootstrap selection (`--tags dotfiles` or `--dotfiles`).

## Repository architecture

| Path | Ownership |
| --- | --- |
| `config/defaults.yml` | Features, preferences, semantic software lists and options |
| `config/presets/` | Reusable software configurations |
| `scripts/configuration.py` | Precedence and validation shared by both engines |
| `scripts/bootstrap.py` | Interactive frontend, dependency checks and orchestration |
| `ansible/playbook.yml` | Readable machine-state role sequence |
| `ansible/roles/` | Base, repositories, packages, Flatpak, applications, development, GNOME and services |
| `ansible/vars/catalog.yml` | Upstream release/checksum pins |
| `chezmoi/` | Home configuration and selected application preferences |
| `systemd/system/`, `systemd/user/` | Custom unit files, added only when needed |
| `justfile` | Convenience commands without configuration logic |

Ansible's explicit user context targets the desktop account and its D-Bus session; system changes use `become`. Custom systemd user units are the deliberate exception to chezmoi's ownership of home configuration: Ansible deploys and manages units together.

## Extending the configuration

Declare applications once under `apps` in `config/defaults.yml`, keyed by a stable name.
Each record has a friendly `name`, an `enabled` flag, a `feature` (`base` or a feature name),
and an `installer` (`flatpak`, `rpm`, or `vendor`). Installer-specific settings belong in its
matching mapping. Presets and `.local.yml` override individual fields; app mappings merge.

```yaml
apps:
  localsend:
    name: LocalSend
    enabled: true
    feature: desktop
    installer: flatpak
    flatpak:
      id: org.localsend.localsend_app
      background: true
    autostart:
      enabled: true
  vscode:
    name: Visual Studio Code
    enabled: true
    feature: desktop
    installer: rpm
    rpm:
      packages: [code]
```

For example, a local override can disable one app and deny another background execution
without repeating the app metadata or other selections:

```yaml
apps:
  spotify:
    enabled: false
  localsend:
    flatpak:
      background: false
    autostart:
      enabled: false
```

An app is active only when enabled and its feature and `requires` conditions are satisfied.
`requires` can declare other `features`, boolean `development` selections, other `apps`,
or preference values such as `browser`, `terminal`, and `container_engine`. Browser/editor/terminal
preferences require their corresponding apps to be active. The resolver produces the RPM,
Flatpak, integration, startup, and verification selections; roles consume those selections.
Custom vendor installers currently support `vendor: {task: jetbrains}`. Native 1Password declares
`integration: onepassword` alongside its RPM packages for desktop integration.

Flatpak `background: true` allows background execution and `false` denies it through the same
per-user portal permission store as Flatseal. Omission or `null` leaves the permission unmanaged;
use `null` in an override to stop managing an inherited setting. Removing management leaves the
existing permission in place. Defaults allow LocalSend, Teams when active, and Steam. Reapplying
restores declared permissions after edits in Flatseal. Flatpak `own_names` lists per-app session-bus
names (used by Teams for its tray icon). Other app permissions remain unchanged.
Apply background permissions alone with `just run --yes --tags flatpak_background` after installation.

Keep infrastructure and development dependencies in `packages.<feature>`, fonts in `fonts`,
and hardware packages in `hardware.packages`. Shared Flatpak remotes remain in `flatpak.remotes`.
Old saved boolean app selections and Flatpak application/background/override lists are translated
by the configuration loader. Inspection and check mode leave `.local.yml` untouched; a normal apply
saves converted overrides. Newly authored configuration should use app records.

Declare RPM repositories under `repositories.rpm` with `name`, `description`, `baseurl`, and `gpgkey`, or COPR names under `repositories.copr`. Repository setup precedes dependent installations. Special vendor repositories live in the repositories role. Ordinary application RPMs and hardware packages live in the packages role; applications requiring custom installation or integration (1Password and JetBrains Toolbox) live in the applications role. Feature selections control tasks independently of role boundaries. Microsoft PowerShell/Azure CLI retain the vendor RHEL 9 channel, with .NET excluded so SDKs come from Fedora. AI CLI scripts, pinned Typst/Anaconda archives, and Toolbox's vendor API are isolated installation exceptions; they do not run on every reapply once installed. Their updates remain vendor-managed, or require an explicit pin change where supported.

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

Hardware-specific packages and services go under `hardware` in `.local.yml`. General applications belong in presets.

GNOME settings are named declarations grouped under `ansible/roles/gnome/files/{interface,keyboard,input,extensions}.yml`. Each has a dconf `key`, GVariant `value`, and a description explaining intent. Discover settings with `gsettings list-recursively <schema>` and `dconf read <path>`; commit only deliberately selected values. GNOME extensions are UUID lists in defaults; incompatible/failed optional extensions are reported and other configuration continues. Unmanaged enabled extensions are preserved.

Startup settings belong to the app’s `autostart` mapping (`enabled`, optional `name`, `command`, and `try_exec`). Flatpak commands and filenames are derived from the app ID; native/vendor apps declare a command. Disabling a declared app or its startup setting writes its managed desktop entry with autostart disabled, including entries left by earlier applies. Unrelated autostart files are preserved. `gnome.autostart` remains available for supplemental commands outside the app catalog, such as hardware helpers; names must not collide with app startup entries.

For a new feature, add a default and validation, associate app records and dependency lists with it, and add a role only when behavior is substantial. Extend the interactive frontend where useful; execution must work from configuration alone. Add validation tests and update this README when changing the public interface.

Keep credentials, tokens, private keys/certificates, and employer secrets out of Git and local configuration. Application authentication remains separate; password-manager integration can be added when a managed configuration actually needs a secret.

MIT License; see LICENSE. MoreWaita is downloaded under its upstream license.
