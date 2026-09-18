# Personal Fedora Workstation Provisioning

Ansible setup for a fresh personal Fedora workstation, including selected preferences captured from the work laptop. The playbook installs software and changes system configuration; run it on the **personal laptop**.

## Run on the Personal Laptop

Log into your GNOME desktop account, open a terminal, and run from this repository:

```bash
sudo dnf install -y ansible git
sudo ansible-galaxy collection install -r requirements.yml
sudo ansible-playbook -i intentory.ini local-setup.yml
```

The inventory filename is intentionally `intentory.ini`. User configuration targets the account that invoked sudo. To select another existing account, pass `-e provisioning_user=YOUR_USER`.

Check syntax without provisioning:

```bash
ansible-playbook -i intentory.ini local-setup.yml --syntax-check
```

Run selected roles using `--tags base`, `shell`, `desktop`, `containers`, `dev`, or `preferences`. For example, after software installation:

```bash
sudo ansible-playbook -i intentory.ini local-setup.yml --tags preferences
```

The preferences role expects VS Code to be installed. Desktop extension installation requires GNOME. Log out and back in after provisioning so GNOME loads newly installed extensions. A syntax check does not verify repository availability or package compatibility; full provisioning still needs validation on the destination laptop.

## What Transfers

- Desktop appearance, clock, US International/Greek keyboard layouts, pointer preferences, shortcuts, and extension configuration.
- The source's enabled GNOME extension selection, where compatible releases exist. Unavailable releases are reported and skipped.
- MoreWaita icons at the captured Git revision and Ptyxis terminal profile preferences.
- Selected VS Code preferences and 29 extensions. Replaced preference files receive backups.
- The installed Flatpak apps, plus the repository's existing app selection.
- Node.js 22/npm, Python/pip, .NET SDKs, compiler tools, GitHub CLI, Terraform, Azure CLI, Typst 0.15.0, and existing shell/container/CLI tooling.

Passwords, work tokens, SSH keys, browser profiles, cloud project selections, playback history, wallpapers, custom sounds, and company configuration are not copied. Authenticate applications separately. Bash receives a portable `$HOME/.local/bin` PATH block; the work laptop's startup file is not copied.

## JetBrains Preferences

Install Rider, PyCharm, WebStorm, and DataGrip using Toolbox. Close the IDEs, then supply their destination configuration versions in a local variables file:

```yaml
personal_jetbrains_versions:
  Rider: '2026.2'
  PyCharm: '2026.2'
  WebStorm: '2026.2'
  DataGrip: '2026.2'
```

Apply with `--tags preferences -e @/path/to/your-versions.yml`. Match the versions actually installed; editor and appearance preferences were captured from 2026.2 and may need adjustment for other releases. Existing files are backed up. Licensing and account setup remain interactive.

## Structure and Sources

`local-setup.yml` runs `base` → `shell` → `desktop` → `containers` → `dev` → `preferences`. Each role uses `tasks/main.yml` to import focused task files. Captured preferences are under `roles/preferences/files/`; enabled extensions and the Typst version are in `group_vars/all.yml`.

Installation references: [Ansible dconf](https://docs.ansible.com/projects/ansible/latest/collections/community/general/dconf_module.html), [VS Code CLI](https://code.visualstudio.com/docs/configure/command-line), [Terraform](https://docs.hashicorp.com/terraform/install), [Azure CLI](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli-linux?pivots=dnf), [MoreWaita](https://github.com/somepaulo/MoreWaita), and [Typst releases](https://github.com/typst/typst/releases).

MIT License; see LICENSE. MoreWaita is downloaded separately under its upstream license.
