---
name: add-software
description: Add ordinary software to the workstation provisioning, such as a DNF package, Flatpak, GNOME extension, font, COPR or RPM repository, or vendor-installed tool. Use when the user asks to install, add, or include an app, package, CLI, repo or extension in this repo.
---

# Add software

Pick the mechanism, in this order of preference: Fedora DNF package, Flatpak (GUI apps), COPR/RPM repository plus package, pinned vendor installer. Software is data; add a task only for vendor installers.

## Where it goes

| Kind | Edit |
|---|---|
| RPM application | `config/defaults.yml` `apps.<key>` with friendly `name`, `enabled`, `feature`, `installer: rpm`, and `rpm.packages` |
| Infrastructure/development dependency | `packages.<group>` (`base`, `desktop`, `development`, `work`, `personal`, `virtualization`) |
| Flatpak application | `apps.<key>` with `name`, `enabled`, `feature`, `installer: flatpak`, and `flatpak.id` |
| Font | `fonts` |
| COPR / third-party RPM repo | `repositories.copr` / `repositories.rpm` (`name`, `description`, `baseurl`, `gpgkey`); keep `gpgcheck` on |
| Packaged GNOME extension | `gnome.system_extensions` (`package`, `uuid`); add the uuid to `gnome.enabled_extensions` to enable it |
| Extension not in Fedora | `gnome.user_extensions` (uuid); optional, failures are reported, not fatal |
| Flatpak background permission | `apps.<key>.flatpak.background` (`true`, `false`, or `null` for unmanaged) |
| Flatpak session-bus ownership override | `apps.<key>.flatpak.own_names` |
| App startup at login | `apps.<key>.autostart` (`enabled`, native/vendor `command`, optional `name` and `try_exec`) |

An app’s `feature` must be active for it to install; `base` is unconditional. `requires` can add feature, development, app-dependency and preference conditions. App mappings merge across defaults → preset → local overrides, so presets disable individual apps with `enabled: false`. Dependency lists still replace earlier lists. Do not author the legacy boolean app format or `flatpak.applications`, `flatpak.background`, or `flatpak.overrides`; the loader translates them only for existing saved selections.

## Vendor installer (no suitable package)

For GUI applications, declare `installer: vendor` and `vendor.task` in the app record, add the substantive installer to the applications role, and extend the supported task validation and installed-path verification. Dispatch from `selected.vendor_tasks`; do not add a parallel boolean selection. Native apps needing additional integration can declare a supported `integration` alongside their RPM packages. The workflow below is for development CLI/runtime installers, which remain development selections.

```
- [ ] 1. Pin in catalog.yml
- [ ] 2. Add the installer task
- [ ] 3. Add the selection key and UI entry
- [ ] 4. Add the verify check
- [ ] 5. Tests if validation changed
```

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
