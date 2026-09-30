# Personal Fedora Workstation Provisioning

Ansible setup for a fresh personal Fedora workstation, including selected preferences captured from the work laptop. The
playbook installs software and changes system configuration; run it on the **personal laptop**.

## Run on the Personal Laptop

Log into your GNOME desktop account, open a terminal, and run from this repository:

```bash
sudo dnf install -y ansible git
sudo ansible-galaxy collection install -r requirements.yml
sudo ansible-playbook -i intentory.ini local-setup.yml
```

The inventory filename is intentionally `intentory.ini`. User configuration targets the account that invoked sudo. To
select another existing account, pass `-e provisioning_user=YOUR_USER`.

Check syntax without provisioning:

```bash
ansible-playbook -i intentory.ini local-setup.yml --syntax-check
```

Run selected roles using `--tags base`, `shell`, `desktop`, `containers`, `dev`, or `preferences`. For example, after
software installation:

```bash
sudo ansible-playbook -i intentory.ini local-setup.yml --tags preferences
```

The preferences role expects VS Code to be installed. Desktop extension installation requires GNOME. Log out and back in
after provisioning so GNOME loads newly installed extensions. A syntax check does not verify repository availability or
package compatibility; full provisioning still needs validation on the destination laptop.

## What Transfers

- Desktop appearance, clock, US International/Greek keyboard layouts, pointer preferences, shortcuts, and extension
  configuration.
- The source's enabled GNOME extension selection, where compatible releases exist. Unavailable releases are reported and
  skipped.
- MoreWaita icons at the captured Git revision and Ptyxis terminal profile preferences.
- Selected VS Code preferences and 29 extensions. Replaced preference files receive backups.
- The installed Flatpak apps, plus the repository's existing app selection.
- Node.js 22/npm, Python/pip, .NET SDKs, compiler tools, GitHub CLI, Terraform, Azure CLI, Typst 0.15.0, and existing
  shell/container/CLI tooling.

Passwords, work tokens, SSH keys, browser profiles, cloud project selections, playback history, wallpapers, custom
sounds, and company configuration are not copied. Authenticate applications separately. Bash receives a portable
`$HOME/.local/bin` PATH block; the work laptop's startup file is not copied.

## Optional Work Tools

Work-specific software is disabled on the personal profile by default:

```yaml
include_work_tools: false
```

The work group currently contains Teams for Linux, Azure CLI, and the Azure Repos VS Code extension. Enable it for a run
with:

```bash
sudo ansible-playbook -i intentory.ini local-setup.yml -e include_work_tools=true
```

The owning role defaults keep the lists separate: `desktop_work_flatpak_apps` for Flatpak applications and
`personal_work_vscode_extensions` for VS Code extensions. Add future employer-specific tools to those lists or guard
their task imports with `when: include_work_tools | bool`. Credentials, VPN profiles, certificates, Git identities, and
organization settings stay outside this repository.

## Personal Directories and Git

The preferences role creates `~/Projects` as the destination user. Add other home-relative directory names and your
personal Git identity to `group_vars/all.yml` or a local variables file:

```yaml
personal_directories:
  - Projects
  - Projects/experiments
  - Documents/Obsidian
personal_git_name: George Gkonis
personal_git_email: git@georgegkonis.com
```

Apply just these settings on the personal laptop:

```bash
sudo ansible-playbook -i intentory.ini local-setup.yml --tags directories,git
```

Git defaults to `main` for new repositories, prunes stale remote references on fetch, uses LF line endings in the
repository, and requires an explicitly configured identity. Empty identity variables leave existing values untouched;
set them before your first commit on a fresh laptop. Other existing Git settings are preserved. Customize defaults
through the `personal_git_config` dictionary. SSH keys, authentication, and commit signing are configured separately.

### Git-synchronized Obsidian vaults

Configure each existing vault repository with its local directory name:

```yaml
personal_obsidian_vaults:
  - name: Personal
    repo: git@github.com:georgegkonis/personal-vault.git
```

Then clone configured vaults with:

```bash
sudo ansible-playbook -i intentory.ini local-setup.yml --tags obsidian
```

Vaults are cloned under `~/Documents/Obsidian/<name>`. Provisioning performs the initial clone and does not pull changes
on later runs, avoiding automatic merges while Obsidian may have local edits. Continue using your normal `git pull`,
commit, and push workflow. Configure SSH keys and host access before running this tag, or use an authenticated HTTPS
remote.

References: [Git setup](https://git-scm.com/book/en/v2/Getting-Started-First-Time-Git-Setup)
and [Ansible Git configuration](https://docs.ansible.com/projects/ansible/latest/collections/community/general/git_config_module.html).

## JetBrains Preferences

Install Rider, PyCharm, WebStorm, and DataGrip using Toolbox. Close the IDEs, then supply their destination
configuration versions in a local variables file:

```yaml
personal_jetbrains_versions:
  Rider: '2026.2'
  PyCharm: '2026.2'
  WebStorm: '2026.2'
  DataGrip: '2026.2'
```

Apply with `--tags preferences -e @/path/to/your-versions.yml`. Match the versions actually installed; editor and
appearance preferences were captured from 2026.2 and may need adjustment for other releases. Existing files are backed
up. Licensing and account setup remain interactive.

## Structure and Sources

`local-setup.yml` resolves the desktop user once through `tasks/user_context.yml`, then runs `base` → `shell` →
`desktop` → `containers` → `dev` → `preferences`.

| Location                   | Responsibility                                                    |
|----------------------------|-------------------------------------------------------------------|
| `tasks/`                   | Shared user and session setup                                     |
| `roles/base/tasks/`        | System updates, core packages, DNF configuration                  |
| `roles/shell/tasks/`       | Shell packages and PowerShell                                     |
| `roles/desktop/tasks/`     | Desktop packages, Flatpak apps, GNOME extensions, 1Password       |
| `roles/containers/tasks/`  | Docker and Podman                                                 |
| `roles/dev/tasks/`         | Editors, SDKs, development packages, individual CLI tools         |
| `roles/preferences/tasks/` | Personal directories, Git, icons, dconf, Bash, editor preferences |
| `roles/preferences/files/` | Captured settings and preference assets                           |
| `group_vars/all.yml`       | Personal selections and pinned Typst version                      |

Each role's `tasks/main.yml` imports focused task files. 1Password installation, shortcuts, and Firefox integration are
grouped under `roles/desktop/tasks/1password/`.

Package lists, Flatpak app IDs, and GNOME extension installation lists live in the owning role's `defaults/main.yml`.
Override these variables in `group_vars/all.yml` or a local file passed with `-e @/path/to/overrides.yml`; edit task
files when changing installation behavior. Enabled extensions remain in `group_vars/all.yml` under
`personal_gnome_extensions_enabled`.

Installation
references: [Ansible dconf](https://docs.ansible.com/projects/ansible/latest/collections/community/general/dconf_module.html), [VS Code CLI](https://code.visualstudio.com/docs/configure/command-line), [Terraform](https://docs.hashicorp.com/terraform/install), [Azure CLI](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli-linux?pivots=dnf), [MoreWaita](https://github.com/somepaulo/MoreWaita),
and [Typst releases](https://github.com/typst/typst/releases).

MIT License; see LICENSE. MoreWaita is downloaded separately under its upstream license.
