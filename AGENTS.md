# AGENTS Guide

Talk to a senior engineer; keep responses concise. Use the `commit` skill when creating commits.

## Architecture

- Ansible owns Fedora machine state: packages, repositories/COPRs, Flatpak, GNOME, installation, hardware and system/user services.
- Chezmoi owns home configuration: shell hooks, Git, editor/CLI/application preferences. Custom systemd user units are deployed by Ansible with their service lifecycle.
- Git is the source of truth. Never commit credentials, `.local.yml`, legacy `profile.local.yml`, or generated `.workstation/` state.
- `bootstrap.sh` delegates orchestration to `scripts/bootstrap.py`; UI emits configuration and never performs feature installation directly.
- `scripts/configuration.py` is the only precedence/validation implementation: defaults → preset → machine → local overrides. Mappings merge; lists/scalars replace.
- Machine definition, machine type, feature selection and implementation preferences are independent. Machine files contain only hardware options and machine metadata.

## Layout

- `config/defaults.yml`: shared selections and software data grouped by semantic ownership.
- `config/presets/`: reusable profiles. Optional `config/machines/` definitions are created only for actual hardware needs.
- `.local.yml`: ignored selections/overrides, with `_selection` remembering preset/machine names.
- `ansible/playbook.yml`: primary readable role sequence. Old setup/verify playbook paths are compatibility wrappers.
- `ansible/intentory.ini`: intentional inventory filename; preserve it.
- `ansible/tasks/{configuration,user_context,software}.yml`: shared validation, desktop account/session and selected-state resolution.
- `ansible/roles/`: substantive machine-state components. Do not create empty roles just to match a diagram.
- `ansible/vars/catalog.yml`: upstream installer/version pins.
- `chezmoi/`: home state, using templates only where selections vary; modification scripts preserve unrelated state.
- `systemd/{system,user}/`: custom unit files, created only when needed.
- `justfile`: convenience commands, no configuration logic.

## Commands

```bash
./bootstrap.sh                        # interactive apply
./bootstrap.sh --preset personal-laptop
./bootstrap.sh --show-config
./bootstrap.sh --validate
./bootstrap.sh --yes                  # reapply saved selections
./bootstrap.sh --check --diff
just check                           # validation, syntax, configuration tests
just lint
just dotfiles
just verify
```

Check mode must not install bootstrap dependencies, save user selections, or execute installers. It may write ignored execution metadata. Syntax/profile checks must run before changing task behavior. In restricted environments, redirect Ansible local/remote temporary paths to `/tmp` through environment variables.

## Conventions

- Prefer fully qualified native Ansible modules, Fedora/DNF/RPM mechanisms, explicit file modes, and command guards.
- Keep ordinary software in lists. Add options only for meaningful choices; disabling a parent feature makes child selections inactive.
- Configure repositories before packages. Isolate/document vendor installers where packages are unsuitable.
- Preserve additive/idempotent behavior and unrelated existing state. Never purge unlisted packages or reset whole exported configuration databases.
- Manage GNOME settings as named, described declarations; optional extension failures must be reported without stopping setup.
- Scope work Git identities separately from personal projects; chezmoi owns the files.
- Run validation, syntax/lint and applicable check-mode tests without provisioning the developer's workstation. Review the diff for local/generated state.
