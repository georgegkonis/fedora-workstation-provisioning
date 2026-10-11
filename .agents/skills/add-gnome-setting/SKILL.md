---
name: add-gnome-setting
description: Add or change a managed GNOME/dconf setting, keybinding, input option, or extension preference in this repo's gnome role. Use when the user wants a GNOME desktop setting, shortcut, theme, dock or extension option applied by provisioning.
---

# Add GNOME setting

Settings are named declarations in `ansible/roles/gnome/files/`, loaded by `tasks/dconf.yml` and applied with `community.general.dconf` as the desktop user. Only listed keys are written; never reset a schema or whole dconf database.

## Pick the file

| File | Variable | Holds |
|---|---|---|
| `interface.yml` | `gnome_interface_settings` | appearance, fonts, clock, window buttons, Files |
| `keyboard.yml` | `gnome_keyboard_settings` | shortcuts, keybindings |
| `input.yml` | `gnome_input_settings` | mouse, touchpad, input sources |
| `extensions.yml` | `gnome_extensions_settings` | per-extension preferences |

A new file must be added to the loop list in `tasks/dconf.yml`.

## Entry format

```yaml
- key: /org/gnome/desktop/interface/clock-format
  value: '''24h'''          # GVariant text: strings are quoted twice
  description: Use a 24-hour clock
```

- `value` is GVariant: strings `'''x'''`, booleans `'true'`, lists `'[''<Super>v'']'`, unsigned ints `uint32 5`.
- `description` is required and states the outcome in plain words.
- Find key and type with `dconf watch /` while changing the setting in the UI, or `gsettings range <schema> <key>`; do not guess types.

## Extensions

Extension preferences only apply when the extension is declared in `gnome.system_extensions` or `gnome.user_extensions` in `config/defaults.yml`; enabling is controlled by `gnome.enabled_extensions`. Optional extension failures must be reported through `gnome_extension_failures`, never stop the play. Use `add-software` to add the extension itself.

## Finish

Do not apply to the live desktop. Run `validate-change`. Commit with the `commit` skill, scope `gnome`.
