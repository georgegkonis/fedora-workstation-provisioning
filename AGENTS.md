# AGENTS Guide

You are talking to a senior engineer. Keep responses concise. When creating git commits, use the `commit` skill.

## Repository

This repository provisions a personal Fedora workstation using Ansible on `localhost`. `ansible/playbooks/local-setup.yml` applies the full setup, `ansible/playbooks/update.yml` upgrades installed software, and `ansible/playbooks/verify.yml` checks installed state. The inventory is intentionally named `ansible/intentory.ini`.

The user flow is `./bootstrap.sh` → edit ignored `profile.local.yml` → `just check` → `just validate` → `just run`. Bootstrap copies committed `profile.yml` to the local file only when absent. The playbook runs as the desktop user. System tasks use `become: true`, and user settings use `desktop_target_user` and `desktop_user_env` resolved in `ansible/tasks/user_context.yml`.

## Organization

- `profile.yml`: committed template for the short machine profile.
- `profile.local.yml`: ignored machine-specific profile loaded by the playbook. Keep secrets out.
- `ansible/playbooks/`: top-level Ansible playbooks.
- `ansible/ansible.cfg`: resolves repository roles when running playbooks from `ansible/playbooks/`.
- `ansible/vars/catalog.yml`: fixed common software, work additions, and preference lists.
- `ansible/tasks/system.yml`, `ansible/tasks/dnf.yml`, `ansible/tasks/packages.yml`: DNF tuning and simple package/Flatpak lists.
- `ansible/tasks/update.yml`, `ansible/tasks/verify.yml`: update-only and read-only verification tasks.
- `ansible/tasks/features/`: small features with ordered tasks, such as Docker, Terraform, Git, and CLI installers.
- `ansible/tasks/toolchains/`: Fedora .NET, Java, Node.js, and Python versions, plus pinned Anaconda Distribution.
- `ansible/roles/gnome/`, `ansible/roles/onepassword/`, `ansible/roles/vscode/`, `ansible/roles/jetbrains/`: features with multiple task files and settings assets.

Keep common software in the catalog. `ansible/tasks/user_context.yml` computes project paths from the work flag and shares them with directory, Git, and verification tasks. On work machines, Git identities are scoped separately to personal and work project directories. Empty toolchain lists skip those runtimes; removing a version does not uninstall it.

## Commands

```bash
./bootstrap.sh
just check
just validate
just run
just tag docker
just update
just verify
```

Bootstrap installs `ansible`, `git`, and `just` with DNF and installs the `community.general` collection as the desktop user. The playbook prompts for sudo through `-K` and escalates individual tasks.

## Conventions

- Prefer fully qualified module names (`ansible.builtin.*`, `community.general.*`).
- Keep explicit modes on downloaded/copied files (`'0644'`, `'0755'`).
- Preserve idempotency guards for command tasks.
- Use Fedora/DNF and RPM repositories; do not substitute apt.
- Preserve the exact `intentory.ini` filename under `ansible/`.
- Run syntax and profile checks without provisioning before changing task behavior.
