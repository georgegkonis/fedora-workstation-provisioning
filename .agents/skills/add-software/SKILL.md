---
name: add-software
description: Add ordinary software to the workstation provisioning, such as a DNF package, Flatpak, GNOME extension, font, COPR or RPM repository, or vendor-installed tool. Use when the user asks to install, add, or include an app, package, CLI, repo or extension in this repo.
---

# Add software

Pick the mechanism, in this order of preference: Fedora DNF package, Flatpak (GUI apps), COPR/RPM repository plus package, pinned vendor installer. Software is data; add a task only for vendor installers.

## Where it goes

| Kind | Edit |
|---|---|
| DNF package | `config/defaults.yml` `packages.<group>` (`base`, `desktop`, `development`, `work`, `personal`, `virtualization`) |
| Flatpak | `config/defaults.yml` `flatpak.applications.<group>` (same groups; use the Flathub app ID) |
| Font | `fonts` |
| COPR / third-party RPM repo | `repositories.copr` / `repositories.rpm` (`name`, `description`, `baseurl`, `gpgkey`); keep `gpgcheck` on |
| Packaged GNOME extension | `gnome.system_extensions` (`package`, `uuid`); add the uuid to `gnome.enabled_extensions` to enable it |
| Extension not in Fedora | `gnome.user_extensions` (uuid); optional, failures are reported, not fatal |
| Flatpak sandbox override | `flatpak.overrides` |

The group is the feature that must be enabled for the item to install. Pick the narrowest one. Presets in `config/presets/` only override lists to narrow them; touch them only if the item must differ per profile (lists replace, they do not merge).

## Vendor installer (no suitable package)

1. Pin version and checksums in `ansible/vars/catalog.yml` as `provision_<name>_*`. Use the `update-pins` skill to register the pin in `update_pins.py`.
2. Add `ansible/roles/development/tasks/<name>.yml`, modelled on `typst.yml` (architecture `assert`, guarded download, checksum, idempotent extract) and `anaconda.yml` (validating `assert`).
3. Add a boolean under `development` in `config/defaults.yml`, import the task in `ansible/roles/development/tasks/main.yml` with `when` and a tag, and add the key to `components` in `scripts/bootstrap.py` so the UI can select it.
4. Add the installed path to `verify_expected_paths` (or CLI to `verify_expected_clis`) in `ansible/tasks/verify.yml`.
5. Mention it in `tests/test_configuration.py` only if validation or selection logic changed.

## Rules

- Repositories are configured before packages; a package from a new repo needs the repo declared first.
- Never purge or replace unlisted packages. Additive only.
- RPMs and Flatpaks are verified automatically from `select()` in `scripts/configuration.py`; do not duplicate them in `verify.yml`.
- Do not edit `config/defaults.yml` structure (new top-level keys) here; use `add-feature`.

## Finish

Run the `validate-change` skill. Commit with the `commit` skill, scope `packages`, `flatpak`, `repositories`, `gnome` or `development`.
