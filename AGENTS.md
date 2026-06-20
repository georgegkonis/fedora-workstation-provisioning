# AGENTS Guide

## What this repo is

- Personal Fedora workstation provisioning via Ansible, run on `localhost` with privilege escalation.
- Entry point is `playbook.yml`; inventory is intentionally named `intentory.ini` (keep that exact filename).
- Main flow is role-based and linear: `base` -> `shell` -> `desktop` -> `containers` -> dev role.

## Architecture and role boundaries

- `roles/base/tasks/`: OS update + core CLI tooling + DNF tuning (`system.yml`, `core.yml`).
- `roles/shell/tasks/`: terminal shell setup (`tools.yml`) + PowerShell repo/package install (`powershell.yml`).
- `roles/desktop/tasks/`: GUI apps via DNF + Flatpak (`apps.yml`), 1Password + GNOME shortcut script (`1password.yml`).
- `roles/containers/tasks/`: Docker CE repo/packages/service (`docker.yml`) and Podman (`podman.yml`).
- `roles/dev/tasks/`: IDEs and SDKs (`jetbrains.yml`, `vscode.yml`, `sdks.yml`, `postman.yml`).

## Execution/data flow patterns

- Role `tasks/main.yml` files are thin orchestrators using `ansible.builtin.import_tasks`.
- Most installation steps use `ansible.builtin.dnf` with package lists; repo onboarding uses `rpm_key`,
  `yum_repository`, or direct repo file downloads.
- Dynamic version flow exists in `roles/dev/tasks/jetbrains.yml`: `uri` call -> register JSON -> template URL into
  `get_url`.
- System config mutation pattern: `blockinfile` with explicit markers (see DNF optimization in
  `roles/base/tasks/core.yml`).

## Critical workflows

- Bootstrap dependencies:

```bash
sudo dnf install -y ansible git
```

- Run full provisioning:

```bash
sudo ansible-playbook -i intentory.ini playbook.yml
```

- Run a role by tag:

```bash
sudo ansible-playbook -i intentory.ini playbook.yml --tags base
```

## Project-specific conventions to preserve

- Prefer fully-qualified module names (`ansible.builtin.*`, `community.general.flatpak*`).
- Keep explicit file modes on downloaded/copied files (`'0644'`, `'0755'`).
- Preserve idempotency guards when commands are required (`changed_when` usage in `roles/desktop/tasks/1password.yml`).
- This repo targets Fedora/RHEL-style package management (`dnf`, `.repo`, RPM keys), not Debian apt.

## External integration points

- Docker CE repo: `https://download.docker.com/linux/fedora/docker-ce.repo`.
- Microsoft repos used for PowerShell and VS Code (`packages.microsoft.com`).
- JetBrains release API consumed at `data.services.jetbrains.com`.
- Flatpak remote `flathub` is required before Flatpak app installs.

## Known gotcha before editing

- `playbook.yml` references role `development` with tag `dev`, but repo directory is `roles/dev/`.
- If provisioning fails with "role not found", align playbook role name with the actual role directory.
