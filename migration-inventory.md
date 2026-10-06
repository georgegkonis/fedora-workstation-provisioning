# Workstation migration provenance

The original migration inventory was collected from a Fedora 44 work laptop. It is historical context, not a complete backup or a declaration that every exported value should be managed.

The current architecture uses `config/defaults.yml`, presets and ignored `.local.yml` selections. The legacy `profile.local.yml` is translated on the next bootstrap apply when `.local.yml` does not exist.

## Intentionally retained state

- Software and extension choices are represented as semantic package/Flatpak lists and component options.
- GNOME appearance, keyboard layout, selected input behavior and a small set of extension preferences are named declarations under the GNOME role.
- The old 244-value dconf export was removed. Profile UUIDs, window sizes, extension runtime data and unreviewed defaults are not restored.
- VS Code installation is managed by Ansible; extensions and personal editor settings are restored through Settings Sync after signing in. Provisioning preserves existing VS Code state.
- Selected JetBrains editor/appearance XML components are retained under `chezmoi/.chezmoitemplates/jetbrains`; registry state, accounts, company code styles and project data remain unmanaged.
- Shell configuration receives a managed hook. The source startup file contained a work credential and must never be copied wholesale.
- Git identities and work/personal directory scopes are rendered by chezmoi.

## Manual state

Authenticate applications and install/authenticate IDEs through Toolbox. Select JetBrains destination versions in `.local.yml` before applying preferences. Wallpapers and custom sounds remain unmanaged. Keep SSH keys, VPN credentials, certificates, tokens and employer secrets outside the repository.

Syntax, lint, loader tests and isolated dotfile verification do not prove that every external repository/installer works on a fresh Fedora system. Validate full provisioning on a disposable workstation or VM before relying on a rebuild.
