# Fedora workstation provisioning

Clone this repository on a fresh Fedora desktop, then run:

```bash
./bootstrap.sh
$EDITOR profile.local.yml
just check
just validate
just run
just verify
```

`bootstrap.sh` installs Ansible, Git, and Just, then installs the Ansible collection in `ansible/requirements.yml`. Run the playbook as your logged-in desktop user. `just run` prompts for sudo and applies the system changes. The inventory is intentionally named `ansible/intentory.ini`.

## Machine profile

`profile.yml` is the committed template. Bootstrap copies it to ignored `profile.local.yml` if that file does not exist. Edit the local copy for each machine; rerunning bootstrap preserves it.

```yaml
profile:
  work_machine: false
  install_anaconda: false
  toolchains:
    dotnet: ['8.0']
    java: []
    node: ['22']
    python: ['system']
  git:
    name: George Gkonis
    email: git@georgegkonis.com
    work_name: ''
    work_email: ''
  jetbrains_versions: {}
  obsidian_vaults: []
```

The common setup installs the applications, CLI tools, and desktop preferences listed in `ansible/vars/catalog.yml`. Personal repos go directly under `~/Projects`. With `work_machine: true`, the personal projects path becomes `~/Projects/Personal`, and setup also creates `~/Projects/Work`. Fill in `git.work_name` and `git.work_email` in the local profile. Git uses the personal identity under `Personal` and the work identity under `Work`; commits outside those directories require an explicit identity. Work machines also add Teams, Azure CLI, and the Azure Repos VS Code extension.

Toolchain lists select Fedora package versions; an empty list skips that runtime. `python: ['system']` installs Fedora's default Python and pip. Versions must be available on the destination Fedora release. Set `install_anaconda: true` for the full Anaconda Distribution in `~/anaconda3`. Its release and checksums are pinned in `ansible/vars/catalog.yml`; batch installation accepts its installer terms and does not activate the base environment by default.

`jetbrains_versions` maps an IDE to an installed version for preference restoration; install the IDE with Toolbox first. `obsidian_vaults` lists Git repositories to clone initially; later runs do not pull them. Keep credentials out of both profile files. Changing a choice to false or removing a version does not uninstall existing software.

`just check` checks all three playbooks' syntax, and `just validate` checks the profile without provisioning. `just verify` checks installed RPMs, system Flatpaks, selected runtimes, user paths, CLI tools, and VS Code extensions without changing them. Run it after setup; it fails if expected items are missing. These checks do not verify package or installer availability before installation. Log out and back in after provisioning so GNOME loads extensions. Authenticate applications separately.

## Run setup, updates, and verification

```bash
just run       # apply the full setup
just update    # upgrade installed RPMs and system Flatpaks
just verify    # read-only checks against the local profile
```

`just update` upgrades installed software; it does not install missing profile selections or reapply preferences. To revisit one setup feature:

```bash
just tag docker
just tag vscode
just tag gnome
just tag dotnet
```

Use `just --list` for all recipes. A tagged run may rely on prerequisites from a full run.

## Layout

The root contains the bootstrap command and machine profile; Ansible internals live under `ansible/`.

| Path | Purpose |
| --- | --- |
| `profile.yml` | Committed profile template |
| `profile.local.yml` | Ignored machine-specific profile, created by bootstrap |
| `ansible/vars/catalog.yml` | Common and work-specific software and preference lists |
| `ansible/playbooks/local-setup.yml` | Full setup |
| `ansible/playbooks/update.yml` | Update installed RPMs and system Flatpaks |
| `ansible/playbooks/verify.yml` | Read-only setup checks |
| `ansible/ansible.cfg` | Resolves roles within `ansible/` |
| `ansible/tasks/features/` | Small features with ordered tasks |
| `ansible/tasks/toolchains/` | Versioned runtimes and Anaconda |
| `ansible/roles/gnome/`, `ansible/roles/onepassword/`, `ansible/roles/vscode/`, `ansible/roles/jetbrains/` | Features with multiple tasks or settings assets |

`ansible/tasks/user_context.yml` resolves the desktop account. User settings target that account; system changes use `become: true`. This repository targets Fedora and DNF.

The Anaconda installer comes from the [official archive](https://repo.anaconda.com/archive/). Provisioning also uses Flathub, Docker CE, Microsoft, HashiCorp, 1Password, GNOME Extensions, and JetBrains services.

MIT License; see LICENSE. MoreWaita is downloaded separately under its upstream license.
